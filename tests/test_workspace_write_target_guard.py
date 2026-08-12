"""Phase 5F2B tests: the create-aware canonical write-target guard (library only).

Kept separate from ``test_workspace_canonical_path_guard.py`` so the Phase 5D0
suite stays readable: that file pins the *existing-path* guard, this one pins the
*write-target* guard layered on top of it.

Every filesystem path used here lives under pytest's ``tmp_path``. No real
project workspace is created, read, listed, stat'd, or resolved, no file or
directory is written by production code, no environment value is read, no socket
is opened, no command is run, and no CLI command gains anything.
"""

from __future__ import annotations

import ast
import builtins
import os
import shutil
import socket
import stat as stat_module
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_dev_orchestrator.cli import app
from ai_dev_orchestrator.workspace import canonical
from ai_dev_orchestrator.workspace import (
    CanonicalPathAmbiguityError,
    CanonicalPathContainmentError,
    CanonicalPathError,
    CanonicalPathInputError,
    CanonicalPathResolutionError,
    CanonicalPathSymlinkError,
    CanonicalPathWriteTargetError,
    CanonicalWriteTarget,
    canonicalize_write_target_under_workspace,
)

runner = CliRunner()

IS_WINDOWS = sys.platform == "win32"


class Detonated(AssertionError):
    """Raised by a monkeypatched entry point the guard must never reach."""


def detonate(*args, **kwargs):
    raise Detonated("the write-target guard reached a forbidden entry point")


def make_workspace(tmp_path: Path) -> Path:
    """A workspace root under tmp_path with one file in a subdirectory."""
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "src" / "mod.py").write_text("value = 1\n", encoding="utf-8")
    return root


def try_symlink(link: Path, target: Path, *, target_is_directory: bool = False) -> None:
    """Create a symlink or skip the test if the platform/user cannot."""
    try:
        link.symlink_to(target, target_is_directory=target_is_directory)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(
            "platform/user cannot create symlinks "
            f"({type(exc).__name__}); the destination-is-never-a-link rule is "
            "also covered by the detection-helper tests"
        )


def snapshot(root: Path) -> list[str]:
    """Every path under ``root``, so a test can prove nothing was created."""
    return sorted(str(p.relative_to(root)) for p in root.rglob("*"))


# -- 1. Error hierarchy and change types ---------------------------------------


def test_new_error_joins_the_existing_closed_family():
    assert issubclass(CanonicalPathWriteTargetError, CanonicalPathError)
    assert issubclass(CanonicalPathError, Exception)
    # It is a *new* leaf, not a rename or a subclass of an existing leaf.
    for existing in (
        CanonicalPathInputError,
        CanonicalPathResolutionError,
        CanonicalPathContainmentError,
        CanonicalPathSymlinkError,
        CanonicalPathAmbiguityError,
    ):
        assert not issubclass(CanonicalPathWriteTargetError, existing)


def test_exactly_two_change_types_exist():
    assert canonical.WRITE_CHANGE_TYPES == ("modify", "create")


@pytest.mark.parametrize(
    "change_type",
    [
        "delete",
        "rename",
        "mkdir",
        "rmdir",
        "chmod",
        "chown",
        "binary",
        "append",
        "Modify",
        "CREATE",
        "modify ",
        "",
        None,
        42,
        True,
        ["create"],
    ],
)
def test_unknown_change_type_rejected(tmp_path, change_type):
    root = make_workspace(tmp_path)

    with pytest.raises(CanonicalPathInputError, match="change_type"):
        canonicalize_write_target_under_workspace(
            root, "src/mod.py", change_type=change_type  # type: ignore[arg-type]
        )


def test_change_type_is_never_inferred_from_the_filesystem(tmp_path):
    """The declared operation wins; the world disagreeing is a reason to stop."""
    root = make_workspace(tmp_path)

    # Present on disk, declared 'create'.
    with pytest.raises(CanonicalPathWriteTargetError, match="already exists"):
        canonicalize_write_target_under_workspace(
            root, "src/mod.py", change_type="create"
        )
    # Absent from disk, declared 'modify'.
    with pytest.raises(CanonicalPathWriteTargetError, match="does not exist"):
        canonicalize_write_target_under_workspace(
            root, "src/absent.py", change_type="modify"
        )


# -- 2. modify -----------------------------------------------------------------


def test_modify_existing_regular_file_accepted(tmp_path):
    root = make_workspace(tmp_path)

    target = canonicalize_write_target_under_workspace(
        root, "src/mod.py", change_type="modify"
    )

    assert isinstance(target, CanonicalWriteTarget)
    assert target.change_type == "modify"
    assert target.target_existed is True
    assert target.is_inside_workspace is True
    assert target.allow_symlinks is False
    assert target.relative_destination == os.path.join("src", "mod.py")
    assert os.path.isabs(target.resolved_destination)
    assert target.resolved_parent == os.path.dirname(target.resolved_destination)
    assert (
        os.path.join(target.resolved_workspace_root, target.relative_destination)
        == target.resolved_destination
    )


def test_modify_relative_and_absolute_forms_agree(tmp_path):
    root = make_workspace(tmp_path)

    from_relative = canonicalize_write_target_under_workspace(
        root, "src/mod.py", change_type="modify"
    )
    from_backslash = canonicalize_write_target_under_workspace(
        root, "src\\mod.py", change_type="modify"
    )
    from_dotted = canonicalize_write_target_under_workspace(
        root, "./src/../src/mod.py", change_type="modify"
    )
    from_absolute = canonicalize_write_target_under_workspace(
        root, root / "src" / "mod.py", change_type="modify"
    )

    for target in (from_backslash, from_dotted, from_absolute):
        assert target.resolved_destination == from_relative.resolved_destination
        assert target.relative_destination == from_relative.relative_destination
    assert from_absolute.candidate_input == str(root / "src" / "mod.py")


def test_modify_missing_destination_rejected(tmp_path):
    root = make_workspace(tmp_path)

    with pytest.raises(CanonicalPathWriteTargetError, match="modify"):
        canonicalize_write_target_under_workspace(
            root, "src/absent.py", change_type="modify"
        )


def test_modify_directory_rejected(tmp_path):
    root = make_workspace(tmp_path)

    for candidate in ("src", root):
        with pytest.raises(CanonicalPathWriteTargetError, match="regular file"):
            canonicalize_write_target_under_workspace(
                root, candidate, change_type="modify"
            )


