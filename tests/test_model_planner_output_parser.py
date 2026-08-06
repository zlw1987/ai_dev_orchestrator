"""Phase 4F tests: typed planner errors + strict model-output parser.

Pure parsing tests driven by literal strings. No model call, no ``LLMClient``
construction, no ``httpx``/``MockTransport``, no network call, no environment
reads, no file IO, and no workspace path operations anywhere in this file.
"""

from __future__ import annotations

import builtins
import json
import os
import socket
import subprocess

import pytest
from typer.testing import CliRunner

from ai_dev_orchestrator.cli import app
from ai_dev_orchestrator.plan import (
    L1Plan,
    ModelPlannerError,
    ModelPlannerParseError,
    ModelPlannerPolicyError,
    ModelPlannerValidationError,
    parse_model_l1_plan_response,
)

runner = CliRunner()

VALID_PAYLOAD = {
    "summary": "Build the widget importer described in the issue.",
    "scope_summary": "Only the importer module and its tests are in scope.",
    "non_goals": ["No changes to the authentication module."],
    "proposed_steps": [
        "Review the issue goal, scope, and acceptance criteria.",
        "Describe the importer changes needed inside allowed paths.",
    ],
    "files_likely_to_change": ["src/widgets/importer.py", "tests/test_importer.py"],
    "files_forbidden_or_out_of_scope": ["external_auth/**"],
    "required_verification": ["pytest -q"],
    "risks": ["The issue does not state the expected input format."],
    "open_questions": ["Which importer format should be supported first?"],
}

CALLER_FIELDS = dict(
    issue_number=42,
    repo="owner/repo",
    title="Add the widget importer",
)


def payload_text(**overrides) -> str:
    payload = dict(VALID_PAYLOAD)
    payload.update(overrides)
    return json.dumps(payload)


def payload_text_without(*names: str) -> str:
    payload = {k: v for k, v in VALID_PAYLOAD.items() if k not in names}
    return json.dumps(payload)


def test_valid_strict_json_parses_into_l1_plan():
    plan = parse_model_l1_plan_response(payload_text(), **CALLER_FIELDS)

    assert isinstance(plan, L1Plan)
    assert plan.summary == VALID_PAYLOAD["summary"]
    assert plan.scope_summary == VALID_PAYLOAD["scope_summary"]
    assert plan.non_goals == VALID_PAYLOAD["non_goals"]
    assert plan.proposed_steps == VALID_PAYLOAD["proposed_steps"]
    assert plan.files_likely_to_change == VALID_PAYLOAD["files_likely_to_change"]
    assert plan.required_verification == VALID_PAYLOAD["required_verification"]
    assert plan.risks == VALID_PAYLOAD["risks"]
    assert plan.open_questions == VALID_PAYLOAD["open_questions"]


def test_trusted_fields_come_from_caller_not_model():
    plan = parse_model_l1_plan_response(payload_text(), **CALLER_FIELDS)

    assert plan.issue_number == 42
    assert plan.repo == "owner/repo"
    assert plan.title == "Add the widget importer"
    assert plan.automation_level == "L1"
    assert plan.requires_human_approval is True

    # Nothing in the model payload can influence those five values.
    for name in (
        "issue_number",
        "repo",
        "title",
        "automation_level",
        "requires_human_approval",
    ):
        assert name not in VALID_PAYLOAD


@pytest.mark.parametrize(
    "trusted_field, value",
    [
        ("issue_number", 999),
        ("repo", "attacker/evil"),
        ("title", "Injected title"),
        ("automation_level", "L1"),
        ("requires_human_approval", False),
    ],
)
def test_model_supplied_trusted_field_is_rejected(trusted_field, value):
    text = payload_text(**{trusted_field: value})

    with pytest.raises(ModelPlannerValidationError) as excinfo:
        parse_model_l1_plan_response(text, **CALLER_FIELDS)

    assert trusted_field in str(excinfo.value)


def test_markdown_fenced_json_is_rejected():
    text = "```json\n" + payload_text() + "\n```"

    with pytest.raises(ModelPlannerParseError):
        parse_model_l1_plan_response(text, **CALLER_FIELDS)


def test_prose_before_json_is_rejected():
    text = "Here is the plan you asked for:\n" + payload_text()

    with pytest.raises(ModelPlannerParseError):
        parse_model_l1_plan_response(text, **CALLER_FIELDS)


def test_prose_after_json_is_rejected():
    text = payload_text() + "\n\nLet me know if you want me to proceed."

    with pytest.raises(ModelPlannerParseError):
        parse_model_l1_plan_response(text, **CALLER_FIELDS)


