"""Phase 5D0 tests: the canonical workspace path guard (library only).

Every filesystem path used here lives under pytest's ``tmp_path``. No real
project workspace is created, read, listed, stat'd, or resolved, no environment
value is read, no socket is opened, no command is run, and no CLI command is
exercised beyond asserting that the shipped surface did not change.
"""

from __future__ import annotations

import builtins
import os
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
    CanonicalWorkspacePath,
    canonicalize_existing_path_under_workspace,
)

runner = CliRunner()

IS_WINDOWS = sys.platform == "win32"


class Detonated(AssertionError):
    """Raised by a monkeypatched entry point the guard must never reach."""


def detonate(*args, **kwargs):
    raise Detonated("the canonical path guard reached a forbidden entry point")


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
            f"({type(exc).__name__}); symlink policy is covered by the "
            "detection-helper tests"
        )


# -- 1. Error hierarchy --------------------------------------------------------


def test_error_hierarchy_is_a_single_closed_family():
    for error in (
        CanonicalPathInputError,
        CanonicalPathResolutionError,
        CanonicalPathContainmentError,
        CanonicalPathSymlinkError,
        CanonicalPathAmbiguityError,
    ):
        assert issubclass(error, CanonicalPathError)
    assert issubclass(CanonicalPathError, Exception)


# -- 2. Happy paths ------------------------------------------------------------


def test_existing_file_under_workspace_accepted(tmp_path):
    root = make_workspace(tmp_path)

    decision = canonicalize_existing_path_under_workspace(root, "src/mod.py")

    assert isinstance(decision, CanonicalWorkspacePath)
    assert decision.is_inside_workspace is True
    assert decision.allow_symlinks is False
    assert decision.relative_path == os.path.join("src", "mod.py")


def test_existing_directory_under_workspace_accepted(tmp_path):
    root = make_workspace(tmp_path)

    decision = canonicalize_existing_path_under_workspace(root, "src")

    assert decision.relative_path == "src"


def test_relative_candidate_under_workspace_accepted(tmp_path):
    root = make_workspace(tmp_path)

    for spelling in ("src/mod.py", "src\\mod.py", "./src/mod.py", "src/../src/mod.py"):
        decision = canonicalize_existing_path_under_workspace(root, spelling)
        assert decision.relative_path == os.path.join("src", "mod.py")
        assert decision.candidate_input == spelling


def test_absolute_candidate_under_workspace_accepted(tmp_path):
    root = make_workspace(tmp_path)
    candidate = root / "src" / "mod.py"

    decision = canonicalize_existing_path_under_workspace(root, candidate)

    assert decision.relative_path == os.path.join("src", "mod.py")
    assert decision.candidate_input == str(candidate)


def test_returned_relative_path_is_relative_and_stable(tmp_path):
    root = make_workspace(tmp_path)

    from_relative = canonicalize_existing_path_under_workspace(root, "src/mod.py")
    from_absolute = canonicalize_existing_path_under_workspace(
        root, root / "src" / "mod.py"
    )

    for decision in (from_relative, from_absolute):
        assert not os.path.isabs(decision.relative_path)
        assert ".." not in decision.relative_path
    assert from_relative.relative_path == from_absolute.relative_path
    assert from_relative.resolved_candidate == from_absolute.resolved_candidate


def test_resolved_candidate_is_inside_resolved_workspace_root(tmp_path):
    root = make_workspace(tmp_path)

    decision = canonicalize_existing_path_under_workspace(root, "src/mod.py")

    resolved_root = decision.resolved_workspace_root
    resolved_candidate = decision.resolved_candidate
    assert os.path.isabs(resolved_root)
    assert os.path.isabs(resolved_candidate)
    assert os.path.commonpath(
        [os.path.normcase(resolved_root), os.path.normcase(resolved_candidate)]
    ) == os.path.normcase(resolved_root)
    assert (
        os.path.join(resolved_root, decision.relative_path) == resolved_candidate
    )


