"""Phase 5F1 tests: the ``l2-preview-file-edits`` command.

The command reads two local files — a project config and a human-approved Phase
5F0 diff proposal artifact — validates the artifact against the config and the
lexical Phase 1 write policy, and prints a **dry-run preview** of what a future
file-editing phase would be allowed to attempt.

It describes a hypothetical without touching the thing it describes, so these
tests assert absence far more than presence: no target project workspace is
read, listed, stat'd, globbed, walked, resolved, or canonicalized; no file is
opened beyond the two named on the command line; no path the approved diff names
is opened or checked for existence; no diff is applied; no apply-cleanliness is
checked; no file is edited; no command is executed; no environment variable is
read; no socket is opened; no model is called; nothing is fetched from or
written to GitHub; no branch, commit, push or PR happens; no artifact file is
written; and no approval is stamped.

Every input here is literal JSON written into pytest's own ``tmp_path``. The
configured ``workspace_path`` points at a directory that is normally never
created — the one rejection test that creates one creates it under ``tmp_path``
and never reads anything inside it.
"""

from __future__ import annotations

import builtins
import copy
import json
import os
import socket
import subprocess

import pytest
import typer
from typer.testing import CliRunner

from ai_dev_orchestrator import cli

# Imported at module scope so the lazy imports inside the command are already
# cached in sys.modules: the no-IO tests below replace os.stat and friends, and
# the import machinery would otherwise trip over them.
from ai_dev_orchestrator import config_loader as _config_loader  # noqa: F401
from ai_dev_orchestrator.cli import app
from ai_dev_orchestrator.diff_proposal import (
    DIFF_PROPOSAL_MODE,
    DIFF_PROPOSAL_SCHEMA_VERSION,
)
from ai_dev_orchestrator.file_editing import (
    APPROVED_DIFF_PROPOSAL_MODE,
    APPROVED_DIFF_PROPOSAL_SCHEMA_VERSION,
    FILE_EDIT_PREVIEW_MODE,
    FILE_EDIT_PREVIEW_SCHEMA_VERSION,
    REQUIRED_DIFF_EDIT_APPROVAL_TEXT,
    FileEditPreviewReport,
)
from ai_dev_orchestrator.handoff import REQUIRED_APPROVAL_TEXT

runner = CliRunner()

PROJECT_ID = "demo_project"
REPO = "demo/widgets"
ISSUE_NUMBER = 42
TITLE = "Add currency formatting helper"
APPROVER = "operator@example.invalid"
APPROVED_AT = "2026-01-04T06:00:00+00:00"

# Distinctive markers, so a test can prove what did and did not reach stdout.
SUMMARY_MARKER = "SENTINEL_PLAN_SUMMARY_PROSE"
VERIFICATION_MARKER = "SENTINEL_VERIFICATION_TEXT"
SOURCE_MARKER = "SENTINEL_SOURCE_LINE_NEVER_PREVIEWED"

# Path-shaped strings. Nothing below is ever opened, stat'd, listed, globbed,
# walked, or resolved: they are compared and copied as strings only.
PLAN_FILE_A = "src/billing/sentinel_never_opened_a.py"
PLAN_FILE_NEW = "tests/sentinel_never_opened_new.py"
PLAN_PROTECTED = "src/billing/protected_sentinel.py"
PLAN_UNLISTED = "docs/sentinel_never_opened.md"
PLAN_POLICY_FORBIDDEN = "secrets/sentinel_never_opened.env"
PLAN_OUT_OF_SCOPE = "external_auth/sentinel_never_opened.py"

CONFIG_TEMPLATE = """\
project_id: {project_id}
display_name: Demo Project
repo:
  workspace_path: {workspace_path}
  github_repo: {github_repo}
  default_base_branch: main
  branch_prefix: ai/demo
workspace_policy:
  deny_outside_workspace: true
  allow_symlinks: false
  max_changed_files: {max_changed_files}
allowed_paths:
  - "src/**"
  - "tests/**"
protected_paths:
  - "src/billing/protected_*.py"
forbidden_paths:
  - ".git/**"
  - "secrets/**"
"""

VALID_PLAN: dict = {
    "issue_number": ISSUE_NUMBER,
    "repo": REPO,
    "title": TITLE,
    "summary": f"Format invoice totals through one shared helper. {SUMMARY_MARKER}",
    "scope_summary": "Only the billing formatting helper and its tests.",
    "non_goals": ["No changes to the payment gateway client."],
    "proposed_steps": ["Describe a single shared helper for a human to write."],
    # Deliberately wider than the project's path rules allow: the plan's list and
    # the project's path policy are independent, and the preview applies both.
    "files_likely_to_change": [
        PLAN_FILE_A,
        PLAN_FILE_NEW,
        PLAN_PROTECTED,
        PLAN_UNLISTED,
        PLAN_POLICY_FORBIDDEN,
    ],
    "files_forbidden_or_out_of_scope": [PLAN_OUT_OF_SCOPE],
    "required_verification": [f"pytest -q {VERIFICATION_MARKER}"],
    "risks": ["Rounding differences on reissued invoices."],
    "open_questions": ["Which locale should totals use?"],
    "automation_level": "L1",
    "requires_human_approval": True,
}

