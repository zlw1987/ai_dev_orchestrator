"""Phase 4D tests: `generate-plan` CLI command.

The command is **offline-only**: it reads only the two local files given via
``--project-config`` and ``--body-file``, never fetches GitHub, never calls a
model, never reads ``AIDO_LITELLM_*`` (or any other) environment variable,
and never reads the project's configured ``repo.workspace_path``.
"""

from __future__ import annotations

import builtins
import json
import os
import socket
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_dev_orchestrator.cli import app
from ai_dev_orchestrator.plan.models import L1Plan

runner = CliRunner()

FULL_BODY = """\
## Goal
Build the widget importer.

## Scope
- Update `src/widgets/importer.py`
- Add tests/test_widget_importer.py

## Non-goals
- Do not touch config/settings.py

## Acceptance Criteria
- [ ] tests pass

## Required Verification
- pytest -q
"""

MINIMAL_BODY = "## Goal\nJust a goal.\n"

PROJECT_CONFIG_TEMPLATE = """
project_id: demo_project
display_name: Demo Project
repo:
  workspace_path: "{workspace_path}"
  github_repo: "owner/demo_project"
  branch_prefix: "ai/demo"
allowed_paths:
  - "src/**"
forbidden_paths:
  - ".env"
protected_paths:
  - "config/settings.py"
"""


def _write_body_file(tmp_path: Path, text: str) -> Path:
    body_file = tmp_path / "issue_body.md"
    body_file.write_text(text, encoding="utf-8")
    return body_file


def _write_project_config(tmp_path: Path, workspace_path: str | None = None) -> Path:
    if workspace_path is None:
        workspace_path = (tmp_path / "does_not_exist_workspace").as_posix()
    config_file = tmp_path / "project.yaml"
    config_file.write_text(
        PROJECT_CONFIG_TEMPLATE.format(workspace_path=workspace_path),
        encoding="utf-8",
    )
    return config_file


def _invoke(project_config: Path, body_file: Path, extra: list[str] | None = None):
    args = [
        "generate-plan",
        "--project-config",
        str(project_config),
        "--repo",
        "owner/repo",
        "--issue",
        "7",
        "--title",
        "Add the widget importer",
        "--body-file",
        str(body_file),
    ]
    if extra:
        args.extend(extra)
    return runner.invoke(app, args)


def test_generate_plan_succeeds_with_temp_files(tmp_path):
    project_config = _write_project_config(tmp_path)
    body_file = _write_body_file(tmp_path, FULL_BODY)

    result = _invoke(project_config, body_file)

    assert result.exit_code == 0


def test_generate_plan_output_is_valid_json_and_validates_as_l1plan(tmp_path):
    project_config = _write_project_config(tmp_path)
    body_file = _write_body_file(tmp_path, FULL_BODY)

    result = _invoke(project_config, body_file)

    data = json.loads(result.output)
    plan = L1Plan.model_validate(data)
    assert plan.issue_number == 7


def test_generate_plan_output_includes_expected_fields(tmp_path):
    project_config = _write_project_config(tmp_path)
    body_file = _write_body_file(tmp_path, FULL_BODY)

    result = _invoke(project_config, body_file)
    data = json.loads(result.output)

    assert data["issue_number"] == 7
    assert data["repo"] == "owner/demo_project"
    assert data["title"] == "Add the widget importer"
    assert "widget importer" in data["summary"].lower()
    assert "src/widgets/importer.py" in data["scope_summary"]
    assert data["non_goals"] == ["Do not touch config/settings.py"]
    assert data["required_verification"] == ["pytest -q"]


def test_generate_plan_output_is_l1_and_requires_human_approval(tmp_path):
    project_config = _write_project_config(tmp_path)
    body_file = _write_body_file(tmp_path, FULL_BODY)

    result = _invoke(project_config, body_file)
    data = json.loads(result.output)

    assert data["automation_level"] == "L1"
    assert data["requires_human_approval"] is True
    assert "notice" in data
    assert "human" in data["notice"].lower()


def test_generate_plan_missing_required_sections_still_valid_json(tmp_path):
    project_config = _write_project_config(tmp_path)
    body_file = _write_body_file(tmp_path, MINIMAL_BODY)

    result = _invoke(project_config, body_file)

    assert result.exit_code == 0
    data = json.loads(result.output)
    plan = L1Plan.model_validate(data)
    assert plan.risks  # missing-required-section risk present
    assert plan.open_questions  # vague-scope open question present


def test_generate_plan_makes_no_real_network_call(monkeypatch, tmp_path):
    """Any real socket connect attempt fails the test instead of hanging."""
    project_config = _write_project_config(tmp_path)
    body_file = _write_body_file(tmp_path, FULL_BODY)

    def boom(*args, **kwargs):
        raise AssertionError("real network connection attempted")

    monkeypatch.setattr("socket.socket.connect", boom)

    result = _invoke(project_config, body_file)

    assert result.exit_code == 0