def test_decision_object_is_frozen_and_data_only(tmp_path):
    root = make_workspace(tmp_path)

    decision = canonicalize_existing_path_under_workspace(root, "src/mod.py")

    with pytest.raises(Exception):
        decision.relative_path = "other"  # type: ignore[misc]
    public_attributes = {name for name in vars(decision)}
    assert public_attributes == {
        "workspace_root_input",
        "candidate_input",
        "resolved_workspace_root",
        "resolved_candidate",
        "relative_path",
        "allow_symlinks",
        "is_inside_workspace",
    }
    # Data only: no callables to reach the disk with.
    assert not [
        name
        for name in dir(decision)
        if not name.startswith("_") and callable(getattr(decision, name))
    ]
    # The file's contents are not carried anywhere in the decision.
    assert "value = 1" not in repr(decision)


def test_candidate_equal_to_workspace_root_is_accepted_as_inside(tmp_path):
    """Deliberate choice: the root is inside itself, and reports ``.``.

    "Inside the workspace" and "is a file" are different questions; a future
    caller that needs a file must check the kind separately.
    """
    root = make_workspace(tmp_path)

    decision = canonicalize_existing_path_under_workspace(root, root)

    assert decision.relative_path == "."
    assert decision.is_inside_workspace is True
    assert decision.resolved_candidate == decision.resolved_workspace_root


def test_inputs_are_not_mutated_and_nothing_is_created(tmp_path):
    root = make_workspace(tmp_path)
    root_input = str(root)
    candidate_input = "src/mod.py"
    before = sorted(p.name for p in root.rglob("*"))

    decision = canonicalize_existing_path_under_workspace(root_input, candidate_input)

    assert root_input == str(root)
    assert candidate_input == "src/mod.py"
    assert decision.workspace_root_input == root_input
    assert decision.candidate_input == candidate_input
    assert sorted(p.name for p in root.rglob("*")) == before


# -- 3. Input failures ---------------------------------------------------------


@pytest.mark.parametrize("blank", ["", " ", "\t", "\n"])
def test_blank_workspace_root_rejected(tmp_path, blank):
    root = make_workspace(tmp_path)

    with pytest.raises(CanonicalPathInputError, match="workspace_root"):
        canonicalize_existing_path_under_workspace(blank, root / "src" / "mod.py")


@pytest.mark.parametrize("blank", ["", " ", "\t", "\n"])
def test_blank_candidate_rejected(tmp_path, blank):
    root = make_workspace(tmp_path)

    with pytest.raises(CanonicalPathInputError, match="candidate"):
        canonicalize_existing_path_under_workspace(root, blank)


@pytest.mark.parametrize("wrong", [None, 42, b"src/mod.py", ["src"]])
def test_wrongly_typed_input_rejected(tmp_path, wrong):
    root = make_workspace(tmp_path)

    with pytest.raises(CanonicalPathInputError):
        canonicalize_existing_path_under_workspace(root, wrong)
    with pytest.raises(CanonicalPathInputError):
        canonicalize_existing_path_under_workspace(wrong, "src/mod.py")


def test_non_bool_allow_symlinks_rejected(tmp_path):
    root = make_workspace(tmp_path)

    with pytest.raises(CanonicalPathInputError, match="allow_symlinks"):
        canonicalize_existing_path_under_workspace(
            root, "src/mod.py", allow_symlinks="yes"  # type: ignore[arg-type]
        )


def test_missing_workspace_root_rejected(tmp_path):
    root = make_workspace(tmp_path)

    with pytest.raises(CanonicalPathInputError, match="workspace_root"):
        canonicalize_existing_path_under_workspace(
            tmp_path / "no_such_root", root / "src" / "mod.py"
        )


