"""Phase 5E3 tests: the ``generate-diff-proposal`` command.

The command reads four local files — a project config, a human-approved L1 plan
artifact, a Phase 5D2 ``l2-read-workspace-files`` packet, and a proposed-content
JSON object — generates a **proposal-only** diff proposal artifact
deterministically and offline, and prints it to stdout.

It generates diff text and does nothing with it, so these tests assert absence
far more than presence: no target project workspace is read, listed, stat'd, or
resolved; no file is opened beyond the four named on the command line; no diff
is applied; no apply-cleanliness is checked; no file is edited; no command is
executed; no environment variable is read; no socket is opened; no model is
called; nothing is fetched from or written to GitHub; no artifact file is
written; and no approval is stamped.

Every input here is literal JSON written into pytest's own ``tmp_path``. The
configured ``workspace_path`` points at a directory that is normally never
created — the rejection tests that do create one create it under ``tmp_path``
and never read anything inside it.
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
    PROPOSED_CONTENT_MODE,
    PROPOSED_CONTENT_SCHEMA_VERSION,
    parse_diff_proposal_artifact,
)
from ai_dev_orchestrator.handoff import REQUIRED_APPROVAL_TEXT

runner = CliRunner()

PROJECT_ID = "demo_project"
REPO = "demo/widgets"
ISSUE_NUMBER = 42
TITLE = "Add currency formatting helper"
APPROVER = "operator@example.invalid"
APPROVED_AT = "2026-01-02T04:00:00+00:00"

# Distinctive markers, so a test can prove what did and did not reach stdout.
SUMMARY_MARKER = "SENTINEL_PLAN_SUMMARY_PROSE"
VERIFICATION_MARKER = "SENTINEL_VERIFICATION_TEXT"
SECRET_VALUE = "SENTINEL_SECRET_VALUE_NEVER_ECHOED"

# Path-shaped plan strings. Nothing below is ever opened, stat'd, listed, or
# resolved: they are compared and copied as strings only.
PLAN_FILE_A = "src/billing/sentinel_never_opened_a.py"
PLAN_FILE_NEW = "src/billing/sentinel_never_opened_new.py"
PLAN_FORBIDDEN = "secrets/sentinel_never_opened.env"

ORIGINAL_A = "def total(amount):\n    return amount\n"
PROPOSED_A = "def total(amount):\n    return round(amount, 2)\n"
CREATED_TEXT = "def helper():\n    return 'new'\n"

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
  max_changed_files: 20
allowed_paths:
  - "src/**"
forbidden_paths:
  - ".git/**"
"""

VALID_PLAN: dict = {
    "issue_number": ISSUE_NUMBER,
    "repo": REPO,
    "title": TITLE,
    "summary": f"Format invoice totals through one shared helper. {SUMMARY_MARKER}",
    "scope_summary": "Only the billing formatting helper and its tests.",
    "non_goals": ["No changes to the payment gateway client."],
    "proposed_steps": ["Describe a single shared helper for a human to write."],
    "files_likely_to_change": [PLAN_FILE_A, PLAN_FILE_NEW],
    "files_forbidden_or_out_of_scope": [PLAN_FORBIDDEN],
    "required_verification": [f"pytest -q {VERIFICATION_MARKER}"],
    "risks": ["Rounding differences on reissued invoices."],
    "open_questions": ["Which locale should totals use?"],
    "automation_level": "L1",
    "requires_human_approval": True,
}