def test_modify_final_symlink_to_inside_file_rejected_in_both_modes(tmp_path):
    """``allow_symlinks`` is a traversal policy; a destination link is refused anyway."""
    root = make_workspace(tmp_path)
    try_symlink(root / "src" / "alias.py", root / "src" / "mod.py")

    for allow_symlinks in (False, True):
        with pytest.raises(CanonicalPathSymlinkError, match="destination"):
            canonicalize_write_target_under_workspace(
                root,
                "src/alias.py",
                change_type="modify",
                allow_symlinks=allow_symlinks,
            )


def test_modify_final_symlink_pointing_outside_rejected(tmp_path):
    root = make_workspace(tmp_path)
    outside = tmp_path / "outside.py"
    outside.write_text("secret = 1\n", encoding="utf-8")
    try_symlink(root / "src" / "escape.py", outside)

    for allow_symlinks in (False, True):
        with pytest.raises(CanonicalPathSymlinkError):
            canonicalize_write_target_under_workspace(
                root,
                "src/escape.py",
                change_type="modify",
                allow_symlinks=allow_symlinks,
            )


def test_modify_dangling_final_symlink_rejected(tmp_path):
    root = make_workspace(tmp_path)
    try_symlink(root / "src" / "dangling.py", root / "src" / "absent.py")

    for allow_symlinks in (False, True):
        with pytest.raises(CanonicalPathSymlinkError):
            canonicalize_write_target_under_workspace(
                root,
                "src/dangling.py",
                change_type="modify",
                allow_symlinks=allow_symlinks,
            )


def test_modify_intermediate_symlink_still_follows_allow_symlinks(tmp_path):
    root = make_workspace(tmp_path)
    try_symlink(root / "alias_dir", root / "src", target_is_directory=True)

    with pytest.raises(CanonicalPathSymlinkError, match="component"):
        canonicalize_write_target_under_workspace(
            root, "alias_dir/mod.py", change_type="modify"
        )

    target = canonicalize_write_target_under_workspace(
        root, "alias_dir/mod.py", change_type="modify", allow_symlinks=True
    )
    assert target.relative_destination == os.path.join("src", "mod.py")
    assert target.target_existed is True


def test_modify_through_intermediate_symlink_leaving_workspace_rejected(tmp_path):
    root = make_workspace(tmp_path)
    outside_dir = tmp_path / "outside_dir"
    outside_dir.mkdir()
    (outside_dir / "file.py").write_text("secret = 1\n", encoding="utf-8")
    try_symlink(root / "vendor", outside_dir, target_is_directory=True)

    with pytest.raises(CanonicalPathSymlinkError):
        canonicalize_write_target_under_workspace(
            root, "vendor/file.py", change_type="modify"
        )
    with pytest.raises(CanonicalPathContainmentError):
        canonicalize_write_target_under_workspace(
            root, "vendor/file.py", change_type="modify", allow_symlinks=True
        )


def test_modify_outside_workspace_rejected(tmp_path):
    root = make_workspace(tmp_path)
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (outside / "file.py").write_text("secret = 1\n", encoding="utf-8")

    for allow_symlinks in (False, True):
        with pytest.raises(CanonicalPathContainmentError):
            canonicalize_write_target_under_workspace(
                root,
                outside / "file.py",
                change_type="modify",
                allow_symlinks=allow_symlinks,
            )
        with pytest.raises(CanonicalPathContainmentError):
            canonicalize_write_target_under_workspace(
                root,
                "../elsewhere/file.py",
                change_type="modify",
                allow_symlinks=allow_symlinks,
            )


def test_modify_sibling_prefix_confusion_rejected(tmp_path):
    root = make_workspace(tmp_path)
    sibling = tmp_path / "repo_evil"
    sibling.mkdir()
    (sibling / "file.py").write_text("secret = 1\n", encoding="utf-8")

    for allow_symlinks in (False, True):
        with pytest.raises(CanonicalPathContainmentError):
            canonicalize_write_target_under_workspace(
                root,
                sibling / "file.py",
                change_type="modify",
                allow_symlinks=allow_symlinks,
            )


def test_modify_symlinked_workspace_root_follows_phase_5d0_rules(tmp_path):
    real_root = make_workspace(tmp_path)
    link_root = tmp_path / "linked_repo"
    try_symlink(link_root, real_root, target_is_directory=True)

    with pytest.raises(CanonicalPathSymlinkError, match="workspace_root"):
        canonicalize_write_target_under_workspace(
            link_root, "src/mod.py", change_type="modify"
        )

    target = canonicalize_write_target_under_workspace(
        link_root, "src/mod.py", change_type="modify", allow_symlinks=True
    )
    assert target.relative_destination == os.path.join("src", "mod.py")


# -- 3. create -----------------------------------------------------------------


def test_create_missing_file_under_existing_parent_accepted(tmp_path):
    root = make_workspace(tmp_path)
    before = snapshot(root)

    target = canonicalize_write_target_under_workspace(
        root, "src/new_module.py", change_type="create"
    )

    assert target.change_type == "create"
    assert target.target_existed is False
    assert target.is_inside_workspace is True
    assert target.relative_destination == os.path.join("src", "new_module.py")
    assert target.resolved_parent == os.path.dirname(target.resolved_destination)
    assert not os.path.lexists(target.resolved_destination)
    # The guard created nothing to make the answer true.
    assert snapshot(root) == before


def test_create_directly_in_the_workspace_root_accepted(tmp_path):
    root = make_workspace(tmp_path)

    target = canonicalize_write_target_under_workspace(
        root, "NOTES.md", change_type="create"
    )

    assert target.relative_destination == "NOTES.md"
    assert target.resolved_parent == target.resolved_workspace_root


def test_create_nested_under_existing_directories_accepted(tmp_path):
    root = make_workspace(tmp_path)
    (root / "src" / "deep" / "deeper").mkdir(parents=True)
    before = snapshot(root)

    target = canonicalize_write_target_under_workspace(
        root, "src/deep/deeper/new.py", change_type="create"
    )

    assert target.relative_destination == os.path.join(
        "src", "deep", "deeper", "new.py"
    )
    assert target.target_existed is False
    assert snapshot(root) == before


def test_create_absolute_form_accepted(tmp_path):
    root = make_workspace(tmp_path)

    target = canonicalize_write_target_under_workspace(
        root, root / "src" / "new.py", change_type="create"
    )

    assert target.relative_destination == os.path.join("src", "new.py")