def test_workspace_root_that_is_a_file_rejected(tmp_path):
    root = make_workspace(tmp_path)
    file_root = root / "src" / "mod.py"

    with pytest.raises(CanonicalPathInputError, match="not a directory"):
        canonicalize_existing_path_under_workspace(file_root, file_root)


def test_missing_candidate_rejected(tmp_path):
    root = make_workspace(tmp_path)

    with pytest.raises(CanonicalPathInputError, match="candidate"):
        canonicalize_existing_path_under_workspace(root, "src/absent.py")


def test_relative_candidate_escaping_with_dotdot_rejected(tmp_path):
    root = make_workspace(tmp_path)
    (tmp_path / "outside.py").write_text("secret = 1\n", encoding="utf-8")

    for escape in ("../outside.py", "src/../../outside.py", "..\\outside.py"):
        with pytest.raises(CanonicalPathContainmentError):
            canonicalize_existing_path_under_workspace(root, escape)
        with pytest.raises(CanonicalPathContainmentError):
            canonicalize_existing_path_under_workspace(
                root, escape, allow_symlinks=True
            )


def test_absolute_candidate_outside_workspace_rejected(tmp_path):
    root = make_workspace(tmp_path)
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (outside / "file.py").write_text("secret = 1\n", encoding="utf-8")

    with pytest.raises(CanonicalPathContainmentError):
        canonicalize_existing_path_under_workspace(root, outside / "file.py")
    with pytest.raises(CanonicalPathContainmentError):
        canonicalize_existing_path_under_workspace(
            root, outside / "file.py", allow_symlinks=True
        )


def test_workspace_root_parent_rejected(tmp_path):
    root = make_workspace(tmp_path)

    with pytest.raises(CanonicalPathContainmentError):
        canonicalize_existing_path_under_workspace(root, tmp_path)


# -- 4. Containment ------------------------------------------------------------


def test_sibling_prefix_confusion_rejected(tmp_path):
    root = make_workspace(tmp_path)
    sibling = tmp_path / "repo_evil"
    sibling.mkdir()
    (sibling / "file.py").write_text("secret = 1\n", encoding="utf-8")

    for allow_symlinks in (False, True):
        with pytest.raises(CanonicalPathContainmentError):
            canonicalize_existing_path_under_workspace(
                root, sibling / "file.py", allow_symlinks=allow_symlinks
            )
        with pytest.raises(CanonicalPathContainmentError):
            canonicalize_existing_path_under_workspace(
                root, "../repo_evil/file.py", allow_symlinks=allow_symlinks
            )


def test_containment_uses_commonpath_not_a_string_prefix():
    root = os.path.normcase(os.path.abspath(os.sep + "canonical_guard_root"))
    sibling = root + "_evil"

    with pytest.raises(CanonicalPathContainmentError):
        canonical._relative_path_inside(root, os.path.join(sibling, "file.py"))


def test_drive_or_form_mismatch_fails_closed():
    """A comparison that cannot be made is refused, never guessed."""
    if IS_WINDOWS:
        with pytest.raises(CanonicalPathAmbiguityError):
            canonical._relative_path_inside("c:\\root", "d:\\root\\file.py")
    else:
        with pytest.raises(CanonicalPathContainmentError):
            canonical._relative_path_inside("/root", "/other/file.py")


def test_case_behavior_matches_the_platform():
    """Lexical containment follows ``os.path.normcase`` and nothing else."""
    if IS_WINDOWS:
        assert canonical._lexical_relative_components(
            "C:\\Root\\Repo", "C:\\ROOT\\repo\\src\\mod.py"
        ) == ["src", "mod.py"]
    else:
        assert (
            canonical._lexical_relative_components(
                "/Root/Repo", "/ROOT/repo/src/mod.py"
            )
            is None
        )
        assert canonical._lexical_relative_components(
            "/Root/Repo", "/Root/Repo/src/mod.py"
        ) == ["src", "mod.py"]


