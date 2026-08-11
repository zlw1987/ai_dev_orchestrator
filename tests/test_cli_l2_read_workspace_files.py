"""Phase 5D2 tests: the ``l2-read-workspace-files`` command.

Phase 5D1 shipped the first command that may *touch* a target workspace. This
is the first command whose **output may contain that workspace's source**, so
these tests are organized around three questions: how many gates stand in front
of the first byte, how tightly bounded the read is once they all pass, and what
still never happens. It lists no directory, globs nothing, walks no tree,
generates no diff, edits nothing, runs no command, calls no model, opens no
socket, reads no environment variable, and contacts no GitHub — and no content
it reads is sent anywhere but stdout, redacted.

Every path in this module lives under pytest's own ``tmp_path``. No real project
workspace is named anywhere, and the "workspace" these tests configure is a
directory the test itself created a moment earlier.
"""

from __future__ import annotations

import builtins
import copy
import inspect
import json
import os
import socket
import subprocess
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from ai_dev_orchestrator import cli

# Imported at module scope so the command's lazy imports are already cached in
# sys.modules: the no-IO tests below replace os.stat and friends, and the import
# machinery would otherwise trip over them.
from ai_dev_orchestrator import config_loader as _config_loader  # noqa: F401
from ai_dev_orchestrator import models as _models  # noqa: F401
from ai_dev_orchestrator import workspace as _workspace  # noqa: F401
from ai_dev_orchestrator.cli import app
from ai_dev_orchestrator.config_loader import load_project_config
from ai_dev_orchestrator.handoff import REQUIRED_APPROVAL_TEXT
from ai_dev_orchestrator.models import ProjectConfig, ReadOnlyWorkspaceContentConfig

runner = CliRunner()

PROJECT_ID = "demo_project"
REPO = "demo/widgets"
ISSUE_NUMBER = 42
TITLE = "Add currency formatting helper"
APPROVER = "operator@example.invalid"
APPROVED_AT = "2026-01-02T04:00:00+00:00"
PLAN_MODEL = "fake-planner-model"

# The configured workspace directory name is deliberately distinctive and does
# **not** contain the word "workspace": the output JSON legitimately carries
# keys like `workspace_policy`, so a generic name would make the "the workspace
# path never appears in the output" assertion vacuously true.
WORKSPACE_DIRNAME = "target_ws_sentinel"

# Path-shaped strings that live in plan fields which are **prose**, never paths.
# They must never be opened and never reach stdout.
STEP_MARKER = "src/sentinel_step_never_a_path.py"
VERIFICATION_MARKER = "src/sentinel_verification_never_a_path.py"
RISK_MARKER = "src/sentinel_risk_never_a_path.py"
QUESTION_MARKER = "src/sentinel_question_never_a_path.py"
OUT_OF_SCOPE_MARKER = "src/sentinel_out_of_scope_never_read.py"

MOD_TEXT = "value = 1\n"
TEST_MOD_TEXT = "def test_x():\n    pass\n"

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
  allow_symlinks: {allow_symlinks}
  max_changed_files: {max_changed_files}
allowed_paths:
  - "src/**"
  - "tests/**"
protected_paths:
  - "src/protected/**"
forbidden_paths:
  - ".git/**"
  - "secrets/**"
{content_block}"""

CONTENT_BLOCK = """\
read_only_workspace_content:
  enabled: {enabled}
  max_files: {max_files}
  max_file_bytes: {max_file_bytes}
  max_total_bytes: {max_total_bytes}
  allow_protected_paths: {allow_protected_paths}
"""

VALID_PROVENANCE: dict = {
    "engine": "real-model",
    "operation": "l1-plan",
    "real_call": True,
    "model": PLAN_MODEL,
    "endpoint_host": "fake-litellm.invalid:8000",
    "generated_at": "2026-01-02T03:04:05+00:00",
    "project_id": PROJECT_ID,
    "repo": REPO,
    "issue_number": ISSUE_NUMBER,
    "title": TITLE,
}

VALID_APPROVAL: dict = {
    "approved_by": APPROVER,
    "approved_at": APPROVED_AT,
    "approval_text": REQUIRED_APPROVAL_TEXT,
    "source": "manual",
}


def _yaml_string(value) -> str:
    """Quote a path for YAML. ``json.dumps`` produces a valid double-quoted scalar."""
    return json.dumps(str(value))


def _workspace_path(tmp_path: Path) -> Path:
    return tmp_path / WORKSPACE_DIRNAME


def _write_source(path: Path, text: str) -> Path:
    """Write UTF-8 source with its newlines exactly as written.

    ``Path.write_text`` would translate ``\\n`` to ``\\r\\n`` on Windows, which
    the command — reading raw bytes and decoding without newline translation —
    would faithfully report back. Writing bytes keeps the fixtures and the
    expectations identical on every platform.
    """
    path.write_bytes(text.encode("utf-8"))
    return path


def _make_workspace(tmp_path: Path) -> Path:
    """Create the configured workspace and its files, all under tmp_path."""
    root = _workspace_path(tmp_path)
    (root / "src" / "pkg").mkdir(parents=True)
    (root / "src" / "protected").mkdir(parents=True)
    (root / "tests").mkdir(parents=True)
    _write_source(root / "src" / "mod.py", MOD_TEXT)
    _write_source(root / "src" / "pkg" / "__init__.py", "SENTINEL_INSIDE_A_DIRECTORY = 1\n")
    _write_source(root / "src" / "protected" / "secret_ish.py", "x = 2\n")
    _write_source(root / "tests" / "test_mod.py", TEST_MOD_TEXT)
    return root


def _write_config(
    tmp_path: Path,
    *,
    project_id: str = PROJECT_ID,
    github_repo: str = REPO,
    enabled: bool = True,
    max_files: int = 10,
    max_file_bytes: int = 50000,
    max_total_bytes: int = 200000,
    allow_protected_paths: bool = False,
    allow_symlinks: bool = False,
    max_changed_files: int = 20,
    include_content_block: bool = True,
    workspace_path: Path | None = None,
    name: str = "project.yaml",
) -> Path:
    """Write a project config inside the test's own tmp dir."""
    block = ""
    if include_content_block:
        block = CONTENT_BLOCK.format(
            enabled=str(enabled).lower(),
            max_files=max_files,
            max_file_bytes=max_file_bytes,
            max_total_bytes=max_total_bytes,
            allow_protected_paths=str(allow_protected_paths).lower(),
        )
    path = tmp_path / name
    path.write_text(
        CONFIG_TEMPLATE.format(
            project_id=project_id,
            github_repo=github_repo,
            workspace_path=_yaml_string(
                _workspace_path(tmp_path) if workspace_path is None else workspace_path
            ),
            allow_symlinks=str(allow_symlinks).lower(),
            max_changed_files=max_changed_files,
            content_block=block,
        ),
        encoding="utf-8",
    )
    return path


def _plan(files: list[str] | None = None) -> dict:
    return {
        "issue_number": ISSUE_NUMBER,
        "repo": REPO,
        "title": TITLE,
        "summary": "Format invoice totals through one shared helper.",
        "scope_summary": "Only the billing formatting helper and its tests.",
        "non_goals": ["No changes to the payment gateway client."],
        "proposed_steps": [f"Review the helper described in {STEP_MARKER}."],
        "files_likely_to_change": ["src/mod.py"] if files is None else files,
        "files_forbidden_or_out_of_scope": [OUT_OF_SCOPE_MARKER],
        "required_verification": [f"pytest -q {VERIFICATION_MARKER}"],
        "risks": [f"Rounding differences near {RISK_MARKER}."],
        "open_questions": [f"Which locale applies in {QUESTION_MARKER}?"],
        "automation_level": "L1",
        "requires_human_approval": True,
    }


def _artifact(files: list[str] | None = None) -> dict:
    return {
        "approval": copy.deepcopy(VALID_APPROVAL),
        "plan_provenance": copy.deepcopy(VALID_PROVENANCE),
        "plan": _plan(files),
        "project_id": PROJECT_ID,
        "repo": REPO,
        "issue_number": ISSUE_NUMBER,
    }