VALID_PLAN_PROVENANCE: dict = {
    "engine": "real-model",
    "operation": "l1-plan",
    "real_call": True,
    "model": "fake-planner-model",
    "endpoint_host": "fake-litellm.invalid:8000",
    "generated_at": "2026-01-02T03:04:05+00:00",
    "project_id": PROJECT_ID,
    "repo": REPO,
    "issue_number": ISSUE_NUMBER,
    "title": TITLE,
}

VALID_PLAN_APPROVAL: dict = {
    "approved_by": APPROVER,
    "approved_at": "2026-01-02T04:00:00+00:00",
    "approval_text": REQUIRED_APPROVAL_TEXT,
    "source": "manual",
}

VALID_APPROVED_PLAN: dict = {
    "approval": copy.deepcopy(VALID_PLAN_APPROVAL),
    "plan_provenance": copy.deepcopy(VALID_PLAN_PROVENANCE),
    "plan": copy.deepcopy(VALID_PLAN),
    "project_id": PROJECT_ID,
    "repo": REPO,
    "issue_number": ISSUE_NUMBER,
}

VALID_DIFF_PROVENANCE: dict = {
    "engine": "deterministic",
    "operation": "diff-proposal",
    "real_call": False,
    "model": None,
    "generated_at": "2026-01-03T05:06:07+00:00",
    "project_id": PROJECT_ID,
    "repo": REPO,
    "issue_number": ISSUE_NUMBER,
    "title": TITLE,
}

VALID_EDIT_APPROVAL: dict = {
    "approved_by": APPROVER,
    "approved_at": APPROVED_AT,
    "approval_text": REQUIRED_DIFF_EDIT_APPROVAL_TEXT,
    "source": "manual",
}

NEXT_AUTHORIZATION = (
    "A file-editing phase must be explicitly authorized before anything writes "
    "these diffs."
)


def _modify_diff(path: str) -> str:
    return (
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
        "@@ -1,4 +1,4 @@\n"
        f" def format_total(amount):  # {SOURCE_MARKER}\n"
        "-    return str(amount)\n"
        '+    return f"{amount:.2f}"\n'
        " \n"
    )


def _create_diff(path: str) -> str:
    return (
        "--- /dev/null\n"
        f"+++ b/{path}\n"
        "@@ -0,0 +1,2 @@\n"
        "+def test_format_total():\n"
        '+    assert format_total(1) == "1.00"\n'
    )


# Phase 5F2C image identities. These fixtures exercise artifact *shape*, so
# the digests only have to be well-formed lowercase 64-hex values; the writer
# is what compares them against real bytes.
PRE_IMAGE_SHA256 = "3f79bb7b435b05321651daefd374cdc681dc06faa65e374e38337b88ca046dea"
POST_IMAGE_SHA256 = "2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae"


def _change(path: str = PLAN_FILE_A, change_type: str = "modify", **overrides) -> dict:
    diff = _create_diff(path) if change_type == "create" else _modify_diff(path)
    change = {
        "path": path,
        "change_type": change_type,
        "unified_diff": diff,
        # Phase 5F2C: diff-proposal.v2 binds both ends of the transformation.
        # A create has no original, so its pre-image digest is null.
        "pre_image_sha256": None if change_type == "create" else PRE_IMAGE_SHA256,
        "post_image_sha256": POST_IMAGE_SHA256,
        "rationale": "Round invoice totals to two decimal places.",
        "risks": ["Reissued invoices may differ by a cent."],
        "requires_human_review": True,
    }
    change.update(overrides)
    return change


def _diff_proposal(changes: list[dict] | None = None, **overrides) -> dict:
    payload = {
        "schema_version": DIFF_PROPOSAL_SCHEMA_VERSION,
        "mode": DIFF_PROPOSAL_MODE,
        "provenance": copy.deepcopy(VALID_DIFF_PROVENANCE),
        "approved_plan": copy.deepcopy(VALID_APPROVED_PLAN),
        "patch_proposal": None,
        "changes": copy.deepcopy(changes) if changes is not None else [_change()],
        "omitted_paths": [],
        "assumptions": ["The helper has no existing callers outside billing."],
        "risks": ["A human may need to reconcile historical invoices."],
        "open_questions": [],
        "source_contents_read": True,
        "diffs_generated": True,
        "files_edited": False,
        "commands_run": False,
        "applies_cleanly_checked": False,
        "requires_human_review": True,
        "next_authorization_required": "Phase 5F0 approval is required separately.",
    }
    payload.update(overrides)
    return payload


def _artifact(changes: list[dict] | None = None, **overrides) -> dict:
    """A fresh, fully valid Phase 5F0 approved-diff-proposal artifact dict."""
    payload = {
        "schema_version": APPROVED_DIFF_PROPOSAL_SCHEMA_VERSION,
        "mode": APPROVED_DIFF_PROPOSAL_MODE,
        "approval": copy.deepcopy(VALID_EDIT_APPROVAL),
        "diff_proposal": _diff_proposal(changes),
        "project_id": PROJECT_ID,
        "repo": REPO,
        "issue_number": ISSUE_NUMBER,
        "title": TITLE,
        "next_authorization_required": NEXT_AUTHORIZATION,
    }
    payload.update(overrides)
    return payload