VALID_PROVENANCE: dict = {
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

VALID_APPROVAL: dict = {
    "approved_by": APPROVER,
    "approved_at": APPROVED_AT,
    "approval_text": REQUIRED_APPROVAL_TEXT,
    "source": "manual",
}


def _artifact() -> dict:
    """A fresh, fully valid approved-plan artifact dict."""
    return {
        "approval": copy.deepcopy(VALID_APPROVAL),
        "plan_provenance": copy.deepcopy(VALID_PROVENANCE),
        "plan": copy.deepcopy(VALID_PLAN),
        "project_id": PROJECT_ID,
        "repo": REPO,
        "issue_number": ISSUE_NUMBER,
    }


def _read_item(path: str, content: str, **overrides) -> dict:
    item = {
        "original_plan_path": path,
        "canonical_relative_path": path,
        "status": "read",
        "kind": "file",
        "size_bytes": len(content.encode("utf-8")),
        "bytes_read": len(content.encode("utf-8")),
        "encoding": "utf-8",
        "redacted": False,
        "redaction_count": 0,
        "redaction_kinds": [],
        "content_text": content,
    }
    item.update(overrides)
    return item


def _empty_item(path: str, status: str) -> dict:
    return {
        "original_plan_path": path,
        "canonical_relative_path": None,
        "status": status,
        "kind": None,
        "size_bytes": None,
        "bytes_read": 0,
        "encoding": None,
        "redacted": False,
        "redaction_count": 0,
        "redaction_kinds": [],
        "content_text": None,
    }


def _packet(items: list[dict] | None = None) -> dict:
    """The shape ``l2-read-workspace-files`` prints, notice and policies and all."""
    return {
        "notice": "L2 READ-ONLY FILE-CONTENT INSPECTION ONLY",
        "mode": "l2-read-workspace-files",
        "project": {
            "project_id": PROJECT_ID,
            "repo": REPO,
            "workspace_policy": {
                "deny_outside_workspace": True,
                "allow_symlinks": False,
                "max_changed_files": 20,
            },
            "content_policy": {
                "enabled": True,
                "max_files": 10,
                "max_file_bytes": 65536,
                "max_total_bytes": 262144,
                "allow_protected_paths": False,
                "redaction": "mandatory_basic_secret_like_redaction",
            },
        },
        "approved_plan": {
            "approved_by": APPROVER,
            "approved_at": APPROVED_AT,
            "source": "manual",
            "plan_engine": "real-model",
            "real_call": True,
            "model": "fake-planner-model",
            "issue_number": ISSUE_NUMBER,
            "title": TITLE,
        },
        "workspace_content": {
            "note": "Bounded content only.",
            "candidate_source": "approved_plan.files_likely_to_change",
            "file_contents_read": True,
            "directories_listed": False,
            "commands_run": False,
            "model_called": False,
            "diffs_generated": False,
            "files_edited": False,
            "total_bytes_read": len(ORIGINAL_A),
            "items": [
                _read_item(PLAN_FILE_A, ORIGINAL_A),
                _empty_item(PLAN_FILE_NEW, "missing"),
            ]
            if items is None
            else items,
        },
        "next_authorization_required": "Phase 5E2 or later must be authorized.",
    }


def _change(
    path: str = PLAN_FILE_A,
    content: str = PROPOSED_A,
    change_type: str = "modify",
    **overrides,
) -> dict:
    change = {
        "path": path,
        "change_type": change_type,
        "content_text": content,
        "rationale": "Round invoice totals to two decimal places.",
        "risks": ["Reissued invoices may differ by a cent."],
        "requires_human_review": True,
    }
    change.update(overrides)
    return change


def _proposed(changes: list[dict] | None = None, **overrides) -> dict:
    payload = {
        "schema_version": PROPOSED_CONTENT_SCHEMA_VERSION,
        "mode": PROPOSED_CONTENT_MODE,
        "changes": [_change()] if changes is None else changes,
        "assumptions": [],
        "risks": [],
        "open_questions": [],
        "requires_human_review": True,
        "next_authorization_required": "A human must review before anything is applied.",
    }
    payload.update(overrides)
    return payload


def _workspace_path(tmp_path):
    """A workspace path that is a **string only**: never created or touched."""
    return tmp_path / "never_touched_workspace"


def _write_config(
    tmp_path, *, project_id: str = PROJECT_ID, github_repo: str = REPO
):
    path = tmp_path / "project.yaml"
    path.write_text(
        CONFIG_TEMPLATE.format(
            project_id=project_id,
            github_repo=github_repo,
            workspace_path=str(_workspace_path(tmp_path)).replace("\\", "\\\\"),
        ),
        encoding="utf-8",
    )
    return path


def _write(tmp_path, name: str, payload: dict | str):
    path = tmp_path / name
    text = payload if isinstance(payload, str) else json.dumps(payload)
    path.write_text(text, encoding="utf-8")
    return path


def _write_artifact(tmp_path, payload=None, name: str = "approved_plan.json"):
    return _write(tmp_path, name, _artifact() if payload is None else payload)


def _write_packet(tmp_path, payload=None, name: str = "workspace_content.json"):
    return _write(tmp_path, name, _packet() if payload is None else payload)


def _write_proposed(tmp_path, payload=None, name: str = "proposed_content.json"):
    return _write(tmp_path, name, _proposed() if payload is None else payload)


def _run(tmp_path, **overrides):
    """Call the private helper directly, so file reads can be tracked."""
    kwargs = {
        "project_config": overrides.pop("project_config", None)
        or _write_config(tmp_path),
        "approved_plan": overrides.pop("approved_plan", None)
        or _write_artifact(tmp_path),
        "workspace_content": overrides.pop("workspace_content", None)
        or _write_packet(tmp_path),
        "proposed_content": overrides.pop("proposed_content", None)
        or _write_proposed(tmp_path),
        "apply_approved_plan": True,
        "generate_diff": True,
    }
    kwargs.update(overrides)
    return cli._run_generate_diff_proposal(**kwargs)


def _invoke(
    config_path,
    artifact_path,
    packet_path,
    proposed_path,
    *,
    apply_flag=True,
    diff_flag=True,
):
    args = [
        "generate-diff-proposal",
        "--project-config",
        str(config_path),
        "--approved-plan",
        str(artifact_path),
        "--workspace-content",
        str(packet_path),
        "--proposed-content",
        str(proposed_path),
    ]
    if apply_flag:
        args.append("--apply-approved-plan")
    if diff_flag:
        args.append("--generate-diff")
    return runner.invoke(app, args)


def _invoke_all(tmp_path, **kwargs):
    return _invoke(
        _write_config(tmp_path),
        _write_artifact(tmp_path),
        _write_packet(tmp_path),
        _write_proposed(tmp_path),
        **kwargs,
    )


def _track_read_text(monkeypatch, path_type, sink: list[str]):
    """Record every ``Path.read_text`` call while still performing it."""
    real_read_text = path_type.read_text

    def tracking_read_text(self, *args, **kwargs):
        sink.append(str(self))
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(path_type, "read_text", tracking_read_text)


def _option_names(command: str) -> set[str]:
    """The command's declared option strings, read from the parser, not prose.

    Substring matching against rendered help cannot express "``--workspace`` is
    absent" when ``--workspace-content`` is present, so the forbidden-option
    assertions compare against these exact strings instead. ``--help`` is added
    by the framework and never appears here.
    """
    subcommand = typer.main.get_command(app).commands[command]
    names: set[str] = set()
    for parameter in subcommand.params:
        names.update(parameter.opts)
        names.update(parameter.secondary_opts)
    return names


# -- 1. CLI surface ------------------------------------------------------------


def test_generate_diff_proposal_appears_in_root_help():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "generate-diff-proposal" in result.output


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
    ):
        assert command in result.output


