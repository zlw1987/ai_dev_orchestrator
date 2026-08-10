"""Phase 5D1 tests: the ``l2-inspect-workspace`` command.

This is the first shipped command that may touch a configured target workspace,
so these tests are organized around *how far* it goes and *where it stops*. It
canonicalizes and stats the paths an approved plan lists under
``files_likely_to_change`` — and that is the entire capability. It reads no file
contents, lists no directory, globs nothing, walks no tree, runs no command,
edits nothing, calls no model, opens no socket, reads no environment variable,
and contacts no GitHub.

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
from ai_dev_orchestrator.models import ProjectConfig, ReadOnlyWorkspaceInspectionConfig

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
# They must never be stat'd and never reach stdout.
STEP_MARKER = "src/sentinel_step_never_a_path.py"
VERIFICATION_MARKER = "src/sentinel_verification_never_a_path.py"
RISK_MARKER = "src/sentinel_risk_never_a_path.py"
QUESTION_MARKER = "src/sentinel_question_never_a_path.py"
OUT_OF_SCOPE_MARKER = "src/sentinel_out_of_scope_never_inspected.py"

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
{inspection_block}"""

INSPECTION_BLOCK = """\
read_only_workspace_inspection:
  enabled: {enabled}
  max_inspected_files: {max_inspected_files}
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


def _make_workspace(tmp_path: Path) -> Path:
    """Create the configured workspace and a few files inside it, under tmp_path."""
    root = _workspace_path(tmp_path)
    (root / "src" / "pkg").mkdir(parents=True)
    (root / "src" / "protected").mkdir(parents=True)
    (root / "tests").mkdir(parents=True)
    (root / "src" / "mod.py").write_text("value = 1\n", encoding="utf-8")
    (root / "src" / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (root / "src" / "protected" / "secret_ish.py").write_text("x = 2\n", encoding="utf-8")
    (root / "tests" / "test_mod.py").write_text("def test_x():\n    pass\n", encoding="utf-8")
    return root


def _write_config(
    tmp_path: Path,
    *,
    project_id: str = PROJECT_ID,
    github_repo: str = REPO,
    enabled: bool = True,
    max_inspected_files: int = 20,
    allow_protected_paths: bool = False,
    allow_symlinks: bool = False,
    max_changed_files: int = 20,
    include_inspection_block: bool = True,
    workspace_path: Path | None = None,
    name: str = "project.yaml",
) -> Path:
    """Write a project config inside the test's own tmp dir."""
    block = ""
    if include_inspection_block:
        block = INSPECTION_BLOCK.format(
            enabled=str(enabled).lower(),
            max_inspected_files=max_inspected_files,
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
            inspection_block=block,
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
        "inspect_workspace": True,
    }
    kwargs.update(overrides)
    return cli._run_l2_inspect_workspace(**kwargs)


def _invoke(config_path, artifact_path, *, apply_flag: bool = True, inspect_flag: bool = True):
    args = [
        "l2-inspect-workspace",
        "--project-config",
        str(config_path),
        "--approved-plan",
        str(artifact_path),
    ]
    if apply_flag:
        args.append("--apply-approved-plan")
    if inspect_flag:
        args.append("--inspect-workspace")
    return runner.invoke(app, args)


def _payload(tmp_path, capsys, **overrides) -> dict:
    _run(tmp_path, **overrides)
    return json.loads(capsys.readouterr().out)


def _track_read_text(monkeypatch, sink: list[str]):
    """Record every ``Path.read_text`` call while still performing it."""
    real_read_text = Path.read_text

    def tracking_read_text(self, *args, **kwargs):
        sink.append(str(self))
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", tracking_read_text)