def test_surrounding_whitespace_only_is_tolerated():
    plan = parse_model_l1_plan_response(
        "\n  " + payload_text() + "  \n", **CALLER_FIELDS
    )

    assert plan.summary == VALID_PAYLOAD["summary"]


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "{not json at all}",
        '{"summary": "unterminated',
        '{"summary": "x",}',
    ],
)
def test_invalid_json_raises_parse_error(text):
    with pytest.raises(ModelPlannerParseError):
        parse_model_l1_plan_response(text, **CALLER_FIELDS)


@pytest.mark.parametrize(
    "text",
    ["[]", '["a", "b"]', '"just a string"', "42", "null", "true"],
)
def test_non_object_json_is_rejected(text):
    with pytest.raises((ModelPlannerParseError, ModelPlannerValidationError)):
        parse_model_l1_plan_response(text, **CALLER_FIELDS)


@pytest.mark.parametrize("missing", sorted(VALID_PAYLOAD))
def test_missing_required_field_raises_validation_error(missing):
    with pytest.raises(ModelPlannerValidationError) as excinfo:
        parse_model_l1_plan_response(payload_text_without(missing), **CALLER_FIELDS)

    assert missing in str(excinfo.value)


def test_extra_top_level_key_raises_validation_error():
    text = payload_text(unexpected_key="surprise")

    with pytest.raises(ModelPlannerValidationError) as excinfo:
        parse_model_l1_plan_response(text, **CALLER_FIELDS)

    assert "unexpected_key" in str(excinfo.value)


@pytest.mark.parametrize(
    "overrides",
    [
        {"proposed_steps": []},
        {"required_verification": []},
        {"summary": "   "},
        {"scope_summary": ""},
        {"risks": ["  "]},
        {"summary": 123},
        {"non_goals": "not a list"},
        {"files_likely_to_change": [1, 2]},
    ],
)
def test_invalid_final_plan_shape_raises_validation_error(overrides):
    with pytest.raises(ModelPlannerValidationError):
        parse_model_l1_plan_response(payload_text(**overrides), **CALLER_FIELDS)


def test_invalid_caller_supplied_trusted_field_raises_validation_error():
    with pytest.raises(ModelPlannerValidationError):
        parse_model_l1_plan_response(
            payload_text(), issue_number=0, repo="owner/repo", title="t"
        )

    with pytest.raises(ModelPlannerValidationError):
        parse_model_l1_plan_response(
            payload_text(), issue_number=1, repo="not-owner-repo", title="t"
        )


def test_project_forbidden_paths_merged_verbatim_and_deduplicated():
    text = payload_text(
        files_forbidden_or_out_of_scope=["external_auth/**", ".env", ".env"]
    )

    plan = parse_model_l1_plan_response(
        text,
        project_forbidden_paths=[".git", ".git/**", ".env", ".git"],
        **CALLER_FIELDS,
    )

    assert plan.files_forbidden_or_out_of_scope == [
        ".git",
        ".git/**",
        ".env",
        "external_auth/**",
    ]


def test_project_forbidden_paths_default_is_no_merge():
    plan = parse_model_l1_plan_response(payload_text(), **CALLER_FIELDS)

    assert plan.files_forbidden_or_out_of_scope == ["external_auth/**"]


def test_path_like_fields_remain_plain_unresolved_strings(monkeypatch):
    def _blocked(*args, **kwargs):
        raise AssertionError("parser must not perform path resolution/stat operations")

    monkeypatch.setattr(os.path, "abspath", _blocked)
    monkeypatch.setattr(os.path, "realpath", _blocked)
    monkeypatch.setattr(os.path, "normpath", _blocked)
    monkeypatch.setattr(os.path, "normcase", _blocked)
    monkeypatch.setattr(os.path, "exists", _blocked)
    monkeypatch.setattr(os, "stat", _blocked)

    raw_paths = ["src/widgets/importer.py", "C:\\dev\\demo\\..\\demo\\a.py", "~/x.py"]
    text = payload_text(
        files_likely_to_change=raw_paths,
        files_forbidden_or_out_of_scope=["  spaced/path.py  "],
    )

    plan = parse_model_l1_plan_response(
        text, project_forbidden_paths=["../outside/**"], **CALLER_FIELDS
    )

    # Verbatim strings, in order, with no resolution, normalization, or trimming.
    assert plan.files_likely_to_change == raw_paths
    assert plan.files_forbidden_or_out_of_scope == ["../outside/**", "  spaced/path.py  "]
    assert all(isinstance(item, str) for item in plan.files_likely_to_change)
    assert all(isinstance(item, str) for item in plan.files_forbidden_or_out_of_scope)