def test_create_with_missing_parent_rejected_and_no_directory_made(tmp_path):
    root = make_workspace(tmp_path)
    before = snapshot(root)

    with pytest.raises(CanonicalPathWriteTargetError, match="parent"):
        canonicalize_write_target_under_workspace(
            root, "absent_dir/new.py", change_type="create"
        )
    with pytest.raises(CanonicalPathWriteTargetError, match="parent"):
        canonicalize_write_target_under_workspace(
            root, "src/absent_dir/deeper/new.py", change_type="create"
        )

    assert snapshot(root) == before
    assert not (root / "absent_dir").exists()


def test_create_with_a_file_as_the_parent_rejected(tmp_path):
    root = make_workspace(tmp_path)

    with pytest.raises(CanonicalPathError):
        canonicalize_write_target_under_workspace(
            root, "src/mod.py/new.py", change_type="create"
        )


def test_create_candidate_equal_to_workspace_root_rejected(tmp_path):
    root = make_workspace(tmp_path)

    for candidate in (root, str(root), ".", "./", "src/.."):
        with pytest.raises(CanonicalPathWriteTargetError):
            canonicalize_write_target_under_workspace(
                root, candidate, change_type="create"
            )


@pytest.mark.parametrize(
    "candidate",
    ["src/.", "src/..", "src/./", "src/", "src\\", ".", "..", "src/mod.py/.."],
)
def test_create_with_a_directory_shaped_final_component_rejected(tmp_path, candidate):
    root = make_workspace(tmp_path)

    with pytest.raises(CanonicalPathWriteTargetError):
        canonicalize_write_target_under_workspace(
            root, candidate, change_type="create"
        )


def test_create_over_existing_regular_file_rejected(tmp_path):
    root = make_workspace(tmp_path)

    with pytest.raises(CanonicalPathWriteTargetError, match="already exists"):
        canonicalize_write_target_under_workspace(
            root, "src/mod.py", change_type="create"
        )


def test_create_over_existing_directory_rejected(tmp_path):
    root = make_workspace(tmp_path)

    with pytest.raises(CanonicalPathWriteTargetError, match="already exists"):
        canonicalize_write_target_under_workspace(
            root, "src", change_type="create"
        )


def test_create_over_a_symlink_rejected_in_both_modes(tmp_path):
    root = make_workspace(tmp_path)
    try_symlink(root / "src" / "alias.py", root / "src" / "mod.py")

    for allow_symlinks in (False, True):
        with pytest.raises(CanonicalPathSymlinkError, match="destination"):
            canonicalize_write_target_under_workspace(
                root,
                "src/alias.py",
                change_type="create",
                allow_symlinks=allow_symlinks,
            )


def test_create_over_a_dangling_symlink_rejected_not_treated_as_absent(tmp_path):
    """``os.path.exists`` would call this absent; ``lstat`` does not follow."""
    root = make_workspace(tmp_path)
    link = root / "src" / "dangling.py"
    try_symlink(link, root / "src" / "absent.py")

    assert not os.path.exists(link)  # the trap this rule exists to avoid
    for allow_symlinks in (False, True):
        with pytest.raises(CanonicalPathSymlinkError):
            canonicalize_write_target_under_workspace(
                root,
                "src/dangling.py",
                change_type="create",
                allow_symlinks=allow_symlinks,
            )


def test_create_over_a_dangling_symlink_to_outside_rejected(tmp_path):
    root = make_workspace(tmp_path)
    try_symlink(root / "src" / "escape.py", tmp_path / "never_created.py")

    for allow_symlinks in (False, True):
        with pytest.raises(CanonicalPathSymlinkError):
            canonicalize_write_target_under_workspace(
                root,
                "src/escape.py",
                change_type="create",
                allow_symlinks=allow_symlinks,
            )


def test_create_intermediate_symlink_follows_allow_symlinks(tmp_path):
    root = make_workspace(tmp_path)
    try_symlink(root / "alias_dir", root / "src", target_is_directory=True)

    with pytest.raises(CanonicalPathSymlinkError, match="component"):
        canonicalize_write_target_under_workspace(
            root, "alias_dir/new.py", change_type="create"
        )

    target = canonicalize_write_target_under_workspace(
        root, "alias_dir/new.py", change_type="create", allow_symlinks=True
    )
    assert target.relative_destination == os.path.join("src", "new.py")
    assert target.target_existed is False
    assert not os.path.lexists(target.resolved_destination)


def test_create_with_parent_resolving_outside_workspace_rejected(tmp_path):
    root = make_workspace(tmp_path)
    outside_dir = tmp_path / "outside_dir"
    outside_dir.mkdir()
    try_symlink(root / "vendor", outside_dir, target_is_directory=True)

    with pytest.raises(CanonicalPathSymlinkError):
        canonicalize_write_target_under_workspace(
            root, "vendor/new.py", change_type="create"
        )
    with pytest.raises(CanonicalPathContainmentError):
        canonicalize_write_target_under_workspace(
            root, "vendor/new.py", change_type="create", allow_symlinks=True
        )


def test_create_outside_workspace_rejected(tmp_path):
    root = make_workspace(tmp_path)
    outside = tmp_path / "elsewhere"
    outside.mkdir()

    for allow_symlinks in (False, True):
        with pytest.raises(CanonicalPathContainmentError):
            canonicalize_write_target_under_workspace(
                root,
                outside / "new.py",
                change_type="create",
                allow_symlinks=allow_symlinks,
            )
        with pytest.raises(CanonicalPathContainmentError):
            canonicalize_write_target_under_workspace(
                root,
                "../elsewhere/new.py",
                change_type="create",
                allow_symlinks=allow_symlinks,
            )


def test_create_sibling_prefix_escape_rejected(tmp_path):
    root = make_workspace(tmp_path)
    sibling = tmp_path / "repo_evil"
    sibling.mkdir()

    for allow_symlinks in (False, True):
        with pytest.raises(CanonicalPathContainmentError):
            canonicalize_write_target_under_workspace(
                root,
                sibling / "new.py",
                change_type="create",
                allow_symlinks=allow_symlinks,
            )
        with pytest.raises(CanonicalPathContainmentError):
            canonicalize_write_target_under_workspace(
                root,
                "../repo_evil/new.py",
                change_type="create",
                allow_symlinks=allow_symlinks,
            )