def _write_artifact(
    tmp_path: Path,
    artifact: dict | str | None = None,
    *,
    name: str = "approved_plan.json",
    directory: Path | None = None,
) -> Path:
    """Write an approved-plan artifact, by default outside the workspace."""
    path = (tmp_path if directory is None else directory) / name
    text = (
        artifact
        if isinstance(artifact, str)
        else json.dumps(_artifact() if artifact is None else artifact)
    )
    path.write_text(text, encoding="utf-8")
    return path


def _run(tmp_path: Path, **overrides):
    """Call the private helper directly, so file reads can be tracked."""
    kwargs = {
        "project_config": overrides.pop("project_config", None) or _write_config(tmp_path),
        "approved_plan": overrides.pop("approved_plan", None) or _write_artifact(tmp_path),
        "apply_approved_plan": True,
        "read_contents": True,
    }
    kwargs.update(overrides)
    return cli._run_l2_read_workspace_files(**kwargs)


def _invoke(config_path, artifact_path, *, apply_flag: bool = True, read_flag: bool = True):
    args = [
        "l2-read-workspace-files",
        "--project-config",
        str(config_path),
        "--approved-plan",
        str(artifact_path),
    ]
    if apply_flag:
        args.append("--apply-approved-plan")
    if read_flag:
        args.append("--read-contents")
    return runner.invoke(app, args)


def _payload(tmp_path, capsys, **overrides) -> dict:
    _run(tmp_path, **overrides)
    return json.loads(capsys.readouterr().out)


def _items(payload: dict) -> list[dict]:
    return payload["workspace_content"]["items"]


def _track_read_text(monkeypatch, sink: list[str]):
    """Record every ``Path.read_text`` call while still performing it."""
    real_read_text = Path.read_text

    def tracking_read_text(self, *args, **kwargs):
        sink.append(str(self))
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", tracking_read_text)


def _track_filesystem(monkeypatch, sink: list[str]) -> list[str]:
    """Record every path handed to an existence/stat/resolution/open entry point.

    ``os.path.abspath`` is deliberately not tracked: ``_is_same_or_under`` uses
    it to compare strings and it performs no filesystem access.
    """
    for module, name in (
        (os, "stat"),
        (os, "lstat"),
        (os, "listdir"),
        (os, "scandir"),
        (os.path, "exists"),
        (os.path, "realpath"),
        (builtins, "open"),
    ):
        real = getattr(module, name)

        def tracking(*args, _real=real, **kwargs):
            if args:
                sink.append(str(args[0]))
            return _real(*args, **kwargs)

        monkeypatch.setattr(module, name, tracking)
    return sink


def _detonate_all_filesystem_entry_points(monkeypatch, message: str):
    """Make every path-touching entry point raise, so a touch is unmissable."""

    def _blocked(*args, **kwargs):
        raise AssertionError(message)

    for module, name in (
        (os, "stat"),
        (os, "lstat"),
        (os, "listdir"),
        (os, "scandir"),
        (os, "walk"),
        (os.path, "exists"),
        (os.path, "realpath"),
        (Path, "resolve"),
        (builtins, "open"),
    ):
        monkeypatch.setattr(module, name, _blocked)


def try_symlink(link: Path, target: Path, *, target_is_directory: bool = False) -> None:
    """Create a symlink or skip the test if the platform/user cannot."""
    try:
        link.symlink_to(target, target_is_directory=target_is_directory)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"platform/user cannot create symlinks ({type(exc).__name__})")


# -- 1..7. CLI surface ---------------------------------------------------------


def test_l2_read_workspace_files_appears_in_root_help():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "l2-read-workspace-files" in result.output


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
    ):
        assert command in result.output


def test_help_exposes_its_options():
    result = runner.invoke(app, ["l2-read-workspace-files", "--help"])

    assert result.exit_code == 0
    for present in (
        "--project-config",
        "--approved-plan",
        "--apply-approved-plan",
        "--read-contents",
        "--format",
        "--help",
    ):
        assert present in result.output


def test_help_hides_forbidden_options():
    result = runner.invoke(app, ["l2-read-workspace-files", "--help"])

    assert result.exit_code == 0
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
        "--generate-proposal",
        "--diff",
        "--apply-patch",
        "--run",
        "--verify",
        "--allow-symlinks",
        "--no-redact",
    ):
        assert absent not in result.output

    # Passing one is an error, not a silently ignored argument.
    for rejected in ("--output", "--diff", "--apply-patch", "--edit", "--no-redact"):
        assert runner.invoke(app, ["l2-read-workspace-files", rejected]).exit_code != 0


@pytest.mark.parametrize(
    ("command", "present", "absent"),
    [
        (
            "generate-patch-proposal",
            ("--project-config", "--approved-plan", "--apply-approved-plan",
             "--generate-proposal", "--format"),
            ("--read-contents", "--inspect-workspace", "--diff", "--apply-patch"),
        ),
        (
            "l2-inspect-workspace",
            ("--project-config", "--approved-plan", "--apply-approved-plan",
             "--inspect-workspace", "--format"),
            ("--read-contents", "--generate-proposal", "--diff", "--apply-patch"),
        ),
        (
            "l2-dry-run",
            ("--project-config", "--approved-plan", "--apply-approved-plan", "--format"),
            ("--read-contents", "--inspect-workspace", "--generate-proposal", "--diff"),
        ),
        (
            "generate-plan",
            ("--project-config", "--repo", "--issue", "--title", "--body-file", "--format"),
            ("--read-contents", "--real-model", "--model", "--approved-plan"),
        ),
        (
            "generate-model-plan",
            ("--project-config", "--issue", "--title", "--body-file", "--model",
             "--real-model"),
            ("--read-contents", "--approved-plan", "--apply-approved-plan"),
        ),
    ],
)
def test_existing_command_help_is_unchanged(command, present, absent):
    result = runner.invoke(app, [command, "--help"])

    assert result.exit_code == 0
    for option in present:
        assert option in result.output
    for option in absent:
        assert option not in result.output


# -- 8..15. the project-level content opt-in block -----------------------------


def test_content_block_defaults_to_disabled_when_absent(tmp_path):
    config_path = _write_config(tmp_path, include_content_block=False)

    project = load_project_config(config_path)

    content = project.read_only_workspace_content
    assert content.enabled is False
    assert content.max_files == 10
    assert content.max_file_bytes == 50000
    assert content.max_total_bytes == 200000
    assert content.allow_protected_paths is False


def test_project_config_defaults_the_block_when_absent():
    project = ProjectConfig(
        project_id="p",
        display_name="P",
        repo={
            "workspace_path": "C:/nowhere",
            "github_repo": "owner/name",
            "branch_prefix": "ai/p",
        },
    )

    assert project.read_only_workspace_content.enabled is False


def test_allow_protected_paths_defaults_to_false():
    assert ReadOnlyWorkspaceContentConfig().allow_protected_paths is False
    assert ReadOnlyWorkspaceContentConfig(enabled=True).allow_protected_paths is False


def test_content_block_rejects_unknown_fields():
    for bad in ({"api_key": "nope"}, {"base_url": "http://x"}, {"model": "m"},
                {"api_key_env": "AIDO_LITELLM_API_KEY"}):
        with pytest.raises(Exception):
            ReadOnlyWorkspaceContentConfig(enabled=True, **bad)


@pytest.mark.parametrize("value", [0, -1, 51, 1000])
def test_max_files_rejects_out_of_range_values(value):
    with pytest.raises(Exception):
        ReadOnlyWorkspaceContentConfig(max_files=value)


@pytest.mark.parametrize("value", [0, -1, 1_000_001, 10_000_000])
def test_max_file_bytes_rejects_out_of_range_values(value):
    with pytest.raises(Exception):
        ReadOnlyWorkspaceContentConfig(max_file_bytes=value)