# -- 5. Symlink / reparse policy ----------------------------------------------


def test_symlink_to_file_inside_workspace_rejected_unless_allowed(tmp_path):
    root = make_workspace(tmp_path)
    link = root / "src" / "alias.py"
    try_symlink(link, root / "src" / "mod.py")

    with pytest.raises(CanonicalPathSymlinkError):
        canonicalize_existing_path_under_workspace(root, "src/alias.py")

    decision = canonicalize_existing_path_under_workspace(
        root, "src/alias.py", allow_symlinks=True
    )
    assert decision.allow_symlinks is True
    assert decision.relative_path == os.path.join("src", "mod.py")


def test_symlink_pointing_outside_workspace_rejected_even_when_allowed(tmp_path):
    root = make_workspace(tmp_path)
    outside = tmp_path / "outside.py"
    outside.write_text("secret = 1\n", encoding="utf-8")
    link = root / "src" / "escape.py"
    try_symlink(link, outside)

    with pytest.raises(CanonicalPathSymlinkError):
        canonicalize_existing_path_under_workspace(root, "src/escape.py")
    with pytest.raises(CanonicalPathContainmentError):
        canonicalize_existing_path_under_workspace(
            root, "src/escape.py", allow_symlinks=True
        )


def test_intermediate_directory_symlink_rejected_unless_allowed(tmp_path):
    root = make_workspace(tmp_path)
    outside_dir = tmp_path / "outside_dir"
    outside_dir.mkdir()
    (outside_dir / "file.py").write_text("secret = 1\n", encoding="utf-8")
    try_symlink(root / "vendor", outside_dir, target_is_directory=True)

    with pytest.raises(CanonicalPathSymlinkError):
        canonicalize_existing_path_under_workspace(root, "vendor/file.py")
    with pytest.raises(CanonicalPathContainmentError):
        canonicalize_existing_path_under_workspace(
            root, "vendor/file.py", allow_symlinks=True
        )


def test_symlinked_workspace_root_rejected_when_symlinks_disallowed(tmp_path):
    real_root = make_workspace(tmp_path)
    link_root = tmp_path / "linked_repo"
    try_symlink(link_root, real_root, target_is_directory=True)

    with pytest.raises(CanonicalPathSymlinkError, match="workspace_root"):
        canonicalize_existing_path_under_workspace(link_root, "src/mod.py")

    decision = canonicalize_existing_path_under_workspace(
        link_root, "src/mod.py", allow_symlinks=True
    )
    assert decision.relative_path == os.path.join("src", "mod.py")


def test_dangling_symlink_candidate_fails_closed(tmp_path):
    root = make_workspace(tmp_path)
    try_symlink(root / "src" / "dangling.py", root / "src" / "absent.py")

    with pytest.raises(CanonicalPathSymlinkError):
        canonicalize_existing_path_under_workspace(root, "src/dangling.py")
    with pytest.raises(CanonicalPathResolutionError):
        canonicalize_existing_path_under_workspace(
            root, "src/dangling.py", allow_symlinks=True
        )


class FakeStat:
    """A stand-in for ``os.stat_result`` carrying only the fields we inspect."""

    def __init__(self, *, st_mode: int, **extra: int) -> None:
        self.st_mode = st_mode
        for name, value in extra.items():
            setattr(self, name, value)


