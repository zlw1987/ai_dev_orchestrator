"""Phase 5F2C tests: the ``l2-apply-approved-file-edit`` command and its writer.

This is the first command in this repository that writes a file, so these tests
are organized around the one positive capability and the very large set of
refusals that fence it in:

1. **Gates** — every way the command must fail before it reads anything, before
   it touches a workspace, or before it writes.
2. **The Git contract** — the clean baseline, the simple index, and the tracked
   target.
3. **The target's filesystem state** — regular file, no link, no reparse point,
   supported attributes, supported text.
4. **The approved transformation** — exact pre-image, exact application, exact
   post-image.
5. **The write itself** — exactly one tracked file changes, to exactly the
   approved bytes, uncommitted, with nothing else disturbed.
6. **Failure semantics** — refused-before-write and
   write-attempted-state-indeterminate are never conflated.
7. **Absent capabilities** — no verification command, no model, no network, no
   GitHub, no shell, no arbitrary subprocess.

**Every repository used here is a synthetic Git repository created under
pytest's own ``tmp_path``.** No real target project is used, read, or written by
any test in this file.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_dev_orchestrator import cli
from ai_dev_orchestrator.cli import app
from ai_dev_orchestrator.diff_proposal import (
    DIFF_PROPOSAL_MODE,
    DIFF_PROPOSAL_SCHEMA_VERSION,
)
from ai_dev_orchestrator.file_editing import (
    APPROVED_DIFF_PROPOSAL_MODE,
    APPROVED_DIFF_PROPOSAL_SCHEMA_VERSION,
    REQUIRED_DIFF_EDIT_APPROVAL_TEXT,
    WorkspaceWriteReport,
)
from ai_dev_orchestrator.file_editing import writer as writer_module
from ai_dev_orchestrator.handoff import REQUIRED_APPROVAL_TEXT

runner = CliRunner()

windows_only = pytest.mark.skipif(
    sys.platform != "win32", reason="the Phase 5F2C writer is Windows-only"
)
git_required = pytest.mark.skipif(
    shutil.which("git") is None, reason="git is not installed"
)

PROJECT_ID = "demo_project"
REPO = "demo/widgets"
ISSUE_NUMBER = 42
TITLE = "Round invoice totals to two decimal places"
APPROVER = "operator@example.invalid"

TARGET = "src/billing/totals.py"
SECOND_TARGET = "src/billing/tax.py"
NEW_FILE = "src/billing/new_helper.py"
PROTECTED_TARGET = "src/billing/protected_secrets.py"
FORBIDDEN_TARGET = "secrets/keys.env"
UNLISTED_TARGET = "docs/notes.md"
OUT_OF_SCOPE = "external/other.py"

ORIGINAL_TEXT = (
    "def format_total(amount):\n"
    "    return str(amount)\n"
    "\n"
    "\n"
    "def total(items):\n"
    "    return sum(items)\n"
)
PROPOSED_TEXT = (
    "def format_total(amount):\n"
    '    return f"{amount:.2f}"\n'
    "\n"
    "\n"
    "def total(items):\n"
    "    return sum(items)\n"
)

SECOND_ORIGINAL = "TAX_RATE = 0.2\n"

CONFIG_TEMPLATE = """\
project_id: {project_id}
display_name: Demo Project
repo:
  workspace_path: {workspace_path}
  github_repo: {github_repo}
  default_base_branch: main
  branch_prefix: ai/demo
workspace_policy:
  deny_outside_workspace: {deny_outside_workspace}
  allow_symlinks: {allow_symlinks}
  max_changed_files: {max_changed_files}
workspace_write:
  enabled: {write_enabled}
  max_file_bytes: {max_file_bytes}
allowed_paths:
  - "src/**"
  - "tests/**"
  - "docs/allowed/**"
protected_paths:
  - "src/billing/protected_*.py"
forbidden_paths:
  - ".git/**"
  - "secrets/**"