@pytest.mark.parametrize("value", [0, -1, 5_000_001, 50_000_000])
def test_max_total_bytes_rejects_out_of_range_values(value):
    with pytest.raises(Exception):
        ReadOnlyWorkspaceContentConfig(max_total_bytes=value)


@pytest.mark.parametrize(
    "field", ["max_files", "max_file_bytes", "max_total_bytes"]
)
@pytest.mark.parametrize("value", ["ten", 1.5, None])
def test_the_caps_reject_non_integers(field, value):
    with pytest.raises(Exception):
        ReadOnlyWorkspaceContentConfig(**{field: value})


def test_the_caps_accept_their_permitted_range():
    assert ReadOnlyWorkspaceContentConfig(max_files=1).max_files == 1
    assert ReadOnlyWorkspaceContentConfig(max_files=50).max_files == 50
    assert ReadOnlyWorkspaceContentConfig(max_file_bytes=1).max_file_bytes == 1
    assert (
        ReadOnlyWorkspaceContentConfig(max_file_bytes=1_000_000).max_file_bytes
        == 1_000_000
    )
    assert ReadOnlyWorkspaceContentConfig(max_total_bytes=1).max_total_bytes == 1
    assert (
        ReadOnlyWorkspaceContentConfig(max_total_bytes=5_000_000).max_total_bytes
        == 5_000_000
    )


def test_example_yaml_ships_the_block_disabled():
    # Found by pattern rather than named, so this module never spells out a
    # real project's name (see the audit test at the bottom of the file).
    examples = sorted(
        (Path(__file__).resolve().parents[1] / "projects").glob("*.yaml.example")
    )
    assert examples, "no example project config found"
    example = examples[0]

    project = load_project_config(example)

    assert project.read_only_workspace_content.enabled is False
    assert project.read_only_workspace_content.allow_protected_paths is False
    # And the block is written out explicitly, not merely defaulted.
    assert "read_only_workspace_content:" in example.read_text(encoding="utf-8")


def test_enabled_true_permits_the_command_to_continue(tmp_path, capsys):
    _make_workspace(tmp_path)

    payload = _payload(tmp_path, capsys)

    assert payload["mode"] == "l2-read-workspace-files"
    assert payload["project"]["content_policy"] == {
        "enabled": True,
        "max_files": 10,
        "max_file_bytes": 50000,
        "max_total_bytes": 200000,
        "allow_protected_paths": False,
        "redaction": "mandatory_basic_secret_like_redaction",
    }


def test_the_metadata_block_does_not_enable_content_reads(tmp_path, capsys):
    """Phase 5D1's opt-in grants nothing here: they are separate consents."""
    _make_workspace(tmp_path)
    config_path = tmp_path / "metadata_only.yaml"
    config_path.write_text(
        CONFIG_TEMPLATE.format(
            project_id=PROJECT_ID,
            github_repo=REPO,
            workspace_path=_yaml_string(_workspace_path(tmp_path)),
            allow_symlinks="false",
            max_changed_files=20,
            content_block=(
                "read_only_workspace_inspection:\n"
                "  enabled: true\n"
                "  max_inspected_files: 20\n"
                "  allow_protected_paths: true\n"
            ),
        ),
        encoding="utf-8",
    )

    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, project_config=config_path)

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert "read_only_workspace_content" in captured.err
    assert captured.out.strip() == ""


# -- 16..25. gate ordering, fail closed ----------------------------------------


@pytest.mark.parametrize(
    ("apply_flag", "read_flag", "expected"),
    [
        (False, True, "--apply-approved-plan"),
        (True, False, "--read-contents"),
        (False, False, "--apply-approved-plan"),
    ],
)
def test_missing_flags_fail_before_any_file_is_read(
    tmp_path, monkeypatch, apply_flag, read_flag, expected
):
    _make_workspace(tmp_path)
    config_path = _write_config(tmp_path)
    artifact_path = _write_artifact(tmp_path)
    read: list[str] = []
    _track_read_text(monkeypatch, read)

    result = _invoke(config_path, artifact_path, apply_flag=apply_flag, read_flag=read_flag)

    assert result.exit_code == 1
    assert expected in result.stderr
    assert result.stdout.strip() == ""
    # Nothing at all was read: not the artifact, and not even the config.
    assert read == []


@pytest.mark.parametrize(
    "overrides", [{"apply_approved_plan": False}, {"read_contents": False}]
)
def test_missing_flags_touch_no_filesystem_entry_point(tmp_path, monkeypatch, overrides):
    config_path = _write_config(tmp_path)
    artifact_path = _write_artifact(tmp_path)
    _detonate_all_filesystem_entry_points(
        monkeypatch, "a missing confirmation flag must fail before any IO"
    )

    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, project_config=config_path, approved_plan=artifact_path, **overrides)

    assert excinfo.value.exit_code == 1


def test_disabled_config_fails_before_the_artifact_is_read(tmp_path, monkeypatch):
    _make_workspace(tmp_path)
    config_path = _write_config(tmp_path, enabled=False)
    artifact_path = _write_artifact(tmp_path)
    read: list[str] = []
    _track_read_text(monkeypatch, read)

    result = _invoke(config_path, artifact_path)

    assert result.exit_code == 1
    assert "does not enable read-only workspace content reads" in result.stderr
    assert result.stdout.strip() == ""
    # The config was read; the artifact was not.
    assert read == [str(config_path)]


def test_absent_config_block_also_blocks(tmp_path, capsys):
    _make_workspace(tmp_path)
    config_path = _write_config(tmp_path, include_content_block=False)

    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, project_config=config_path)

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert "read_only_workspace_content" in captured.err
    assert captured.out.strip() == ""


def test_disabled_config_touches_no_workspace_path(tmp_path, monkeypatch, capsys):
    workspace = _make_workspace(tmp_path)
    config_path = _write_config(tmp_path, enabled=False)
    artifact_path = _write_artifact(tmp_path)
    touched: list[str] = []
    _track_filesystem(monkeypatch, touched)

    with pytest.raises(typer.Exit):
        _run(tmp_path, project_config=config_path, approved_plan=artifact_path)

    capsys.readouterr()
    for path in touched:
        assert str(workspace) not in path


def test_approved_plan_inside_workspace_is_rejected_before_it_is_read(
    tmp_path, monkeypatch
):
    workspace = _make_workspace(tmp_path)
    config_path = _write_config(tmp_path)
    inside = workspace / "approved_plan.json"
    inside.write_text(
        json.dumps(_artifact()) + "\nSENTINEL_WORKSPACE_ARTIFACT_CONTENT",
        encoding="utf-8",
    )
    read: list[str] = []
    _track_read_text(monkeypatch, read)

    result = _invoke(config_path, inside)

    assert result.exit_code == 1
    assert "is inside the project's configured repo.workspace_path" in result.stderr
    assert result.stdout.strip() == ""
    assert read == [str(config_path)]
    assert "SENTINEL_WORKSPACE_ARTIFACT_CONTENT" not in result.output


def test_approved_plan_in_a_workspace_subdirectory_is_also_rejected(tmp_path, capsys):
    workspace = _make_workspace(tmp_path)
    config_path = _write_config(tmp_path)
    inside = workspace / "src" / "approved_plan.json"
    inside.write_text(json.dumps(_artifact()), encoding="utf-8")

    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, project_config=config_path, approved_plan=inside)

    assert excinfo.value.exit_code == 1
    assert capsys.readouterr().out.strip() == ""