def _workspace_path(tmp_path):
    """A workspace path that is a **string only**: never created or touched."""
    return tmp_path / "never_touched_workspace"


def _write_config(
    tmp_path,
    *,
    project_id: str = PROJECT_ID,
    github_repo: str = REPO,
    max_changed_files: int = 20,
    name: str = "project.yaml",
):
    path = tmp_path / name
    path.write_text(
        CONFIG_TEMPLATE.format(
            project_id=project_id,
            github_repo=github_repo,
            max_changed_files=max_changed_files,
            workspace_path=str(_workspace_path(tmp_path)).replace("\\", "\\\\"),
        ),
        encoding="utf-8",
    )
    return path


def _write_artifact(tmp_path, payload=None, name: str = "approved_diff.json"):
    path = tmp_path / name
    text = payload if isinstance(payload, str) else json.dumps(
        _artifact() if payload is None else payload
    )
    path.write_text(text, encoding="utf-8")
    return path


def _run(tmp_path, **overrides):
    """Call the private helper directly, so file reads can be tracked."""
    kwargs = {
        "project_config": overrides.pop("project_config", None)
        or _write_config(tmp_path),
        "approved_diff_proposal": overrides.pop("approved_diff_proposal", None)
        or _write_artifact(tmp_path),
        "apply_approved_plan": True,
        "preview_file_edits": True,
    }
    kwargs.update(overrides)
    return cli._run_l2_preview_file_edits(**kwargs)


def _invoke(config_path, artifact_path, *, apply_flag=True, preview_flag=True):
    args = [
        "l2-preview-file-edits",
        "--project-config",
        str(config_path),
        "--approved-diff-proposal",
        str(artifact_path),
    ]
    if apply_flag:
        args.append("--apply-approved-plan")
    if preview_flag:
        args.append("--preview-file-edits")
    return runner.invoke(app, args)


def _invoke_all(tmp_path, **kwargs):
    return _invoke(_write_config(tmp_path), _write_artifact(tmp_path), **kwargs)


def _track_read_text(monkeypatch, path_type, sink: list[str]):
    """Record every ``Path.read_text`` call while still performing it."""
    real_read_text = path_type.read_text

    def tracking_read_text(self, *args, **kwargs):
        sink.append(str(self))
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(path_type, "read_text", tracking_read_text)


def _option_names(command: str) -> set[str]:
    """The command's declared option strings, read from the parser, not prose.

    Substring matching against rendered help cannot express "``--approved-plan``
    is absent" when ``--approved-diff-proposal`` is present, so the
    forbidden-option assertions compare against these exact strings instead.
    ``--help`` is added by the framework and never appears here.
    """
    subcommand = typer.main.get_command(app).commands[command]
    names: set[str] = set()
    for parameter in subcommand.params:
        names.update(parameter.opts)
        names.update(parameter.secondary_opts)
    return names


# -- 1. CLI surface ------------------------------------------------------------


def test_l2_preview_file_edits_appears_in_root_help():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "l2-preview-file-edits" in result.output


def test_existing_commands_still_appear_in_root_help():
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
        "generate-patch-proposal",
        "l2-read-workspace-files",
        "generate-diff-proposal",
    ):
        assert command in result.output


def test_help_exposes_exactly_the_declared_options():
    assert _option_names("l2-preview-file-edits") == {
        "--project-config",
        "--approved-diff-proposal",
        "--apply-approved-plan",
        "--preview-file-edits",
        "--format",
    }

    result = runner.invoke(app, ["l2-preview-file-edits", "--help"])
    assert result.exit_code == 0
    for present in (
        "--project-config",
        "--approved-diff-proposal",
        "--apply-approved-plan",
        "--preview-file-edits",
        "--format",
        "--help",
    ):
        assert present in result.output


def test_help_hides_forbidden_options():
    declared = _option_names("l2-preview-file-edits")

    for absent in (
        "--output",
        "--model",
        "--real-model",
        "--body-file",
        "--issue",
        "--title",
        "--github",
        "--fetch",
        "--workspace",
        "--file",
        "--context-file",
        "--command",
        "--edit",
        "--audit-dir",
        "--inspect-workspace",
        "--read-contents",
        "--generate-proposal",
        "--generate-diff",
        "--apply-patch",
        "--apply-diff",
        "--write-files",
        "--run",
        "--verify",
        "--branch",
        "--commit",
        "--push",
        "--pr",
        "--open-pr",
        "--allow-protected",
        "--allow-protected-paths",
    ):
        assert absent not in declared

    result = runner.invoke(app, ["l2-preview-file-edits", "--help"])
    for absent in (
        "--output",
        "--real-model",
        "--body-file",
        "--context-file",
        "--audit-dir",
        "--inspect-workspace",
        "--read-contents",
        "--generate-proposal",
        "--generate-diff",
        "--apply-patch",
        "--apply-diff",
        "--write-files",
        "--open-pr",
    ):
        assert absent not in result.output

    # Passing one is an error, not a silently ignored argument.
    for rejected_flag in (
        "--real-model",
        "--apply-patch",
        "--apply-diff",
        "--output",
        "--edit",
        "--write-files",
        "--commit",
        "--push",
    ):
        rejected = runner.invoke(app, ["l2-preview-file-edits", rejected_flag])
        assert rejected.exit_code != 0