def test_reparse_point_detection_covers_windows_attributes():
    """Junctions need admin-free creation to test live; detect on attributes.

    NTFS junctions and directory mount points are reparse points that ``stat``
    follows silently and that ``S_ISLNK`` does not report, so the detector reads
    the Windows-only ``st_file_attributes`` reparse bit and ``st_reparse_tag``
    as well. Both are exercised here with fabricated stat results, which works
    on every platform and needs no elevation.
    """
    reparse_flag = getattr(stat_module, "FILE_ATTRIBUTE_REPARSE_POINT", 0x0400)
    directory_flag = getattr(stat_module, "FILE_ATTRIBUTE_DIRECTORY", 0x0010)

    plain_file = FakeStat(st_mode=stat_module.S_IFREG | 0o644)
    plain_directory = FakeStat(
        st_mode=stat_module.S_IFDIR | 0o755, st_file_attributes=directory_flag
    )
    posix_symlink = FakeStat(st_mode=stat_module.S_IFLNK | 0o777)
    junction = FakeStat(
        st_mode=stat_module.S_IFDIR | 0o755,
        st_file_attributes=directory_flag | reparse_flag,
    )
    tagged_reparse = FakeStat(st_mode=stat_module.S_IFDIR | 0o755, st_reparse_tag=0xA0000003)

    assert canonical._is_symlink_or_reparse_point(plain_file) is False
    assert canonical._is_symlink_or_reparse_point(plain_directory) is False
    assert canonical._is_symlink_or_reparse_point(posix_symlink) is True
    assert canonical._is_symlink_or_reparse_point(junction) is True
    assert canonical._is_symlink_or_reparse_point(tagged_reparse) is True


def test_reparse_point_workspace_root_rejected_via_faked_attributes(tmp_path, monkeypatch):
    """The root reparse check fires on attributes, not only on ``S_ISLNK``."""
    root = make_workspace(tmp_path)
    reparse_flag = getattr(stat_module, "FILE_ATTRIBUTE_REPARSE_POINT", 0x0400)
    real_lstat = os.lstat
    target = os.path.normcase(os.path.abspath(str(root)))

    def faked_lstat(path, *args, **kwargs):
        result = real_lstat(path, *args, **kwargs)
        if os.path.normcase(os.path.abspath(os.fspath(path))) == target:
            return FakeStat(
                st_mode=result.st_mode, st_file_attributes=reparse_flag
            )
        return result

    monkeypatch.setattr(os, "lstat", faked_lstat)

    with pytest.raises(CanonicalPathSymlinkError, match="workspace_root"):
        canonicalize_existing_path_under_workspace(root, "src/mod.py")


def test_reparse_point_component_rejected_via_faked_attributes(tmp_path, monkeypatch):
    root = make_workspace(tmp_path)
    reparse_flag = getattr(stat_module, "FILE_ATTRIBUTE_REPARSE_POINT", 0x0400)
    real_lstat = os.lstat
    target = os.path.normcase(os.path.abspath(str(root / "src")))

    def faked_lstat(path, *args, **kwargs):
        result = real_lstat(path, *args, **kwargs)
        if os.path.normcase(os.path.abspath(os.fspath(path))) == target:
            return FakeStat(
                st_mode=result.st_mode, st_file_attributes=reparse_flag
            )
        return result

    monkeypatch.setattr(os, "lstat", faked_lstat)

    with pytest.raises(CanonicalPathSymlinkError, match="component"):
        canonicalize_existing_path_under_workspace(root, "src/mod.py")


# -- 6. Lexical rejection happens before any disk touch -----------------------

# A root that is never stat'd: the lexical precheck refuses these strings first.
SAFE_UNTOUCHED_ROOT = os.sep + "canonical_guard_root"

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


@pytest.mark.parametrize("unsafe", UNSAFE_FORMS)
def test_unsafe_candidate_form_rejected_before_any_disk_touch(monkeypatch, unsafe):
    monkeypatch.setattr(os, "stat", detonate)
    monkeypatch.setattr(os, "lstat", detonate)
    monkeypatch.setattr(Path, "resolve", detonate)
    monkeypatch.setattr(os.path, "realpath", detonate)
    monkeypatch.setattr(os.path, "exists", detonate)
    monkeypatch.setattr(os, "listdir", detonate)
    monkeypatch.setattr(os, "scandir", detonate)
    monkeypatch.setattr(builtins, "open", detonate)

    with pytest.raises(CanonicalPathAmbiguityError, match="candidate"):
        canonicalize_existing_path_under_workspace(SAFE_UNTOUCHED_ROOT, unsafe)