def test_create_workspace_root_input_failures_match_phase_5d0(tmp_path):
    root = make_workspace(tmp_path)

    with pytest.raises(CanonicalPathInputError, match="workspace_root"):
        canonicalize_write_target_under_workspace(
            tmp_path / "no_such_root", "src/new.py", change_type="create"
        )
    with pytest.raises(CanonicalPathInputError, match="not a directory"):
        canonicalize_write_target_under_workspace(
            root / "src" / "mod.py", "new.py", change_type="create"
        )


# -- 4. Shared input handling --------------------------------------------------


@pytest.mark.parametrize("change_type", ["modify", "create"])
@pytest.mark.parametrize("blank", ["", " ", "\t", "\n"])
def test_blank_inputs_rejected(tmp_path, change_type, blank):
    root = make_workspace(tmp_path)

    with pytest.raises(CanonicalPathInputError, match="workspace_root"):
        canonicalize_write_target_under_workspace(
            blank, "src/mod.py", change_type=change_type
        )
    with pytest.raises(CanonicalPathInputError, match="candidate"):
        canonicalize_write_target_under_workspace(
            root, blank, change_type=change_type
        )


@pytest.mark.parametrize("change_type", ["modify", "create"])
@pytest.mark.parametrize("wrong", [None, 42, b"src/mod.py", ["src"]])
def test_wrongly_typed_inputs_rejected(tmp_path, change_type, wrong):
    root = make_workspace(tmp_path)

    with pytest.raises(CanonicalPathInputError):
        canonicalize_write_target_under_workspace(
            root, wrong, change_type=change_type
        )
    with pytest.raises(CanonicalPathInputError):
        canonicalize_write_target_under_workspace(
            wrong, "src/mod.py", change_type=change_type
        )


@pytest.mark.parametrize("change_type", ["modify", "create"])
def test_non_bool_allow_symlinks_rejected(tmp_path, change_type):
    root = make_workspace(tmp_path)

    with pytest.raises(CanonicalPathInputError, match="allow_symlinks"):
        canonicalize_write_target_under_workspace(
            root,
            "src/mod.py",
            change_type=change_type,
            allow_symlinks="yes",  # type: ignore[arg-type]
        )


# -- 5. Lexical rejection happens before any disk touch -----------------------

# A root that is never stat'd: the lexical precheck refuses these strings first.
SAFE_UNTOUCHED_ROOT = os.sep + "write_target_guard_root"

UNSAFE_FORMS = [
    pytest.param("\\\\server\\share\\file.py", id="unc-backslash"),
    pytest.param("//server/share/file.py", id="unc-forward"),
    pytest.param("\\\\?\\C:\\repo\\file.py", id="extended-length"),
    pytest.param("//?/C:/repo/file.py", id="extended-length-forward"),
    pytest.param("\\\\.\\PhysicalDrive0", id="device"),
    pytest.param("//./PhysicalDrive0", id="device-forward"),
    pytest.param("src/trailing_dot./mod.py", id="trailing-dot-component"),
    pytest.param("src/mod.py.", id="trailing-dot-leaf"),
    pytest.param("src/trailing_space /mod.py", id="trailing-space-component"),
    pytest.param("src/mod.py ", id="trailing-space-leaf"),
    pytest.param("PROGRA~1/mod.py", id="short-name-component"),
    pytest.param("src/LONGFI~1.TXT", id="short-name-leaf"),
]


def forbid_all_filesystem_entry_points(monkeypatch) -> None:
    monkeypatch.setattr(os, "stat", detonate)
    monkeypatch.setattr(os, "lstat", detonate)
    monkeypatch.setattr(Path, "resolve", detonate)
    monkeypatch.setattr(os.path, "realpath", detonate)
    monkeypatch.setattr(os.path, "exists", detonate)
    monkeypatch.setattr(os.path, "lexists", detonate)
    monkeypatch.setattr(os, "listdir", detonate)
    monkeypatch.setattr(os, "scandir", detonate)
    monkeypatch.setattr(os, "mkdir", detonate)
    monkeypatch.setattr(os, "makedirs", detonate)
    monkeypatch.setattr(builtins, "open", detonate)


@pytest.mark.parametrize("change_type", ["modify", "create"])
@pytest.mark.parametrize("unsafe", UNSAFE_FORMS)
def test_unsafe_candidate_form_rejected_before_any_disk_touch(
    monkeypatch, change_type, unsafe
):
    forbid_all_filesystem_entry_points(monkeypatch)

    with pytest.raises(CanonicalPathAmbiguityError, match="candidate"):
        canonicalize_write_target_under_workspace(
            SAFE_UNTOUCHED_ROOT, unsafe, change_type=change_type
        )


@pytest.mark.parametrize("change_type", ["modify", "create"])
@pytest.mark.parametrize("unsafe", UNSAFE_FORMS)
def test_unsafe_workspace_root_form_rejected_before_any_disk_touch(
    monkeypatch, change_type, unsafe
):
    forbid_all_filesystem_entry_points(monkeypatch)

    with pytest.raises(CanonicalPathAmbiguityError, match="workspace_root"):
        canonicalize_write_target_under_workspace(
            unsafe, "src/mod.py", change_type=change_type
        )


@pytest.mark.parametrize("change_type", ["modify", "create"])
def test_blank_and_unknown_change_type_rejected_before_any_disk_touch(
    monkeypatch, change_type
):
    forbid_all_filesystem_entry_points(monkeypatch)

    with pytest.raises(CanonicalPathInputError):
        canonicalize_write_target_under_workspace(
            "   ", "src/mod.py", change_type=change_type
        )
    with pytest.raises(CanonicalPathInputError):
        canonicalize_write_target_under_workspace(
            SAFE_UNTOUCHED_ROOT, "   ", change_type=change_type
        )
    with pytest.raises(CanonicalPathInputError):
        canonicalize_write_target_under_workspace(
            SAFE_UNTOUCHED_ROOT, "src/mod.py", change_type="delete"
        )


# -- 5b. Phase 5F2B-FU1: Windows namespace hardening, also before disk touch ---

# Alternate data streams, drive-relative forms, reserved device names and
# reserved characters. Every one of these stats and resolves like an ordinary
# file on Windows, which is exactly why the decision is made on the string.
ADS_FORMS = [
    pytest.param("src\\mod.py:stream", id="ads-backslash"),
    pytest.param("src/new.py:stream", id="ads-forward"),
    pytest.param("src\\mod.py::$DATA", id="ads-default-stream"),
    pytest.param("src/foo:bar:baz", id="ads-multiple-colons"),
    pytest.param("mod.py:stream", id="ads-leaf-only"),
    pytest.param("C:\\repo\\src\\mod.py:stream", id="ads-after-drive"),
    pytest.param("C:\\repo\\src\\mod.py::$DATA", id="ads-default-after-drive"),
    pytest.param(":stream", id="ads-bare"),
]