def _track_filesystem(monkeypatch, sink: list[str]) -> list[str]:
    """Record every path handed to an existence/stat/resolution entry point.

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
        pytest.skip(
            f"platform/user cannot create symlinks ({type(exc).__name__})"
        )


# -- 1..6. CLI surface ---------------------------------------------------------


def test_l2_inspect_workspace_appears_in_root_help():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "l2-inspect-workspace" in result.output


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
    ):
        assert command in result.output


def test_help_exposes_its_options():
    result = runner.invoke(app, ["l2-inspect-workspace", "--help"])

    assert result.exit_code == 0
    for present in (
        "--project-config",
        "--approved-plan",
        "--apply-approved-plan",
        "--inspect-workspace",
        "--format",
    ):
        assert present in result.output


def test_help_hides_forbidden_options():
    result = runner.invoke(app, ["l2-inspect-workspace", "--help"])

    assert result.exit_code == 0
    for absent in (
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
        "--allow-symlinks",
    ):
        assert absent not in result.output

    # Passing one is an error, not a silently ignored argument.
    for rejected in ("--real-model", "--allow-symlinks", "--edit"):
        assert runner.invoke(app, ["l2-inspect-workspace", rejected]).exit_code != 0


def test_l2_dry_run_help_is_unchanged():
    result = runner.invoke(app, ["l2-dry-run", "--help"])

    assert result.exit_code == 0
    for present in ("--project-config", "--approved-plan", "--apply-approved-plan", "--format"):
        assert present in result.output
    # Phase 5D1 did not give the dry run a workspace path of any kind.
    for absent in ("--inspect-workspace", "--allow-symlinks", "--workspace", "--edit"):
        assert absent not in result.output


@pytest.mark.parametrize(
    ("command", "present", "absent"),
    [
        (
            "generate-plan",
            ("--project-config", "--repo", "--issue", "--title", "--body-file", "--format"),
            ("--real-model", "--model", "--approved-plan", "--inspect-workspace"),
        ),
        (
            "generate-model-plan",
            ("--project-config", "--issue", "--title", "--body-file", "--model", "--real-model"),
            ("--approved-plan", "--apply-approved-plan", "--inspect-workspace"),
        ),
        (
            "real-llm-smoke-test",
            ("--project-config", "--model", "--real-model"),
            ("--approved-plan", "--apply-approved-plan", "--inspect-workspace"),
        ),
    ],
)
def test_other_command_help_is_unchanged(command, present, absent):
    result = runner.invoke(app, [command, "--help"])

    assert result.exit_code == 0
    for option in present:
        assert option in result.output
    for option in absent:
        assert option not in result.output


# -- 7..12. the project-level opt-in config block ------------------------------


def test_inspection_block_defaults_to_disabled_when_absent(tmp_path):
    config_path = _write_config(tmp_path, include_inspection_block=False)

    project = load_project_config(config_path)

    assert project.read_only_workspace_inspection.enabled is False
    assert project.read_only_workspace_inspection.max_inspected_files == 20
    assert project.read_only_workspace_inspection.allow_protected_paths is False


def test_allow_protected_paths_defaults_to_false():
    assert ReadOnlyWorkspaceInspectionConfig().allow_protected_paths is False
    assert ReadOnlyWorkspaceInspectionConfig(enabled=True).allow_protected_paths is False


def test_inspection_block_rejects_unknown_fields():
    with pytest.raises(Exception):
        ReadOnlyWorkspaceInspectionConfig(enabled=True, api_key="nope")


@pytest.mark.parametrize("value", [0, -1, 101, 1000])
def test_max_inspected_files_rejects_out_of_range_values(value):
    with pytest.raises(Exception):
        ReadOnlyWorkspaceInspectionConfig(max_inspected_files=value)


@pytest.mark.parametrize("value", ["twenty", 1.5, None])
def test_max_inspected_files_rejects_non_integers(value):
    with pytest.raises(Exception):
        ReadOnlyWorkspaceInspectionConfig(max_inspected_files=value)


def test_max_inspected_files_accepts_the_permitted_range():
    assert ReadOnlyWorkspaceInspectionConfig(max_inspected_files=1).max_inspected_files == 1
    assert ReadOnlyWorkspaceInspectionConfig(max_inspected_files=100).max_inspected_files == 100


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

    assert project.read_only_workspace_inspection.enabled is False


def test_example_yaml_ships_the_block_disabled():
    # Found by pattern rather than named, so this module never spells out a
    # real project's name (see the audit test at the bottom of the file).
    examples = sorted(
        (Path(__file__).resolve().parents[1] / "projects").glob("*.yaml.example")
    )
    assert examples, "no example project config found"
    example = examples[0]

    project = load_project_config(example)

    assert project.read_only_workspace_inspection.enabled is False
    assert project.read_only_workspace_inspection.allow_protected_paths is False
    # And the block is written out explicitly, not merely defaulted.
    assert "read_only_workspace_inspection:" in example.read_text(encoding="utf-8")


def test_enabled_true_permits_the_command_to_continue(tmp_path, capsys):
    _make_workspace(tmp_path)

    payload = _payload(tmp_path, capsys)

    assert payload["mode"] == "l2-inspect-workspace"
    assert payload["project"]["inspection_policy"] == {
        "enabled": True,
        "max_inspected_files": 20,
        "allow_protected_paths": False,
    }


# -- 13..22. gate ordering, fail closed ----------------------------------------


@pytest.mark.parametrize(
    ("apply_flag", "inspect_flag", "expected"),
    [
        (False, True, "--apply-approved-plan"),
        (True, False, "--inspect-workspace"),
        (False, False, "--apply-approved-plan"),
    ],
)
def test_missing_flags_fail_before_any_file_is_read(
    tmp_path, monkeypatch, apply_flag, inspect_flag, expected
):
    _make_workspace(tmp_path)
    config_path = _write_config(tmp_path)
    artifact_path = _write_artifact(tmp_path)
    read: list[str] = []
    _track_read_text(monkeypatch, read)

    result = _invoke(
        config_path, artifact_path, apply_flag=apply_flag, inspect_flag=inspect_flag
    )

    assert result.exit_code == 1
    assert expected in result.stderr
    assert result.stdout.strip() == ""
    # Nothing at all was read: not the artifact, and not even the config.
    assert read == []


@pytest.mark.parametrize(
    "overrides",
    [{"apply_approved_plan": False}, {"inspect_workspace": False}],
)
def test_missing_flags_touch_no_filesystem_entry_point(tmp_path, monkeypatch, overrides):
    config_path = _write_config(tmp_path)
    artifact_path = _write_artifact(tmp_path)
    _detonate_all_filesystem_entry_points(
        monkeypatch, "a missing confirmation flag must fail before any IO"
    )

    with pytest.raises(typer.Exit) as excinfo:
        _run(
            tmp_path,
            project_config=config_path,
            approved_plan=artifact_path,
            **overrides,
        )

    assert excinfo.value.exit_code == 1


def test_disabled_config_fails_before_the_artifact_is_read(tmp_path, monkeypatch):
    _make_workspace(tmp_path)
    config_path = _write_config(tmp_path, enabled=False)
    artifact_path = _write_artifact(tmp_path)
    read: list[str] = []
    _track_read_text(monkeypatch, read)

    result = _invoke(config_path, artifact_path)

    assert result.exit_code == 1
    assert "does not enable read-only workspace inspection" in result.stderr
    assert result.stdout.strip() == ""
    # The config was read; the artifact was not.
    assert read == [str(config_path)]


def test_absent_config_block_also_blocks(tmp_path, capsys):
    _make_workspace(tmp_path)
    config_path = _write_config(tmp_path, include_inspection_block=False)

    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, project_config=config_path)

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert "read_only_workspace_inspection" in captured.err
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


def test_too_many_candidates_for_the_inspection_cap_fails_before_workspace_touch(
    tmp_path, monkeypatch, capsys
):
    workspace = _make_workspace(tmp_path)
    config_path = _write_config(tmp_path, max_inspected_files=2)
    artifact_path = _write_artifact(
        tmp_path, _artifact(["src/a.py", "src/b.py", "src/c.py"])
    )
    touched: list[str] = []
    _track_filesystem(monkeypatch, touched)

    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, project_config=config_path, approved_plan=artifact_path)

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert "max_inspected_files" in captured.err
    assert captured.out.strip() == ""
    for path in touched:
        assert str(workspace) not in path


def test_too_many_candidates_for_max_changed_files_fails_before_workspace_touch(
    tmp_path, monkeypatch, capsys
):
    workspace = _make_workspace(tmp_path)
    config_path = _write_config(tmp_path, max_inspected_files=100, max_changed_files=2)
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


def test_one_refused_path_abandons_the_whole_inspection(tmp_path, monkeypatch, capsys):
    """A plan naming one forbidden path gets no partial inspection of the rest."""
    _make_workspace(tmp_path)
    config_path = _write_config(tmp_path)
    artifact_path = _write_artifact(
        tmp_path, _artifact(["src/mod.py", "secrets/creds.env"])
    )
    _detonate_all_filesystem_entry_points(
        monkeypatch, "no candidate may be inspected once any candidate is refused"
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
    artifact_path = _write_artifact(
        tmp_path, _artifact(["src/protected/secret_ish.py"])
    )
    _detonate_all_filesystem_entry_points(
        monkeypatch, "a protected refusal must precede any workspace touch"
    )

    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, project_config=config_path, approved_plan=artifact_path)

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert "allow_protected_paths" in captured.err
    assert captured.out.strip() == ""


def test_protected_path_passes_the_lexical_phase_when_explicitly_allowed(
    tmp_path, capsys
):
    _make_workspace(tmp_path)
    config_path = _write_config(tmp_path, allow_protected_paths=True)
    artifact_path = _write_artifact(
        tmp_path, _artifact(["src/protected/secret_ish.py"])
    )

    payload = _payload(
        tmp_path, capsys, project_config=config_path, approved_plan=artifact_path
    )

    item = payload["workspace_inspection"]["items"][0]
    assert item["original_plan_path"] == "src/protected/secret_ish.py"
    assert item["status"] == "exists"
    assert item["kind"] == "file"


# -- 23..30. the success path ---------------------------------------------------


def test_existing_file_reports_kind_size_and_canonical_relative_path(tmp_path, capsys):
    workspace = _make_workspace(tmp_path)
    expected_size = (workspace / "src" / "mod.py").stat().st_size

    payload = _payload(tmp_path, capsys)

    inspection = payload["workspace_inspection"]
    assert inspection["candidate_source"] == "approved_plan.files_likely_to_change"
    assert inspection["file_contents_read"] is False
    assert inspection["directories_listed"] is False
    assert inspection["commands_run"] is False
    assert inspection["items"] == [
        {
            "original_plan_path": "src/mod.py",
            "canonical_relative_path": "src/mod.py",
            "status": "exists",
            "kind": "file",
            "size_bytes": expected_size,
            "symlinks_allowed": False,
        }
    ]

    notice = payload["notice"]
    assert "METADATA INSPECTION ONLY" in notice
    for claim in (
        "no file contents were read",
        "no files were edited",
        "no commands were run",
        "no implementation occurred",
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

    assert "Phase 5E" in payload["next_authorization_required"]


def test_directory_candidate_reports_a_directory_and_is_not_listed(
    tmp_path, monkeypatch, capsys
):
    _make_workspace(tmp_path)
    config_path = _write_config(tmp_path)
    artifact_path = _write_artifact(tmp_path, _artifact(["src/pkg"]))

    def _blocked(*args, **kwargs):
        raise AssertionError("a directory candidate must never be listed")

    monkeypatch.setattr(os, "listdir", _blocked)
    monkeypatch.setattr(os, "scandir", _blocked)
    monkeypatch.setattr(os, "walk", _blocked)

    payload = _payload(
        tmp_path, capsys, project_config=config_path, approved_plan=artifact_path
    )

    assert payload["workspace_inspection"]["items"] == [
        {
            "original_plan_path": "src/pkg",
            "canonical_relative_path": "src/pkg",
            "status": "exists",
            "kind": "directory",
            "size_bytes": None,
            "symlinks_allowed": False,
        }
    ]
    # The file that lives inside that directory is nowhere in the output.
    assert "__init__" not in json.dumps(payload)


def test_missing_file_reports_missing_and_the_run_continues(tmp_path, capsys):
    _make_workspace(tmp_path)
    config_path = _write_config(tmp_path)
    artifact_path = _write_artifact(
        tmp_path, _artifact(["src/absent.py", "src/mod.py"])
    )

    payload = _payload(
        tmp_path, capsys, project_config=config_path, approved_plan=artifact_path
    )

    items = payload["workspace_inspection"]["items"]
    assert [item["original_plan_path"] for item in items] == [
        "src/absent.py",
        "src/mod.py",
    ]
    assert items[0] == {
        "original_plan_path": "src/absent.py",
        "canonical_relative_path": None,
        "status": "missing",
        "kind": None,
        "size_bytes": None,
        "symlinks_allowed": False,
    }
    assert items[1]["status"] == "exists"


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

    assert [
        item["original_plan_path"] for item in payload["workspace_inspection"]["items"]
    ] == ["tests/test_mod.py", "src/mod.py", "src/absent.py"]


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
    assert payload["workspace_inspection"]["items"] == []
    assert "no files_likely_to_change" in payload["workspace_inspection"]["note"]
    for path in touched:
        assert str(_workspace_path(tmp_path)) not in path


def test_only_files_likely_to_change_are_inspected(tmp_path, monkeypatch, capsys):
    """Prose fields and the out-of-scope list are never treated as paths."""
    workspace = _make_workspace(tmp_path)
    config_path = _write_config(tmp_path)
    artifact_path = _write_artifact(tmp_path)
    stat_calls: list[str] = []
    real_stat = os.stat

    def tracking_stat(path, *args, **kwargs):
        stat_calls.append(str(path))
        return real_stat(path, *args, **kwargs)

    monkeypatch.setattr(os, "stat", tracking_stat)

    _run(tmp_path, project_config=config_path, approved_plan=artifact_path)

    stdout = capsys.readouterr().out
    payload = json.loads(stdout)

    assert payload["workspace_inspection"]["candidate_source"] == (
        "approved_plan.files_likely_to_change"
    )
    assert [
        item["original_plan_path"] for item in payload["workspace_inspection"]["items"]
    ] == ["src/mod.py"]

    for marker in (
        STEP_MARKER,
        VERIFICATION_MARKER,
        RISK_MARKER,
        QUESTION_MARKER,
        OUT_OF_SCOPE_MARKER,
    ):
        # Never stat'd...
        leaf = marker.rsplit("/", 1)[-1]
        for path in stat_calls:
            assert leaf not in path
        # ...and never printed.
        assert marker not in stdout

    # Nothing under the workspace was stat'd except the root and the one
    # candidate the plan actually listed.
    inspected = [
        path for path in stat_calls if str(workspace) in path and "mod.py" not in path
    ]
    for path in inspected:
        assert Path(path) == workspace or Path(path).resolve() == workspace.resolve()


def test_required_verification_is_neither_printed_nor_executed(
    tmp_path, monkeypatch, capsys
):
    _make_workspace(tmp_path)

    def _blocked(*args, **kwargs):
        raise AssertionError("l2-inspect-workspace must never execute a command")

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
        "workspace_inspection",
        "next_authorization_required",
    }

    # No configured workspace path, and no resolved absolute path of any kind.
    assert str(workspace) not in stdout
    assert WORKSPACE_DIRNAME not in stdout
    assert str(tmp_path) not in stdout
    assert "workspace_path" not in stdout
    assert "resolved" not in stdout

    # No file contents, no raw artifact, no approval text, no credentials.
    assert "value = 1" not in stdout
    assert REQUIRED_APPROVAL_TEXT not in stdout
    assert "approval_text" not in stdout
    assert "plan_provenance" not in stdout
    for absent in ("api_key", "AIDO_LITELLM", "http://", "https://", "Bearer ", "prompt", "completion"):
        assert absent not in stdout


def test_success_through_the_cli_matches_the_helper(tmp_path):
    _make_workspace(tmp_path)
    config_path = _write_config(tmp_path)
    artifact_path = _write_artifact(tmp_path)

    result = _invoke(config_path, artifact_path)

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["mode"] == "l2-inspect-workspace"
    assert payload["workspace_inspection"]["items"][0]["kind"] == "file"


# -- 31..35. canonical guard integration ---------------------------------------


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
    artifact_path = _write_artifact(
        tmp_path, _artifact(["src/mod.py", "tests/test_mod.py"])
    )

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
    assert (
        payload["workspace_inspection"]["items"][0]["symlinks_allowed"] is allow_symlinks
    )


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


def test_symlink_pointing_outside_the_workspace_is_rejected_even_when_allowed(
    tmp_path, capsys
):
    workspace = _make_workspace(tmp_path)
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (outside / "other.py").write_text("SENTINEL_OUTSIDE_CONTENT\n", encoding="utf-8")
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


def test_a_guard_failure_stops_the_whole_run_with_no_stdout(
    tmp_path, monkeypatch, capsys
):
    import ai_dev_orchestrator.workspace as workspace_pkg
    from ai_dev_orchestrator.workspace import (
        CanonicalPathAmbiguityError,
        CanonicalPathContainmentError,
        CanonicalPathResolutionError,
        CanonicalPathSymlinkError,
    )

    _make_workspace(tmp_path)
    config_path = _write_config(tmp_path)
    artifact_path = _write_artifact(
        tmp_path, _artifact(["src/mod.py", "tests/test_mod.py"])
    )
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
        assert "inspection is abandoned" in captured.err
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


# -- 36..46. no forbidden behavior ---------------------------------------------


def test_workspace_file_contents_are_never_opened_or_read(tmp_path, capsys):
    workspace = _make_workspace(tmp_path)
    config_path = _write_config(tmp_path)
    artifact_path = _write_artifact(
        tmp_path, _artifact(["src/mod.py", "src/pkg", "tests/test_mod.py"])
    )

    workspace_key = os.path.normcase(str(workspace))
    real_read_text = Path.read_text
    real_open = builtins.open

    def guarded_read_text(self, *args, **kwargs):
        assert workspace_key not in os.path.normcase(str(self)), (
            f"a workspace path was read: {self}"
        )
        return real_read_text(self, *args, **kwargs)

    def guarded_open(file, *args, **kwargs):
        assert workspace_key not in os.path.normcase(str(file)), (
            f"a workspace path was opened: {file}"
        )
        return real_open(file, *args, **kwargs)

    # Applied without monkeypatch so the guards stay in place for the whole run
    # and are restored explicitly afterwards.
    Path.read_text = guarded_read_text
    builtins.open = guarded_open
    try:
        _run(tmp_path, project_config=config_path, approved_plan=artifact_path)
    finally:
        Path.read_text = real_read_text
        builtins.open = real_open

    payload = json.loads(capsys.readouterr().out)
    assert [item["status"] for item in payload["workspace_inspection"]["items"]] == [
        "exists",
        "exists",
        "exists",
    ]


def test_no_directory_is_ever_listed(tmp_path, monkeypatch, capsys):
    _make_workspace(tmp_path)
    config_path = _write_config(tmp_path)
    artifact_path = _write_artifact(
        tmp_path, _artifact(["src/mod.py", "src/pkg", "src/absent.py"])
    )

    def _blocked(*args, **kwargs):
        raise AssertionError("l2-inspect-workspace must never list a directory")

    monkeypatch.setattr(os, "listdir", _blocked)
    monkeypatch.setattr(os, "scandir", _blocked)
    monkeypatch.setattr(os, "walk", _blocked)

    _run(tmp_path, project_config=config_path, approved_plan=artifact_path)

    payload = json.loads(capsys.readouterr().out)
    assert payload["workspace_inspection"]["directories_listed"] is False


def test_no_command_is_ever_executed(tmp_path, monkeypatch, capsys):
    _make_workspace(tmp_path)

    def _blocked(*args, **kwargs):
        raise AssertionError("l2-inspect-workspace must never execute a command")

    monkeypatch.setattr(subprocess, "Popen", _blocked)
    monkeypatch.setattr(subprocess, "run", _blocked)
    monkeypatch.setattr(os, "system", _blocked)

    payload = _payload(tmp_path, capsys)

    assert payload["workspace_inspection"]["commands_run"] is False


def test_no_environment_read_no_socket_and_no_model_client(tmp_path, monkeypatch, capsys):
    import ai_dev_orchestrator.llm.client as llm_client
    import ai_dev_orchestrator.llm.config as llm_config

    _make_workspace(tmp_path)

    def _blocked(*args, **kwargs):
        raise AssertionError("l2-inspect-workspace must not read env, network, or models")

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

    assert payload["mode"] == "l2-inspect-workspace"


def test_no_github_fetch_or_write(tmp_path, monkeypatch, capsys):
    import ai_dev_orchestrator.github.client as github_client

    _make_workspace(tmp_path)

    def _blocked(*args, **kwargs):
        raise AssertionError("l2-inspect-workspace must not contact GitHub")

    monkeypatch.setattr(github_client.GitHubClient, "__init__", _blocked)
    monkeypatch.setattr(github_client.GitHubClient, "get_issue", _blocked)

    payload = _payload(tmp_path, capsys)

    assert payload["mode"] == "l2-inspect-workspace"


def _snapshot(root: Path) -> dict[str, bytes | None]:
    return {
        str(path.relative_to(root)): (path.read_bytes() if path.is_file() else None)
        for path in sorted(root.rglob("*"))
    }


def test_nothing_in_the_workspace_or_tmp_path_is_created_or_modified(tmp_path, capsys):
    workspace = _make_workspace(tmp_path)
    config_path = _write_config(tmp_path)
    artifact_path = _write_artifact(tmp_path)
    before_workspace = _snapshot(workspace)
    before_tmp = _snapshot(tmp_path)

    _run(tmp_path, project_config=config_path, approved_plan=artifact_path)

    capsys.readouterr()
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


def _command_source() -> str:
    return "".join(
        inspect.getsource(obj)
        for obj in (
            cli._run_l2_inspect_workspace,
            cli.l2_inspect_workspace,
            cli._stat_kind_and_size,
            cli._dedupe_preserving_order,
        )
    )


def test_command_source_names_no_client_network_or_process_symbol():
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
        "read_bytes",
    ):
        assert forbidden not in source, forbidden

    # The one read the command does make is the approved-plan artifact, which
    # lives outside the workspace by construction (gate 5). There is no second
    # content read anywhere in the command.
    assert source.count("read_text(") == 1
    assert "approved_plan.read_text(" in source


def test_the_canonical_guard_is_imported_lazily_not_at_module_import():
    assert not hasattr(cli, "canonicalize_existing_path_under_workspace")
    assert "canonicalize_existing_path_under_workspace" in inspect.getsource(
        cli._run_l2_inspect_workspace
    )


def test_no_real_target_workspace_is_named_anywhere_in_this_phase():
    """Neither the new command nor this test module names a real project.

    Scoped to the Phase 5D1 code rather than all of ``cli.py``: the older
    ``generate-plan`` help text cites this repo's own
    ``projects/*.yaml.example`` path, which is a config template checked into
    this repository, not a target workspace.
    """
    # Split literals so this assertion cannot match its own source text.
    forbidden_names = ("mis" "_project", "a8" "_oa", "bible" "_reading_v2")
    sources = {
        "phase 5d1 command": _command_source(),
        "test module": Path(__file__).read_text(encoding="utf-8"),
    }
    for label, source in sources.items():
        for forbidden in forbidden_names:
            assert forbidden not in source, (label, forbidden)

    # And neither names the shared parent root in either separator spelling.
    # Split so the check cannot match its own text.
    shared_root = "C:" + "\\" + "dev"
    for label, source in sources.items():
        assert shared_root not in source, label
        assert shared_root.replace("\\", "/") not in source, label


def test_no_other_command_gained_an_inspection_path():
    for command in (
        "generate-plan",
        "generate-model-plan",
        "real-llm-smoke-test",
        "llm-smoke-test",
        "inspect-issue",
        "l2-dry-run",
    ):
        result = runner.invoke(app, [command, "--help"])
        assert result.exit_code == 0
        assert "--inspect-workspace" not in result.output


def test_existing_commands_still_behave_the_same():
    smoke = runner.invoke(app, ["llm-smoke-test"])
    assert smoke.exit_code == 0
    assert "No real model was called." in smoke.output

    assert runner.invoke(app, ["version"]).exit_code == 0