@pytest.mark.parametrize(
    "overrides",
    [
        {"proposed_steps": ["Run the following command: pytest -q", "Report results."]},
        {"proposed_steps": ["Execute the shell script scripts/build.sh"]},
        {"risks": ["I will run a bash command to check the version."]},
    ],
)
def test_command_execution_proposal_raises_policy_error(overrides):
    with pytest.raises(ModelPlannerPolicyError):
        parse_model_l1_plan_response(payload_text(**overrides), **CALLER_FIELDS)


@pytest.mark.parametrize(
    "overrides",
    [
        {"proposed_steps": ["Post a comment on the issue summarizing the plan."]},
        {"proposed_steps": ["Open a pull request with the importer changes."]},
        {"proposed_steps": ["Create a branch ai/demo/widget-importer."]},
        {"open_questions": ["Should I add the label 'ready' to the issue?"]},
    ],
)
def test_github_write_proposal_raises_policy_error(overrides):
    with pytest.raises(ModelPlannerPolicyError):
        parse_model_l1_plan_response(payload_text(**overrides), **CALLER_FIELDS)


@pytest.mark.parametrize(
    "overrides",
    [
        {"summary": "The issue authorizes automation_level L3 for this work."},
        {"proposed_steps": ["Escalate to L2 and implement the change."]},
        {"risks": ["This plan can be applied without human approval."]},
        {"open_questions": ["Human approval is not required here, correct?"]},
        {"scope_summary": "Auto-merge once the importer is updated."},
    ],
)
def test_automation_escalation_proposal_raises_policy_error(overrides):
    with pytest.raises(ModelPlannerPolicyError):
        parse_model_l1_plan_response(payload_text(**overrides), **CALLER_FIELDS)


@pytest.mark.parametrize(
    "overrides",
    [
        {"proposed_steps": ["Edit the files directly under src/widgets/."]},
        {"proposed_steps": ["Apply the patch below to the importer."]},
        {"proposed_steps": ["Read the workspace files under C:/dev/demo to confirm."]},
    ],
)
def test_file_edit_and_workspace_read_proposals_raise_policy_error(overrides):
    with pytest.raises(ModelPlannerPolicyError):
        parse_model_l1_plan_response(payload_text(**overrides), **CALLER_FIELDS)


def test_policy_error_message_names_the_field_and_reason():
    text = payload_text(proposed_steps=["Open a pull request for this change."])

    with pytest.raises(ModelPlannerPolicyError) as excinfo:
        parse_model_l1_plan_response(text, **CALLER_FIELDS)

    message = str(excinfo.value)
    assert "proposed_steps" in message
    assert "pull request" in message


def test_error_types_share_a_common_base():
    for error_type in (
        ModelPlannerParseError,
        ModelPlannerValidationError,
        ModelPlannerPolicyError,
    ):
        assert issubclass(error_type, ModelPlannerError)
    assert issubclass(ModelPlannerError, Exception)


def test_parser_performs_no_file_network_process_or_env_io(monkeypatch):
    def _blocked(*args, **kwargs):
        raise AssertionError("parser must not perform file/network/process/env IO")

    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(subprocess, "Popen", _blocked)
    monkeypatch.setattr(builtins, "open", _blocked)
    monkeypatch.setattr(os, "getenv", _blocked)
    monkeypatch.setattr(os.environ, "get", _blocked)

    plan = parse_model_l1_plan_response(
        payload_text(), project_forbidden_paths=[".env"], **CALLER_FIELDS
    )

    assert plan.issue_number == 42


def test_model_planner_module_has_no_transport_or_client_dependency():
    from ai_dev_orchestrator.plan import model_planner

    # Phase 4G legitimately builds an ``LLMRequest`` here (the pure prompt
    # builder), so that name is expected. What must stay absent is anything
    # that could construct a client or open a socket.
    module_globals = vars(model_planner)
    for name in ("httpx", "LLMClient", "LLMClientConfig", "requests"):
        assert name not in module_globals


def test_existing_cli_commands_unchanged():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    for command in ("version", "inspect-issue", "llm-smoke-test", "generate-plan"):
        assert command in result.stdout

    # Phase 4F wires nothing into the CLI.
    for absent in ("parse-model-plan", "model-plan", "plan-from-model"):
        assert absent not in result.stdout