def test_help_exposes_exactly_the_declared_options():
    assert _option_names("generate-diff-proposal") == {
        "--project-config",
        "--approved-plan",
        "--workspace-content",
        "--proposed-content",
        "--apply-approved-plan",
        "--generate-diff",
        "--format",
    }

    result = runner.invoke(app, ["generate-diff-proposal", "--help"])
    assert result.exit_code == 0
    for present in (
        "--project-config",
        "--approved-plan",
        "--workspace-content",
        "--proposed-content",
        "--apply-approved-plan",
        "--generate-diff",
        "--format",
        "--help",
    ):
        assert present in result.output


def test_help_hides_forbidden_options():
    declared = _option_names("generate-diff-proposal")

    # Compared against the *declared* option strings, not against the rendered
    # prose: `--workspace-content` legitimately contains `--workspace`.
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
        "--apply-patch",
        "--run",
        "--verify",
    ):
        assert absent not in declared

    result = runner.invoke(app, ["generate-diff-proposal", "--help"])
    for absent in (
        "--output",
        "--real-model",
        "--body-file",
        "--context-file",
        "--audit-dir",
        "--inspect-workspace",
        "--read-contents",
        "--generate-proposal",
        "--apply-patch",
    ):
        assert absent not in result.output

    # Passing one is an error, not a silently ignored argument.
    for rejected_flag in ("--real-model", "--apply-patch", "--output", "--edit"):
        rejected = runner.invoke(app, ["generate-diff-proposal", rejected_flag])
        assert rejected.exit_code != 0


@pytest.mark.parametrize(
    "command, present, absent",
    [
        (
            "l2-read-workspace-files",
            ("--project-config", "--approved-plan", "--apply-approved-plan",
             "--read-contents", "--format"),
            ("--generate-diff", "--proposed-content", "--apply-patch", "--edit-files"),
        ),
        (
            "generate-patch-proposal",
            ("--project-config", "--approved-plan", "--apply-approved-plan",
             "--generate-proposal", "--format"),
            ("--generate-diff", "--proposed-content", "--workspace-content",
             "--apply-patch"),
        ),
        (
            "l2-inspect-workspace",
            ("--project-config", "--approved-plan", "--apply-approved-plan",
             "--inspect-workspace", "--format"),
            ("--generate-diff", "--proposed-content", "--workspace-content"),
        ),
        (
            "l2-dry-run",
            ("--project-config", "--approved-plan", "--format"),
            ("--generate-diff", "--proposed-content", "--workspace-content"),
        ),
        (
            "generate-plan",
            ("--project-config", "--repo", "--issue", "--title", "--body-file",
             "--format"),
            ("--generate-diff", "--proposed-content", "--approved-plan"),
        ),
        (
            "generate-model-plan",
            ("--project-config", "--issue", "--title", "--body-file", "--model",
             "--real-model"),
            ("--generate-diff", "--proposed-content", "--approved-plan"),
        ),
    ],
)
def test_existing_command_options_are_unchanged(command, present, absent):
    declared = _option_names(command)

    for option in present:
        assert option in declared
    for option in absent:
        assert option not in declared