@pytest.mark.parametrize(
    "text", ["not json at all", '{"approval": ', "```json\n{}\n```", "[]", ""]
)
def test_artifact_parse_failure_fails_before_any_workspace_touch(
    tmp_path, monkeypatch, capsys, text
):
    workspace = _make_workspace(tmp_path)
    config_path = _write_config(tmp_path)
    artifact_path = _write_artifact(tmp_path, text)
    touched: list[str] = []
    _track_filesystem(monkeypatch, touched)

    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, project_config=config_path, approved_plan=artifact_path)

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert "ApprovedPlanParseError" in captured.err
    assert captured.out.strip() == ""
    for path in touched:
        assert str(workspace) not in path


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(lambda a: a.pop("approval"), id="approval-missing"),
        pytest.param(
            lambda a: a["approval"].update(approval_text="I approve this plan"),
            id="paraphrased-approval",
        ),
        pytest.param(
            lambda a: a["approval"].update(source="automatic"), id="non-manual-source"
        ),
        pytest.param(
            lambda a: a["plan"].update(automation_level="L2"), id="escalated-plan"
        ),
        pytest.param(
            lambda a: a["plan"].update(approval=copy.deepcopy(VALID_APPROVAL)),
            id="forged-approval-inside-plan",
        ),
    ],
)
def test_artifact_validation_failure_fails_before_any_workspace_touch(
    tmp_path, monkeypatch, capsys, mutate
):
    workspace = _make_workspace(tmp_path)
    config_path = _write_config(tmp_path)
    artifact = _artifact()
    mutate(artifact)
    artifact_path = _write_artifact(tmp_path, artifact)
    touched: list[str] = []
    _track_filesystem(monkeypatch, touched)

    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, project_config=config_path, approved_plan=artifact_path)

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert "ApprovedPlanValidationError" in captured.err
    assert captured.out.strip() == ""
    for path in touched:
        assert str(workspace) not in path


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"project_id": "a_different_project"}, "Mismatch in project_id"),
        ({"github_repo": "someone-else/widgets"}, "Mismatch in repo"),
        ({"github_repo": REPO.upper()}, "Mismatch in repo"),
    ],
)
def test_identity_mismatch_fails_before_any_workspace_touch(
    tmp_path, monkeypatch, capsys, kwargs, expected
):
    workspace = _make_workspace(tmp_path)
    config_path = _write_config(tmp_path, **kwargs)
    touched: list[str] = []
    _track_filesystem(monkeypatch, touched)

    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, project_config=config_path)

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert expected in captured.err
    assert captured.out.strip() == ""
    for path in touched:
        assert str(workspace) not in path


def test_too_many_candidates_for_max_files_fails_before_workspace_touch(
    tmp_path, monkeypatch, capsys
):
    workspace = _make_workspace(tmp_path)
    config_path = _write_config(tmp_path, max_files=2)
    artifact_path = _write_artifact(
        tmp_path, _artifact(["src/a.py", "src/b.py", "src/c.py"])
    )
    touched: list[str] = []
    _track_filesystem(monkeypatch, touched)

    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, project_config=config_path, approved_plan=artifact_path)

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert "read_only_workspace_content.max_files" in captured.err
    assert captured.out.strip() == ""
    for path in touched:
        assert str(workspace) not in path


def test_too_many_candidates_for_max_changed_files_fails_before_workspace_touch(
    tmp_path, monkeypatch, capsys
):
    workspace = _make_workspace(tmp_path)
    config_path = _write_config(tmp_path, max_files=50, max_changed_files=2)
    artifact_path = _write_artifact(
        tmp_path, _artifact(["src/a.py", "src/b.py", "src/c.py"])
    )
    touched: list[str] = []
    _track_filesystem(monkeypatch, touched)

    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, project_config=config_path, approved_plan=artifact_path)

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert "max_changed_files" in captured.err
    assert captured.out.strip() == ""
    for path in touched:
        assert str(workspace) not in path


@pytest.mark.parametrize(
    ("candidate", "expected"),
    [
        pytest.param("secrets/creds.env", "forbidden", id="forbidden"),
        pytest.param("docs/README.md", "unlisted", id="unlisted"),
        pytest.param("../outside.py", "forbidden", id="escaping"),
        pytest.param("Q:/somewhere_else/other.py", "forbidden", id="absolute-outside"),
    ],
)
def test_lexical_policy_failures_happen_before_any_workspace_touch(
    tmp_path, monkeypatch, capsys, candidate, expected
):
    _make_workspace(tmp_path)
    config_path = _write_config(tmp_path)
    artifact_path = _write_artifact(tmp_path, _artifact([candidate]))
    _detonate_all_filesystem_entry_points(
        monkeypatch, "a lexical policy refusal must precede any workspace touch"
    )

    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, project_config=config_path, approved_plan=artifact_path)

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert "path policy refuses to read" in captured.err
    assert expected in captured.err
    assert captured.out.strip() == ""


def test_one_refused_path_abandons_the_whole_run(tmp_path, monkeypatch, capsys):
    """A plan naming one forbidden path gets no partial read of the rest."""
    _make_workspace(tmp_path)
    config_path = _write_config(tmp_path)
    artifact_path = _write_artifact(tmp_path, _artifact(["src/mod.py", "secrets/creds.env"]))
    _detonate_all_filesystem_entry_points(
        monkeypatch, "no candidate may be read once any candidate is refused"
    )

    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, project_config=config_path, approved_plan=artifact_path)

    assert excinfo.value.exit_code == 1
    assert capsys.readouterr().out.strip() == ""


def test_protected_path_is_refused_unless_allow_protected_paths(
    tmp_path, monkeypatch, capsys
):
    _make_workspace(tmp_path)
    config_path = _write_config(tmp_path, allow_protected_paths=False)
    artifact_path = _write_artifact(tmp_path, _artifact(["src/protected/secret_ish.py"]))
    _detonate_all_filesystem_entry_points(
        monkeypatch, "a protected refusal must precede any workspace touch"
    )

    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, project_config=config_path, approved_plan=artifact_path)

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert "allow_protected_paths" in captured.err
    assert captured.out.strip() == ""


def test_protected_path_is_read_only_when_explicitly_allowed(tmp_path, capsys):
    _make_workspace(tmp_path)
    config_path = _write_config(tmp_path, allow_protected_paths=True)
    artifact_path = _write_artifact(tmp_path, _artifact(["src/protected/secret_ish.py"]))

    payload = _payload(
        tmp_path, capsys, project_config=config_path, approved_plan=artifact_path
    )

    item = _items(payload)[0]
    assert item["original_plan_path"] == "src/protected/secret_ish.py"
    assert item["status"] == "read"
    assert item["content_text"] == "x = 2\n"


# -- 26..38. the success path, bounded ------------------------------------------


def test_small_utf8_file_is_read_and_reported_in_full(tmp_path, capsys):
    workspace = _make_workspace(tmp_path)
    expected_size = (workspace / "src" / "mod.py").stat().st_size

    payload = _payload(tmp_path, capsys)

    content = payload["workspace_content"]
    assert content["candidate_source"] == "approved_plan.files_likely_to_change"
    assert content["file_contents_read"] is True
    assert content["directories_listed"] is False
    assert content["commands_run"] is False
    assert content["model_called"] is False
    assert content["diffs_generated"] is False
    assert content["files_edited"] is False
    assert content["total_bytes_read"] == expected_size
    assert content["items"] == [
        {
            "original_plan_path": "src/mod.py",
            "canonical_relative_path": "src/mod.py",
            "status": "read",
            "kind": "file",
            "size_bytes": expected_size,
            "bytes_read": expected_size,
            "encoding": "utf-8",
            "redacted": False,
            "redaction_count": 0,
            "redaction_kinds": [],
            "content_text": MOD_TEXT,
        }
    ]

    notice = payload["notice"]
    assert "READ-ONLY FILE-CONTENT INSPECTION ONLY" in notice
    for claim in (
        "no files were edited",
        "no diffs were generated",
        "no commands were run",
        "no model was called",
    ):
        assert claim in notice

    approved = payload["approved_plan"]
    assert approved["approved_by"] == APPROVER
    assert approved["approved_at"] == APPROVED_AT
    assert approved["source"] == "manual"
    assert approved["plan_engine"] == "real-model"
    assert approved["real_call"] is True
    assert approved["model"] == PLAN_MODEL
    assert approved["issue_number"] == ISSUE_NUMBER
    assert approved["title"] == TITLE

    assert "Phase 5E2" in payload["next_authorization_required"]