def test_no_apply_edit_or_git_command_exists():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    for absent in (
        "apply-diff",
        "apply-patch",
        "edit-files",
        "write-files",
        "implement",
        "create-branch",
        "open-pr",
    ):
        assert absent not in result.output

    for absent in (
        "apply-diff",
        "apply-diff-proposal",
        "apply-patch",
        "l2-apply-file-edits",
        "edit-files",
        "write-files",
        "implement-plan",
        "run-verification",
        "create-branch",
        "open-pr",
    ):
        assert runner.invoke(app, [absent, "--help"]).exit_code != 0


@pytest.mark.parametrize(
    "command, present, absent",
    [
        (
            "generate-diff-proposal",
            ("--project-config", "--approved-plan", "--workspace-content",
             "--proposed-content", "--apply-approved-plan", "--generate-diff",
             "--format"),
            ("--approved-diff-proposal", "--preview-file-edits", "--apply-diff",
             "--write-files"),
        ),
        (
            "l2-read-workspace-files",
            ("--project-config", "--approved-plan", "--apply-approved-plan",
             "--read-contents", "--format"),
            ("--approved-diff-proposal", "--preview-file-edits", "--generate-diff"),
        ),
        (
            "generate-patch-proposal",
            ("--project-config", "--approved-plan", "--apply-approved-plan",
             "--generate-proposal", "--format"),
            ("--approved-diff-proposal", "--preview-file-edits", "--generate-diff"),
        ),
        (
            "l2-inspect-workspace",
            ("--project-config", "--approved-plan", "--apply-approved-plan",
             "--inspect-workspace", "--format"),
            ("--approved-diff-proposal", "--preview-file-edits", "--generate-diff"),
        ),
        (
            "l2-dry-run",
            ("--project-config", "--approved-plan", "--apply-approved-plan",
             "--format"),
            ("--approved-diff-proposal", "--preview-file-edits", "--generate-diff"),
        ),
        (
            "generate-plan",
            ("--project-config", "--repo", "--issue", "--title", "--body-file",
             "--format"),
            ("--approved-diff-proposal", "--preview-file-edits", "--approved-plan"),
        ),
        (
            "generate-model-plan",
            ("--project-config", "--issue", "--title", "--body-file", "--model",
             "--real-model"),
            ("--approved-diff-proposal", "--preview-file-edits", "--approved-plan"),
        ),
    ],
)
def test_existing_command_options_are_unchanged(command, present, absent):
    declared = _option_names(command)

    for option in present:
        assert option in declared
    for option in absent:
        assert option not in declared


def test_existing_command_helps_still_render():
    for command in (
        "generate-diff-proposal",
        "l2-read-workspace-files",
        "generate-patch-proposal",
        "l2-inspect-workspace",
        "l2-dry-run",
        "generate-plan",
        "generate-model-plan",
    ):
        result = runner.invoke(app, [command, "--help"])
        assert result.exit_code == 0


# -- 2. fail closed: the two flags come before any file read -------------------


def test_missing_apply_flag_fails_before_any_file_is_read(tmp_path, monkeypatch):
    config_path = _write_config(tmp_path)
    artifact_path = _write_artifact(tmp_path)
    read: list[str] = []
    _track_read_text(monkeypatch, type(config_path), read)

    result = _invoke(config_path, artifact_path, apply_flag=False)

    assert result.exit_code == 1
    assert "--apply-approved-plan" in result.stderr
    assert result.stdout.strip() == ""
    # Nothing at all was read: not the artifact, and not even the config.
    assert read == []
    assert SUMMARY_MARKER not in result.output


def test_missing_preview_flag_fails_before_any_file_is_read(tmp_path, monkeypatch):
    config_path = _write_config(tmp_path)
    artifact_path = _write_artifact(tmp_path)
    read: list[str] = []
    _track_read_text(monkeypatch, type(config_path), read)

    result = _invoke(config_path, artifact_path, preview_flag=False)

    assert result.exit_code == 1
    assert "--preview-file-edits" in result.stderr
    assert result.stdout.strip() == ""
    assert read == []
    assert SUMMARY_MARKER not in result.output


@pytest.mark.parametrize(
    "missing", [{"apply_approved_plan": False}, {"preview_file_edits": False}]
)
def test_missing_flags_fail_with_the_injected_helper(tmp_path, missing, capsys):
    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, **missing)

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert captured.out.strip() == ""
    assert "Nothing was read." in captured.err


# -- 3. fail closed: the workspace guard, before the artifact is read ----------