DRIVE_RELATIVE_FORMS = [
    pytest.param("C:file.py", id="drive-relative-leaf"),
    pytest.param("C:src\\file.py", id="drive-relative-backslash"),
    pytest.param("C:src/file.py", id="drive-relative-forward"),
    pytest.param("d:file.py", id="drive-relative-lowercase"),
    pytest.param("C:", id="drive-relative-bare"),
]

RESERVED_DEVICE_FORMS = [
    pytest.param("NUL", id="device-nul"),
    pytest.param("NUL.txt", id="device-nul-extension"),
    pytest.param("src\\CON.py", id="device-con-in-subdirectory"),
    pytest.param("src\\COM1", id="device-com1"),
    pytest.param("src\\LPT9.log", id="device-lpt9"),
    pytest.param("PRN", id="device-prn"),
    pytest.param("src/AUX.json", id="device-aux"),
    pytest.param("src/nul.txt", id="device-lowercase"),
    pytest.param("src/CoN.Py", id="device-mixed-case"),
    pytest.param("CON/mod.py", id="device-as-directory-component"),
    pytest.param("src/COM\u00b9", id="device-superscript-com"),
    pytest.param("src/LPT\u00b2.log", id="device-superscript-lpt"),
]

RESERVED_CHARACTER_FORMS = [
    pytest.param("src/mod<.py", id="less-than"),
    pytest.param("src/mod>.py", id="greater-than"),
    pytest.param('src/mod".py', id="double-quote"),
    pytest.param("src/mod|.py", id="pipe"),
    pytest.param("src/mod?.py", id="question-mark"),
    pytest.param("src/*.py", id="asterisk"),
    pytest.param("src/mod\x00.py", id="embedded-nul"),
    pytest.param("src/mod\n.py", id="embedded-newline"),
    pytest.param("src/mod\t.py", id="embedded-tab"),
]

FU1_UNSAFE_FORMS = (
    ADS_FORMS + DRIVE_RELATIVE_FORMS + RESERVED_DEVICE_FORMS + RESERVED_CHARACTER_FORMS
)


@pytest.mark.parametrize("change_type", ["modify", "create"])
@pytest.mark.parametrize("unsafe", FU1_UNSAFE_FORMS)
def test_windows_namespace_aliases_rejected_before_any_disk_touch(
    monkeypatch, change_type, unsafe
):
    forbid_all_filesystem_entry_points(monkeypatch)

    with pytest.raises(CanonicalPathAmbiguityError, match="candidate"):
        canonicalize_write_target_under_workspace(
            SAFE_UNTOUCHED_ROOT, unsafe, change_type=change_type
        )


@pytest.mark.parametrize("change_type", ["modify", "create"])
@pytest.mark.parametrize("unsafe", ADS_FORMS + DRIVE_RELATIVE_FORMS)
def test_colon_forms_rejected_for_the_workspace_root_too(
    monkeypatch, change_type, unsafe
):
    """A drive-relative or stream-bearing *root* is as ambient as a destination."""
    forbid_all_filesystem_entry_points(monkeypatch)

    with pytest.raises(CanonicalPathAmbiguityError, match="workspace_root"):
        canonicalize_write_target_under_workspace(
            unsafe, "src/mod.py", change_type=change_type
        )


@pytest.mark.parametrize("unsafe", ADS_FORMS)
def test_alternate_data_streams_are_named_as_such_and_never_normalized(unsafe):
    with pytest.raises(CanonicalPathAmbiguityError, match="alternate-data-stream"):
        canonical._reject_unsafe_write_target_form(unsafe, role="candidate")


@pytest.mark.parametrize("unsafe", DRIVE_RELATIVE_FORMS)
def test_drive_relative_forms_are_named_as_such(unsafe):
    with pytest.raises(CanonicalPathAmbiguityError, match="drive-relative"):
        canonical._reject_unsafe_write_target_form(unsafe, role="candidate")


@pytest.mark.parametrize("unsafe", RESERVED_DEVICE_FORMS)
def test_reserved_device_names_are_named_as_such(unsafe):
    with pytest.raises(CanonicalPathAmbiguityError, match="reserved Windows device"):
        canonical._reject_unsafe_write_target_form(unsafe, role="candidate")


@pytest.mark.parametrize("unsafe", RESERVED_CHARACTER_FORMS)
def test_reserved_characters_are_named_as_such(unsafe):
    with pytest.raises(
        CanonicalPathAmbiguityError, match="reserved character|control character"
    ):
        canonical._reject_unsafe_write_target_form(unsafe, role="candidate")


@pytest.mark.parametrize(
    "candidate",
    [
        "console.py",
        "src/console.py",
        "src/com1_helper.py",
        "src/nullable.py",
        "src/auxiliary/mod.py",
        "src/prnt.py",
        "src/lpt10.log",
        "src/CONTEXT.md",
    ],
)
def test_names_that_merely_look_like_devices_are_still_accepted(tmp_path, candidate):
    """The device rule is anchored: ``console.py`` is not ``CON``."""
    root = make_workspace(tmp_path)
    (root / "src" / "auxiliary").mkdir()

    target = canonicalize_write_target_under_workspace(
        root, candidate, change_type="create"
    )

    assert target.target_existed is False


def test_fully_qualified_windows_absolute_paths_still_work(tmp_path):
    """The colon rule must not reject ``C:\\repo\\...``: the drive colon is legal."""
    root = make_workspace(tmp_path)
    absolute_root = str(root)
    if not IS_WINDOWS:
        pytest.skip("no drive designator to preserve on this platform")
    assert absolute_root[1] == ":"

    modify_target = canonicalize_write_target_under_workspace(
        absolute_root, str(root / "src" / "mod.py"), change_type="modify"
    )
    create_target = canonicalize_write_target_under_workspace(
        absolute_root, str(root / "src" / "new.py"), change_type="create"
    )

    assert modify_target.relative_destination == os.path.join("src", "mod.py")
    assert create_target.relative_destination == os.path.join("src", "new.py")
    # Forward-slash spelling of the same fully-qualified path.
    forward = canonicalize_write_target_under_workspace(
        absolute_root.replace("\\", "/"),
        str(root / "src" / "mod.py").replace("\\", "/"),
        change_type="modify",
    )
    assert forward.resolved_destination == modify_target.resolved_destination