def test_multiple_files_are_read_in_plan_order(tmp_path, capsys):
    _make_workspace(tmp_path)
    config_path = _write_config(tmp_path)
    artifact_path = _write_artifact(
        tmp_path, _artifact(["tests/test_mod.py", "src/mod.py"])
    )

    payload = _payload(
        tmp_path, capsys, project_config=config_path, approved_plan=artifact_path
    )

    items = _items(payload)
    assert [item["original_plan_path"] for item in items] == [
        "tests/test_mod.py",
        "src/mod.py",
    ]
    assert [item["content_text"] for item in items] == [TEST_MOD_TEXT, MOD_TEXT]
    assert payload["workspace_content"]["total_bytes_read"] == sum(
        item["bytes_read"] for item in items
    )


def test_duplicate_candidates_are_deduplicated_preserving_order(tmp_path, capsys):
    _make_workspace(tmp_path)
    config_path = _write_config(tmp_path)
    artifact_path = _write_artifact(
        tmp_path,
        _artifact(
            [
                "tests/test_mod.py",
                "src/mod.py",
                "tests/test_mod.py",
                "src/mod.py",
                "src/absent.py",
            ]
        ),
    )

    payload = _payload(
        tmp_path, capsys, project_config=config_path, approved_plan=artifact_path
    )

    assert [item["original_plan_path"] for item in _items(payload)] == [
        "tests/test_mod.py",
        "src/mod.py",
        "src/absent.py",
    ]


def test_missing_file_reports_missing_and_the_run_continues(tmp_path, capsys):
    _make_workspace(tmp_path)
    config_path = _write_config(tmp_path)
    artifact_path = _write_artifact(tmp_path, _artifact(["src/absent.py", "src/mod.py"]))

    payload = _payload(
        tmp_path, capsys, project_config=config_path, approved_plan=artifact_path
    )

    items = _items(payload)
    assert items[0] == {
        "original_plan_path": "src/absent.py",
        "canonical_relative_path": None,
        "status": "missing",
        "kind": None,
        "size_bytes": None,
        "bytes_read": 0,
        "encoding": None,
        "redacted": False,
        "redaction_count": 0,
        "redaction_kinds": [],
        "content_text": None,
    }
    assert items[1]["status"] == "read"


def test_directory_candidate_reports_no_content_and_is_not_listed(
    tmp_path, monkeypatch, capsys
):
    _make_workspace(tmp_path)
    config_path = _write_config(tmp_path)
    artifact_path = _write_artifact(tmp_path, _artifact(["src/pkg", "src/mod.py"]))

    def _blocked(*args, **kwargs):
        raise AssertionError("a directory candidate must never be listed")

    monkeypatch.setattr(os, "listdir", _blocked)
    monkeypatch.setattr(os, "scandir", _blocked)
    monkeypatch.setattr(os, "walk", _blocked)

    payload = _payload(
        tmp_path, capsys, project_config=config_path, approved_plan=artifact_path
    )

    directory = _items(payload)[0]
    assert directory["status"] == "directory_no_content"
    assert directory["kind"] == "directory"
    assert directory["canonical_relative_path"] == "src/pkg"
    assert directory["content_text"] is None
    assert directory["bytes_read"] == 0
    # Neither the name nor the content of the file inside it appears anywhere.
    serialized = json.dumps(payload)
    assert "__init__" not in serialized
    assert "SENTINEL_INSIDE_A_DIRECTORY" not in serialized


def test_file_over_the_per_file_cap_reports_too_large_and_is_not_read(tmp_path, capsys):
    workspace = _make_workspace(tmp_path)
    _write_source(workspace / "src" / "big.py", "B" * 200)
    config_path = _write_config(tmp_path, max_file_bytes=50)
    artifact_path = _write_artifact(tmp_path, _artifact(["src/big.py", "src/mod.py"]))

    payload = _payload(
        tmp_path, capsys, project_config=config_path, approved_plan=artifact_path
    )

    big, small = _items(payload)
    assert big["status"] == "too_large"
    assert big["size_bytes"] == 200
    assert big["bytes_read"] == 0
    assert big["content_text"] is None
    # The run continues, and the oversize file's bytes are not in the total.
    assert small["status"] == "read"
    assert payload["workspace_content"]["total_bytes_read"] == small["bytes_read"]
    assert "BBBB" not in capsys.readouterr().out


def test_total_byte_cap_skips_later_files_unread(tmp_path, capsys):
    workspace = _make_workspace(tmp_path)
    _write_source(workspace / "src" / "first.py", "A" * 40)
    _write_source(workspace / "src" / "second.py", "C" * 40)
    config_path = _write_config(tmp_path, max_file_bytes=100, max_total_bytes=60)
    artifact_path = _write_artifact(
        tmp_path, _artifact(["src/first.py", "src/second.py"])
    )

    payload = _payload(
        tmp_path, capsys, project_config=config_path, approved_plan=artifact_path
    )

    first, second = _items(payload)
    assert first["status"] == "read"
    assert first["bytes_read"] == 40
    assert second["status"] == "skipped_total_limit"
    assert second["size_bytes"] == 40
    assert second["bytes_read"] == 0
    assert second["content_text"] is None
    assert payload["workspace_content"]["total_bytes_read"] == 40
    assert "CCCC" not in capsys.readouterr().out


def test_a_file_holding_a_nul_byte_reports_binary_and_is_not_printed(tmp_path, capsys):
    workspace = _make_workspace(tmp_path)
    (workspace / "src" / "blob.py").write_bytes(b"SENTINEL_BINARY\x00\x01\x02payload")
    config_path = _write_config(tmp_path)
    artifact_path = _write_artifact(tmp_path, _artifact(["src/blob.py", "src/mod.py"]))

    payload = _payload(
        tmp_path, capsys, project_config=config_path, approved_plan=artifact_path
    )

    blob, small = _items(payload)
    assert blob["status"] == "binary_or_non_utf8"
    assert blob["kind"] == "file"
    assert blob["bytes_read"] == 0
    assert blob["encoding"] is None
    assert blob["content_text"] is None
    assert small["status"] == "read"
    assert "SENTINEL_BINARY" not in json.dumps(payload)


def test_non_utf8_bytes_report_binary_and_are_not_printed(tmp_path, capsys):
    workspace = _make_workspace(tmp_path)
    # Valid latin-1, invalid UTF-8, and no NUL: the decode is what refuses it.
    (workspace / "src" / "latin.py").write_bytes(b"caf\xe9 = 1\n")
    config_path = _write_config(tmp_path)
    artifact_path = _write_artifact(tmp_path, _artifact(["src/latin.py"]))

    payload = _payload(
        tmp_path, capsys, project_config=config_path, approved_plan=artifact_path
    )

    item = _items(payload)[0]
    assert item["status"] == "binary_or_non_utf8"
    assert item["content_text"] is None
    assert payload["workspace_content"]["total_bytes_read"] == 0
    assert "caf" not in json.dumps(payload)


def test_an_empty_candidate_list_succeeds_and_touches_nothing(
    tmp_path, monkeypatch, capsys
):
    _make_workspace(tmp_path)
    config_path = _write_config(tmp_path)
    artifact_path = _write_artifact(tmp_path, _artifact([]))
    touched: list[str] = []
    _track_filesystem(monkeypatch, touched)

    _run(tmp_path, project_config=config_path, approved_plan=artifact_path)

    payload = json.loads(capsys.readouterr().out)
    assert _items(payload) == []
    assert payload["workspace_content"]["total_bytes_read"] == 0
    assert "no files_likely_to_change" in payload["workspace_content"]["note"]
    for path in touched:
        assert str(_workspace_path(tmp_path)) not in path