def test_no_apply_edit_or_implement_command_exists():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    for absent in ("apply-diff", "apply-patch", "approve-plan", "implement", "edit-files"):
        assert absent not in result.output

    for absent in (
        "apply-diff",
        "apply-diff-proposal",
        "apply-patch",
        "edit-files",
        "implement-plan",
        "run-verification",
    ):
        assert runner.invoke(app, [absent, "--help"]).exit_code != 0


# -- 2. fail closed: the two flags come before any file read -------------------


def test_missing_apply_flag_fails_before_any_file_is_read(tmp_path, monkeypatch):
    config_path = _write_config(tmp_path)
    read: list[str] = []
    _track_read_text(monkeypatch, type(config_path), read)

    result = _invoke(
        config_path,
        _write_artifact(tmp_path),
        _write_packet(tmp_path),
        _write_proposed(tmp_path),
        apply_flag=False,
    )

    assert result.exit_code == 1
    assert "--apply-approved-plan" in result.stderr
    assert result.stdout.strip() == ""
    # Nothing at all was read: not an input, and not even the config.
    assert read == []
    assert SUMMARY_MARKER not in result.output


def test_missing_generate_diff_flag_fails_before_any_file_is_read(
    tmp_path, monkeypatch
):
    config_path = _write_config(tmp_path)
    read: list[str] = []
    _track_read_text(monkeypatch, type(config_path), read)

    result = _invoke(
        config_path,
        _write_artifact(tmp_path),
        _write_packet(tmp_path),
        _write_proposed(tmp_path),
        diff_flag=False,
    )

    assert result.exit_code == 1
    assert "--generate-diff" in result.stderr
    assert result.stdout.strip() == ""
    assert read == []
    assert SUMMARY_MARKER not in result.output


@pytest.mark.parametrize(
    "missing", [{"apply_approved_plan": False}, {"generate_diff": False}]
)
def test_missing_flags_fail_with_the_injected_helper(tmp_path, missing):
    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, **missing)

    assert excinfo.value.exit_code == 1


# -- 3. fail closed: the workspace guard, before any input is read -------------


@pytest.mark.parametrize(
    "which, label",
    [
        ("approved_plan", "--approved-plan"),
        ("workspace_content", "--workspace-content"),
        ("proposed_content", "--proposed-content"),
    ],
)
def test_any_input_inside_the_workspace_is_rejected_before_it_is_read(
    tmp_path, monkeypatch, which, label
):
    config_path = _write_config(tmp_path)
    workspace = _workspace_path(tmp_path)
    workspace.mkdir()

    payloads = {
        "approved_plan": _artifact(),
        "workspace_content": _packet(),
        "proposed_content": _proposed(),
    }
    inside = workspace / f"{which}.json"
    inside.write_text(
        json.dumps(payloads[which]) + "\nSENTINEL_WORKSPACE_INPUT_CONTENT",
        encoding="utf-8",
    )

    read: list[str] = []
    _track_read_text(monkeypatch, type(inside), read)

    kwargs = {
        "approved_plan": _write_artifact(tmp_path),
        "workspace_content": _write_packet(tmp_path),
        "proposed_content": _write_proposed(tmp_path),
    }
    kwargs[which] = inside

    result = _invoke(
        config_path,
        kwargs["approved_plan"],
        kwargs["workspace_content"],
        kwargs["proposed_content"],
    )

    assert result.exit_code == 1
    assert f"{label} is inside the project's configured" in result.stderr
    assert "No input was read" in result.stderr
    assert result.stdout.strip() == ""
    # The guard ran before *any* input read: only the config was opened, even
    # when the offending input is the last of the three.
    assert read == [str(config_path)]
    assert "SENTINEL_WORKSPACE_INPUT_CONTENT" not in result.output


def test_an_input_in_a_workspace_subdirectory_is_also_rejected(tmp_path):
    config_path = _write_config(tmp_path)
    nested = _workspace_path(tmp_path) / "docs" / "packets"
    nested.mkdir(parents=True)
    inside = nested / "workspace_content.json"
    inside.write_text(json.dumps(_packet()), encoding="utf-8")

    result = _invoke(
        config_path,
        _write_artifact(tmp_path),
        inside,
        _write_proposed(tmp_path),
    )

    assert result.exit_code == 1
    assert "repo.workspace_path" in result.stderr
    assert result.stdout.strip() == ""