def test_an_artifact_inside_the_workspace_is_rejected_before_it_is_read(
    tmp_path, monkeypatch
):
    config_path = _write_config(tmp_path)
    workspace = _workspace_path(tmp_path)
    workspace.mkdir()
    inside = workspace / "approved_diff.json"
    inside.write_text(
        json.dumps(_artifact()) + "\nSENTINEL_WORKSPACE_INPUT_CONTENT",
        encoding="utf-8",
    )
    read: list[str] = []
    _track_read_text(monkeypatch, type(inside), read)

    result = _invoke(config_path, inside)

    assert result.exit_code == 1
    assert "--approved-diff-proposal is inside the project's configured" in result.stderr
    assert "was not read" in result.stderr
    assert result.stdout.strip() == ""
    # Only the config was opened; the guard ran before the artifact read.
    assert read == [str(config_path)]
    assert "SENTINEL_WORKSPACE_INPUT_CONTENT" not in result.output


def test_an_artifact_in_a_workspace_subdirectory_is_also_rejected(tmp_path):
    config_path = _write_config(tmp_path)
    nested = _workspace_path(tmp_path) / "docs" / "approvals"
    nested.mkdir(parents=True)
    inside = nested / "approved_diff.json"
    inside.write_text(json.dumps(_artifact()), encoding="utf-8")

    result = _invoke(config_path, inside)

    assert result.exit_code == 1
    assert "repo.workspace_path" in result.stderr
    assert result.stdout.strip() == ""


def test_the_workspace_itself_is_rejected_as_the_artifact_path(tmp_path):
    config_path = _write_config(tmp_path)

    result = _invoke(config_path, _workspace_path(tmp_path))

    assert result.exit_code == 1
    assert "repo.workspace_path" in result.stderr
    assert result.stdout.strip() == ""
    # The guard is string/path reasoning: the workspace was never created.
    assert not _workspace_path(tmp_path).exists()


def test_unloadable_project_config_fails_before_the_artifact_is_read(
    tmp_path, monkeypatch
):
    bad_config = tmp_path / "broken.yaml"
    bad_config.write_text("project_id: demo_project\n", encoding="utf-8")
    read: list[str] = []
    _track_read_text(monkeypatch, type(bad_config), read)

    result = _invoke(bad_config, _write_artifact(tmp_path))

    assert result.exit_code == 1
    assert "was not read" in result.stderr
    assert result.stdout.strip() == ""
    assert read == [str(bad_config)]


def test_a_missing_artifact_fails_cleanly(tmp_path, capsys):
    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, approved_diff_proposal=tmp_path / "does_not_exist.json")

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert "could not read --approved-diff-proposal" in captured.err
    assert captured.out.strip() == ""


def test_command_reads_only_the_two_explicit_files(tmp_path, monkeypatch, capsys):
    config_path = _write_config(tmp_path)
    artifact_path = _write_artifact(tmp_path)
    read: list[str] = []
    _track_read_text(monkeypatch, type(config_path), read)

    _run(
        tmp_path,
        project_config=config_path,
        approved_diff_proposal=artifact_path,
    )

    capsys.readouterr()
    assert read == [str(config_path), str(artifact_path)]


# -- 4. fail closed on the artifact, then on the preview -----------------------


@pytest.mark.parametrize(
    "text", ["not json at all", '{"approval": ', "```json\n{}\n```", "[]", ""]
)
def test_unparseable_artifact_text_fails_with_no_stdout(tmp_path, capsys, text):
    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, approved_diff_proposal=_write_artifact(tmp_path, text))

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert "FileEditingApprovalParseError" in captured.err
    assert "parse failure" in captured.err
    assert captured.out.strip() == ""


@pytest.mark.parametrize(
    "mutate",
    [
        # A paraphrased file-edit approval is not approval.
        lambda a: a["approval"].update({"approval_text": "looks fine to me"}),
        # The Phase 5B *plan* approval is an approval of a different thing.
        lambda a: a["approval"].update({"approval_text": REQUIRED_APPROVAL_TEXT}),
        # A non-manual source is refused.
        lambda a: a["approval"].update({"source": "model"}),
        # An approval cannot be obtained by omission.
        lambda a: a.pop("approval"),
        # A forged extra is rejected, not stored.
        lambda a: a.update({"auto_apply": True}),
        # An artifact claiming a write already happened is not a valid approval.
        lambda a: a["diff_proposal"].update({"files_edited": True}),
        lambda a: a["diff_proposal"].update({"applies_cleanly_checked": True}),
        # A path the plan forbade may never be approved.
        lambda a: a["diff_proposal"].update(
            {"changes": [_change(PLAN_OUT_OF_SCOPE)]}
        ),
    ],
)
def test_invalid_artifact_fails_after_the_config_and_before_the_preview(
    tmp_path, capsys, monkeypatch, mutate
):
    payload = _artifact()
    mutate(payload)
    config_path = _write_config(tmp_path)
    artifact_path = _write_artifact(tmp_path, payload)
    read: list[str] = []
    _track_read_text(monkeypatch, type(config_path), read)

    with pytest.raises(typer.Exit) as excinfo:
        _run(
            tmp_path,
            project_config=config_path,
            approved_diff_proposal=artifact_path,
        )

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert "FileEditingApprovalValidationError" in captured.err
    assert captured.out.strip() == ""
    # The config and the artifact were read, in that order, and nothing else.
    assert read == [str(config_path), str(artifact_path)]
    # Neither the diff nor the approval sentence is echoed back.
    assert SOURCE_MARKER not in captured.err
    assert REQUIRED_DIFF_EDIT_APPROVAL_TEXT not in captured.err