def test_only_files_likely_to_change_are_read(tmp_path, monkeypatch, capsys):
    """Prose fields and the out-of-scope list are never treated as paths."""
    workspace = _make_workspace(tmp_path)
    # Create real files at the prose-marker paths, so "was it opened" is a
    # question about the command's choices and not about what exists.
    for marker in (STEP_MARKER, VERIFICATION_MARKER, RISK_MARKER, QUESTION_MARKER,
                   OUT_OF_SCOPE_MARKER):
        _write_source(workspace / marker, "SENTINEL_NEVER_READ = 1\n")

    opened: list[str] = []
    real_open = builtins.open

    def tracking_open(file, *args, **kwargs):
        opened.append(str(file))
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", tracking_open)

    _run(tmp_path)
    stdout = capsys.readouterr().out
    payload = json.loads(stdout)

    assert payload["workspace_content"]["candidate_source"] == (
        "approved_plan.files_likely_to_change"
    )
    assert [item["original_plan_path"] for item in _items(payload)] == ["src/mod.py"]

    for marker in (STEP_MARKER, VERIFICATION_MARKER, RISK_MARKER, QUESTION_MARKER,
                   OUT_OF_SCOPE_MARKER):
        leaf = marker.rsplit("/", 1)[-1]
        for path in opened:
            assert leaf not in path
        assert marker not in stdout
    assert "SENTINEL_NEVER_READ" not in stdout

    # The only workspace file opened is the one the plan actually listed.
    workspace_opens = [path for path in opened if str(workspace) in path]
    assert len(workspace_opens) == 1
    assert "mod.py" in workspace_opens[0]


def test_required_verification_is_neither_printed_nor_executed(
    tmp_path, monkeypatch, capsys
):
    _make_workspace(tmp_path)

    def _blocked(*args, **kwargs):
        raise AssertionError("l2-read-workspace-files must never execute a command")

    monkeypatch.setattr(subprocess, "Popen", _blocked)
    monkeypatch.setattr(subprocess, "run", _blocked)
    monkeypatch.setattr(os, "system", _blocked)

    _run(tmp_path)

    stdout = capsys.readouterr().out
    assert "required_verification" not in stdout
    assert VERIFICATION_MARKER not in stdout
    assert "pytest" not in stdout


def test_output_omits_workspace_path_absolute_paths_and_secrets(tmp_path, capsys):
    workspace = _make_workspace(tmp_path)

    _run(tmp_path)
    stdout = capsys.readouterr().out
    payload = json.loads(stdout)

    assert set(payload) == {
        "notice",
        "mode",
        "project",
        "approved_plan",
        "workspace_content",
        "next_authorization_required",
    }

    # No configured workspace path, and no resolved absolute path of any kind.
    assert str(workspace) not in stdout
    assert WORKSPACE_DIRNAME not in stdout
    assert str(tmp_path) not in stdout
    assert "workspace_path" not in stdout
    assert "resolved" not in stdout

    # No raw artifact, no approval text, no credentials, no diff, no command.
    assert REQUIRED_APPROVAL_TEXT not in stdout
    assert "approval_text" not in stdout
    assert "plan_provenance" not in stdout
    for absent in ("api_key", "AIDO_LITELLM", "http://", "https://", "Bearer ",
                   "prompt", "completion", "@@ -", "--- a/", "+++ b/"):
        assert absent not in stdout

    # File content appears in exactly one place.
    assert stdout.count(json.dumps(MOD_TEXT)) == 1
    assert _items(payload)[0]["content_text"] == MOD_TEXT


def test_success_through_the_cli_matches_the_helper(tmp_path):
    _make_workspace(tmp_path)
    config_path = _write_config(tmp_path)
    artifact_path = _write_artifact(tmp_path)

    result = _invoke(config_path, artifact_path)

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["mode"] == "l2-read-workspace-files"
    assert _items(payload)[0]["content_text"] == MOD_TEXT


# -- 39..43. redaction ----------------------------------------------------------


SECRET_SOURCE = (
    "headers = {'Authorization': 'Bearer abc123DEF456ghi'}\n"
    "API_KEY=super-hunter-value\n"
    'password: "hunter2"\n'
    'client = make_client("sk-ABCDEFGH12345678")\n'
)


@pytest.mark.parametrize(
    ("text", "secret", "expected_kind"),
    [
        pytest.param(
            "Authorization: Bearer abc123DEF456ghi",
            "abc123DEF456ghi",
            "bearer_token",
            id="bearer",
        ),
        pytest.param("API_KEY=abc123secretvalue", "abc123secretvalue",
                     "secret_assignment", id="api-key-assignment"),
        pytest.param("MY_API_KEY = abc123secretvalue", "abc123secretvalue",
                     "secret_assignment", id="prefixed-api-key"),
        pytest.param('token = "abc123secretvalue"', "abc123secretvalue",
                     "secret_assignment", id="token-assignment"),
        pytest.param("password: abc123secretvalue", "abc123secretvalue",
                     "secret_assignment", id="password-assignment"),
        pytest.param("passwd=abc123secretvalue", "abc123secretvalue",
                     "secret_assignment", id="passwd-assignment"),
        pytest.param("pwd: abc123secretvalue", "abc123secretvalue",
                     "secret_assignment", id="pwd-assignment"),
        pytest.param("secret = abc123secretvalue", "abc123secretvalue",
                     "secret_assignment", id="secret-assignment"),
        pytest.param("use('sk-ABCDEFGH12345678')", "sk-ABCDEFGH12345678",
                     "openai_style_key", id="openai-style-key"),
    ],
)
def test_the_redaction_helper_blanks_each_pattern(text, secret, expected_kind):
    redacted, kinds = cli._redact_secret_like_text(text)

    assert secret not in redacted
    assert kinds == [expected_kind]
    assert "[REDACTED" in redacted


def test_the_redaction_helper_keeps_the_key_and_the_quotes():
    redacted, _ = cli._redact_secret_like_text('password: "hunter2"\ntoken = plain\n')

    assert redacted == 'password: "[REDACTED]"\ntoken = [REDACTED]\n'


def test_the_redaction_helper_leaves_ordinary_text_alone():
    text = "def total(items):\n    return sum(items)  # no secrets here\n"

    redacted, kinds = cli._redact_secret_like_text(text)

    assert redacted == text
    assert kinds == []


def test_read_content_is_redacted_and_the_redaction_is_reported(tmp_path, capsys):
    workspace = _make_workspace(tmp_path)
    _write_source(workspace / "src" / "creds.py", SECRET_SOURCE)
    config_path = _write_config(tmp_path)
    artifact_path = _write_artifact(tmp_path, _artifact(["src/creds.py"]))

    _run(tmp_path, project_config=config_path, approved_plan=artifact_path)
    stdout = capsys.readouterr().out
    item = _items(json.loads(stdout))[0]

    assert item["status"] == "read"
    assert item["redacted"] is True
    assert item["redaction_count"] == 4
    assert sorted(item["redaction_kinds"]) == [
        "bearer_token",
        "openai_style_key",
        "secret_assignment",
    ]
    for secret in ("abc123DEF456ghi", "super-hunter-value", "hunter2",
                   "sk-ABCDEFGH12345678"):
        assert secret not in stdout
    assert "[REDACTED]" in item["content_text"]
    assert "[REDACTED_API_KEY]" in item["content_text"]
    # Structure around the secrets survives, so the read is still useful.
    assert "API_KEY=" in item["content_text"]


def test_a_clean_file_reports_no_redaction(tmp_path, capsys):
    _make_workspace(tmp_path)

    item = _items(_payload(tmp_path, capsys))[0]

    assert item["redacted"] is False
    assert item["redaction_count"] == 0
    assert item["redaction_kinds"] == []


def test_no_configuration_can_disable_redaction(tmp_path):
    # There is no field for it on the model...
    assert not [
        name for name in ReadOnlyWorkspaceContentConfig.model_fields
        if "redact" in name or "raw" in name
    ]
    for bad in ({"redaction": False}, {"redact": False}, {"allow_raw_content": True},
                {"disable_redaction": True}):
        with pytest.raises(Exception):
            ReadOnlyWorkspaceContentConfig(enabled=True, **bad)

    # ...and no flag for it on the command.
    result = runner.invoke(app, ["l2-read-workspace-files", "--help"])
    assert result.exit_code == 0
    for absent in ("--no-redact", "--raw", "--redact", "--unredacted"):
        assert absent not in result.output


