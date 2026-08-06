"""Phase 4C tests: deterministic fake/offline L1 planner engine.

Pure transformation tests. No file reads, no command execution, no GitHub
or model/network calls anywhere in this file.
"""

from __future__ import annotations

import builtins
import os
import socket
import subprocess

import pytest

from ai_dev_orchestrator.github.issue_parser import parse_issue_body
from ai_dev_orchestrator.github.models import GitHubIssue
from ai_dev_orchestrator.models import ProjectConfig, RepoConfig
from ai_dev_orchestrator.plan import FakeL1Planner

FULL_BODY = """\
## Goal
Build the widget importer.

## Current Context
Phase 1 is done.

## Scope
- Update `src/widgets/importer.py`
- Add tests/test_widget_importer.py

## Non-goals
- Do not touch config/settings.py
- No changes to external_auth/**

## Acceptance Criteria
- [ ] tests pass

## Required Verification
- pytest -q
- python -m ai_dev_orchestrator --help
"""

MINIMAL_BODY = "## Goal\nJust a goal.\n"


def make_issue(**overrides) -> GitHubIssue:
    kwargs = dict(
        number=42,
        title="Add the widget importer",
        body=FULL_BODY,
        state="open",
        html_url="https://github.com/owner/repo/issues/42",
        labels=["enhancement"],
    )
    kwargs.update(overrides)
    return GitHubIssue(**kwargs)


def make_project(**overrides) -> ProjectConfig:
    kwargs = dict(
        project_id="demo_project",
        display_name="Demo Project",
        repo=RepoConfig(
            workspace_path="C:/dev/demo_project",
            github_repo="owner/repo",
            default_base_branch="main",
            branch_prefix="ai/demo",
        ),
        forbidden_paths=[".git", ".git/**", ".env"],
        protected_paths=["config/settings.py", "**/migrations/**"],
    )
    kwargs.update(overrides)
    return ProjectConfig(**kwargs)


def test_full_issue_produces_valid_plan():
    issue = make_issue()
    parsed = parse_issue_body(FULL_BODY)
    project = make_project()

    plan = FakeL1Planner().create_plan(issue, parsed, project)

    assert plan.issue_number == 42
    assert plan.repo == "owner/repo"
    assert plan.title == "Add the widget importer"
    assert plan.automation_level == "L1"
    assert plan.requires_human_approval is True


def test_summary_from_goal_and_scope_summary_from_scope():
    issue = make_issue()
    parsed = parse_issue_body(FULL_BODY)
    project = make_project()

    plan = FakeL1Planner().create_plan(issue, parsed, project)

    assert plan.summary == "Build the widget importer."
    assert "Update `src/widgets/importer.py`" in plan.scope_summary


def test_non_goals_and_required_verification_become_lists():
    issue = make_issue()
    parsed = parse_issue_body(FULL_BODY)
    project = make_project()

    plan = FakeL1Planner().create_plan(issue, parsed, project)

    assert plan.non_goals == [
        "Do not touch config/settings.py",
        "No changes to external_auth/**",
    ]
    assert plan.required_verification == [
        "pytest -q",
        "python -m ai_dev_orchestrator --help",
    ]


def test_missing_required_sections_produce_risk_and_open_question_not_crash():
    issue = make_issue(body=MINIMAL_BODY)
    parsed = parse_issue_body(MINIMAL_BODY)
    project = make_project()

    plan = FakeL1Planner().create_plan(issue, parsed, project)

    assert plan.summary == "Just a goal."
    assert plan.scope_summary  # non-blank fallback text
    assert any("missing required section" in risk.lower() for risk in plan.risks)
    assert any("scope" in question.lower() for question in plan.open_questions)
    assert plan.required_verification  # non-empty fallback
    assert plan.non_goals == []


def test_empty_body_does_not_crash():
    issue = make_issue(body=None)
    parsed = parse_issue_body(None)
    project = make_project()

    plan = FakeL1Planner().create_plan(issue, parsed, project)

    assert plan.summary == issue.title
    assert plan.scope_summary


def test_project_forbidden_paths_copied_as_plain_strings():
    issue = make_issue()
    parsed = parse_issue_body(FULL_BODY)
    project = make_project(forbidden_paths=[".git", ".env", "secrets/**"])

    plan = FakeL1Planner().create_plan(issue, parsed, project)

    for path in [".git", ".env", "secrets/**"]:
        assert path in plan.files_forbidden_or_out_of_scope
        assert isinstance(path, str)


def test_protected_paths_produce_risk():
    issue = make_issue()
    parsed = parse_issue_body(FULL_BODY)
    project = make_project(protected_paths=["config/settings.py"])

    plan = FakeL1Planner().create_plan(issue, parsed, project)

    assert any("protected path" in risk.lower() for risk in plan.risks)


def test_no_protected_paths_no_protected_risk():
    issue = make_issue()
    parsed = parse_issue_body(FULL_BODY)
    project = make_project(protected_paths=[])

    plan = FakeL1Planner().create_plan(issue, parsed, project)

    assert not any("protected path" in risk.lower() for risk in plan.risks)


def test_files_likely_to_change_inferred_from_scope():
    issue = make_issue()
    parsed = parse_issue_body(FULL_BODY)
    project = make_project()

    plan = FakeL1Planner().create_plan(issue, parsed, project)

    assert "src/widgets/importer.py" in plan.files_likely_to_change
    assert "tests/test_widget_importer.py" in plan.files_likely_to_change


def test_vague_scope_with_no_paths_produces_open_question():
    body = "## Goal\nDo something.\n## Scope\nGeneral improvements.\n"
    issue = make_issue(body=body)
    parsed = parse_issue_body(body)
    project = make_project()

    plan = FakeL1Planner().create_plan(issue, parsed, project)

    assert plan.files_likely_to_change == []
    assert any(
        "no specific files" in question.lower() for question in plan.open_questions
    )


def test_no_file_network_process_or_env_io(monkeypatch):
    def _blocked(*args, **kwargs):
        raise AssertionError(
            "fake planner must not perform file/network/process/env IO"
        )

    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(subprocess, "Popen", _blocked)
    monkeypatch.setattr(builtins, "open", _blocked)
    monkeypatch.setattr(os, "getenv", _blocked)
    monkeypatch.setattr(os.environ, "get", _blocked)

    issue = make_issue()
    parsed = parse_issue_body(FULL_BODY)
    project = make_project()

    plan = FakeL1Planner().create_plan(issue, parsed, project)
    assert plan.issue_number == 42


def test_deterministic_same_inputs_equal_model_dump():
    issue = make_issue()
    parsed = parse_issue_body(FULL_BODY)
    project = make_project()

    planner = FakeL1Planner()
    plan_a = planner.create_plan(issue, parsed, project)
    plan_b = planner.create_plan(issue, parsed, project)

    assert plan_a.model_dump() == plan_b.model_dump()


def test_no_cli_plan_command_added():
    from typer.testing import CliRunner

    from ai_dev_orchestrator.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "plan" not in result.output.lower()


@pytest.mark.parametrize(
    "body", [FULL_BODY, MINIMAL_BODY, None, "## Scope\nvague\n"]
)
def test_automation_level_always_l1_and_requires_human_approval(body):
    issue = make_issue(body=body)
    parsed = parse_issue_body(body)
    project = make_project()

    plan = FakeL1Planner().create_plan(issue, parsed, project)

    assert plan.automation_level == "L1"
    assert plan.requires_human_approval is True