@pytest.mark.parametrize(
    "config_overrides",
    [
        {"project_id": "some_other_project"},
        {"github_repo": "other/widgets"},
    ],
)
def test_identity_mismatch_fails_with_no_stdout(tmp_path, capsys, config_overrides):
    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, project_config=_write_config(tmp_path, **config_overrides))

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert "FileEditPreviewError" in captured.err
    assert "does not match this project config" in captured.err
    assert captured.out.strip() == ""


@pytest.mark.parametrize(
    "path, reason",
    [
        (PLAN_PROTECTED, "PROTECTED"),
        (PLAN_UNLISTED, "unlisted"),
        (PLAN_POLICY_FORBIDDEN, "forbidden"),
    ],
)
def test_write_policy_failure_fails_with_no_stdout(tmp_path, capsys, path, reason):
    artifact_path = _write_artifact(tmp_path, _artifact([_change(path)]))

    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, approved_diff_proposal=artifact_path)

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert "FileEditPreviewError" in captured.err
    assert reason in captured.err
    assert "no workspace was touched" in captured.err
    assert captured.out.strip() == ""


def test_one_refused_path_fails_the_whole_preview(tmp_path, capsys):
    artifact_path = _write_artifact(
        tmp_path, _artifact([_change(PLAN_FILE_A), _change(PLAN_PROTECTED)])
    )

    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, approved_diff_proposal=artifact_path)

    assert excinfo.value.exit_code == 1
    assert capsys.readouterr().out.strip() == ""


def test_change_count_above_the_cap_fails_with_no_stdout(tmp_path, capsys):
    artifact_path = _write_artifact(
        tmp_path,
        _artifact([_change(PLAN_FILE_A), _change(PLAN_FILE_NEW, "create")]),
    )

    with pytest.raises(typer.Exit) as excinfo:
        _run(
            tmp_path,
            project_config=_write_config(tmp_path, max_changed_files=1),
            approved_diff_proposal=artifact_path,
        )

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert "max_changed_files" in captured.err
    assert captured.out.strip() == ""


# -- 5. the happy path ---------------------------------------------------------


def _preview(tmp_path, capsys, **overrides) -> FileEditPreviewReport:
    _run(tmp_path, **overrides)
    return FileEditPreviewReport.model_validate_json(capsys.readouterr().out)


def test_valid_command_prints_a_parseable_preview_report(tmp_path, capsys):
    report = _preview(tmp_path, capsys)

    assert report.schema_version == FILE_EDIT_PREVIEW_SCHEMA_VERSION
    assert report.mode == FILE_EDIT_PREVIEW_MODE
    assert report.project.project_id == PROJECT_ID
    assert report.project.repo == REPO
    assert report.approved_diff.approved_by == APPROVER
    assert report.approved_diff.issue_number == ISSUE_NUMBER
    assert report.approved_diff.title == TITLE
    assert report.preview.paths_count == 1
    assert report.preview.changes[0].path == PLAN_FILE_A
    assert report.preview.changes[0].policy_result == "allowed"


def test_modify_create_and_empty_change_sets_all_preview(tmp_path, capsys):
    modify = _preview(
        tmp_path,
        capsys,
        approved_diff_proposal=_write_artifact(
            tmp_path, _artifact([_change(PLAN_FILE_A, "modify")]), name="m.json"
        ),
    )
    assert [c.change_type for c in modify.preview.changes] == ["modify"]
    assert modify.preview.changes[0].diff_stats.removed_lines == 1

    create = _preview(
        tmp_path,
        capsys,
        approved_diff_proposal=_write_artifact(
            tmp_path, _artifact([_change(PLAN_FILE_NEW, "create")]), name="c.json"
        ),
    )
    assert [c.change_type for c in create.preview.changes] == ["create"]
    assert create.preview.changes[0].diff_stats.added_lines == 2

    empty = _preview(
        tmp_path,
        capsys,
        approved_diff_proposal=_write_artifact(
            tmp_path, _artifact([]), name="e.json"
        ),
    )
    assert empty.preview.paths_count == 0
    assert empty.preview.changes == []
    assert empty.approved_diff.change_count == 0


def test_multiple_changes_preserve_order_through_the_cli(tmp_path, capsys):
    report = _preview(
        tmp_path,
        capsys,
        approved_diff_proposal=_write_artifact(
            tmp_path,
            _artifact([_change(PLAN_FILE_NEW, "create"), _change(PLAN_FILE_A)]),
        ),
    )

    assert [c.path for c in report.preview.changes] == [PLAN_FILE_NEW, PLAN_FILE_A]