def test_the_drive_colon_survives_every_layer(tmp_path):
    """Whole string, per component, and the re-checked create leaf."""
    canonical._reject_unsafe_write_target_form("C:\\repo\\src\\mod.py", role="candidate")
    canonical._reject_unsafe_write_target_form("C:/repo/src/mod.py", role="candidate")
    canonical._reject_unsafe_write_target_form("mod.py", role="candidate")
    canonical._reject_unsafe_colon_form("C:\\repo", role="workspace_root")


def test_hardening_did_not_widen_anything_phase_5f2b_already_refused(tmp_path):
    """Every Phase 5F2B rejection still rejects, with its original category."""
    root = make_workspace(tmp_path)

    with pytest.raises(CanonicalPathWriteTargetError):
        canonicalize_write_target_under_workspace(
            root, "src/absent.py", change_type="modify"
        )
    with pytest.raises(CanonicalPathWriteTargetError):
        canonicalize_write_target_under_workspace(
            root, "src/mod.py", change_type="create"
        )
    with pytest.raises(CanonicalPathContainmentError):
        canonicalize_write_target_under_workspace(
            root, "../outside.py", change_type="create"
        )
    with pytest.raises(CanonicalPathAmbiguityError):
        canonicalize_write_target_under_workspace(
            root, "src/LONGFI~1.TXT", change_type="create"
        )


def test_the_read_guard_did_not_inherit_the_write_target_rules(tmp_path):
    """Phase 5D0 read semantics are untouched: the FU1 gate is layered, not folded.

    The read guard is not being endorsed as ADS-safe here — it is being pinned
    as *unchanged*. These strings fail for the reasons they failed before FU1
    (the path does not exist), not for the new lexical reasons, which is what
    makes the existing ``l2-inspect-workspace`` / ``l2-read-workspace-files``
    behavior identical to what shipped.
    """
    root = make_workspace(tmp_path)

    for candidate in ("src/mod.py:stream", "src/CON.py", "src/mod?.py"):
        with pytest.raises(CanonicalPathInputError):
            canonical.canonicalize_existing_path_under_workspace(root, candidate)

    # And a path the read guard accepted before FU1 is still accepted.
    decision = canonical.canonicalize_existing_path_under_workspace(root, "src/mod.py")
    assert decision.relative_path == os.path.join("src", "mod.py")


def test_no_stream_or_device_is_created_or_opened_to_decide(tmp_path, monkeypatch):
    """Rejection is lexical: nothing is probed to discover what a name means."""
    root = make_workspace(tmp_path)
    before = snapshot(root)
    forbid_all_filesystem_entry_points(monkeypatch)

    try:
        for change_type in ("modify", "create"):
            for candidate in (
                "src/mod.py:stream",
                "src/mod.py::$DATA",
                "C:file.py",
                "NUL",
                "src/COM1",
                "src/mod|.py",
            ):
                with pytest.raises(CanonicalPathAmbiguityError):
                    canonicalize_write_target_under_workspace(
                        root, candidate, change_type=change_type
                    )
    finally:
        monkeypatch.undo()

    assert snapshot(root) == before


def test_the_final_name_is_rechecked_lexically(tmp_path):
    """The leaf is re-checked before it is joined onto a canonical parent."""
    with pytest.raises(CanonicalPathAmbiguityError, match="file name"):
        canonical._check_final_component_is_a_plain_file_name(
            "src/LONGFI~1.TXT", "LONGFI~1.TXT"
        )
    with pytest.raises(CanonicalPathWriteTargetError, match="separator"):
        canonical._check_final_component_is_a_plain_file_name("src/a", "a/b")


# -- 6. The result object ------------------------------------------------------


def test_result_is_frozen_and_data_only(tmp_path):
    root = make_workspace(tmp_path)

    for change_type, candidate in (("modify", "src/mod.py"), ("create", "src/new.py")):
        target = canonicalize_write_target_under_workspace(
            root, candidate, change_type=change_type
        )

        with pytest.raises(Exception):
            target.relative_destination = "other"  # type: ignore[misc]
        assert set(vars(target)) == {
            "workspace_root_input",
            "candidate_input",
            "change_type",
            "resolved_workspace_root",
            "resolved_parent",
            "resolved_destination",
            "relative_destination",
            "allow_symlinks",
            "target_existed",
            "is_inside_workspace",
        }
        # Data only: no callables to reach the disk with, and no write verb.
        assert not [
            name
            for name in dir(target)
            if not name.startswith("_") and callable(getattr(target, name))
        ]
        # No file contents, no diff, no approval, no config, no command, no Git
        # state, and no write/apply/rollback status.
        text = repr(target)
        assert "value = 1" not in text
        for absent in (
            "diff",
            "approval",
            "approved",
            "command",
            "git",
            "branch",
            "commit",
            "digest",
            "hash",
            "written",
            "applied",
            "rollback",
            "authorized",
        ):
            assert absent not in text.lower(), absent


def test_relative_destination_is_relative_and_does_not_escape(tmp_path):
    root = make_workspace(tmp_path)

    for change_type, candidate in (("modify", "src/mod.py"), ("create", "src/new.py")):
        target = canonicalize_write_target_under_workspace(
            root, candidate, change_type=change_type
        )
        assert not os.path.isabs(target.relative_destination)
        assert ".." not in target.relative_destination
        assert os.path.commonpath(
            [
                os.path.normcase(target.resolved_workspace_root),
                os.path.normcase(target.resolved_destination),
            ]
        ) == os.path.normcase(target.resolved_workspace_root)


def test_inputs_are_echoed_unmutated(tmp_path):
    root = make_workspace(tmp_path)
    root_input = str(root)
    candidate_input = "src/new.py"

    target = canonicalize_write_target_under_workspace(
        root_input, candidate_input, change_type="create"
    )

    assert target.workspace_root_input == root_input
    assert target.candidate_input == candidate_input
    assert root_input == str(root)
    assert candidate_input == "src/new.py"