"""


# -- Synthetic repository ------------------------------------------------------


def _run_git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _make_repo(tmp_path: Path, files: dict[str, str] | None = None) -> Path:
    """Create one synthetic Git repository under ``tmp_path``.

    Deliberately never a real project: the whole repository is created, written,
    committed and inspected inside pytest's own temporary directory.
    """
    repo = tmp_path / "workspace"
    repo.mkdir()
    _run_git(repo, "init", "-q")
    for key, value in (
        ("user.name", "AIDO Test"),
        ("user.email", "aido-test@example.invalid"),
        ("commit.gpgsign", "false"),
        ("core.autocrlf", "false"),
    ):
        _run_git(repo, "config", key, value)

    payload = {TARGET: ORIGINAL_TEXT, SECOND_TARGET: SECOND_ORIGINAL}
    if files is not None:
        payload = files
    for relative, content in payload.items():
        destination = repo / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content.encode("utf-8"))

    _run_git(repo, "add", "-A")
    _run_git(repo, "commit", "-q", "-m", "initial")
    return repo


# -- Artifact construction -----------------------------------------------------


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _unified_diff(path: str, original: str, proposed: str) -> str:
    import difflib

    return "\n".join(
        difflib.unified_diff(
            original.splitlines(),
            proposed.splitlines(),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            lineterm="",
        )
    )


def _plan(files_likely: list[str] | None = None) -> dict:
    return {
        "issue_number": ISSUE_NUMBER,
        "repo": REPO,
        "title": TITLE,
        "summary": "Format invoice totals through one shared helper.",
        "scope_summary": "Only the billing formatting helper.",
        "non_goals": ["No changes to the payment gateway client."],
        "proposed_steps": ["Round totals to two decimal places."],
        "files_likely_to_change": files_likely
        or [
            TARGET,
            SECOND_TARGET,
            NEW_FILE,
            PROTECTED_TARGET,
            FORBIDDEN_TARGET,
            UNLISTED_TARGET,
        ],
        "files_forbidden_or_out_of_scope": [OUT_OF_SCOPE],
        "required_verification": ["pytest -q SENTINEL_VERIFICATION_NEVER_RUN"],
        "risks": ["Rounding differences on reissued invoices."],
        "open_questions": [],
        "automation_level": "L1",
        "requires_human_approval": True,
    }


def _approved_plan(files_likely: list[str] | None = None) -> dict:
    return {
        "approval": {
            "approved_by": APPROVER,
            "approved_at": "2026-01-02T04:00:00+00:00",
            "approval_text": REQUIRED_APPROVAL_TEXT,
            "source": "manual",
        },
        "plan_provenance": {
            "engine": "deterministic",
            "operation": "l1-plan",
            "real_call": False,
            "model": None,
            "endpoint_host": None,
            "generated_at": "2026-01-02T03:04:05+00:00",
            "project_id": PROJECT_ID,
            "repo": REPO,
            "issue_number": ISSUE_NUMBER,
            "title": TITLE,
        },
        "plan": _plan(files_likely),
        "project_id": PROJECT_ID,
        "repo": REPO,
        "issue_number": ISSUE_NUMBER,
    }


def _change(
    path: str = TARGET,
    original: str = ORIGINAL_TEXT,
    proposed: str = PROPOSED_TEXT,
    change_type: str = "modify",
    **overrides,
) -> dict:
    if change_type == "create":
        diff = "\n".join(
            [
                "--- /dev/null",
                f"+++ b/{path}",
                f"@@ -0,0 +1,{len(proposed.splitlines())} @@",
                *[f"+{line}" for line in proposed.splitlines()],
            ]
        )
        pre = None
    else:
        diff = _unified_diff(path, original, proposed)
        pre = _sha(original)
    change = {
        "path": path,
        "change_type": change_type,
        "unified_diff": diff,
        "pre_image_sha256": pre,
        "post_image_sha256": _sha(proposed),
        "rationale": "Round invoice totals to two decimal places.",
        "risks": ["Reissued invoices may differ by a cent."],
        "requires_human_review": True,
    }
    change.update(overrides)
    return change


def _artifact(
    changes: list[dict] | None = None,
    files_likely: list[str] | None = None,
    **overrides,
) -> dict:
    proposal = {
        "schema_version": DIFF_PROPOSAL_SCHEMA_VERSION,
        "mode": DIFF_PROPOSAL_MODE,
        "provenance": {
            "engine": "deterministic",
            "operation": "diff-proposal",
            "real_call": False,
            "model": None,
            "generated_at": None,
            "project_id": PROJECT_ID,
            "repo": REPO,
            "issue_number": ISSUE_NUMBER,
            "title": TITLE,
        },
        "approved_plan": _approved_plan(files_likely),
        "patch_proposal": None,
        "changes": copy.deepcopy(changes) if changes is not None else [_change()],
        "omitted_paths": [],
        "assumptions": [],
        "risks": [],
        "open_questions": [],
        "source_contents_read": True,
        "diffs_generated": True,
        "files_edited": False,
        "commands_run": False,
        "applies_cleanly_checked": False,
        "requires_human_review": True,
        "next_authorization_required": "A writer must be authorized separately.",
    }
    payload = {
        "schema_version": APPROVED_DIFF_PROPOSAL_SCHEMA_VERSION,
        "mode": APPROVED_DIFF_PROPOSAL_MODE,
        "approval": {
            "approved_by": APPROVER,
            "approved_at": "2026-01-04T06:00:00+00:00",
            "approval_text": REQUIRED_DIFF_EDIT_APPROVAL_TEXT,
            "source": "manual",
        },
        "diff_proposal": proposal,
        "project_id": PROJECT_ID,
        "repo": REPO,
        "issue_number": ISSUE_NUMBER,
        "title": TITLE,
        "next_authorization_required": "Verification and review remain unauthorized.",
    }
    payload.update(overrides)
    return payload


def _write_config(
    tmp_path: Path,
    workspace: Path | str,
    *,
    write_enabled: bool = True,
    max_changed_files: int = 20,
    max_file_bytes: int = 200_000,
    allow_symlinks: bool = False,
    deny_outside_workspace: bool = True,
    project_id: str = PROJECT_ID,
    github_repo: str = REPO,
    name: str = "project.yaml",
) -> Path:
    path = tmp_path / name
    path.write_text(
        CONFIG_TEMPLATE.format(
            project_id=project_id,
            workspace_path=json.dumps(str(workspace)),
            github_repo=github_repo,
            deny_outside_workspace=str(deny_outside_workspace).lower(),
            allow_symlinks=str(allow_symlinks).lower(),
            max_changed_files=max_changed_files,
            write_enabled=str(write_enabled).lower(),
            max_file_bytes=max_file_bytes,
        ),
        encoding="utf-8",
    )
    return path


def _write_artifact(tmp_path: Path, artifact: dict, name: str = "approved.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(artifact), encoding="utf-8")
    return path


def _invoke(config: Path, artifact: Path, *extra: str):
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
            *extra,
        ],
    )


def _setup(tmp_path: Path, *, artifact: dict | None = None, **config_kwargs):
    repo = _make_repo(tmp_path)
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    config = _write_config(inputs, repo, **config_kwargs)
    artifact_path = _write_artifact(inputs, artifact if artifact else _artifact())
    return repo, config, artifact_path


# =============================================================================
# 1. Gates that must fail before anything is read or touched
# =============================================================================


def test_missing_both_action_flags_reads_nothing(tmp_path, monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("a file was read without both action flags")

    monkeypatch.setattr(Path, "read_text", boom)

    result = runner.invoke(
        app,
        [
            "l2-apply-approved-file-edit",
            "--project-config",
            str(tmp_path / "nonexistent.yaml"),
            "--approved-diff-proposal",
            str(tmp_path / "nonexistent.json"),
        ],
    )
    assert result.exit_code != 0


@pytest.mark.parametrize(
    "flags", [["--apply-approved-plan"], ["--write-approved-file"], []]
)
def test_either_action_flag_alone_reads_nothing(tmp_path, monkeypatch, flags):
    repo = _make_repo(tmp_path)
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    config = _write_config(inputs, repo)
    artifact = _write_artifact(inputs, _artifact())

    reads: list[str] = []
    original_read_text = Path.read_text

    def tracking(self, *args, **kwargs):
        reads.append(str(self))
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", tracking)

    result = runner.invoke(
        app,
        [
            "l2-apply-approved-file-edit",
            "--project-config",
            str(config),
            "--approved-diff-proposal",
            str(artifact),
            *flags,
        ],
    )

    assert result.exit_code == 1
    assert reads == []
    assert (repo / TARGET).read_bytes() == ORIGINAL_TEXT.encode("utf-8")


def test_workspace_write_disabled_touches_no_workspace(tmp_path, monkeypatch):
    repo, config, artifact = _setup(tmp_path, write_enabled=False)

    def boom(*args, **kwargs):
        raise AssertionError("a subprocess was started while write was disabled")

    monkeypatch.setattr(subprocess, "run", boom)

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "workspace_write" in result.output
    assert (repo / TARGET).read_bytes() == ORIGINAL_TEXT.encode("utf-8")


def test_absent_workspace_write_block_is_identical_to_disabled(tmp_path):
    repo = _make_repo(tmp_path)
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    config = inputs / "project.yaml"
    config.write_text(
        "project_id: %s\n"
        "display_name: Demo\n"
        "repo:\n"
        "  workspace_path: %s\n"
        "  github_repo: %s\n"
        "  branch_prefix: ai/demo\n"
        'allowed_paths: ["src/**"]\n' % (PROJECT_ID, json.dumps(str(repo)), REPO),
        encoding="utf-8",
    )
    artifact = _write_artifact(inputs, _artifact())

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert (repo / TARGET).read_bytes() == ORIGINAL_TEXT.encode("utf-8")


def test_non_windows_refuses_before_any_workspace_touch(tmp_path, monkeypatch):
    repo, config, artifact = _setup(tmp_path)

    monkeypatch.setattr(cli.sys, "platform", "linux")

    def boom(*args, **kwargs):
        raise AssertionError("a subprocess was started on an unsupported platform")

    monkeypatch.setattr(subprocess, "run", boom)

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "Windows-only" in result.output
    assert (repo / TARGET).read_bytes() == ORIGINAL_TEXT.encode("utf-8")


def test_artifact_inside_the_workspace_is_refused_before_it_is_read(
    tmp_path, monkeypatch
):
    repo = _make_repo(tmp_path)
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    config = _write_config(inputs, repo)
    inside = repo / "approved.json"
    inside.write_text(json.dumps(_artifact()), encoding="utf-8")

    original_read_text = Path.read_text

    def tracking(self, *args, **kwargs):
        assert "approved.json" not in str(self), "the in-workspace artifact was read"
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", tracking)

    result = _invoke(config, inside)

    assert result.exit_code == 1
    assert "workspace_path" in result.output


def test_identity_mismatch_is_refused(tmp_path):
    repo, config, artifact = _setup(tmp_path, github_repo="someone/else")

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "identity error" in result.output
    assert (repo / TARGET).read_bytes() == ORIGINAL_TEXT.encode("utf-8")


def test_zero_changes_is_refused(tmp_path):
    repo, config, artifact = _setup(tmp_path, artifact=_artifact(changes=[]))

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "0 changes" in result.output or "scope error" in result.output


def test_two_changes_are_refused_even_under_a_larger_cap(tmp_path):
    repo, config, artifact = _setup(
        tmp_path,
        artifact=_artifact(
            changes=[
                _change(),
                _change(SECOND_TARGET, SECOND_ORIGINAL, "TAX_RATE = 0.25\n"),
            ]
        ),
        max_changed_files=20,
    )

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "exactly one file" in result.output
    assert (repo / TARGET).read_bytes() == ORIGINAL_TEXT.encode("utf-8")
    assert (repo / SECOND_TARGET).read_bytes() == SECOND_ORIGINAL.encode("utf-8")


def test_max_changed_files_zero_permits_no_write(tmp_path):
    repo, config, artifact = _setup(tmp_path, max_changed_files=0)

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "max_changed_files" in result.output


def test_create_is_refused(tmp_path):
    repo, config, artifact = _setup(
        tmp_path,
        artifact=_artifact(
            changes=[_change(NEW_FILE, "", "def helper():\n    return 1\n", "create")]
        ),
    )

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "'create'" in result.output or "create" in result.output
    assert not (repo / NEW_FILE).exists()


def test_protected_path_is_refused_and_no_flag_permits_it(tmp_path):
    repo = _make_repo(
        tmp_path,
        files={
            TARGET: ORIGINAL_TEXT,
            PROTECTED_TARGET: ORIGINAL_TEXT,
        },
    )
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    config = _write_config(inputs, repo)
    artifact = _write_artifact(
        inputs, _artifact(changes=[_change(PROTECTED_TARGET)])
    )

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "PROTECTED" in result.output
    assert (repo / PROTECTED_TARGET).read_bytes() == ORIGINAL_TEXT.encode("utf-8")

    help_output = runner.invoke(
        app, ["l2-apply-approved-file-edit", "--help"]
    ).output
    assert "allow-protected" not in help_output


def test_forbidden_path_is_refused(tmp_path):
    repo = _make_repo(
        tmp_path, files={TARGET: ORIGINAL_TEXT, FORBIDDEN_TARGET: ORIGINAL_TEXT}
    )
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    config = _write_config(inputs, repo)
    artifact = _write_artifact(inputs, _artifact(changes=[_change(FORBIDDEN_TARGET)]))

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "policy error" in result.output


def test_unlisted_path_is_refused(tmp_path):
    repo = _make_repo(
        tmp_path, files={TARGET: ORIGINAL_TEXT, UNLISTED_TARGET: ORIGINAL_TEXT}
    )
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    config = _write_config(inputs, repo)
    artifact = _write_artifact(inputs, _artifact(changes=[_change(UNLISTED_TARGET)]))

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "policy error" in result.output


def test_allow_symlinks_true_is_refused(tmp_path):
    repo, config, artifact = _setup(tmp_path, allow_symlinks=True)

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "allow_symlinks" in result.output
    assert (repo / TARGET).read_bytes() == ORIGINAL_TEXT.encode("utf-8")


def test_deny_outside_workspace_false_is_refused(tmp_path):
    repo, config, artifact = _setup(tmp_path, deny_outside_workspace=False)

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "deny_outside_workspace" in result.output


def test_a_malformed_artifact_is_refused_without_echoing_it(tmp_path):
    repo = _make_repo(tmp_path)
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    config = _write_config(inputs, repo)
    artifact = inputs / "approved.json"
    artifact.write_text("SENTINEL_NOT_JSON_AT_ALL", encoding="utf-8")

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "SENTINEL_NOT_JSON_AT_ALL" not in result.output


def test_a_v1_artifact_is_rejected_not_upgraded(tmp_path):
    artifact = _artifact()
    artifact["schema_version"] = "approved-diff-proposal.v1"
    repo, config, artifact_path = _setup(tmp_path, artifact=artifact)

    result = _invoke(config, artifact_path)

    assert result.exit_code == 1
    assert (repo / TARGET).read_bytes() == ORIGINAL_TEXT.encode("utf-8")


# =============================================================================
# 2. The Git contract
# =============================================================================


@git_required
@windows_only
def test_a_clean_repository_passes_preflight_and_writes(tmp_path):
    repo, config, artifact = _setup(tmp_path)

    result = _invoke(config, artifact)

    assert result.exit_code == 0, result.output
    assert (repo / TARGET).read_bytes() == PROPOSED_TEXT.encode("utf-8")


@git_required
def test_an_unstaged_modification_anywhere_refuses(tmp_path):
    repo, config, artifact = _setup(tmp_path)
    (repo / SECOND_TARGET).write_bytes(b"TAX_RATE = 0.99\n")

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "not clean" in result.output
    assert (repo / TARGET).read_bytes() == ORIGINAL_TEXT.encode("utf-8")


@git_required
def test_a_staged_modification_refuses(tmp_path):
    repo, config, artifact = _setup(tmp_path)
    (repo / SECOND_TARGET).write_bytes(b"TAX_RATE = 0.99\n")
    _run_git(repo, "add", SECOND_TARGET)

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "not clean" in result.output


@git_required
def test_an_untracked_file_refuses(tmp_path):
    repo, config, artifact = _setup(tmp_path)
    (repo / "stray.txt").write_bytes(b"x\n")

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "not clean" in result.output


@git_required
def test_a_deleted_tracked_file_refuses(tmp_path):
    repo, config, artifact = _setup(tmp_path)
    (repo / SECOND_TARGET).unlink()

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "not clean" in result.output


@git_required
def test_a_staged_rename_refuses(tmp_path):
    repo, config, artifact = _setup(tmp_path)
    _run_git(repo, "mv", SECOND_TARGET, "src/billing/tax_renamed.py")

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "not clean" in result.output


@git_required
def test_assume_unchanged_anywhere_refuses(tmp_path):
    repo, config, artifact = _setup(tmp_path)
    _run_git(repo, "update-index", "--assume-unchanged", SECOND_TARGET)

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "assume-unchanged" in result.output
    assert (repo / TARGET).read_bytes() == ORIGINAL_TEXT.encode("utf-8")


@git_required
def test_skip_worktree_anywhere_refuses(tmp_path):
    repo, config, artifact = _setup(tmp_path)
    _run_git(repo, "update-index", "--skip-worktree", SECOND_TARGET)

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "skip-worktree" in result.output


@git_required
def test_an_unmerged_conflict_state_refuses(tmp_path):
    repo, config, artifact = _setup(tmp_path)

    # Build a genuine conflict on the second file, so the target itself is
    # untouched and only the repository's state is unsupported.
    _run_git(repo, "checkout", "-q", "-b", "side")
    (repo / SECOND_TARGET).write_bytes(b"TAX_RATE = 0.3\n")
    _run_git(repo, "commit", "-q", "-am", "side")
    _run_git(repo, "checkout", "-q", "-")
    (repo / SECOND_TARGET).write_bytes(b"TAX_RATE = 0.4\n")
    _run_git(repo, "commit", "-q", "-am", "main")
    merge = subprocess.run(["git", "merge", "side"], cwd=repo, capture_output=True)
    assert merge.returncode != 0

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert (repo / TARGET).read_bytes() == ORIGINAL_TEXT.encode("utf-8")


@git_required
def test_a_gitlink_submodule_entry_refuses_the_whole_repository(tmp_path):
    repo, config, artifact = _setup(tmp_path)

    other = tmp_path / "other"
    other.mkdir()
    _run_git(other, "init", "-q")
    for key, value in (
        ("user.name", "AIDO Test"),
        ("user.email", "aido-test@example.invalid"),
        ("commit.gpgsign", "false"),
    ):
        _run_git(other, "config", key, value)
    (other / "f.txt").write_bytes(b"x\n")
    _run_git(other, "add", "-A")
    _run_git(other, "commit", "-q", "-m", "init")

    added = subprocess.run(
        ["git", "-c", "protocol.file.allow=always", "submodule", "add", "-q",
         str(other).replace("\\", "/"), "vendor/other"],
        cwd=repo,
        capture_output=True,
    )
    if added.returncode != 0:
        pytest.skip("this git refuses local submodule addition")
    _run_git(repo, "commit", "-q", "-m", "add submodule")

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "gitlink" in result.output or "submodule" in result.output
    assert (repo / TARGET).read_bytes() == ORIGINAL_TEXT.encode("utf-8")


@git_required
def test_a_workspace_that_is_not_the_git_top_level_refuses(tmp_path):
    """The configured workspace must be exactly the Git worktree root.

    Here the repository root is one level above the configured workspace, so the
    target path, the path policy and the canonical guard all still line up — only
    the Git top level disagrees, which is the thing under test.
    """
    repo = _make_repo(tmp_path, files={f"sub/{TARGET}": ORIGINAL_TEXT})
    workspace = repo / "sub"
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    config = _write_config(inputs, workspace)
    artifact = _write_artifact(inputs, _artifact())

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "top level" in result.output
    assert (workspace / TARGET).read_bytes() == ORIGINAL_TEXT.encode("utf-8")


@git_required
def test_a_repository_with_no_head_refuses(tmp_path):
    repo = tmp_path / "workspace"
    repo.mkdir()
    _run_git(repo, "init", "-q")
    (repo / "src" / "billing").mkdir(parents=True)
    (repo / TARGET).write_bytes(ORIGINAL_TEXT.encode("utf-8"))
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    config = _write_config(inputs, repo)
    artifact = _write_artifact(inputs, _artifact())

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert (repo / TARGET).read_bytes() == ORIGINAL_TEXT.encode("utf-8")


@git_required
def test_a_non_git_workspace_refuses(tmp_path):
    workspace = tmp_path / "workspace"
    (workspace / "src" / "billing").mkdir(parents=True)
    (workspace / TARGET).write_bytes(ORIGINAL_TEXT.encode("utf-8"))
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    config = _write_config(inputs, workspace)
    artifact = _write_artifact(inputs, _artifact())

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert (workspace / TARGET).read_bytes() == ORIGINAL_TEXT.encode("utf-8")


@git_required
def test_an_untracked_target_refuses(tmp_path):
    repo = _make_repo(tmp_path, files={SECOND_TARGET: SECOND_ORIGINAL})
    (repo / "src" / "billing").mkdir(parents=True, exist_ok=True)
    (repo / TARGET).write_bytes(ORIGINAL_TEXT.encode("utf-8"))
    # Ignore the target so the repository stays clean while the file is untracked.
    (repo / ".gitignore").write_bytes(b"src/billing/totals.py\n")
    _run_git(repo, "add", ".gitignore")
    _run_git(repo, "commit", "-q", "-m", "ignore target")

    inputs = tmp_path / "inputs"
    inputs.mkdir()
    config = _write_config(inputs, repo)
    artifact = _write_artifact(inputs, _artifact())

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "not tracked" in result.output
    assert (repo / TARGET).read_bytes() == ORIGINAL_TEXT.encode("utf-8")


# =============================================================================
# 3. The target's filesystem and content state
# =============================================================================


@git_required
def test_a_directory_target_refuses(tmp_path):
    repo = _make_repo(
        tmp_path,
        files={SECOND_TARGET: SECOND_ORIGINAL, f"{TARGET}/inner.py": "x = 1\n"},
    )
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    config = _write_config(inputs, repo)
    artifact = _write_artifact(inputs, _artifact())

    result = _invoke(config, artifact)

    assert result.exit_code == 1


@git_required
@windows_only
def test_a_hard_linked_target_refuses(tmp_path):
    repo, config, artifact = _setup(tmp_path)
    link = tmp_path / "outside_link.py"
    try:
        os.link(repo / TARGET, link)
    except (OSError, NotImplementedError, AttributeError):
        pytest.skip("hard links are unavailable on this filesystem")

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "hard links" in result.output
    assert (repo / TARGET).read_bytes() == ORIGINAL_TEXT.encode("utf-8")
    assert link.read_bytes() == ORIGINAL_TEXT.encode("utf-8")


@git_required
@windows_only
def test_a_read_only_target_refuses_as_an_unsupported_attribute(tmp_path):
    repo, config, artifact = _setup(tmp_path)
    import stat as stat_module

    target = repo / TARGET
    target.chmod(target.stat().st_mode & ~stat_module.S_IWRITE)
    try:
        result = _invoke(config, artifact)
        assert result.exit_code == 1
        assert "attributes" in result.output
        assert target.read_bytes() == ORIGINAL_TEXT.encode("utf-8")
    finally:
        target.chmod(target.stat().st_mode | stat_module.S_IWRITE)


@git_required
def test_an_oversized_target_refuses(tmp_path):
    repo, config, artifact = _setup(tmp_path, max_file_bytes=10)

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "max_file_bytes" in result.output
    assert (repo / TARGET).read_bytes() == ORIGINAL_TEXT.encode("utf-8")


@git_required
def test_a_non_utf8_target_refuses(tmp_path):
    repo = _make_repo(tmp_path)
    (repo / TARGET).write_bytes(b"\xff\xfe not utf-8\n")
    _run_git(repo, "add", "-A")
    _run_git(repo, "commit", "-q", "-m", "binary-ish")

    inputs = tmp_path / "inputs"
    inputs.mkdir()
    config = _write_config(inputs, repo)
    artifact = _write_artifact(
        inputs,
        _artifact(
            changes=[
                _change(
                    TARGET,
                    ORIGINAL_TEXT,
                    PROPOSED_TEXT,
                    pre_image_sha256=hashlib.sha256(
                        b"\xff\xfe not utf-8\n"
                    ).hexdigest(),
                )
            ]
        ),
    )

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "UTF-8" in result.output


@git_required
def test_a_nul_bearing_target_refuses(tmp_path):
    content = b"alpha\x00beta\n"
    repo = _make_repo(tmp_path)
    (repo / TARGET).write_bytes(content)
    _run_git(repo, "add", "-A")
    _run_git(repo, "commit", "-q", "-m", "nul")

    inputs = tmp_path / "inputs"
    inputs.mkdir()
    config = _write_config(inputs, repo)
    artifact = _write_artifact(
        inputs,
        _artifact(
            changes=[
                _change(
                    TARGET,
                    ORIGINAL_TEXT,
                    PROPOSED_TEXT,
                    pre_image_sha256=hashlib.sha256(content).hexdigest(),
                )
            ]
        ),
    )

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "NUL" in result.output


@git_required
def test_mixed_line_endings_refuse(tmp_path):
    content = "alpha\r\nbeta\ngamma\r\n"
    repo = _make_repo(tmp_path)
    (repo / TARGET).write_bytes(content.encode("utf-8"))
    _run_git(repo, "add", "-A")
    _run_git(repo, "commit", "-q", "-m", "mixed")

    inputs = tmp_path / "inputs"
    inputs.mkdir()
    config = _write_config(inputs, repo)
    artifact = _write_artifact(
        inputs, _artifact(changes=[_change(TARGET, content, "alpha\r\nBETA\r\n")])
    )

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "mixes CRLF and LF" in result.output


@git_required
def test_a_missing_terminal_newline_refuses(tmp_path):
    content = "alpha\nbeta"
    repo = _make_repo(tmp_path)
    (repo / TARGET).write_bytes(content.encode("utf-8"))
    _run_git(repo, "add", "-A")
    _run_git(repo, "commit", "-q", "-m", "no terminal newline")

    inputs = tmp_path / "inputs"
    inputs.mkdir()
    config = _write_config(inputs, repo)
    artifact = _write_artifact(
        inputs, _artifact(changes=[_change(TARGET, content, "alpha\nBETA")])
    )

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "terminal newline" in result.output


@git_required
def test_a_bare_carriage_return_file_refuses(tmp_path):
    content = "alpha\rbeta\r"
    repo = _make_repo(tmp_path)
    (repo / TARGET).write_bytes(content.encode("utf-8"))
    _run_git(repo, "add", "-A")
    _run_git(repo, "commit", "-q", "-m", "cr only")

    inputs = tmp_path / "inputs"
    inputs.mkdir()
    config = _write_config(inputs, repo)
    artifact = _write_artifact(
        inputs, _artifact(changes=[_change(TARGET, content, "alpha\rBETA\r")])
    )

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "carriage return" in result.output


# =============================================================================
# 4. The approved transformation
# =============================================================================


@git_required
def test_a_pre_image_digest_mismatch_refuses_before_any_write(tmp_path):
    repo = _make_repo(tmp_path)
    drifted = ORIGINAL_TEXT.replace("def total(items):", "def total(items, /):")
    (repo / TARGET).write_bytes(drifted.encode("utf-8"))
    _run_git(repo, "add", "-A")
    _run_git(repo, "commit", "-q", "-m", "drift")

    inputs = tmp_path / "inputs"
    inputs.mkdir()
    config = _write_config(inputs, repo)
    artifact = _write_artifact(inputs, _artifact())

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "pre-image error" in result.output
    assert "No attempt was made to apply the diff anyway" in result.output
    assert (repo / TARGET).read_bytes() == drifted.encode("utf-8")


@git_required
def test_a_post_image_digest_mismatch_refuses_before_any_write(tmp_path):
    change = _change()
    change["post_image_sha256"] = hashlib.sha256(b"something else entirely").hexdigest()
    repo, config, artifact = _setup(tmp_path, artifact=_artifact(changes=[change]))

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "post-image error" in result.output
    assert (repo / TARGET).read_bytes() == ORIGINAL_TEXT.encode("utf-8")


@git_required
def test_a_context_mismatch_in_the_diff_refuses(tmp_path):
    change = _change()
    change["unified_diff"] = change["unified_diff"].replace(
        " def format_total(amount):", " def format_total(amount, currency):"
    )
    repo, config, artifact = _setup(tmp_path, artifact=_artifact(changes=[change]))

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "apply error" in result.output
    assert (repo / TARGET).read_bytes() == ORIGINAL_TEXT.encode("utf-8")


@git_required
def test_a_malformed_hunk_header_refuses(tmp_path):
    change = _change()
    lines = change["unified_diff"].split("\n")
    for index, line in enumerate(lines):
        if line.startswith("@@"):
            lines[index] = "@@ -99,4 +1,4 @@"
            break
    change["unified_diff"] = "\n".join(lines)
    repo, config, artifact = _setup(tmp_path, artifact=_artifact(changes=[change]))

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "apply error" in result.output


@git_required
def test_no_fuzzy_application_when_the_file_shifted(tmp_path):
    """The diff would apply two lines lower with fuzz. It is refused instead."""
    shifted = "# header added by somebody\n# second header\n" + ORIGINAL_TEXT
    repo = _make_repo(tmp_path)
    (repo / TARGET).write_bytes(shifted.encode("utf-8"))
    _run_git(repo, "add", "-A")
    _run_git(repo, "commit", "-q", "-m", "shift")

    inputs = tmp_path / "inputs"
    inputs.mkdir()
    config = _write_config(inputs, repo)
    # The approval names the shifted pre-image, so only the diff is stale.
    change = _change()
    change["pre_image_sha256"] = _sha(shifted)
    change["post_image_sha256"] = _sha(
        shifted.replace("    return str(amount)", '    return f"{amount:.2f}"')
    )
    artifact = _write_artifact(inputs, _artifact(changes=[change]))

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "apply error" in result.output
    assert (repo / TARGET).read_bytes() == shifted.encode("utf-8")


# =============================================================================
# 5. The write itself
# =============================================================================


@git_required
@windows_only
def test_the_exact_approved_transformation_is_performed(tmp_path):
    repo, config, artifact = _setup(tmp_path)

    result = _invoke(config, artifact)

    assert result.exit_code == 0, result.output
    written = (repo / TARGET).read_bytes()
    assert written == PROPOSED_TEXT.encode("utf-8")
    assert hashlib.sha256(written).hexdigest() == _sha(PROPOSED_TEXT)
    # Nothing else changed.
    assert (repo / SECOND_TARGET).read_bytes() == SECOND_ORIGINAL.encode("utf-8")


@git_required
@windows_only
def test_the_report_is_the_only_thing_on_stdout_and_validates(tmp_path):
    repo, config, artifact = _setup(tmp_path)

    result = _invoke(config, artifact)

    assert result.exit_code == 0, result.output
    report = WorkspaceWriteReport.model_validate_json(result.stdout)

    assert report.outcome == "written-and-verified"
    assert report.files_edited == 1
    assert report.target.path == TARGET
    assert report.target.change_type == "modify"
    assert report.target.line_ending == "lf"
    assert report.checks.git_baseline_clean is True
    assert report.checks.target_tracked is True
    assert report.checks.pre_image_verified is True
    assert report.checks.post_image_verified_on_disk is True
    assert report.checks.only_approved_target_dirty is True
    assert report.exclusions.project_verification_commands_run is False
    assert report.exclusions.model_called is False
    assert report.exclusions.network_called is False
    assert report.exclusions.committed is False
    assert report.exclusions.pushed is False
    assert report.exclusions.pr_created is False
    assert report.exclusions.branch_created is False
    assert report.git.dirty_paths_after_write == [TARGET]
    assert "human review" in report.next_step


@git_required
@windows_only
def test_only_the_approved_target_is_dirty_and_nothing_is_committed(tmp_path):
    repo, config, artifact = _setup(tmp_path)
    before = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True
    ).stdout

    result = _invoke(config, artifact)
    assert result.exit_code == 0, result.output

    status = subprocess.run(
        ["git", "status", "--porcelain=v1"], cwd=repo, check=True, capture_output=True
    ).stdout.decode()
    assert status.strip() == f"M {TARGET}".replace("M ", " M ").strip()

    after = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True
    ).stdout
    assert after == before

    branches = subprocess.run(
        ["git", "branch", "--format=%(refname:short)"],
        cwd=repo,
        check=True,
        capture_output=True,
    ).stdout.decode().split()
    assert len(branches) == 1

    log = subprocess.run(
        ["git", "log", "--oneline"], cwd=repo, check=True, capture_output=True
    ).stdout.decode()
    assert log.count("\n") == 1


@git_required
@windows_only
def test_no_temp_sibling_is_left_behind(tmp_path):
    repo, config, artifact = _setup(tmp_path)

    assert _invoke(config, artifact).exit_code == 0

    leftovers = list((repo / "src" / "billing").glob(".aido-write-*"))
    assert leftovers == []


@git_required
@windows_only
def test_crlf_line_endings_are_preserved(tmp_path):
    original = "alpha\r\nbeta\r\ngamma\r\n"
    proposed = "alpha\r\nBETA\r\ngamma\r\n"
    repo = _make_repo(tmp_path, files={TARGET: original, SECOND_TARGET: SECOND_ORIGINAL})
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    config = _write_config(inputs, repo)
    artifact = _write_artifact(
        inputs, _artifact(changes=[_change(TARGET, original, proposed)])
    )

    result = _invoke(config, artifact)

    assert result.exit_code == 0, result.output
    assert (repo / TARGET).read_bytes() == proposed.encode("utf-8")
    report = WorkspaceWriteReport.model_validate_json(result.stdout)
    assert report.target.line_ending == "crlf"


@git_required
@windows_only
def test_the_report_leaks_no_workspace_path_absolute_path_or_approval_text(tmp_path):
    repo, config, artifact = _setup(tmp_path)

    result = _invoke(config, artifact)
    assert result.exit_code == 0, result.output

    for absent in (
        str(repo),
        str(repo).replace("\\", "\\\\"),
        REQUIRED_DIFF_EDIT_APPROVAL_TEXT,
        "SENTINEL_VERIFICATION_NEVER_RUN",
        _sha(ORIGINAL_TEXT),
        _sha(PROPOSED_TEXT),
    ):
        assert absent not in result.stdout, absent


@git_required
@windows_only
def test_the_reported_git_diff_is_bounded_to_the_approved_path(tmp_path):
    repo, config, artifact = _setup(tmp_path)

    result = _invoke(config, artifact)
    assert result.exit_code == 0, result.output

    report = WorkspaceWriteReport.model_validate_json(result.stdout)
    assert report.git.target_diff_available is True
    assert TARGET in report.git.target_diff
    assert "tax.py" not in report.git.target_diff


@git_required
@windows_only
def test_a_second_invocation_refuses_because_the_tree_is_no_longer_clean(tmp_path):
    repo, config, artifact = _setup(tmp_path)

    assert _invoke(config, artifact).exit_code == 0

    second = _invoke(config, artifact)
    assert second.exit_code == 1
    assert "not clean" in second.output
    assert (repo / TARGET).read_bytes() == PROPOSED_TEXT.encode("utf-8")


# =============================================================================
# 6. Failure semantics: refused vs. indeterminate
# =============================================================================


@git_required
@windows_only
def test_a_race_detected_at_the_final_revalidation_refuses(tmp_path, monkeypatch):
    """A concurrent edit between the first read and the last one fails closed."""
    repo, config, artifact = _setup(tmp_path)

    original_reader = writer_module._read_bounded_file_bytes
    calls = {"count": 0}

    def racing(path, *, limit):
        calls["count"] += 1
        if calls["count"] == 2:
            # Simulate another process writing the file between the first read
            # and the final pre-write re-read.
            Path(path).write_bytes(b"changed by somebody else\n")
        return original_reader(path, limit=limit)

    monkeypatch.setattr(writer_module, "_read_bounded_file_bytes", racing)

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "pre-image error" in result.output
    assert (repo / TARGET).read_bytes() == b"changed by somebody else\n"


@git_required
@windows_only
def test_a_post_write_verification_failure_is_indeterminate_not_success(
    tmp_path, monkeypatch
):
    """A write happened; the postcondition did not hold. Never reported as clean."""
    repo, config, artifact = _setup(tmp_path)

    from ai_dev_orchestrator.file_editing import windows_write

    real_replace = windows_write.replace_file_with_bytes

    def replace_then_disturb(**kwargs):
        real_replace(**kwargs)
        # Something else appears in the tree straight after the replacement, so
        # "exactly the approved path is dirty" is no longer provable.
        (repo / "unexpected_stray.txt").write_bytes(b"appeared\n")

    monkeypatch.setattr(windows_write, "replace_file_with_bytes", replace_then_disturb)

    result = _invoke(config, artifact)

    assert result.exit_code == 3
    assert "write-attempted-state-indeterminate" in result.output
    assert "NOT a claim that nothing changed" in result.output
    assert "HUMAN REPOSITORY INSPECTION IS REQUIRED" in result.output
    assert result.stdout == ""
    # Nothing was retried and nothing was rolled back: the write is still there.
    assert (repo / TARGET).read_bytes() == PROPOSED_TEXT.encode("utf-8")


@git_required
@windows_only
def test_the_indeterminate_path_runs_no_git_restore(tmp_path, monkeypatch):
    repo, config, artifact = _setup(tmp_path)

    from ai_dev_orchestrator.file_editing import windows_write
    from ai_dev_orchestrator.workspace import git_adapter

    real_replace = windows_write.replace_file_with_bytes

    def replace_then_disturb(**kwargs):
        real_replace(**kwargs)
        (repo / "unexpected_stray.txt").write_bytes(b"appeared\n")

    monkeypatch.setattr(windows_write, "replace_file_with_bytes", replace_then_disturb)

    seen: list[tuple] = []
    real_popen = subprocess.Popen

    def tracking(argv, **kwargs):
        seen.append(tuple(argv))
        return real_popen(argv, **kwargs)

    monkeypatch.setattr(git_adapter.subprocess, "Popen", tracking)

    assert _invoke(config, artifact).exit_code == 3

    for argv in seen:
        assert os.path.isabs(argv[0])
        for forbidden in ("restore", "checkout", "reset", "clean", "stash"):
            assert forbidden not in argv, argv


def test_refused_and_indeterminate_are_distinct_exit_codes():
    assert cli._WRITE_EXIT_REFUSED == 1
    assert cli._WRITE_EXIT_INDETERMINATE == 3
    assert cli._WRITE_EXIT_REFUSED != cli._WRITE_EXIT_INDETERMINATE


@git_required
def test_every_pre_write_refusal_prints_nothing_on_stdout(tmp_path):
    repo, config, artifact = _setup(tmp_path, github_repo="someone/else")

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert result.stdout == ""


# =============================================================================
# 7. Capabilities that do not exist
# =============================================================================


@git_required
@windows_only
def test_no_project_verification_command_is_ever_run(tmp_path, monkeypatch):
    repo, config, artifact = _setup(tmp_path)

    seen: list[tuple] = []
    real_popen = subprocess.Popen

    def tracking(argv, **kwargs):
        seen.append(tuple(argv))
        return real_popen(argv, **kwargs)

    from ai_dev_orchestrator.workspace import git_adapter

    monkeypatch.setattr(git_adapter.subprocess, "Popen", tracking)

    assert _invoke(config, artifact).exit_code == 0

    assert seen, "the writer should have inspected the repository with git"
    for argv in seen:
        assert os.path.isabs(argv[0])
        assert os.path.basename(argv[0]).lower().startswith("git")
        joined = " ".join(argv)
        for forbidden in ("pytest", "npm", "make", "SENTINEL_VERIFICATION_NEVER_RUN"):
            assert forbidden not in joined


@git_required
@windows_only
def test_only_the_fixed_git_argv_shapes_are_invoked(tmp_path, monkeypatch):
    from ai_dev_orchestrator.workspace import git_adapter

    repo, config, artifact = _setup(tmp_path)

    seen: list[tuple] = []
    real_popen = subprocess.Popen

    def tracking(argv, **kwargs):
        assert kwargs.get("shell") is False
        seen.append(tuple(argv))
        return real_popen(argv, **kwargs)

    monkeypatch.setattr(git_adapter.subprocess, "Popen", tracking)

    assert _invoke(config, artifact).exit_code == 0

    resolved = git_adapter.resolve_git_executable(workspace_root="")
    allowed = set()
    for operation, template in git_adapter.FIXED_GIT_OPERATIONS.items():
        path = TARGET if None in template else None
        allowed.add(
            git_adapter.build_git_argv(
                operation, git_executable=resolved, repo_relative_path=path
            )
        )
    assert set(seen) <= allowed
    # Phase 5F2C-FU1: one absolute executable, pinned for the whole run.
    assert {argv[0] for argv in seen} == {resolved}


@git_required
def test_no_socket_is_opened(tmp_path, monkeypatch):
    repo, config, artifact = _setup(tmp_path)

    def boom(*args, **kwargs):
        raise AssertionError("the writer opened a socket")

    monkeypatch.setattr(socket, "socket", boom)
    monkeypatch.setattr(socket, "create_connection", boom)

    result = _invoke(config, artifact)
    assert result.exit_code in (0, 1)


def test_the_writer_module_imports_no_client_no_socket_and_no_shell():
    source = Path(writer_module.__file__).read_text(encoding="utf-8")
    for absent in (
        "import socket",
        "import httpx",
        "import requests",
        "shell=True",
        "os.system",
        "LLMClient",
        "GitHubClient",
        "load_llm_client_config_from_env",
    ):
        assert absent not in source, absent

    # The plan's verification prose is never *read* as anything. It is named in
    # the module docstring only to say it is unreachable, so the assertion is
    # about attribute access rather than the word appearing.
    assert ".required_verification" not in source
    assert "required_verification]" not in source


def test_the_writer_never_creates_deletes_or_renames(tmp_path):
    """No create/delete/rename code path exists, and the change model can't ask."""
    source = Path(writer_module.__file__).read_text(encoding="utf-8")
    for absent in ("os.remove(", "os.rmdir(", "shutil.rmtree", "os.rename(", "os.makedirs", "mkdir("):
        assert absent not in source, absent