# -- 44..48. canonical guard and policy integration -----------------------------


def test_the_canonical_guard_is_used_for_every_existing_candidate(
    tmp_path, monkeypatch, capsys
):
    import ai_dev_orchestrator.workspace as workspace_pkg

    calls: list[tuple] = []
    real_guard = workspace_pkg.canonicalize_existing_path_under_workspace

    def spying_guard(root, candidate, **kwargs):
        calls.append((str(root), str(candidate), kwargs))
        return real_guard(root, candidate, **kwargs)

    monkeypatch.setattr(
        workspace_pkg, "canonicalize_existing_path_under_workspace", spying_guard
    )

    workspace = _make_workspace(tmp_path)
    config_path = _write_config(tmp_path)
    artifact_path = _write_artifact(tmp_path, _artifact(["src/mod.py", "tests/test_mod.py"]))

    _run(tmp_path, project_config=config_path, approved_plan=artifact_path)
    capsys.readouterr()

    # The root is proven first, then each candidate — every call against the
    # configured workspace root and nothing else.
    assert [candidate for _root, candidate, _kwargs in calls] == [
        str(workspace),
        "src/mod.py",
        "tests/test_mod.py",
    ]
    for root, _candidate, _kwargs in calls:
        assert root == str(workspace)


@pytest.mark.parametrize("allow_symlinks", [False, True])
def test_the_projects_allow_symlinks_setting_is_passed_to_the_guard(
    tmp_path, monkeypatch, capsys, allow_symlinks
):
    import ai_dev_orchestrator.workspace as workspace_pkg

    seen: list[dict] = []
    real_guard = workspace_pkg.canonicalize_existing_path_under_workspace

    def spying_guard(root, candidate, **kwargs):
        seen.append(kwargs)
        return real_guard(root, candidate, **kwargs)

    monkeypatch.setattr(
        workspace_pkg, "canonicalize_existing_path_under_workspace", spying_guard
    )

    _make_workspace(tmp_path)
    config_path = _write_config(tmp_path, allow_symlinks=allow_symlinks)

    payload = _payload(tmp_path, capsys, project_config=config_path)

    assert seen and all(kwargs == {"allow_symlinks": allow_symlinks} for kwargs in seen)
    assert payload["project"]["workspace_policy"]["allow_symlinks"] is allow_symlinks


def test_symlink_inside_the_workspace_is_rejected_when_symlinks_are_disallowed(
    tmp_path, capsys
):
    workspace = _make_workspace(tmp_path)
    try_symlink(workspace / "src" / "link.py", workspace / "src" / "mod.py")
    config_path = _write_config(tmp_path, allow_symlinks=False)
    artifact_path = _write_artifact(tmp_path, _artifact(["src/link.py"]))

    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, project_config=config_path, approved_plan=artifact_path)

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert "CanonicalPathSymlinkError" in captured.err
    assert captured.out.strip() == ""
    assert MOD_TEXT.strip() not in captured.err


def test_symlink_pointing_outside_the_workspace_is_rejected_even_when_allowed(
    tmp_path, capsys
):
    workspace = _make_workspace(tmp_path)
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    _write_source(outside / "other.py", "SENTINEL_OUTSIDE_CONTENT\n")
    try_symlink(workspace / "src" / "escape.py", outside / "other.py")
    config_path = _write_config(tmp_path, allow_symlinks=True)
    artifact_path = _write_artifact(tmp_path, _artifact(["src/escape.py"]))

    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, project_config=config_path, approved_plan=artifact_path)

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert "CanonicalPathContainmentError" in captured.err
    assert captured.out.strip() == ""
    assert "SENTINEL_OUTSIDE_CONTENT" not in captured.err


def test_a_guard_failure_stops_the_whole_run_with_no_stdout(tmp_path, monkeypatch, capsys):
    import ai_dev_orchestrator.workspace as workspace_pkg
    from ai_dev_orchestrator.workspace import (
        CanonicalPathAmbiguityError,
        CanonicalPathContainmentError,
        CanonicalPathResolutionError,
        CanonicalPathSymlinkError,
    )

    _make_workspace(tmp_path)
    config_path = _write_config(tmp_path)
    artifact_path = _write_artifact(tmp_path, _artifact(["src/mod.py", "tests/test_mod.py"]))
    real_guard = workspace_pkg.canonicalize_existing_path_under_workspace

    for error_type in (
        CanonicalPathContainmentError,
        CanonicalPathSymlinkError,
        CanonicalPathAmbiguityError,
        CanonicalPathResolutionError,
    ):

        def failing_guard(root, candidate, *, _error=error_type, **kwargs):
            if str(candidate) == "src/mod.py":
                raise _error("synthetic guard failure")
            return real_guard(root, candidate, **kwargs)

        monkeypatch.setattr(
            workspace_pkg, "canonicalize_existing_path_under_workspace", failing_guard
        )

        with pytest.raises(typer.Exit) as excinfo:
            _run(tmp_path, project_config=config_path, approved_plan=artifact_path)

        assert excinfo.value.exit_code == 1
        captured = capsys.readouterr()
        assert error_type.__name__ in captured.err
        assert "run is abandoned" in captured.err
        assert captured.out.strip() == ""


def test_a_bad_workspace_root_fails_closed_before_any_candidate(tmp_path, capsys):
    """The root is canonicalized first, so a missing workspace stops everything."""
    config_path = _write_config(tmp_path)  # the workspace is never created
    artifact_path = _write_artifact(tmp_path)

    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, project_config=config_path, approved_plan=artifact_path)

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert "repo.workspace_path could not be canonicalized" in captured.err
    assert captured.out.strip() == ""


# -- 49..58. no forbidden behavior ----------------------------------------------


def test_no_directory_is_ever_listed(tmp_path, monkeypatch, capsys):
    _make_workspace(tmp_path)
    config_path = _write_config(tmp_path)
    artifact_path = _write_artifact(
        tmp_path, _artifact(["src/mod.py", "src/pkg", "src/absent.py"])
    )

    def _blocked(*args, **kwargs):
        raise AssertionError("l2-read-workspace-files must never list a directory")

    monkeypatch.setattr(os, "listdir", _blocked)
    monkeypatch.setattr(os, "scandir", _blocked)
    monkeypatch.setattr(os, "walk", _blocked)

    payload = _payload(
        tmp_path, capsys, project_config=config_path, approved_plan=artifact_path
    )

    assert payload["workspace_content"]["directories_listed"] is False


def test_no_command_is_ever_executed(tmp_path, monkeypatch, capsys):
    _make_workspace(tmp_path)

    def _blocked(*args, **kwargs):
        raise AssertionError("l2-read-workspace-files must never execute a command")

    monkeypatch.setattr(subprocess, "Popen", _blocked)
    monkeypatch.setattr(subprocess, "run", _blocked)
    monkeypatch.setattr(os, "system", _blocked)

    payload = _payload(tmp_path, capsys)

    assert payload["workspace_content"]["commands_run"] is False


def test_no_environment_read_no_socket_and_no_model_client(tmp_path, monkeypatch, capsys):
    """The content read happens, and nothing goes anywhere near a model."""
    import ai_dev_orchestrator.llm.client as llm_client
    import ai_dev_orchestrator.llm.config as llm_config

    _make_workspace(tmp_path)

    def _blocked(*args, **kwargs):
        raise AssertionError("l2-read-workspace-files must not read env, network, or models")

    monkeypatch.setattr(os, "getenv", _blocked)
    monkeypatch.setattr(os.environ, "get", _blocked)
    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket, "getaddrinfo", _blocked)
    monkeypatch.setattr(socket, "gethostbyname", _blocked)
    monkeypatch.setattr(llm_client.LLMClient, "__init__", _blocked)
    monkeypatch.setattr(llm_config, "load_llm_client_config_from_env", _blocked)
    monkeypatch.setattr(cli, "_build_real_llm_client", _blocked)
    monkeypatch.setattr(cli, "_read_real_llm_env", _blocked)

    payload = _payload(tmp_path, capsys)

    assert payload["mode"] == "l2-read-workspace-files"
    assert payload["workspace_content"]["model_called"] is False
    # The file really was read while every model/network door was detonated.
    assert _items(payload)[0]["content_text"] == MOD_TEXT