def test_unloadable_project_config_fails_before_any_input_is_read(
    tmp_path, monkeypatch
):
    bad_config = tmp_path / "broken.yaml"
    bad_config.write_text("project_id: demo_project\n", encoding="utf-8")
    read: list[str] = []
    _track_read_text(monkeypatch, type(bad_config), read)

    result = _invoke(
        bad_config,
        _write_artifact(tmp_path),
        _write_packet(tmp_path),
        _write_proposed(tmp_path),
    )

    assert result.exit_code == 1
    assert "No input was read" in result.stderr
    assert result.stdout.strip() == ""
    assert read == [str(bad_config)]


@pytest.mark.parametrize(
    "which, label",
    [
        ("approved_plan", "--approved-plan"),
        ("workspace_content", "--workspace-content"),
        ("proposed_content", "--proposed-content"),
    ],
)
def test_a_missing_input_fails_cleanly(tmp_path, capsys, which, label):
    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, **{which: tmp_path / "does_not_exist.json"})

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert f"could not read {label}" in captured.err
    assert captured.out.strip() == ""


def test_command_reads_only_the_four_explicit_files(tmp_path, monkeypatch, capsys):
    config_path = _write_config(tmp_path)
    artifact_path = _write_artifact(tmp_path)
    packet_path = _write_packet(tmp_path)
    proposed_path = _write_proposed(tmp_path)
    read: list[str] = []
    _track_read_text(monkeypatch, type(config_path), read)

    _run(
        tmp_path,
        project_config=config_path,
        approved_plan=artifact_path,
        workspace_content=packet_path,
        proposed_content=proposed_path,
    )

    capsys.readouterr()
    assert read == [
        str(config_path),
        str(artifact_path),
        str(packet_path),
        str(proposed_path),
    ]


# -- 4. fail closed, in order, on each input -----------------------------------


@pytest.mark.parametrize(
    "text", ["not json at all", '{"approval": ', "```json\n{}\n```", "[]", ""]
)
def test_invalid_approved_plan_fails_before_the_later_inputs_are_read(
    tmp_path, monkeypatch, capsys, text
):
    artifact_path = _write_artifact(tmp_path, text)
    packet_path = _write_packet(tmp_path)
    proposed_path = _write_proposed(tmp_path)
    read: list[str] = []
    _track_read_text(monkeypatch, type(artifact_path), read)

    with pytest.raises(typer.Exit) as excinfo:
        _run(
            tmp_path,
            approved_plan=artifact_path,
            workspace_content=packet_path,
            proposed_content=proposed_path,
        )

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert "ApprovedPlanParseError" in captured.err
    assert "The remaining inputs were not read" in captured.err
    assert captured.out.strip() == ""
    assert str(packet_path) not in read
    assert str(proposed_path) not in read


def test_invalid_approved_plan_artifact_fails_before_generation(tmp_path, capsys):
    artifact = _artifact()
    artifact["approval"]["approval_text"] = "I approve this plan"

    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, approved_plan=_write_artifact(tmp_path, artifact))

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert "ApprovedPlanValidationError" in captured.err
    assert captured.out.strip() == ""
    assert SUMMARY_MARKER not in captured.err
    assert REQUIRED_APPROVAL_TEXT not in captured.err


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param("not json at all", id="not-json"),
        pytest.param("[]", id="json-array"),
        pytest.param({"mode": "l2-inspect-workspace"}, id="wrong-mode"),
        pytest.param({}, id="empty-object"),
    ],
)
def test_invalid_workspace_content_fails_before_proposed_content_is_read(
    tmp_path, monkeypatch, capsys, payload
):
    packet_path = _write_packet(tmp_path, payload)
    proposed_path = _write_proposed(tmp_path)
    read: list[str] = []
    _track_read_text(monkeypatch, type(packet_path), read)

    with pytest.raises(typer.Exit) as excinfo:
        _run(
            tmp_path, workspace_content=packet_path, proposed_content=proposed_path
        )

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert "DiffProposalInput" in captured.err
    assert "The proposed content was not read" in captured.err
    assert captured.out.strip() == ""
    assert str(proposed_path) not in read