def test_the_result_is_documented_as_not_an_authorization():
    doc = canonicalize_write_target_under_workspace.__doc__ or ""
    assert "not authorization to write" in doc
    assert "time-of-check" in doc or "time of check" in doc
    assert "not authorization" in (canonical.CanonicalWriteTarget.__doc__ or "").lower() \
        or "not permission to write" in (canonical.CanonicalWriteTarget.__doc__ or "")


# -- 7. No forbidden behavior --------------------------------------------------


FORBIDDEN_GLOBAL_NAMES = (
    "httpx",
    "requests",
    "LLMClient",
    "LLMClientConfig",
    "load_llm_client_config_from_env",
    "GitHubClient",
    "typer",
    "socket",
    "subprocess",
    "shutil",
    "tempfile",
    "difflib",
)


def test_implementation_module_globals_carry_no_forbidden_names():
    module_globals = vars(canonical)
    for name in FORBIDDEN_GLOBAL_NAMES:
        assert name not in module_globals, name


def called_names(module_path: Path) -> set[str]:
    """Every name and dotted attribute the module actually *calls*.

    Parsed rather than grepped, so prose in a docstring — this module explains
    why ``open(..., "x")`` through a dangling link is the trap it avoids — is
    not mistaken for the call it warns about.
    """
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        parts: list[str] = []
        target = node.func
        while isinstance(target, ast.Attribute):
            parts.append(target.attr)
            target = target.value
        if isinstance(target, ast.Name):
            parts.append(target.id)
        if parts:
            names.add(".".join(reversed(parts)))
            names.add(parts[0])
    return names


def test_implementation_module_writes_nothing_and_opens_nothing():
    """Parsed proof: no write, no creation, no listing, no content read."""
    calls = called_names(Path(canonical.__file__))

    for forbidden in (
        "open",
        "os.open",
        "os.mkdir",
        "os.makedirs",
        "mkdir",
        "makedirs",
        "os.rename",
        "os.replace",
        "os.remove",
        "os.unlink",
        "os.rmdir",
        "os.listdir",
        "os.scandir",
        "os.walk",
        "os.symlink",
        "os.link",
        "os.chmod",
        "os.chown",
        "os.utime",
        "write_text",
        "write_bytes",
        "read_text",
        "read_bytes",
        "touch",
        "glob",
        "rglob",
        "iterdir",
        "getenv",
        "os.getenv",
        "system",
        "os.system",
        # The absence decision is lstat, never a link-following existence probe.
        "os.path.exists",
        "exists",
        "os.path.isfile",
        "os.path.isdir",
    ):
        assert forbidden not in calls, forbidden

    assert "os.lstat" in calls

    source = Path(canonical.__file__).read_text(encoding="utf-8")
    for forbidden_import in (
        "import shutil",
        "import tempfile",
        "import subprocess",
        "import socket",
        "import httpx",
        "import requests",
        "import typer",
    ):
        assert forbidden_import not in source, forbidden_import
    assert "os.environ" not in source


@pytest.mark.parametrize(
    ("change_type", "candidate"),
    [("modify", "src/mod.py"), ("create", "src/new.py")],
)
def test_guard_touches_no_forbidden_entry_point_on_the_happy_path(
    tmp_path, monkeypatch, change_type, candidate
):
    """No env read, no file read, no listing, no creation, no process, no socket."""
    root = make_workspace(tmp_path)

    monkeypatch.setattr(builtins, "open", detonate)
    monkeypatch.setattr(os, "getenv", detonate)
    monkeypatch.setattr(os.environ, "get", detonate)
    monkeypatch.setattr(os, "listdir", detonate)
    monkeypatch.setattr(os, "scandir", detonate)
    monkeypatch.setattr(os, "walk", detonate)
    monkeypatch.setattr(os, "mkdir", detonate)
    monkeypatch.setattr(os, "makedirs", detonate)
    monkeypatch.setattr(os, "rename", detonate)
    monkeypatch.setattr(os, "replace", detonate)
    monkeypatch.setattr(os, "remove", detonate)
    monkeypatch.setattr(os, "unlink", detonate)
    monkeypatch.setattr(os, "rmdir", detonate)
    monkeypatch.setattr(os, "symlink", detonate)
    monkeypatch.setattr(os, "chmod", detonate)
    monkeypatch.setattr(os, "system", detonate)
    monkeypatch.setattr(shutil, "copyfile", detonate)
    monkeypatch.setattr(subprocess, "Popen", detonate)
    monkeypatch.setattr(subprocess, "run", detonate)
    monkeypatch.setattr(socket, "socket", detonate)
    monkeypatch.setattr(socket, "create_connection", detonate)
    monkeypatch.setattr(socket, "getaddrinfo", detonate)
    try:
        target = canonicalize_write_target_under_workspace(
            root, candidate, change_type=change_type
        )
    finally:
        monkeypatch.undo()

    assert target.change_type == change_type


def test_guard_touches_no_forbidden_entry_point_on_failure_paths(tmp_path, monkeypatch):
    root = make_workspace(tmp_path)

    monkeypatch.setattr(builtins, "open", detonate)
    monkeypatch.setattr(os, "getenv", detonate)
    monkeypatch.setattr(os.environ, "get", detonate)
    monkeypatch.setattr(os, "listdir", detonate)
    monkeypatch.setattr(os, "scandir", detonate)
    monkeypatch.setattr(os, "walk", detonate)
    monkeypatch.setattr(os, "mkdir", detonate)
    monkeypatch.setattr(os, "makedirs", detonate)
    monkeypatch.setattr(os, "system", detonate)
    monkeypatch.setattr(subprocess, "Popen", detonate)
    monkeypatch.setattr(socket, "socket", detonate)
    try:
        failures = []
        cases = [
            ("modify", "src/absent.py"),
            ("modify", "src"),
            ("modify", "../outside.py"),
            ("create", "src/mod.py"),
            ("create", "absent_dir/new.py"),
            ("create", "src/"),
            ("create", "\\\\server\\share\\x"),
        ]
        for change_type, candidate in cases:
            try:
                canonicalize_write_target_under_workspace(
                    root, candidate, change_type=change_type
                )
            except CanonicalPathError as exc:
                failures.append(type(exc).__name__)
    finally:
        monkeypatch.undo()

    assert len(failures) == 7