def test_no_github_fetch_or_write(tmp_path, monkeypatch, capsys):
    import ai_dev_orchestrator.github.client as github_client

    _make_workspace(tmp_path)

    def _blocked(*args, **kwargs):
        raise AssertionError("l2-read-workspace-files must not contact GitHub")

    monkeypatch.setattr(github_client.GitHubClient, "__init__", _blocked)
    monkeypatch.setattr(github_client.GitHubClient, "get_issue", _blocked)

    payload = _payload(tmp_path, capsys)

    assert payload["mode"] == "l2-read-workspace-files"


def _snapshot(root: Path) -> dict[str, bytes | None]:
    return {
        str(path.relative_to(root)): (path.read_bytes() if path.is_file() else None)
        for path in sorted(root.rglob("*"))
    }


def test_nothing_in_the_workspace_or_tmp_path_is_created_or_modified(tmp_path, capsys):
    workspace = _make_workspace(tmp_path)
    _write_source(workspace / "src" / "creds.py", SECRET_SOURCE)
    config_path = _write_config(tmp_path)
    artifact_path = _write_artifact(tmp_path, _artifact(["src/mod.py", "src/creds.py"]))
    before_workspace = _snapshot(workspace)
    before_tmp = _snapshot(tmp_path)

    _run(tmp_path, project_config=config_path, approved_plan=artifact_path)

    capsys.readouterr()
    # Redaction happens in memory on the way to stdout; the file on disk keeps
    # its original bytes, secrets and all.
    assert _snapshot(workspace) == before_workspace
    assert _snapshot(tmp_path) == before_tmp


def test_no_artifact_is_written_and_no_approval_is_stamped(tmp_path, capsys):
    _make_workspace(tmp_path)
    config_path = _write_config(tmp_path)
    artifact_path = _write_artifact(tmp_path)
    artifact_before = artifact_path.read_text(encoding="utf-8")

    _run(tmp_path, project_config=config_path, approved_plan=artifact_path)

    capsys.readouterr()
    assert artifact_path.read_text(encoding="utf-8") == artifact_before
    # And there is no command that would stamp one.
    for absent in ("approve-plan", "stamp-approval", "apply-approved-plan"):
        assert runner.invoke(app, [absent, "--help"]).exit_code != 0


def test_no_diff_is_generated(tmp_path, capsys):
    workspace = _make_workspace(tmp_path)
    _write_source(workspace / "src" / "other.py", "value = 2\n")
    config_path = _write_config(tmp_path)
    artifact_path = _write_artifact(tmp_path, _artifact(["src/mod.py", "src/other.py"]))

    _run(tmp_path, project_config=config_path, approved_plan=artifact_path)
    stdout = capsys.readouterr().out
    payload = json.loads(stdout)

    assert payload["workspace_content"]["diffs_generated"] is False
    assert payload["workspace_content"]["files_edited"] is False
    for marker in ("@@ -", "--- a/", "+++ b/", "diff --git", "index 0000"):
        assert marker not in stdout
    # No item carries a before/after pair or any patch-shaped field.
    for item in _items(payload):
        assert set(item) == {
            "original_plan_path",
            "canonical_relative_path",
            "status",
            "kind",
            "size_bytes",
            "bytes_read",
            "encoding",
            "redacted",
            "redaction_count",
            "redaction_kinds",
            "content_text",
        }


def test_the_command_reads_exactly_the_config_the_artifact_and_the_candidates(
    tmp_path, monkeypatch, capsys
):
    workspace = _make_workspace(tmp_path)
    config_path = _write_config(tmp_path)
    artifact_path = _write_artifact(tmp_path, _artifact(["src/mod.py", "tests/test_mod.py"]))

    text_reads: list[str] = []
    opened: list[str] = []
    _track_read_text(monkeypatch, text_reads)
    real_open = builtins.open

    def tracking_open(file, *args, **kwargs):
        opened.append(str(file))
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", tracking_open)

    _run(tmp_path, project_config=config_path, approved_plan=artifact_path)
    capsys.readouterr()

    # Two text reads, in order, both named on the command line.
    assert text_reads == [str(config_path), str(artifact_path)]
    # And every file opened as bytes is one of the approved candidates.
    assert [Path(path).name for path in opened] == ["mod.py", "test_mod.py"]
    for path in opened:
        assert str(workspace) in path


def _command_source() -> str:
    return "".join(
        inspect.getsource(obj)
        for obj in (
            cli._run_l2_read_workspace_files,
            cli.l2_read_workspace_files,
            cli._redact_secret_like_text,
            cli._replace_assignment_value,
            cli._read_bounded_bytes,
            cli._decode_utf8_text,
            cli._empty_content_item,
        )
    )


def test_command_source_names_no_client_network_process_or_patch_symbol():
    source = _command_source()

    for forbidden in (
        "httpx",
        "requests",
        "LLMClient",
        "load_llm_client_config_from_env",
        "GitHubClient",
        "subprocess",
        "os.environ",
        "getenv",
        "listdir",
        "scandir",
        "walk(",
        ".glob(",
        "rglob",
        # No diff, patch, apply, or VCS machinery of any kind.
        "difflib",
        "unified_diff",
        "ndiff",
        "@@ -",
        "apply_patch",
        "apply-patch",
        "build_deterministic_patch_proposal",
        "git commit",
        "git push",
        "write_text",
        "write_bytes",
    ):
        assert forbidden not in source, forbidden

    # The only text read is the approved-plan artifact, which lives outside the
    # workspace by construction (gate 5); workspace files are opened as bytes
    # through exactly one bounded helper.
    assert source.count("read_text(") == 1
    assert "approved_plan.read_text(" in source
    assert source.count("open(") == 1


def test_the_canonical_guard_is_imported_lazily_not_at_module_import():
    assert not hasattr(cli, "canonicalize_existing_path_under_workspace")
    assert "canonicalize_existing_path_under_workspace" in inspect.getsource(
        cli._run_l2_read_workspace_files
    )


def test_no_real_target_workspace_is_named_anywhere_in_this_phase():
    """Neither the new command nor this test module names a real project.

    Scoped to the Phase 5D2 code rather than all of ``cli.py``: the older
    ``generate-plan`` help text cites this repo's own ``projects/*.yaml.example``
    path, which is a config template checked into this repository, not a target
    workspace.
    """
    # Split literals so this assertion cannot match its own source text.
    forbidden_names = ("mis" "_project", "a8" "_oa", "bible" "_reading_v2")
    sources = {
        "phase 5d2 command": _command_source(),
        "test module": Path(__file__).read_text(encoding="utf-8"),
    }
    for label, source in sources.items():
        for forbidden in forbidden_names:
            assert forbidden not in source, (label, forbidden)

    # And neither names the shared parent root in either separator spelling.
    shared_root = "C:" + "\\" + "dev"
    for label, source in sources.items():
        assert shared_root not in source, label
        assert shared_root.replace("\\", "/") not in source, label


def test_no_other_command_gained_a_content_read_path():
    for command in (
        "generate-plan",
        "generate-model-plan",
        "real-llm-smoke-test",
        "llm-smoke-test",
        "inspect-issue",
        "l2-dry-run",
        "l2-inspect-workspace",
        "generate-patch-proposal",
    ):
        result = runner.invoke(app, [command, "--help"])
        assert result.exit_code == 0
        for absent in ("--read-contents", "--diff", "--apply-patch", "--edit"):
            assert absent not in result.output


def test_existing_commands_still_behave_the_same():
    smoke = runner.invoke(app, ["llm-smoke-test"])
    assert smoke.exit_code == 0
    assert "No real model was called." in smoke.output

    assert runner.invoke(app, ["version"]).exit_code == 0