def test_a_packet_claiming_edits_or_commands_is_refused(tmp_path, capsys):
    payload = _packet()
    payload["workspace_content"]["files_edited"] = True

    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, workspace_content=_write_packet(tmp_path, payload))

    assert excinfo.value.exit_code == 1
    assert "DiffProposalInputValidationError" in capsys.readouterr().err


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param("not json", id="not-json"),
        pytest.param({}, id="empty-object"),
        pytest.param({"schema_version": "proposed-content.v9"}, id="wrong-version"),
    ],
)
def test_invalid_proposed_content_fails_before_generation(tmp_path, capsys, payload):
    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, proposed_content=_write_proposed(tmp_path, payload))

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert "DiffProposalInput" in captured.err
    assert captured.out.strip() == ""


@pytest.mark.parametrize(
    "config_overrides",
    [
        pytest.param({"project_id": "a_different_project"}, id="project-id"),
        pytest.param({"github_repo": "someone-else/widgets"}, id="repo"),
        pytest.param({"github_repo": REPO.upper()}, id="case-folded-repo"),
    ],
)
def test_identity_mismatch_fails(tmp_path, capsys, config_overrides):
    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, project_config=_write_config(tmp_path, **config_overrides))

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert "DiffProposalGenerationError" in captured.err
    assert captured.out.strip() == ""
    assert SUMMARY_MARKER not in captured.err


def test_out_of_scope_proposed_path_fails_with_no_stdout(tmp_path, capsys):
    proposed = _proposed([_change(PLAN_FORBIDDEN, PROPOSED_A)])

    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, proposed_content=_write_proposed(tmp_path, proposed))

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert "DiffProposalGenerationError" in captured.err
    assert captured.out.strip() == ""


def test_redacted_source_fails_with_no_stdout(tmp_path, capsys):
    packet = _packet(
        [
            _read_item(
                PLAN_FILE_A,
                "api_key = '[REDACTED]'\n",
                redacted=True,
                redaction_count=1,
                redaction_kinds=["secret_assignment"],
            )
        ]
    )

    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, workspace_content=_write_packet(tmp_path, packet))

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert "redacted" in captured.err
    assert captured.out.strip() == ""


def test_secret_like_generated_diff_fails_without_echoing_it(tmp_path, capsys):
    proposed = _proposed(
        [_change(content=ORIGINAL_A + f'api_key = "{SECRET_VALUE}"\n')]
    )

    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, proposed_content=_write_proposed(tmp_path, proposed))

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert "secret_assignment" in captured.err
    assert SECRET_VALUE not in captured.err
    assert captured.out.strip() == ""


# -- 5. the success path -------------------------------------------------------


def test_valid_command_prints_a_parseable_diff_proposal_artifact(tmp_path, capsys):
    _run(tmp_path)
    stdout = capsys.readouterr().out

    proposal = parse_diff_proposal_artifact(stdout)

    assert proposal.schema_version == DIFF_PROPOSAL_SCHEMA_VERSION
    assert proposal.mode == DIFF_PROPOSAL_MODE
    assert [change.path for change in proposal.changes] == [PLAN_FILE_A]
    assert proposal.changes[0].change_type == "modify"
    assert proposal.changes[0].unified_diff.startswith(f"--- a/{PLAN_FILE_A}\n")
    assert proposal.provenance.engine == "deterministic"
    assert proposal.provenance.real_call is False
    assert proposal.provenance.model is None
    assert proposal.provenance.generated_at is None
    assert proposal.source_contents_read is True
    assert proposal.diffs_generated is True
    assert proposal.files_edited is False
    assert proposal.commands_run is False
    assert proposal.applies_cleanly_checked is False
    assert proposal.requires_human_review is True
    assert proposal.next_authorization_required.startswith("Phase 5F or later")


def test_create_through_the_cli(tmp_path, capsys):
    proposed = _proposed(
        [_change(PLAN_FILE_NEW, CREATED_TEXT, change_type="create")]
    )

    _run(tmp_path, proposed_content=_write_proposed(tmp_path, proposed))
    proposal = parse_diff_proposal_artifact(capsys.readouterr().out)

    assert proposal.changes[0].change_type == "create"
    assert proposal.changes[0].unified_diff.startswith("--- /dev/null\n")
    assert proposal.source_contents_read is False


def test_noop_change_is_omitted_through_the_cli(tmp_path, capsys):
    proposed = _proposed([_change(content=ORIGINAL_A)])

    _run(tmp_path, proposed_content=_write_proposed(tmp_path, proposed))
    proposal = parse_diff_proposal_artifact(capsys.readouterr().out)

    assert proposal.changes == []
    assert proposal.omitted_paths == [PLAN_FILE_A]


def test_success_through_the_cli_matches_the_helper(tmp_path):
    result = _invoke_all(tmp_path)

    assert result.exit_code == 0
    proposal = parse_diff_proposal_artifact(result.stdout)
    assert proposal.provenance.project_id == PROJECT_ID
    assert proposal.approved_plan.approval.approved_by == APPROVER