def test_nothing_is_created_by_any_call(tmp_path):
    """The single most important assertion in this suite."""
    root = make_workspace(tmp_path)
    before = snapshot(root)
    outside_before = sorted(p.name for p in tmp_path.iterdir())

    cases = [
        ("modify", "src/mod.py"),
        ("modify", "src/absent.py"),
        ("modify", "src"),
        ("create", "src/new.py"),
        ("create", "new_at_root.py"),
        ("create", "src/mod.py"),
        ("create", "absent_dir/new.py"),
        ("create", "absent_dir/deeper/new.py"),
        ("create", "../escape.py"),
    ]
    for change_type, candidate in cases:
        try:
            canonicalize_write_target_under_workspace(
                root, candidate, change_type=change_type
            )
        except CanonicalPathError:
            pass

    assert snapshot(root) == before
    assert sorted(p.name for p in tmp_path.iterdir()) == outside_before


def test_guard_touches_only_paths_under_tmp_path(tmp_path, monkeypatch):
    root = make_workspace(tmp_path)
    seen: list[str] = []
    real_lstat = os.lstat
    real_stat = os.stat
    real_resolve = Path.resolve

    def tracking_lstat(path, *args, **kwargs):
        seen.append(os.fspath(path))
        return real_lstat(path, *args, **kwargs)

    def tracking_stat(path, *args, **kwargs):
        seen.append(os.fspath(path))
        return real_stat(path, *args, **kwargs)

    def tracking_resolve(self, *args, **kwargs):
        seen.append(str(self))
        return real_resolve(self, *args, **kwargs)

    monkeypatch.setattr(os, "lstat", tracking_lstat)
    monkeypatch.setattr(os, "stat", tracking_stat)
    monkeypatch.setattr(Path, "resolve", tracking_resolve)

    canonicalize_write_target_under_workspace(root, "src/mod.py", change_type="modify")
    canonicalize_write_target_under_workspace(root, "src/new.py", change_type="create")

    monkeypatch.undo()
    tmp_prefix = os.path.normcase(str(tmp_path))
    assert seen
    for path in seen:
        assert os.path.normcase(os.path.abspath(path)).startswith(tmp_prefix), path


def test_unexpected_filesystem_errors_fail_closed_rather_than_reading_absent(
    tmp_path, monkeypatch
):
    """A non-ENOENT error is never converted into "the destination is missing"."""
    root = make_workspace(tmp_path)
    real_lstat = os.lstat
    target_path = os.path.normcase(os.path.abspath(str(root / "src" / "new.py")))

    def failing_lstat(path, *args, **kwargs):
        if os.path.normcase(os.path.abspath(os.fspath(path))) == target_path:
            raise PermissionError(13, "denied")
        return real_lstat(path, *args, **kwargs)

    monkeypatch.setattr(os, "lstat", failing_lstat)

    with pytest.raises(CanonicalPathWriteTargetError, match="could not be established"):
        canonicalize_write_target_under_workspace(
            root, "src/new.py", change_type="create"
        )


def test_reparse_point_destination_rejected_via_faked_attributes(tmp_path, monkeypatch):
    """The destination-is-never-a-link rule fires on attributes, not only S_ISLNK."""
    root = make_workspace(tmp_path)
    reparse_flag = getattr(stat_module, "FILE_ATTRIBUTE_REPARSE_POINT", 0x0400)
    real_lstat = os.lstat
    destination = os.path.normcase(os.path.abspath(str(root / "src" / "mod.py")))

    class FakeStat:
        def __init__(self, *, st_mode: int, **extra: int) -> None:
            self.st_mode = st_mode
            for name, value in extra.items():
                setattr(self, name, value)

    def faked_lstat(path, *args, **kwargs):
        result = real_lstat(path, *args, **kwargs)
        if os.path.normcase(os.path.abspath(os.fspath(path))) == destination:
            return FakeStat(st_mode=result.st_mode, st_file_attributes=reparse_flag)
        return result

    monkeypatch.setattr(os, "lstat", faked_lstat)

    for allow_symlinks in (False, True):
        with pytest.raises(CanonicalPathSymlinkError, match="destination"):
            canonicalize_write_target_under_workspace(
                root,
                "src/mod.py",
                change_type="modify",
                allow_symlinks=allow_symlinks,
            )


def test_this_suite_names_no_real_target_workspace():
    forbidden_names = ("mis" "_project", "a8" "_oa", "bible" "_reading_v2")
    for module_path in (Path(canonical.__file__), Path(__file__)):
        source = module_path.read_text(encoding="utf-8")
        for forbidden in forbidden_names:
            assert forbidden not in source, (module_path.name, forbidden)


# -- 8. Phase 5F2B is library only --------------------------------------------


def test_the_write_target_guard_has_no_caller_at_all():
    """Phase 5D0's guard has exactly one caller; the write-target guard has none."""
    package_root = Path(canonical.__file__).resolve().parents[1]
    exporter = Path(canonical.__file__).resolve().parent / "__init__.py"
    callers = []
    for module_path in sorted(package_root.rglob("*.py")):
        resolved = module_path.resolve()
        if resolved in (Path(canonical.__file__).resolve(), exporter):
            continue
        source = resolved.read_text(encoding="utf-8")
        for name in (
            "canonicalize_write_target_under_workspace",
            "CanonicalWriteTarget",
            "CanonicalPathWriteTargetError",
        ):
            if name in source:
                callers.append((module_path.name, name))
    assert callers == []


def test_no_command_and_no_option_was_added(tmp_path):
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    for command in (
        "version",
        "inspect-issue",
        "llm-smoke-test",
        "generate-plan",
        "real-llm-smoke-test",
        "generate-model-plan",
        "l2-dry-run",
        "l2-inspect-workspace",
        "l2-read-workspace-files",
        "generate-patch-proposal",
        "generate-diff-proposal",
        "l2-preview-file-edits",
    ):
        assert command in result.output
    for absent in (
        "write-target",
        "canonicalize-write",
        "l2-write",
        "apply",
        "workspace-write",
    ):
        assert absent not in result.output

    for command in ("l2-preview-file-edits", "l2-dry-run"):
        command_help = runner.invoke(app, [command, "--help"])
        assert command_help.exit_code == 0
        for absent in (
            "--change-type",
            "--create",
            "--write",
            "--allow-symlinks",
            "--canonicalize",
            "--write-target",
        ):
            assert absent not in command_help.output


def test_no_config_field_was_added_for_workspace_writes():
    from ai_dev_orchestrator import models

    source = Path(models.__file__).read_text(encoding="utf-8")
    for absent in (
        "workspace_write",
        "protected_path_authorizations",
        "allow_workspace_writes",
        "write_journal",
    ):
        assert absent not in source, absent