@git_required
@windows_only
def test_no_environment_credential_reaches_the_git_child(tmp_path, monkeypatch):
    from ai_dev_orchestrator.workspace import git_adapter

    repo, config, artifact = _setup(tmp_path)
    monkeypatch.setenv("AIDO_LITELLM_API_KEY", "SENTINEL_SECRET_KEY")
    monkeypatch.setenv("GITHUB_TOKEN", "SENTINEL_GITHUB_TOKEN")

    environments: list[dict] = []
    real_popen = subprocess.Popen

    def tracking(argv, **kwargs):
        environments.append(kwargs.get("env") or {})
        return real_popen(argv, **kwargs)

    monkeypatch.setattr(git_adapter.subprocess, "Popen", tracking)

    assert _invoke(config, artifact).exit_code == 0

    assert environments
    for environment in environments:
        joined = " ".join(f"{k}={v}" for k, v in environment.items())
        assert "SENTINEL_SECRET_KEY" not in joined
        assert "SENTINEL_GITHUB_TOKEN" not in joined


def test_no_other_command_gained_a_write_path():
    for command in (
        "l2-dry-run",
        "l2-inspect-workspace",
        "l2-read-workspace-files",
        "generate-patch-proposal",
        "generate-diff-proposal",
        "l2-preview-file-edits",
    ):
        output = runner.invoke(app, [command, "--help"]).output
        assert "--write-approved-file" not in output