def test_stdout_is_the_artifact_with_no_wrapper(tmp_path, capsys):
    _run(tmp_path)
    payload = json.loads(capsys.readouterr().out)

    assert set(payload) == {
        "schema_version",
        "mode",
        "provenance",
        "approved_plan",
        "patch_proposal",
        "changes",
        "omitted_paths",
        "assumptions",
        "risks",
        "open_questions",
        "source_contents_read",
        "diffs_generated",
        "files_edited",
        "commands_run",
        "applies_cleanly_checked",
        "requires_human_review",
        "next_authorization_required",
    }
    # No `notice` envelope: the artifact says what it is inside itself.
    assert "notice" not in payload
    assert payload["patch_proposal"] is None

    for change in payload["changes"]:
        assert set(change) == {
            "path",
            "change_type",
            "unified_diff",
            # Phase 5F2C (diff-proposal.v2): both ends of the transformation,
            # bound to the artifact so an approval means "these exact bytes
            # become those exact bytes" rather than "here is a diff".
            "pre_image_sha256",
            "post_image_sha256",
            "rationale",
            "risks",
            "requires_human_review",
        }
        # A modify carries a real pre-image digest; a create carries null.
        if change["change_type"] == "modify":
            assert len(change["pre_image_sha256"]) == 64
        else:
            assert change["pre_image_sha256"] is None
        assert len(change["post_image_sha256"]) == 64


def test_output_carries_no_workspace_path_absolute_path_or_credential(
    tmp_path, capsys
):
    _run(tmp_path)
    stdout = capsys.readouterr().out

    workspace = _workspace_path(tmp_path)
    for absent in (
        str(workspace),
        workspace.name,
        "workspace_path",
        str(tmp_path),
        "api_key",
        "AIDO_LITELLM",
        "Bearer ",
        "base_url",
        "http://",
        "https://",
        '"command"',
        '"command_output"',
        '"applied"',
        '"apply_result"',
        '"stdout"',
        "canonical_relative_path",
        "l2-read-workspace-files",
    ):
        assert absent not in stdout

    payload = json.loads(stdout)
    assert "endpoint_host" not in payload["provenance"]


def test_raw_input_text_is_not_echoed_around_the_artifact(tmp_path, capsys):
    artifact_path = _write_artifact(tmp_path)
    packet_path = _write_packet(tmp_path)
    proposed_path = _write_proposed(tmp_path)
    raw_artifact = artifact_path.read_text(encoding="utf-8")
    raw_packet = packet_path.read_text(encoding="utf-8")
    raw_proposed = proposed_path.read_text(encoding="utf-8")

    _run(
        tmp_path,
        approved_plan=artifact_path,
        workspace_content=packet_path,
        proposed_content=proposed_path,
    )
    stdout = capsys.readouterr().out

    for raw in (raw_artifact, raw_packet, raw_proposed):
        assert raw not in stdout
    # The plan summary appears exactly once — inside the embedded snapshot.
    assert stdout.count(SUMMARY_MARKER) == 1
    # The verification prose appears exactly once, in that same snapshot, and
    # was not executed: no command output is here.
    assert stdout.count(VERIFICATION_MARKER) == 1


def test_approval_text_appears_only_inside_the_embedded_snapshot(tmp_path, capsys):
    _run(tmp_path)
    payload = json.loads(capsys.readouterr().out)

    assert (
        payload["approved_plan"]["approval"]["approval_text"] == REQUIRED_APPROVAL_TEXT
    )
    assert "approval" not in payload
    assert "approval_text" not in payload["provenance"]


def test_original_source_appears_only_as_diff_context(tmp_path, capsys):
    _run(tmp_path)
    payload = json.loads(capsys.readouterr().out)

    diff = payload["changes"][0]["unified_diff"]
    assert "-    return amount" in diff
    assert "+    return round(amount, 2)" in diff
    # There is no separate content field for it to live in.
    for absent in ("content_text", "before_content", "after_content", "file_contents"):
        assert absent not in json.dumps(payload)


# -- 6. no workspace IO, no network, no env, no model, no writes ---------------


