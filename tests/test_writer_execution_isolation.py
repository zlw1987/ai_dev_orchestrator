"""Phase 5F2C-FU1 tests: Git execution isolation and Windows replacement correctness.

These are the regression tests for six review findings against the Phase 5F2C
writer. They are kept in their own file because each one pins a *specific*
correction, and a reader should be able to see the whole set at once:

1. ``ReplaceFileW`` must be called with ``dwReplaceFlags == 0``. The original
   code passed ``REPLACEFILE_WRITE_THROUGH``, which Microsoft documents as **not
   supported** — so the call claimed a durability guarantee the API does not
   offer.
2. Once ``ReplaceFileW`` has been *invoked*, no automatic mutation is permitted.
   The original code deleted the temp file after a failed replacement, at a
   moment when filename state may already have changed.
3. A repository-configured Git **filter** must not be able to execute. "Fixed
   argv plus ``shell=False``" never prevented that, and this file proves the
   escape against a real ``git`` binary before proving it is closed.
4. The Git executable handed to ``subprocess`` must be an absolute path,
   resolved once and reused, and never one living inside the target workspace.
5. Output is bounded during capture; the residual limitation is stated.
6. The result schema must not claim no file was created when a sibling temp file
   was.

**Every repository here is a synthetic Git repository created under pytest's own
``tmp_path``.** The filter tests execute a real ``git`` binary against those
synthetic repositories on purpose — monkeypatching the filter would prove
nothing about whether Git actually runs it. No real target project is touched.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_dev_orchestrator.cli import app
from ai_dev_orchestrator.file_editing import writer as writer_module
from ai_dev_orchestrator.file_editing import windows_write
from ai_dev_orchestrator.file_editing.writer import WorkspaceWriteRefusedError
from ai_dev_orchestrator.workspace import git_adapter
from ai_dev_orchestrator.workspace.git_adapter import resolve_git_executable

# Reuse the Phase 5F2C fixtures rather than duplicating them.
from tests.test_cli_l2_apply_approved_file_edit import (  # noqa: E402
    ORIGINAL_TEXT,
    PROPOSED_TEXT,
    TARGET,
    _artifact,
    _make_repo,
    _write_artifact,
    _write_config,
)

runner = CliRunner()

windows_only = pytest.mark.skipif(
    sys.platform != "win32", reason="the Phase 5F2C writer is Windows-only"
)
git_required = pytest.mark.skipif(
    shutil.which("git") is None, reason="git is not installed"
)


def _setup(tmp_path: Path, **config_kwargs):
    repo = _make_repo(tmp_path)
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    config = _write_config(inputs, repo, **config_kwargs)
    artifact = _write_artifact(inputs, _artifact())
    return repo, config, artifact


def _invoke(config: Path, artifact: Path):
    return runner.invoke(
        app,
        [
            "l2-apply-approved-file-edit",
            "--project-config",
            str(config),
            "--approved-diff-proposal",
            str(artifact),
            "--apply-approved-plan",
            "--write-approved-file",
        ],
    )


def _git_config(repo: Path, key: str, value: str) -> None:
    subprocess.run(
        ["git", "config", key, value], cwd=repo, check=True, capture_output=True
    )


# =============================================================================
# Finding 1 — ReplaceFileW must not pass an unsupported flag
# =============================================================================


def test_the_unsupported_write_through_flag_constant_is_gone():
    """``REPLACEFILE_WRITE_THROUGH`` is not supported by ReplaceFileW."""
    assert not hasattr(windows_write, "REPLACEFILE_WRITE_THROUGH")
    source = Path(windows_write.__file__).read_text(encoding="utf-8")
    # The names may appear in prose explaining why they are absent, but never as
    # a module-level assignment — which is what a passed flag would require.
    for line in source.splitlines():
        for flag in (
            "REPLACEFILE_WRITE_THROUGH",
            "REPLACEFILE_IGNORE_MERGE_ERRORS",
            "REPLACEFILE_IGNORE_ACL_ERRORS",
        ):
            assert not line.startswith(flag), line
    for flag in ("REPLACEFILE_IGNORE_MERGE_ERRORS", "REPLACEFILE_IGNORE_ACL_ERRORS"):
        assert not hasattr(windows_write, flag)


def test_the_replace_flags_constant_is_exactly_zero():
    assert windows_write.REPLACE_FILE_FLAGS == 0


@windows_only
def test_the_actual_flag_value_passed_to_replacefilew_is_zero(tmp_path, monkeypatch):
    """Pin the value that reaches the Win32 call, not just the constant."""
    captured: dict = {}

    class _FakeKernel32:
        class ReplaceFileW:  # noqa: N801 - mimics the ctypes function object
            restype = None
            argtypes = None

            def __call__(self, replaced, replacement, backup, flags, exclude, reserved):
                captured["replaced"] = replaced
                captured["replacement"] = replacement
                captured["backup"] = backup
                captured["flags"] = flags
                captured["exclude"] = exclude
                captured["reserved"] = reserved
                # Perform the swap ourselves so the caller sees success.
                os.replace(replacement, replaced)
                return 1

        def __init__(self):
            self.ReplaceFileW = _FakeKernel32.ReplaceFileW()

    monkeypatch.setattr(windows_write, "_kernel32", lambda: _FakeKernel32())

    destination = tmp_path / "dest.txt"
    destination.write_bytes(b"before\n")

    windows_write.replace_file_with_bytes(
        destination=str(destination),
        parent_directory=str(tmp_path),
        data=b"after\n",
        temp_name=".aido-write-test.tmp",
    )

    assert captured["flags"] == 0
    # And specifically none of the three flags the docs describe.
    assert captured["flags"] & 0x1 == 0  # REPLACEFILE_WRITE_THROUGH (unsupported)
    assert captured["flags"] & 0x2 == 0  # REPLACEFILE_IGNORE_MERGE_ERRORS
    assert captured["flags"] & 0x4 == 0  # REPLACEFILE_IGNORE_ACL_ERRORS
    # No backup file is requested.
    assert captured["backup"] is None
    assert destination.read_bytes() == b"after\n"


@windows_only
def test_durability_still_comes_from_fsync_before_the_replacement(tmp_path, monkeypatch):
    """The temp file is flushed and fsynced before ReplaceFileW is reached."""
    order: list[str] = []
    real_fsync = os.fsync

    def tracking_fsync(fd):
        order.append("fsync")
        return real_fsync(fd)

    class _FakeKernel32:
        def __init__(self):
            outer = self

            class _Replace:
                restype = None
                argtypes = None

                def __call__(self, replaced, replacement, backup, flags, *rest):
                    order.append("ReplaceFileW")
                    os.replace(replacement, replaced)
                    return 1

            self.ReplaceFileW = _Replace()

    monkeypatch.setattr(os, "fsync", tracking_fsync)
    monkeypatch.setattr(windows_write, "_kernel32", lambda: _FakeKernel32())

    destination = tmp_path / "dest.txt"
    destination.write_bytes(b"before\n")
    windows_write.replace_file_with_bytes(
        destination=str(destination),
        parent_directory=str(tmp_path),
        data=b"after\n",
        temp_name=".aido-write-order.tmp",
    )

    assert order == ["fsync", "ReplaceFileW"]


def test_os_replace_was_not_substituted_for_replacefilew():
    """The metadata-preserving architecture is intentional and must remain."""
    source = Path(windows_write.__file__).read_text(encoding="utf-8")
    assert "ReplaceFileW" in source
    # os.replace appears only in prose explaining why it is NOT used.
    assert "os.replace(" not in source


# =============================================================================
# Finding 2 — no automatic mutation after ReplaceFileW has been invoked
# =============================================================================


@windows_only
def test_no_cleanup_runs_after_replacefilew_is_invoked_and_fails(tmp_path, monkeypatch):
    removed: list[str] = []
    monkeypatch.setattr(
        windows_write, "_remove_quietly", lambda path: removed.append(path)
    )

    monkeypatch.setattr(
        windows_write, "_kernel32", _failing_replace_kernel32_factory()
    )

    destination = tmp_path / "dest.txt"
    destination.write_bytes(b"before\n")

    with pytest.raises(windows_write.WindowsReplacementAttemptedError) as excinfo:
        windows_write.replace_file_with_bytes(
            destination=str(destination),
            parent_directory=str(tmp_path),
            data=b"after\n",
            temp_name=".aido-write-noclean.tmp",
        )

    assert removed == [], "cleanup must NOT run after ReplaceFileW was invoked"
    assert excinfo.value.temp_name == ".aido-write-noclean.tmp"
    assert "nothing was cleaned up" in str(excinfo.value)
    # The temp file is deliberately still there for a human to inspect.
    assert (tmp_path / ".aido-write-noclean.tmp").exists()


@windows_only
def test_safe_staging_failure_still_cleans_up_its_own_temp(tmp_path, monkeypatch):
    """A failure entirely before the replacement call is safe to tidy up."""
    removed: list[str] = []
    real_remove = windows_write._remove_quietly

    def tracking(path):
        removed.append(path)
        real_remove(path)

    monkeypatch.setattr(windows_write, "_remove_quietly", tracking)

    def exploding_fsync(fd):
        raise OSError("simulated device failure during staging")

    monkeypatch.setattr(os, "fsync", exploding_fsync)

    destination = tmp_path / "dest.txt"
    destination.write_bytes(b"before\n")

    with pytest.raises(windows_write.WindowsStagingError):
        windows_write.replace_file_with_bytes(
            destination=str(destination),
            parent_directory=str(tmp_path),
            data=b"after\n",
            temp_name=".aido-write-staging.tmp",
        )

    assert removed == [str(tmp_path / ".aido-write-staging.tmp")]
    assert not (tmp_path / ".aido-write-staging.tmp").exists()
    # The destination was never touched.
    assert destination.read_bytes() == b"before\n"


@windows_only
def test_an_exclusive_temp_collision_is_a_staging_failure(tmp_path):
    destination = tmp_path / "dest.txt"
    destination.write_bytes(b"before\n")
    (tmp_path / ".aido-write-collide.tmp").write_bytes(b"in the way\n")

    with pytest.raises(windows_write.WindowsStagingError):
        windows_write.replace_file_with_bytes(
            destination=str(destination),
            parent_directory=str(tmp_path),
            data=b"after\n",
            temp_name=".aido-write-collide.tmp",
        )

    assert destination.read_bytes() == b"before\n"
    # A pre-existing file that this module did not create is never deleted.
    assert (tmp_path / ".aido-write-collide.tmp").read_bytes() == b"in the way\n"


@git_required
@windows_only
def test_a_failed_replacement_surfaces_as_indeterminate_with_no_cleanup(
    tmp_path, monkeypatch
):
    """End to end: exit 3, no rollback, no git mutation, temp left in place."""
    repo, config, artifact = _setup(tmp_path)

    removed: list[str] = []
    monkeypatch.setattr(
        windows_write, "_remove_quietly", lambda path: removed.append(path)
    )

    monkeypatch.setattr(
        windows_write, "_kernel32", _failing_replace_kernel32_factory()
    )

    result = _invoke(config, artifact)

    assert result.exit_code == 3
    assert "write-attempted-state-indeterminate" in result.output
    assert "NOT a claim that nothing changed" in result.output
    assert "deliberately left in place" in result.output
    assert result.stdout == ""
    assert removed == []
    # Nothing was rolled back: the original file is untouched, and the staged
    # sibling is still there for a human.
    assert (repo / TARGET).read_bytes() == ORIGINAL_TEXT.encode("utf-8")
    leftovers = list((repo / "src" / "billing").glob(".aido-write-*"))
    assert len(leftovers) == 1


# =============================================================================
# Finding 3 — repository-configured Git filters must not execute
# =============================================================================


def _repo_with_clean_filter(tmp_path: Path, marker: Path, *, driver_key: str) -> Path:
    """A synthetic repo whose ``.gitattributes`` selects a marker-writing filter.

    The attributes file is committed **before** the driver is configured, because
    a ``process`` filter is invoked by ``git add`` itself — which would make the
    fixture fail for the very reason these tests exist.
    """
    repo = _make_repo(tmp_path)
    (repo / ".gitattributes").write_bytes(b"*.py filter=evil\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "attrs"], cwd=repo, check=True, capture_output=True
    )
    _git_config(repo, driver_key, f'cmd /c echo pwned> "{marker}" & more')
    return repo


def _failing_replace_kernel32_factory():
    """A kernel32 proxy whose only fake is a failing ``ReplaceFileW``.

    Everything else — ``CreateFileW``, ``GetFileInformationByHandle``,
    ``CloseHandle`` — stays real, because the writer uses them to probe the
    target's attributes and hard-link count long before it reaches the
    replacement call.
    """
    real = windows_write._kernel32()

    class _Proxy:
        def __init__(self):
            class _Replace:
                restype = None
                argtypes = None

                def __call__(self, *args):
                    return 0  # failure

            self.ReplaceFileW = _Replace()

        def __getattr__(self, name):
            return getattr(real, name)

    return lambda: _Proxy()


@git_required
def test_the_filter_escape_is_real_against_a_real_git_binary(tmp_path):
    """First prove the hazard exists, so the fix below is not proving a tautology.

    ``git status`` re-hashes a tracked file whose cached stat data is stale, and
    hashing a filtered path runs the clean filter — **on a clean tree**.
    """
    marker = tmp_path / "MARKER.txt"
    repo = _repo_with_clean_filter(tmp_path, marker, driver_key="filter.evil.clean")
    if marker.exists():
        marker.unlink()

    # Make the cached stat data stale without changing content.
    time.sleep(1.1)
    (repo / TARGET).touch()

    subprocess.run(
        ["git", "status", "--porcelain=v1"], cwd=repo, check=True, capture_output=True
    )

    assert marker.exists(), (
        "the hazard this finding describes did not reproduce; the fix test below "
        "would then prove nothing"
    )


@git_required
@pytest.mark.parametrize(
    "driver_key",
    ["filter.evil.clean", "filter.evil.smudge", "filter.evil.process"],
)
def test_a_configured_filter_repository_is_refused_before_it_can_execute(
    tmp_path, driver_key
):
    marker = tmp_path / "MARKER.txt"
    repo = _repo_with_clean_filter(tmp_path, marker, driver_key=driver_key)
    if marker.exists():
        marker.unlink()

    time.sleep(1.1)
    (repo / TARGET).touch()

    git = resolve_git_executable(workspace_root=str(repo))
    with pytest.raises(WorkspaceWriteRefusedError) as excinfo:
        writer_module._run_git_preflight(str(repo), TARGET, git_executable=git)

    assert "git config error" in str(excinfo.value)
    assert not marker.exists(), "the repository-configured filter EXECUTED"


@git_required
@windows_only
def test_the_full_writer_refuses_a_filter_repository_and_writes_nothing(tmp_path):
    """End to end through the CLI: refused, marker never created, no write."""
    marker = tmp_path / "MARKER.txt"
    repo = _repo_with_clean_filter(tmp_path, marker, driver_key="filter.evil.clean")
    if marker.exists():
        marker.unlink()

    time.sleep(1.1)
    (repo / TARGET).touch()

    inputs = tmp_path / "inputs"
    inputs.mkdir()
    config = _write_config(inputs, repo)
    artifact = _write_artifact(inputs, _artifact())

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "git config error" in result.output
    assert result.stdout == ""
    assert not marker.exists(), "the repository-configured filter EXECUTED"
    assert (repo / TARGET).read_bytes() == ORIGINAL_TEXT.encode("utf-8")


@git_required
def test_the_refusal_names_the_key_but_never_the_configured_value(tmp_path):
    repo = _make_repo(tmp_path)
    secret_command = "cmd /c echo SENTINEL_CONFIG_VALUE_MUST_NOT_LEAK"
    _git_config(repo, "filter.evil.clean", secret_command)

    git = resolve_git_executable(workspace_root=str(repo))
    with pytest.raises(WorkspaceWriteRefusedError) as excinfo:
        writer_module._run_git_preflight(str(repo), TARGET, git_executable=git)

    message = str(excinfo.value)
    assert "filter.evil.clean" in message
    assert "SENTINEL_CONFIG_VALUE_MUST_NOT_LEAK" not in message
    assert "No configuration value was read" in message


@git_required
def test_an_include_directive_is_refused_without_being_followed(tmp_path):
    repo = _make_repo(tmp_path)
    hidden = tmp_path / "hidden.cfg"
    hidden.write_text(
        '[filter "hidden"]\n\tclean = cmd /c echo SENTINEL_HIDDEN\n', encoding="utf-8"
    )
    _git_config(repo, "include.path", str(hidden).replace("\\", "/"))

    git = resolve_git_executable(workspace_root=str(repo))
    with pytest.raises(WorkspaceWriteRefusedError) as excinfo:
        writer_module._run_git_preflight(str(repo), TARGET, git_executable=git)

    message = str(excinfo.value)
    assert "include.path" in message
    assert "SENTINEL_HIDDEN" not in message


@git_required
@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("core.fsmonitor", "./hook.sh"),
        ("core.hooksPath", "./hooks"),
        ("core.sshCommand", "ssh -v"),
        ("core.pager", "less"),
        ("diff.external", "./mydiff"),
        ("diff.mine.textconv", "cat"),
        ("diff.mine.command", "./mydiff"),
        ("merge.mine.driver", "./mymerge"),
        ("credential.helper", "store"),
        ("alias.st", "!evil"),
        ("uploadpack.packObjectsHook", "./hook"),
        ("extensions.worktreeConfig", "true"),
        ("core.attributesFile", "../elsewhere"),
        ("core.excludesFile", "../elsewhere"),
    ],
)
def test_execution_capable_configuration_refuses_the_repository(tmp_path, key, value):
    repo = _make_repo(tmp_path)
    _git_config(repo, key, value)

    git = resolve_git_executable(workspace_root=str(repo))
    with pytest.raises(WorkspaceWriteRefusedError) as excinfo:
        writer_module._run_git_preflight(str(repo), TARGET, git_executable=git)
    assert "git config error" in str(excinfo.value)


@git_required
def test_an_ordinary_repository_is_not_refused_by_the_config_gate(tmp_path):
    """The gate must be narrow enough to leave ordinary repositories usable."""
    repo = _make_repo(tmp_path)
    _git_config(repo, "branch.main.remote", "origin")
    _git_config(repo, "remote.origin.url", "https://example.invalid/x.git")
    _git_config(repo, "diff.renames", "true")

    git = resolve_git_executable(workspace_root=str(repo))
    writer_module._run_git_preflight(str(repo), TARGET, git_executable=git)


# =============================================================================
# Finding 3 (ordering) — submodules refused before status can descend
# =============================================================================


@git_required
def test_gitlinks_are_refused_before_status_ever_runs(tmp_path, monkeypatch):
    """``status --ignore-submodules=none`` must not run against a submodule tree."""
    repo = _make_repo(tmp_path)

    other = tmp_path / "other"
    other.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=other, check=True, capture_output=True)
    for key, value in (
        ("user.name", "AIDO Test"),
        ("user.email", "aido-test@example.invalid"),
        ("commit.gpgsign", "false"),
    ):
        subprocess.run(
            ["git", "config", key, value], cwd=other, check=True, capture_output=True
        )
    (other / "f.txt").write_bytes(b"x\n")
    subprocess.run(["git", "add", "-A"], cwd=other, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "init"], cwd=other, check=True, capture_output=True
    )
    added = subprocess.run(
        [
            "git", "-c", "protocol.file.allow=always", "submodule", "add", "-q",
            str(other).replace("\\", "/"), "vendor/other",
        ],
        cwd=repo,
        capture_output=True,
    )
    if added.returncode != 0:
        pytest.skip("this git refuses local submodule addition")
    subprocess.run(
        ["git", "commit", "-q", "-m", "add submodule"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    # A submodule adds .gitmodules, so drop the resulting config indirection out
    # of the way: this test is about ORDERING, not about the config gate.
    subprocess.run(
        ["git", "config", "--remove-section", "submodule.vendor/other"],
        cwd=repo,
        capture_output=True,
    )

    operations: list[str] = []
    real_run = git_adapter.run_fixed_git_operation

    def tracking(operation, **kwargs):
        operations.append(operation)
        return real_run(operation, **kwargs)

    monkeypatch.setattr(writer_module, "run_fixed_git_operation", tracking)

    git = resolve_git_executable(workspace_root=str(repo))
    with pytest.raises(WorkspaceWriteRefusedError) as excinfo:
        writer_module._run_git_preflight(str(repo), TARGET, git_executable=git)

    assert "gitlink" in str(excinfo.value)
    assert "ls_files_stage" in operations
    assert "status_porcelain" not in operations, (
        "status must not run once a gitlink exists — it could descend into it"
    )


@git_required
def test_the_preflight_runs_its_operations_in_the_declared_order(
    tmp_path, monkeypatch
):
    repo = _make_repo(tmp_path)
    operations: list[str] = []
    real_run = git_adapter.run_fixed_git_operation

    def tracking(operation, **kwargs):
        operations.append(operation)
        return real_run(operation, **kwargs)

    monkeypatch.setattr(writer_module, "run_fixed_git_operation", tracking)

    git = resolve_git_executable(workspace_root=str(repo))
    writer_module._run_git_preflight(str(repo), TARGET, git_executable=git)

    assert tuple(operations) == git_adapter.ordered_preflight_operations()


# =============================================================================
# Finding 4 — the Git executable is absolute and pinned for the run
# =============================================================================


@git_required
@windows_only
def test_every_git_invocation_uses_the_same_absolute_executable(tmp_path, monkeypatch):
    repo, config, artifact = _setup(tmp_path)

    seen: list[str] = []
    real_popen = subprocess.Popen

    def tracking(argv, **kwargs):
        seen.append(argv[0])
        return real_popen(argv, **kwargs)

    monkeypatch.setattr(git_adapter.subprocess, "Popen", tracking)

    assert _invoke(config, artifact).exit_code == 0

    assert seen, "the writer should have run git"
    assert len(set(seen)) == 1, "the executable must be pinned for the whole run"
    only = seen[0]
    assert os.path.isabs(only)
    assert only != "git"
    assert os.path.isfile(only)


@git_required
def test_the_writer_refuses_when_no_trusted_git_can_be_established(
    tmp_path, monkeypatch
):
    repo = _make_repo(tmp_path)
    monkeypatch.setattr(git_adapter.shutil, "which", lambda name: None)

    with pytest.raises(WorkspaceWriteRefusedError) as excinfo:
        writer_module._resolve_git(str(repo))
    assert "git executable error" in str(excinfo.value)


@git_required
def test_a_git_planted_inside_the_workspace_is_never_used(tmp_path, monkeypatch):
    """The repository under edit may not supply the program that inspects it."""
    repo = _make_repo(tmp_path)
    planted_dir = repo / "tools"
    planted_dir.mkdir()
    planted = planted_dir / ("git.exe" if os.name == "nt" else "git")
    shutil.copyfile(resolve_git_executable(workspace_root=""), planted)

    monkeypatch.setattr(git_adapter.shutil, "which", lambda name: str(planted))

    with pytest.raises(WorkspaceWriteRefusedError) as excinfo:
        writer_module._resolve_git(str(repo))
    assert "inside the target workspace" in str(excinfo.value)


def test_the_writer_never_passes_a_bare_git_string():
    """The executable only ever comes from ``resolve_git_executable``.

    (``"git"`` does appear in the source as a *report block key*; what must not
    exist is an executable literal.)
    """
    source = Path(writer_module.__file__).read_text(encoding="utf-8")
    for absent in (
        'git_executable="git"',
        "git_executable='git'",
        "GIT_EXECUTABLE",
        '= "git"',
        "shutil.which",
    ):
        assert absent not in source, absent
    assert "resolve_git_executable" in source


# =============================================================================
# Finding 6 — the result schema tells the truth about the temp file
# =============================================================================


def test_the_schema_no_longer_claims_no_file_was_created():
    from ai_dev_orchestrator.file_editing.writer import (
        WorkspaceWriteExclusions,
        WorkspaceWriteOperationalFiles,
    )

    # The misleading blanket field is gone, replaced by a target-scoped one.
    assert "files_created" not in WorkspaceWriteExclusions.model_fields
    assert "target_files_created" in WorkspaceWriteExclusions.model_fields
    # And the operational truth has somewhere honest to live.
    assert set(WorkspaceWriteOperationalFiles.model_fields) == {
        "temp_sibling_used",
        "temp_sibling_consumed_by_replacement",
        "temp_sibling_left_behind",
        "directories_created",
        "backup_or_journal_files_created",
    }


@git_required
@windows_only
def test_a_successful_report_records_the_operational_temp_file(tmp_path):
    from ai_dev_orchestrator.file_editing import WorkspaceWriteReport

    repo, config, artifact = _setup(tmp_path)

    result = _invoke(config, artifact)
    assert result.exit_code == 0, result.output

    report = WorkspaceWriteReport.model_validate_json(result.stdout)

    # No approved target was created, deleted or renamed...
    assert report.exclusions.target_files_created is False
    assert report.exclusions.target_files_deleted is False
    assert report.exclusions.target_files_renamed is False
    # ...but one ephemeral operational sibling was used, and is gone.
    assert report.operational_files.temp_sibling_used is True
    assert report.operational_files.temp_sibling_consumed_by_replacement is True
    assert report.operational_files.temp_sibling_left_behind is False
    assert report.operational_files.directories_created is False
    assert report.operational_files.backup_or_journal_files_created is False

    assert list((repo / "src" / "billing").glob(".aido-write-*")) == []


@git_required
@windows_only
def test_the_report_records_the_executable_and_config_contract(tmp_path):
    from ai_dev_orchestrator.file_editing import WorkspaceWriteReport

    repo, config, artifact = _setup(tmp_path)
    result = _invoke(config, artifact)
    assert result.exit_code == 0, result.output

    report = WorkspaceWriteReport.model_validate_json(result.stdout)

    assert report.git.git_executable_absolute is True
    assert report.git.git_executable_outside_workspace is True
    assert report.git.git_executable_pinned_for_run is True
    assert report.git.config_execution_surface_checked is True
    assert report.git.unsupported_config_found is False
    assert report.checks.git_executable_resolved_absolute is True
    assert report.checks.git_config_execution_surface_supported is True
    assert report.checks.git_index_simple_and_submodule_free is True

    # The executable path itself is never reported.
    resolved = resolve_git_executable(workspace_root="")
    assert resolved not in result.stdout
    assert json.dumps(resolved)[1:-1] not in result.stdout


@git_required
@windows_only
def test_the_reported_operation_order_matches_the_declared_order(tmp_path):
    from ai_dev_orchestrator.file_editing import WorkspaceWriteReport

    repo, config, artifact = _setup(tmp_path)
    result = _invoke(config, artifact)
    assert result.exit_code == 0, result.output

    report = WorkspaceWriteReport.model_validate_json(result.stdout)
    assert report.git.fixed_operations_used == [
        *git_adapter.ordered_preflight_operations(),
        "diff_one_path",
    ]


# =============================================================================
# Unchanged guarantees — re-asserted after the refactor
# =============================================================================


@git_required
@windows_only
def test_no_project_verification_command_runs_after_the_refactor(tmp_path, monkeypatch):
    repo, config, artifact = _setup(tmp_path)

    seen: list[tuple] = []
    real_popen = subprocess.Popen

    def tracking(argv, **kwargs):
        seen.append(tuple(argv))
        return real_popen(argv, **kwargs)

    monkeypatch.setattr(git_adapter.subprocess, "Popen", tracking)

    assert _invoke(config, artifact).exit_code == 0

    assert seen
    for argv in seen:
        joined = " ".join(argv)
        for forbidden in (
            "pytest",
            "npm",
            "make",
            "SENTINEL_VERIFICATION_NEVER_RUN",
            "cmd",
            "powershell",
        ):
            assert forbidden not in joined, argv


def test_no_model_network_github_or_git_write_capability_exists():
    for module in (writer_module, windows_write, git_adapter):
        source = Path(module.__file__).read_text(encoding="utf-8")
        for absent in (
            "import socket",
            "import httpx",
            "import requests",
            "LLMClient",
            "GitHubClient",
            "load_llm_client_config_from_env",
            "shell=True",
        ):
            assert absent not in source, (module.__name__, absent)

    joined = " ".join(
        " ".join(str(item) for item in template)
        for template in git_adapter.FIXED_GIT_OPERATIONS.values()
    )
    for absent in (
        "commit", "push", "fetch", "clone", "branch", "restore", "checkout",
        "reset", "clean", "stash", "apply", "update-index",
    ):
        assert absent not in joined, absent


def test_no_generalized_writer_feature_appeared():
    """5F2C-FU1 corrects; it does not widen. None of these exists."""
    from ai_dev_orchestrator import file_editing

    for absent in (
        "create_file",
        "delete_file",
        "rename_file",
        "apply_multi_file_edit",
        "rollback",
        "write_journal",
        "begin_transaction",
        "recover",
        "acquire_lock",
        "run_verification_commands",
    ):
        assert not hasattr(file_editing, absent), absent