def test_success_through_the_cli_matches_the_helper(tmp_path, capsys):
    from_helper = _preview(tmp_path, capsys).model_dump_json()

    result = _invoke_all(tmp_path)

    assert result.exit_code == 0
    assert (
        FileEditPreviewReport.model_validate_json(result.stdout).model_dump_json()
        == from_helper
    )


def test_stdout_is_the_report_with_no_wrapper(tmp_path, capsys):
    _run(tmp_path)

    out = capsys.readouterr().out
    assert out.lstrip().startswith("{")
    assert out.rstrip().endswith("}")
    payload = json.loads(out)
    assert set(payload) == {
        "schema_version",
        "mode",
        "project",
        "approved_diff",
        "preview",
        "checks_performed",
        "checks_not_performed",
        "files_edited",
        "commands_run",
        "applies_cleanly_checked",
        "workspace_touched",
        "requires_future_authorization",
        "next_authorization_required",
    }


def test_the_report_flags_state_what_did_not_happen(tmp_path, capsys):
    report = _preview(tmp_path, capsys)

    assert report.files_edited is False
    assert report.commands_run is False
    assert report.applies_cleanly_checked is False
    assert report.workspace_touched is False
    assert report.requires_future_authorization is True
    for value in report.checks_not_performed.model_dump().values():
        assert value is False


# -- 6. what stdout does and does not contain ----------------------------------


def test_output_omits_diffs_source_text_and_raw_artifact_text(tmp_path, capsys):
    _run(
        tmp_path,
        approved_diff_proposal=_write_artifact(
            tmp_path, _artifact([_change(PLAN_FILE_A), _change(PLAN_FILE_NEW, "create")])
        ),
    )

    out = capsys.readouterr().out
    assert SOURCE_MARKER not in out
    assert SUMMARY_MARKER not in out
    assert VERIFICATION_MARKER not in out
    assert "unified_diff" not in out
    assert "return str(amount)" not in out
    assert "@@" not in out
    assert "--- a/" not in out
    assert "+++ b/" not in out


def test_output_omits_the_approval_text(tmp_path, capsys):
    _run(tmp_path)

    out = capsys.readouterr().out
    assert "approval_text" not in out
    assert REQUIRED_DIFF_EDIT_APPROVAL_TEXT not in out
    assert REQUIRED_APPROVAL_TEXT not in out


def test_output_omits_workspace_path_and_absolute_paths(tmp_path, capsys):
    _run(tmp_path)

    out = capsys.readouterr().out
    workspace = str(_workspace_path(tmp_path))
    assert workspace not in out
    assert workspace.replace("\\", "/") not in out
    assert "workspace_path" not in out
    assert str(tmp_path) not in out
    assert str(tmp_path).replace("\\", "/") not in out


def test_output_omits_command_apply_and_git_claims(tmp_path, capsys):
    _run(tmp_path)

    payload = json.loads(capsys.readouterr().out)
    flat = json.dumps(payload)
    for absent in (
        "command_output",
        "apply_result",
        "auto_apply",
        "pr_url",
        "branch_name",
        "commit_sha",
        "api_key",
        "base_url",
        "prompt",
        "completion",
    ):
        assert absent not in flat

    # The only branch/commit/push/PR mentions are the false flags recording
    # that none of them happened.
    checks = payload["checks_not_performed"]
    assert checks["branch_created"] is False
    assert checks["commit_created"] is False
    assert checks["pushed"] is False
    assert checks["pr_opened"] is False
    assert checks["model_called"] is False


def test_output_contains_no_executable_command_instruction(tmp_path, capsys):
    _run(tmp_path)

    out = capsys.readouterr().out
    for absent in ("git apply", "git commit", "git push", "patch -p1", "pytest -q"):
        assert absent not in out


def test_failure_output_never_echoes_the_artifact_text(tmp_path, capsys):
    payload = _artifact()
    payload["approval"]["approval_text"] = "looks fine to me"

    with pytest.raises(typer.Exit):
        _run(
            tmp_path,
            approved_diff_proposal=_write_artifact(tmp_path, payload),
        )

    captured = capsys.readouterr()
    assert SOURCE_MARKER not in captured.err
    assert SUMMARY_MARKER not in captured.err
    assert "looks fine to me" not in captured.err
    assert captured.out.strip() == ""


# -- 7. the command touches nothing --------------------------------------------


def _track_filesystem(monkeypatch, sink: list[str]):
    for module, name in (
        (os, "stat"),
        (os, "lstat"),
        (os.path, "realpath"),
        (os.path, "exists"),
        (builtins, "open"),
    ):
        real = getattr(module, name)

        def tracking(*args, _real=real, **kwargs):
            if args:
                sink.append(str(args[0]))
            return _real(*args, **kwargs)

        monkeypatch.setattr(module, name, tracking)