def _track_filesystem(monkeypatch, sink: list[str]):
    """Record every path handed to an existence/listing/resolution entry point.

    ``os.path.abspath`` is deliberately **not** tracked or blocked: it is what
    ``_is_same_or_under`` uses to compare strings, and it performs no filesystem
    access.
    """
    for module, name in (
        (os, "stat"),
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


def test_plan_paths_and_workspace_are_never_touched(tmp_path, monkeypatch, capsys):
    touched: list[str] = []
    _track_filesystem(monkeypatch, touched)

    _run(tmp_path)

    capsys.readouterr()
    workspace = str(_workspace_path(tmp_path))
    for path in touched:
        assert workspace not in path
        for plan_path in (PLAN_FILE_A, PLAN_FILE_NEW, PLAN_FORBIDDEN):
            assert plan_path not in path.replace("\\", "/")
    assert not _workspace_path(tmp_path).exists()


def test_no_workspace_listing_globbing_or_resolution_happens(
    tmp_path, monkeypatch, capsys
):
    config_path = _write_config(tmp_path)
    artifact_path = _write_artifact(tmp_path)
    packet_path = _write_packet(tmp_path)
    proposed_path = _write_proposed(tmp_path)

    # Warm the lazy imports first, so the detonators below catch the command's
    # own behavior rather than the import machinery's.
    _run(
        tmp_path,
        project_config=config_path,
        approved_plan=artifact_path,
        workspace_content=packet_path,
        proposed_content=proposed_path,
    )
    capsys.readouterr()

    def _blocked(*args, **kwargs):
        raise AssertionError("generate-diff-proposal must not inspect the filesystem")

    monkeypatch.setattr(os, "listdir", _blocked)
    monkeypatch.setattr(os, "scandir", _blocked)
    monkeypatch.setattr(os, "walk", _blocked)
    monkeypatch.setattr(os.path, "realpath", _blocked)
    monkeypatch.setattr(os, "stat", _blocked)

    _run(
        tmp_path,
        project_config=config_path,
        approved_plan=artifact_path,
        workspace_content=packet_path,
        proposed_content=proposed_path,
    )

    assert parse_diff_proposal_artifact(capsys.readouterr().out).changes


def test_no_env_read_no_socket_and_no_subprocess(tmp_path, monkeypatch, capsys):
    def _blocked(*args, **kwargs):
        raise AssertionError(
            "generate-diff-proposal must not read env, network, or processes"
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

    assert parse_diff_proposal_artifact(capsys.readouterr().out).changes


def test_command_uses_no_llm_client_httpx_or_github_client(
    tmp_path, monkeypatch, capsys
):
    import ai_dev_orchestrator.github.client as github_client
    import ai_dev_orchestrator.llm.client as llm_client
    import ai_dev_orchestrator.llm.config as llm_config

    def _blocked(*args, **kwargs):
        raise AssertionError(
            "generate-diff-proposal must not build a client or read llm config"
        )

    monkeypatch.setattr(github_client.GitHubClient, "__init__", _blocked)
    monkeypatch.setattr(github_client.GitHubClient, "get_issue", _blocked)
    monkeypatch.setattr(llm_client.LLMClient, "__init__", _blocked)
    monkeypatch.setattr(llm_config, "load_llm_client_config_from_env", _blocked)
    monkeypatch.setattr(cli, "_build_real_llm_client", _blocked)
    monkeypatch.setattr(cli, "_read_real_llm_env", _blocked)

    _run(tmp_path)

    assert parse_diff_proposal_artifact(capsys.readouterr().out).changes


def test_command_writes_no_files_and_stamps_no_approval(tmp_path, capsys):
    config_path = _write_config(tmp_path)
    artifact_path = _write_artifact(tmp_path)
    packet_path = _write_packet(tmp_path)
    proposed_path = _write_proposed(tmp_path)
    before = sorted(p.name for p in tmp_path.iterdir())
    contents_before = {
        path: path.read_text(encoding="utf-8")
        for path in (artifact_path, packet_path, proposed_path)
    }

    _run(
        tmp_path,
        project_config=config_path,
        approved_plan=artifact_path,
        workspace_content=packet_path,
        proposed_content=proposed_path,
    )

    capsys.readouterr()
    # No proposal file was written, no approval was stamped, nothing rewritten.
    assert sorted(p.name for p in tmp_path.iterdir()) == before
    for path, text in contents_before.items():
        assert path.read_text(encoding="utf-8") == text


def test_helper_source_names_no_client_transport_env_or_patch_symbol():
    import inspect

    source = (
        inspect.getsource(cli._run_generate_diff_proposal)
        + inspect.getsource(cli.generate_diff_proposal)
        + inspect.getsource(cli._read_diff_proposal_input)
        + inspect.getsource(cli._fail_diff_proposal)
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
    ):
        assert forbidden not in source


def test_existing_commands_still_behave_the_same():
    smoke = runner.invoke(app, ["llm-smoke-test"])
    assert smoke.exit_code == 0
    assert "No real model was called." in smoke.output

    version = runner.invoke(app, ["version"])
    assert version.exit_code == 0