@pytest.mark.parametrize("unsafe", UNSAFE_FORMS)
def test_unsafe_workspace_root_form_rejected_before_any_disk_touch(monkeypatch, unsafe):
    monkeypatch.setattr(os, "stat", detonate)
    monkeypatch.setattr(os, "lstat", detonate)
    monkeypatch.setattr(Path, "resolve", detonate)
    monkeypatch.setattr(os.path, "realpath", detonate)
    monkeypatch.setattr(os.path, "exists", detonate)

    with pytest.raises(CanonicalPathAmbiguityError, match="workspace_root"):
        canonicalize_existing_path_under_workspace(unsafe, "src/mod.py")


def test_blank_inputs_rejected_before_any_disk_touch(monkeypatch):
    monkeypatch.setattr(os, "stat", detonate)
    monkeypatch.setattr(os, "lstat", detonate)
    monkeypatch.setattr(Path, "resolve", detonate)

    with pytest.raises(CanonicalPathInputError):
        canonicalize_existing_path_under_workspace("   ", "src/mod.py")
    with pytest.raises(CanonicalPathInputError):
        canonicalize_existing_path_under_workspace(SAFE_UNTOUCHED_ROOT, "   ")


def test_dot_and_dotdot_components_are_not_mistaken_for_trailing_dots(tmp_path):
    """``.`` and ``..`` end in a dot but are ordinary components, not ambiguous."""
    root = make_workspace(tmp_path)

    decision = canonicalize_existing_path_under_workspace(root, "./src/../src/mod.py")

    assert decision.relative_path == os.path.join("src", "mod.py")


def test_conservative_precheck_is_documented_as_such():
    assert "conservative" in canonical.__doc__


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
)


def test_implementation_module_globals_carry_no_forbidden_names():
    module_globals = vars(canonical)
    for name in FORBIDDEN_GLOBAL_NAMES:
        assert name not in module_globals, name


def test_implementation_module_imports_nothing_forbidden():
    source = Path(canonical.__file__).read_text(encoding="utf-8")
    for forbidden in ("import httpx", "import requests", "import typer",
                      "import socket", "import subprocess"):
        assert forbidden not in source, forbidden


def test_guard_touches_no_forbidden_entry_point_on_the_happy_path(tmp_path, monkeypatch):
    """No env read, no file read, no directory listing, no process, no socket."""
    root = make_workspace(tmp_path)

    monkeypatch.setattr(builtins, "open", detonate)
    monkeypatch.setattr(os, "getenv", detonate)
    monkeypatch.setattr(os.environ, "get", detonate)
    monkeypatch.setattr(os, "listdir", detonate)
    monkeypatch.setattr(os, "scandir", detonate)
    monkeypatch.setattr(os, "walk", detonate)
    monkeypatch.setattr(os, "system", detonate)
    monkeypatch.setattr(subprocess, "Popen", detonate)
    monkeypatch.setattr(subprocess, "run", detonate)
    monkeypatch.setattr(socket, "socket", detonate)
    monkeypatch.setattr(socket, "create_connection", detonate)
    monkeypatch.setattr(socket, "getaddrinfo", detonate)
    try:
        decision = canonicalize_existing_path_under_workspace(root, "src/mod.py")
        directory_decision = canonicalize_existing_path_under_workspace(root, "src")
    finally:
        monkeypatch.undo()

    assert decision.relative_path == os.path.join("src", "mod.py")
    assert directory_decision.relative_path == "src"