def test_plan_paths_and_workspace_are_never_touched(tmp_path, monkeypatch, capsys):
    touched: list[str] = []
    _track_filesystem(monkeypatch, touched)

    _run(tmp_path)

    capsys.readouterr()
    workspace = str(_workspace_path(tmp_path))
    for path in touched:
        assert workspace not in path
        for plan_path in (
            PLAN_FILE_A,
            PLAN_FILE_NEW,
            PLAN_PROTECTED,
            PLAN_UNLISTED,
            PLAN_POLICY_FORBIDDEN,
            PLAN_OUT_OF_SCOPE,
        ):
            assert plan_path not in path.replace("\\", "/")
    assert not _workspace_path(tmp_path).exists()


def test_no_listing_globbing_canonicalization_or_stat_happens(
    tmp_path, monkeypatch, capsys
):
    config_path = _write_config(tmp_path)
    artifact_path = _write_artifact(tmp_path)

    # Warm the lazy imports first, so the detonators below catch the command's
    # own behavior rather than the import machinery's.
    _run(
        tmp_path,
        project_config=config_path,
        approved_diff_proposal=artifact_path,
    )
    capsys.readouterr()

    def _blocked(*args, **kwargs):
        raise AssertionError("l2-preview-file-edits must not inspect the filesystem")

    monkeypatch.setattr(os, "listdir", _blocked)
    monkeypatch.setattr(os, "scandir", _blocked)
    monkeypatch.setattr(os, "walk", _blocked)
    monkeypatch.setattr(os.path, "realpath", _blocked)
    monkeypatch.setattr(os, "stat", _blocked)
    monkeypatch.setattr(os, "readlink", _blocked)

    _run(
        tmp_path,
        project_config=config_path,
        approved_diff_proposal=artifact_path,
    )

    report = FileEditPreviewReport.model_validate_json(capsys.readouterr().out)
    assert report.preview.paths_count == 1


def test_no_env_read_no_socket_and_no_subprocess(tmp_path, monkeypatch, capsys):
    def _blocked(*args, **kwargs):
        raise AssertionError(
            "l2-preview-file-edits must not read env, network, or processes"
        )

    monkeypatch.setattr(os, "getenv", _blocked)
    monkeypatch.setattr(os.environ, "get", _blocked)
    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket, "getaddrinfo", _blocked)
    monkeypatch.setattr(socket, "gethostbyname", _blocked)
    monkeypatch.setattr(subprocess, "Popen", _blocked)
    monkeypatch.setattr(subprocess, "run", _blocked)
    monkeypatch.setattr(os, "system", _blocked)

    _run(tmp_path)

    assert FileEditPreviewReport.model_validate_json(capsys.readouterr().out)


def test_command_uses_no_llm_client_httpx_or_github_client(
    tmp_path, monkeypatch, capsys
):
    import ai_dev_orchestrator.github.client as github_client
    import ai_dev_orchestrator.llm.client as llm_client
    import ai_dev_orchestrator.llm.config as llm_config

    def _blocked(*args, **kwargs):
        raise AssertionError(
            "l2-preview-file-edits must not build a client or read llm config"
        )

    monkeypatch.setattr(github_client.GitHubClient, "__init__", _blocked)
    monkeypatch.setattr(github_client.GitHubClient, "get_issue", _blocked)
    monkeypatch.setattr(llm_client.LLMClient, "__init__", _blocked)
    monkeypatch.setattr(llm_config, "load_llm_client_config_from_env", _blocked)
    monkeypatch.setattr(cli, "_build_real_llm_client", _blocked)
    monkeypatch.setattr(cli, "_read_real_llm_env", _blocked)

    _run(tmp_path)

    assert FileEditPreviewReport.model_validate_json(capsys.readouterr().out)


def test_command_writes_no_files_and_stamps_no_approval(tmp_path, capsys):
    config_path = _write_config(tmp_path)
    artifact_path = _write_artifact(tmp_path)
    before = sorted(p.name for p in tmp_path.iterdir())
    contents_before = artifact_path.read_text(encoding="utf-8")

    _run(
        tmp_path,
        project_config=config_path,
        approved_diff_proposal=artifact_path,
    )

    capsys.readouterr()
    # No report file was written, no approval was stamped, nothing rewritten.
    assert sorted(p.name for p in tmp_path.iterdir()) == before
    assert artifact_path.read_text(encoding="utf-8") == contents_before


def test_helper_source_names_no_client_transport_env_or_patch_symbol():
    import inspect

    source = inspect.getsource(cli._run_l2_preview_file_edits) + inspect.getsource(
        cli.l2_preview_file_edits
    )

    for forbidden in (
        "LLMClient",
        "httpx",
        "requests",
        "load_llm_client_config_from_env",
        "GitHubClient",
        "subprocess",
        "os.environ",
        "getenv",
        "git apply",
        "apply_patch",
        "write_text",
        "mkdir",
    ):
        assert forbidden not in source


def test_existing_commands_still_behave_the_same():
    smoke = runner.invoke(app, ["llm-smoke-test"])
    assert smoke.exit_code == 0
    assert "No real model was called." in smoke.output

    version = runner.invoke(app, ["version"])
    assert version.exit_code == 0