def test_generate_plan_does_not_require_litellm_or_github_env_vars(
    tmp_path, monkeypatch
):
    project_config = _write_project_config(tmp_path)
    body_file = _write_body_file(tmp_path, FULL_BODY)

    for name in (
        "AIDO_LITELLM_BASE_URL",
        "AIDO_LITELLM_API_KEY",
        "AIDO_LITELLM_DEFAULT_MODEL",
        "GITHUB_TOKEN",
    ):
        monkeypatch.delenv(name, raising=False)

    result = _invoke(project_config, body_file)

    assert result.exit_code == 0


def test_generate_plan_does_not_read_workspace_path(tmp_path, monkeypatch):
    workspace_path = (tmp_path / "does_not_exist_workspace").as_posix()
    project_config = _write_project_config(tmp_path, workspace_path=workspace_path)
    body_file = _write_body_file(tmp_path, FULL_BODY)

    real_open = builtins.open
    real_listdir = os.listdir

    def guarded_open(file, *args, **kwargs):
        if str(file) == workspace_path:
            raise AssertionError("must not open configured workspace_path")
        return real_open(file, *args, **kwargs)

    def guarded_listdir(path=".", *args, **kwargs):
        if str(path) == workspace_path:
            raise AssertionError("must not list configured workspace_path")
        return real_listdir(path, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", guarded_open)
    monkeypatch.setattr(os, "listdir", guarded_listdir)

    result = _invoke(project_config, body_file)

    assert result.exit_code == 0


def test_generate_plan_rejects_body_file_inside_workspace_before_reading(
    tmp_path, monkeypatch
):
    """A body file under repo.workspace_path is refused before it is read."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    body_file = workspace / "issue_body.md"
    body_file.write_text(
        FULL_BODY + "\nSENTINEL_WORKSPACE_BODY_CONTENT\n", encoding="utf-8"
    )
    project_config = _write_project_config(
        tmp_path, workspace_path=workspace.as_posix()
    )

    real_read_text = Path.read_text
    target = os.path.normcase(os.path.abspath(str(body_file)))

    def guarded_read_text(self, *args, **kwargs):
        if os.path.normcase(os.path.abspath(str(self))) == target:
            raise AssertionError(
                "body file inside workspace_path must not be read at all"
            )
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)

    result = _invoke(project_config, body_file)

    assert result.exit_code == 1
    assert "workspace" in result.output.lower()
    assert "SENTINEL_WORKSPACE_BODY_CONTENT" not in result.output


def test_generate_plan_allows_body_file_in_sibling_of_workspace(tmp_path):
    """A sibling path that merely shares a name prefix is not 'inside'."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    sibling = tmp_path / "workspace_notes"
    sibling.mkdir()
    body_file = sibling / "issue_body.md"
    body_file.write_text(FULL_BODY, encoding="utf-8")
    project_config = _write_project_config(
        tmp_path, workspace_path=workspace.as_posix()
    )

    result = _invoke(project_config, body_file)

    assert result.exit_code == 0
    assert json.loads(result.output)["issue_number"] == 7


def test_generate_plan_rejects_unsupported_format(tmp_path):
    project_config = _write_project_config(tmp_path)
    body_file = _write_body_file(tmp_path, FULL_BODY)

    result = _invoke(project_config, body_file, extra=["--format", "yaml"])

    assert result.exit_code != 0


def test_generate_plan_accepts_json_format_explicitly(tmp_path):
    project_config = _write_project_config(tmp_path)
    body_file = _write_body_file(tmp_path, FULL_BODY)

    result = _invoke(project_config, body_file, extra=["--format", "json"])

    assert result.exit_code == 0


def test_generate_plan_help_does_not_expose_live_or_model_options():
    result = runner.invoke(app, ["generate-plan", "--help"])
    assert result.exit_code == 0
    for forbidden in ("--live", "--real", "--github", "--fetch", "--model", "--use-env"):
        assert forbidden not in result.output


def test_cli_still_has_existing_commands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "version" in result.output
    assert "inspect-issue" in result.output
    assert "llm-smoke-test" in result.output
    assert "generate-plan" in result.output


def test_generate_plan_does_not_execute_commands_or_write_github(tmp_path, monkeypatch):
    project_config = _write_project_config(tmp_path)
    body_file = _write_body_file(tmp_path, FULL_BODY)

    def boom(*args, **kwargs):
        raise AssertionError("command execution attempted")

    monkeypatch.setattr(subprocess, "Popen", boom)
    monkeypatch.setattr(subprocess, "run", boom)

    def boom_get_issue(self, repo, issue):
        raise AssertionError("GitHub fetch attempted")

    monkeypatch.setattr(
        "ai_dev_orchestrator.github.client.GitHubClient.get_issue", boom_get_issue
    )

    result = _invoke(project_config, body_file)

    assert result.exit_code == 0