def test_guard_touches_no_forbidden_entry_point_on_failure_paths(tmp_path, monkeypatch):
    root = make_workspace(tmp_path)

    monkeypatch.setattr(builtins, "open", detonate)
    monkeypatch.setattr(os, "getenv", detonate)
    monkeypatch.setattr(os.environ, "get", detonate)
    monkeypatch.setattr(os, "listdir", detonate)
    monkeypatch.setattr(os, "scandir", detonate)
    monkeypatch.setattr(os, "walk", detonate)
    monkeypatch.setattr(os, "system", detonate)
    monkeypatch.setattr(subprocess, "Popen", detonate)
    monkeypatch.setattr(socket, "socket", detonate)
    try:
        failures = []
        for candidate in ("", "src/absent.py", "../outside.py", "\\\\server\\share\\x"):
            try:
                canonicalize_existing_path_under_workspace(root, candidate)
            except CanonicalPathError as exc:
                failures.append(type(exc).__name__)
    finally:
        monkeypatch.undo()

    assert len(failures) == 4


def test_guard_touches_only_paths_under_tmp_path(tmp_path, monkeypatch):
    """Every path the guard stats or resolves is under the test's tmp_path."""
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

    canonicalize_existing_path_under_workspace(root, "src/mod.py")

    monkeypatch.undo()
    tmp_prefix = os.path.normcase(str(tmp_path))
    assert seen
    for path in seen:
        assert os.path.normcase(os.path.abspath(path)).startswith(tmp_prefix), path


def test_this_suite_names_no_real_target_workspace():
    """Neither the guard nor this suite references a real C:\\dev project path."""
    forbidden_names = ("mis" "_project", "a8" "_oa", "bible" "_reading_v2")
    for module_path in (
        Path(canonical.__file__),
        Path(__file__),
    ):
        source = module_path.read_text(encoding="utf-8")
        for forbidden in forbidden_names:
            assert forbidden not in source, (module_path.name, forbidden)


# -- 8. Nothing is wired into the CLI -----------------------------------------


def test_root_help_lists_the_shipped_commands_and_no_canonicalization_command():
    """The guard has callers now, but is still not a command in its own right.

    Phase 5D1 added ``l2-inspect-workspace``, the guard's first caller, and
    Phase 5D2 added ``l2-read-workspace-files``, its second. Both are read-only
    — metadata in the first case, bounded redacted contents in the second — and
    neither exposes canonicalization directly: the guard remains a library that
    those commands call, with no command of its own and no option that reaches
    it.
    """
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
    ):
        assert command in result.output
    for absent in ("canonical", "canonicalize", "workspace-inspect"):
        assert absent not in result.output


@pytest.mark.parametrize(
    "command", ["l2-dry-run", "generate-plan", "generate-model-plan"]
)
def test_command_help_gains_no_canonical_option(command):
    result = runner.invoke(app, [command, "--help"])

    assert result.exit_code == 0
    for absent in (
        "--allow-symlinks",
        "--canonical",
        "--canonicalize",
        "--inspect",
        "--workspace",
        "--file",
        "--context-file",
    ):
        assert absent not in result.output


def test_the_canonical_guard_has_exactly_one_caller():
    """Phase 5D1 gave the guard its first and only caller, ``cli.py``.

    Phase 5D0 shipped it with none. The assertion is kept rather than deleted
    because "how many things can reach a workspace?" is the number worth
    watching: it went from zero to one, deliberately, and a second entry would
    be a change someone should have to make on purpose.

    Nobody imports the private module path either — the guard is reached only
    through the ``workspace`` package's public export.
    """
    package_root = Path(canonical.__file__).resolve().parents[1]
    exporter = Path(canonical.__file__).resolve().parent / "__init__.py"
    callers = []
    for module_path in sorted(package_root.rglob("*.py")):
        resolved = module_path.resolve()
        if resolved in (Path(canonical.__file__).resolve(), exporter):
            continue
        source = resolved.read_text(encoding="utf-8")
        if "canonicalize_existing_path_under_workspace" in source:
            callers.append(module_path.name)
        assert "workspace.canonical" not in source, module_path.name
    assert callers == ["cli.py"]
