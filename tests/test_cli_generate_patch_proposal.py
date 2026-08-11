"""Phase 5E1 tests: the ``generate-patch-proposal`` command.

The command reads a project config and a human-approved L1 plan artifact,
generates a **proposal-only** patch proposal artifact deterministically and
offline, and prints it to stdout. It performs no L2 action, so these tests
assert absence far more than presence: no target project workspace is read,
listed, stat'd, or resolved; no file contents are read beyond the two files
named on the command line; no diff is generated; no file is edited; no command
is executed; no environment variable is read; no socket is opened; no model is
called; nothing is fetched from or written to GitHub; no artifact file is
written; and no approval is stamped.

Every artifact here is literal JSON written into pytest's own ``tmp_path``. The
configured ``workspace_path`` points at a directory that is normally never
created — the two rejection tests that do create one create it under
``tmp_path`` and never read anything inside it.
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
from ai_dev_orchestrator.handoff import REQUIRED_APPROVAL_TEXT
from ai_dev_orchestrator.patch_proposal import (
    PATCH_PROPOSAL_MODE,
    PATCH_PROPOSAL_SCHEMA_VERSION,
    parse_patch_proposal_artifact,
)

runner = CliRunner()

PROJECT_ID = "demo_project"
REPO = "demo/widgets"
ISSUE_NUMBER = 42
TITLE = "Add currency formatting helper"
APPROVER = "operator@example.invalid"
APPROVED_AT = "2026-01-02T04:00:00+00:00"
PLAN_MODEL = "fake-planner-model"

# Distinctive markers, so a test can prove what did and did not reach stdout.
SUMMARY_MARKER = "SENTINEL_PLAN_SUMMARY_PROSE"
VERIFICATION_MARKER = "SENTINEL_VERIFICATION_TEXT"

# Path-shaped plan strings. Nothing below is ever opened, stat'd, listed, or
# resolved: they are compared and copied as strings only.
PLAN_FILE_A = "src/billing/sentinel_never_touched_a.py"
PLAN_FILE_B = "tests/test_sentinel_never_touched_b.py"
PLAN_FORBIDDEN = "secrets/sentinel_never_touched_forbidden.env"

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
    "proposed_steps": [
        "Review where invoice totals are formatted today.",
        "Describe a single shared helper for a human to implement.",
    ],
    "files_likely_to_change": [PLAN_FILE_A, PLAN_FILE_B],
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


def _artifact() -> dict:
    """A fresh, fully valid artifact dict. Callers mutate their own copy."""
    return {
        "approval": copy.deepcopy(VALID_APPROVAL),
        "plan_provenance": copy.deepcopy(VALID_PROVENANCE),
        "plan": copy.deepcopy(VALID_PLAN),
        "project_id": PROJECT_ID,
        "repo": REPO,
        "issue_number": ISSUE_NUMBER,
    }


def _workspace_path(tmp_path):
    """A workspace path that is a **string only**: never created or touched."""
    return tmp_path / "never_touched_workspace"


def _write_config(
    tmp_path,
    *,
    project_id: str = PROJECT_ID,
    github_repo: str = REPO,
    max_changed_files: int = 20,
):
    """Write a temp project config inside the test's own tmp dir."""
    path = tmp_path / "project.yaml"
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


def _write_artifact(
    tmp_path, artifact: dict | str | None = None, name: str = "approved_plan.json"
):
    """Write an approved-plan artifact **outside** the configured workspace."""
    path = tmp_path / name
    text = (
        artifact
        if isinstance(artifact, str)
        else json.dumps(_artifact() if artifact is None else artifact)
    )
    path.write_text(text, encoding="utf-8")
    return path


def _run(tmp_path, **overrides):
    """Call the private helper directly, so file reads can be tracked."""
    kwargs = {
        "project_config": overrides.pop("project_config", None)
        or _write_config(tmp_path),
        "approved_plan": overrides.pop("approved_plan", None)
        or _write_artifact(tmp_path),
        "apply_approved_plan": True,
        "generate_proposal": True,
    }
    kwargs.update(overrides)
    return cli._run_generate_patch_proposal(**kwargs)


def _invoke(config_path, artifact_path, *, apply_flag=True, generate_flag=True):
    args = [
        "generate-patch-proposal",
        "--project-config",
        str(config_path),
        "--approved-plan",
        str(artifact_path),
    ]
    if apply_flag:
        args.append("--apply-approved-plan")
    if generate_flag:
        args.append("--generate-proposal")
    return runner.invoke(app, args)


def _track_read_text(monkeypatch, path_type, sink: list[str]):
    """Record every ``Path.read_text`` call while still performing it."""
    real_read_text = path_type.read_text

    def tracking_read_text(self, *args, **kwargs):
        sink.append(str(self))
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(path_type, "read_text", tracking_read_text)


# -- 1. CLI surface ------------------------------------------------------------


def test_generate_patch_proposal_appears_in_root_help():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "generate-patch-proposal" in result.output


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
    ):
        assert command in result.output


def test_help_exposes_only_the_four_options_and_format():
    result = runner.invoke(app, ["generate-patch-proposal", "--help"])

    assert result.exit_code == 0
    for present in (
        "--project-config",
        "--approved-plan",
        "--apply-approved-plan",
        "--generate-proposal",
        "--format",
        "--help",
    ):
        assert present in result.output


def test_help_hides_forbidden_options():
    result = runner.invoke(app, ["generate-patch-proposal", "--help"])

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
        "--read-contents",
        "--diff",
        "--apply-patch",
    ):
        assert absent not in result.output

    # Passing one is an error, not a silently ignored argument.
    for rejected_flag in ("--real-model", "--diff", "--apply-patch", "--output"):
        rejected = runner.invoke(app, ["generate-patch-proposal", rejected_flag])
        assert rejected.exit_code != 0


def test_l2_inspect_workspace_help_unchanged():
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
    for absent in ("--generate-proposal", "--diff", "--apply-patch", "--read-contents"):
        assert absent not in result.output


def test_l2_dry_run_help_unchanged():
    result = runner.invoke(app, ["l2-dry-run", "--help"])

    assert result.exit_code == 0
    for present in (
        "--project-config",
        "--approved-plan",
        "--apply-approved-plan",
        "--format",
    ):
        assert present in result.output
    for absent in ("--generate-proposal", "--inspect-workspace", "--diff", "--model"):
        assert absent not in result.output


def test_generate_plan_help_unchanged():
    result = runner.invoke(app, ["generate-plan", "--help"])

    assert result.exit_code == 0
    for present in (
        "--project-config",
        "--repo",
        "--issue",
        "--title",
        "--body-file",
        "--format",
    ):
        assert present in result.output
    for absent in (
        "--real-model",
        "--model",
        "--approved-plan",
        "--apply-approved-plan",
        "--generate-proposal",
    ):
        assert absent not in result.output


def test_generate_model_plan_help_unchanged():
    result = runner.invoke(app, ["generate-model-plan", "--help"])

    assert result.exit_code == 0
    for present in (
        "--project-config",
        "--issue",
        "--title",
        "--body-file",
        "--model",
        "--real-model",
    ):
        assert present in result.output
    for absent in (
        "--approved-plan",
        "--apply-approved-plan",
        "--generate-proposal",
        "--diff",
    ):
        assert absent not in result.output


def test_no_other_command_gained_a_proposal_path():
    for command in (
        "generate-plan",
        "generate-model-plan",
        "real-llm-smoke-test",
        "llm-smoke-test",
        "inspect-issue",
        "l2-dry-run",
        "l2-inspect-workspace",
    ):
        result = runner.invoke(app, [command, "--help"])
        assert result.exit_code == 0
        assert "--generate-proposal" not in result.output
        assert "--apply-patch" not in result.output
        assert "--diff" not in result.output


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


def test_missing_generate_flag_fails_before_any_file_is_read(tmp_path, monkeypatch):
    config_path = _write_config(tmp_path)
    artifact_path = _write_artifact(tmp_path)
    read: list[str] = []
    _track_read_text(monkeypatch, type(config_path), read)

    result = _invoke(config_path, artifact_path, generate_flag=False)

    assert result.exit_code == 1
    assert "--generate-proposal" in result.stderr
    assert result.stdout.strip() == ""
    assert read == []
    assert SUMMARY_MARKER not in result.output


@pytest.mark.parametrize(
    "missing", [{"apply_approved_plan": False}, {"generate_proposal": False}]
)
def test_missing_flags_fail_with_the_injected_helper(tmp_path, missing):
    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, **missing)

    assert excinfo.value.exit_code == 1


# -- 3. fail closed: the workspace guard and the two file reads ----------------


def test_artifact_inside_workspace_is_rejected_before_it_is_read(tmp_path, monkeypatch):
    config_path = _write_config(tmp_path)
    workspace = _workspace_path(tmp_path)
    workspace.mkdir()
    inside = workspace / "approved_plan.json"
    inside.write_text(
        json.dumps(_artifact()) + "\nSENTINEL_WORKSPACE_ARTIFACT_CONTENT",
        encoding="utf-8",
    )

    read: list[str] = []
    _track_read_text(monkeypatch, type(inside), read)

    result = _invoke(config_path, inside)

    assert result.exit_code == 1
    assert "is inside the project's configured repo.workspace_path" in result.stderr
    assert "no proposal was generated" in result.stderr
    assert result.stdout.strip() == ""
    # The guard ran before the read, and no content surfaced anywhere.
    assert read == [str(config_path)]
    assert "SENTINEL_WORKSPACE_ARTIFACT_CONTENT" not in result.output
    assert SUMMARY_MARKER not in result.output


def test_artifact_in_a_workspace_subdirectory_is_also_rejected(tmp_path):
    config_path = _write_config(tmp_path)
    nested = _workspace_path(tmp_path) / "docs" / "plans"
    nested.mkdir(parents=True)
    inside = nested / "approved_plan.json"
    inside.write_text(json.dumps(_artifact()), encoding="utf-8")

    result = _invoke(config_path, inside)

    assert result.exit_code == 1
    assert "repo.workspace_path" in result.stderr
    assert result.stdout.strip() == ""


def test_unloadable_project_config_fails_before_the_artifact_is_read(
    tmp_path, monkeypatch
):
    bad_config = tmp_path / "broken.yaml"
    bad_config.write_text("project_id: demo_project\n", encoding="utf-8")
    artifact_path = _write_artifact(tmp_path)
    read: list[str] = []
    _track_read_text(monkeypatch, type(bad_config), read)

    result = _invoke(bad_config, artifact_path)

    assert result.exit_code == 1
    assert "The approved plan artifact was not read" in result.stderr
    assert result.stdout.strip() == ""
    assert read == [str(bad_config)]


def test_missing_artifact_outside_workspace_fails_cleanly(tmp_path, capsys):
    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, approved_plan=tmp_path / "does_not_exist.json")

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert "could not read --approved-plan" in captured.err
    assert "No proposal was generated." in captured.err
    assert captured.out.strip() == ""


def test_command_reads_only_the_two_explicit_files(tmp_path, monkeypatch, capsys):
    config_path = _write_config(tmp_path)
    artifact_path = _write_artifact(tmp_path)
    read: list[str] = []
    _track_read_text(monkeypatch, type(config_path), read)

    _run(tmp_path, project_config=config_path, approved_plan=artifact_path)

    capsys.readouterr()
    # Exactly two file reads, both named on the command line, config first.
    assert read == [str(config_path), str(artifact_path)]


# -- 4. fail closed: invalid artifact, identity mismatch, generation errors ----


@pytest.mark.parametrize(
    "text",
    ["not json at all", '{"approval": ', "```json\n{}\n```", "[]", ""],
)
def test_invalid_json_artifact_fails_before_generation(tmp_path, capsys, text):
    artifact_path = _write_artifact(tmp_path, text)

    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, approved_plan=artifact_path)

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert "ApprovedPlanParseError" in captured.err
    assert "No proposal was generated." in captured.err
    assert captured.out.strip() == ""


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
            lambda a: a["plan"].update(approval=copy.deepcopy(VALID_APPROVAL)),
            id="forged-approval-inside-plan",
        ),
        pytest.param(
            lambda a: a["plan"].update(automation_level="L2"), id="escalated-plan"
        ),
    ],
)
def test_invalid_approved_artifact_fails_before_generation(tmp_path, capsys, mutate):
    artifact = _artifact()
    mutate(artifact)
    artifact_path = _write_artifact(tmp_path, artifact)

    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, approved_plan=artifact_path)

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert "ApprovedPlanValidationError" in captured.err
    assert captured.out.strip() == ""
    # The category is loud; the content stays quiet.
    assert SUMMARY_MARKER not in captured.err
    assert REQUIRED_APPROVAL_TEXT not in captured.err


@pytest.mark.parametrize(
    "config_overrides",
    [
        pytest.param({"project_id": "a_different_project"}, id="project-id"),
        pytest.param({"github_repo": "someone-else/widgets"}, id="repo"),
        pytest.param({"github_repo": REPO.upper()}, id="case-folded-repo"),
    ],
)
def test_identity_mismatch_fails(tmp_path, capsys, config_overrides):
    config_path = _write_config(tmp_path, **config_overrides)

    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, project_config=config_path)

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert "PatchProposalGenerationError" in captured.err
    assert "does not match this project config exactly" in captured.err
    assert captured.out.strip() == ""
    assert SUMMARY_MARKER not in captured.err


def test_too_many_paths_fails_with_no_stdout(tmp_path, capsys):
    artifact = _artifact()
    artifact["plan"]["files_likely_to_change"] = [
        f"src/module_{index}.py" for index in range(5)
    ]
    artifact_path = _write_artifact(tmp_path, artifact)
    config_path = _write_config(tmp_path, max_changed_files=2)

    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, project_config=config_path, approved_plan=artifact_path)

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert "max_changed_files" in captured.err
    assert captured.out.strip() == ""


def test_self_contradicting_plan_fails_with_no_stdout(tmp_path, capsys):
    artifact = _artifact()
    artifact["plan"]["files_likely_to_change"] = [PLAN_FILE_A, PLAN_FORBIDDEN]
    artifact_path = _write_artifact(tmp_path, artifact)

    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, approved_plan=artifact_path)

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert "self-contradicting" in captured.err
    assert captured.out.strip() == ""


def test_unsafe_plan_path_fails_with_no_stdout(tmp_path, capsys):
    artifact = _artifact()
    artifact["plan"]["files_likely_to_change"] = ["../outside_the_repo.py"]
    artifact_path = _write_artifact(tmp_path, artifact)

    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, approved_plan=artifact_path)

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert "PatchProposalGenerationError" in captured.err
    assert captured.out.strip() == ""


# -- 5. the success path -------------------------------------------------------


def _success_payload(tmp_path, capsys, **overrides) -> dict:
    _run(tmp_path, **overrides)
    return json.loads(capsys.readouterr().out)


def test_valid_command_prints_a_parseable_proposal_artifact(tmp_path, capsys):
    _run(tmp_path)
    stdout = capsys.readouterr().out

    proposal = parse_patch_proposal_artifact(stdout)

    assert proposal.schema_version == PATCH_PROPOSAL_SCHEMA_VERSION
    assert proposal.mode == PATCH_PROPOSAL_MODE
    assert [change.path for change in proposal.changes] == [PLAN_FILE_A, PLAN_FILE_B]
    assert all(change.change_type == "modify" for change in proposal.changes)
    assert proposal.provenance.engine == "deterministic"
    assert proposal.provenance.real_call is False
    assert proposal.provenance.model is None
    assert proposal.provenance.generated_at is None
    assert proposal.file_contents_read is False
    assert proposal.files_edited is False
    assert proposal.commands_run is False
    assert proposal.requires_human_review is True
    assert "Phase 5D2/5E2" in proposal.next_authorization_required


def test_success_through_the_cli_matches_the_helper(tmp_path):
    config_path = _write_config(tmp_path)
    artifact_path = _write_artifact(tmp_path)

    result = _invoke(config_path, artifact_path)

    assert result.exit_code == 0
    proposal = parse_patch_proposal_artifact(result.stdout)
    assert proposal.provenance.project_id == PROJECT_ID
    assert proposal.approved_plan.approval.approved_by == APPROVER


def test_stdout_is_the_artifact_with_no_wrapper(tmp_path, capsys):
    payload = _success_payload(tmp_path, capsys)

    assert set(payload) == {
        "schema_version",
        "mode",
        "provenance",
        "approved_plan",
        "changes",
        "omitted_paths",
        "assumptions",
        "risks",
        "open_questions",
        "file_contents_read",
        "files_edited",
        "commands_run",
        "requires_human_review",
        "next_authorization_required",
    }
    # No `notice` envelope: the artifact says what it is inside itself.
    assert "notice" not in payload


def test_output_carries_no_diff_content_or_command_payload(tmp_path, capsys):
    _run(tmp_path)
    stdout = capsys.readouterr().out
    payload = json.loads(stdout)

    for change in payload["changes"]:
        assert set(change) == {
            "path",
            "change_type",
            "rationale",
            "proposed_steps",
            "risks",
            "requires_human_review",
        }

    for absent in (
        '"diff"',
        '"unified_diff"',
        '"patch"',
        '"hunks"',
        '"edit_script"',
        '"content"',
        '"new_content"',
        '"file_content"',
        '"before"',
        '"after"',
        '"source_text"',
        '"command"',
        '"command_output"',
        '"stdout"',
        "@@ ",
        "--- a/",
        "+++ b/",
    ):
        assert absent not in stdout

    # The plan's required_verification text appears exactly once — inside the
    # embedded approved-plan snapshot, which Phase 5E0 requires to travel
    # unchanged. It is never lifted out into a proposal-level field, never
    # copied into a change, and it was not executed: no command output is here.
    assert stdout.count(VERIFICATION_MARKER) == 1
    assert VERIFICATION_MARKER in json.dumps(
        payload["approved_plan"]["plan"]["required_verification"]
    )
    assert "required_verification" not in payload
    for change in payload["changes"]:
        assert VERIFICATION_MARKER not in json.dumps(change)


def test_output_omits_workspace_path_absolute_paths_and_secrets(tmp_path, capsys):
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
    ):
        assert absent not in stdout

    # The proposal's OWN provenance names no endpoint at all — that field does
    # not exist on PatchProposalProvenance. The bare host inside the embedded
    # plan_provenance is part of the approved-plan snapshot, which travels
    # through unchanged by design; it is a host, never a base URL or a key.
    payload = json.loads(stdout)
    assert "endpoint_host" not in payload["provenance"]
    assert (
        payload["approved_plan"]["plan_provenance"]["endpoint_host"]
        == VALID_PROVENANCE["endpoint_host"]
    )


def test_approval_text_appears_only_inside_the_embedded_snapshot(tmp_path, capsys):
    _run(tmp_path)
    payload = json.loads(capsys.readouterr().out)

    assert (
        payload["approved_plan"]["approval"]["approval_text"] == REQUIRED_APPROVAL_TEXT
    )
    # And nowhere else: the top level has no approval block at all.
    assert "approval" not in payload
    assert "approval_text" not in payload["provenance"]


def test_raw_artifact_text_is_not_echoed_around_the_snapshot(tmp_path, capsys):
    artifact_path = _write_artifact(tmp_path)
    raw = artifact_path.read_text(encoding="utf-8")

    _run(tmp_path, approved_plan=artifact_path)
    stdout = capsys.readouterr().out

    # The snapshot is re-serialized by the model, not pasted through.
    assert raw not in stdout
    # The plan summary appears exactly once — inside the embedded snapshot.
    assert stdout.count(SUMMARY_MARKER) == 1


def test_empty_files_likely_to_change_prints_an_empty_proposal(tmp_path, capsys):
    artifact = _artifact()
    artifact["plan"]["files_likely_to_change"] = []
    artifact_path = _write_artifact(tmp_path, artifact)

    _run(tmp_path, approved_plan=artifact_path)
    proposal = parse_patch_proposal_artifact(capsys.readouterr().out)

    assert proposal.changes == []


def test_forbidden_plan_paths_are_never_proposed(tmp_path, capsys):
    proposal = parse_patch_proposal_artifact(
        (_run(tmp_path), capsys.readouterr().out)[1]
    )

    assert PLAN_FORBIDDEN not in [change.path for change in proposal.changes]


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
    config_path = _write_config(tmp_path)
    artifact_path = _write_artifact(tmp_path)
    touched: list[str] = []
    _track_filesystem(monkeypatch, touched)

    _run(tmp_path, project_config=config_path, approved_plan=artifact_path)

    capsys.readouterr()
    workspace = str(_workspace_path(tmp_path))
    for path in touched:
        assert workspace not in path
        for plan_path in (PLAN_FILE_A, PLAN_FILE_B, PLAN_FORBIDDEN):
            assert plan_path not in path.replace("\\", "/")
    # The configured workspace was never created, let alone opened.
    assert not _workspace_path(tmp_path).exists()


def test_no_workspace_listing_globbing_or_resolution_happens(
    tmp_path, monkeypatch, capsys
):
    config_path = _write_config(tmp_path)
    artifact_path = _write_artifact(tmp_path)

    # Warm the lazy imports first, so the detonators below catch the command's
    # own behavior rather than the import machinery's.
    _run(tmp_path, project_config=config_path, approved_plan=artifact_path)
    capsys.readouterr()

    def _blocked(*args, **kwargs):
        raise AssertionError("generate-patch-proposal must not inspect the filesystem")

    monkeypatch.setattr(os, "listdir", _blocked)
    monkeypatch.setattr(os, "scandir", _blocked)
    monkeypatch.setattr(os, "walk", _blocked)
    monkeypatch.setattr(os.path, "realpath", _blocked)
    monkeypatch.setattr(os, "stat", _blocked)

    _run(tmp_path, project_config=config_path, approved_plan=artifact_path)

    assert parse_patch_proposal_artifact(capsys.readouterr().out).changes


def test_no_env_read_no_socket_and_no_subprocess(tmp_path, monkeypatch, capsys):
    def _blocked(*args, **kwargs):
        raise AssertionError(
            "generate-patch-proposal must not read env, network, or processes"
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

    assert parse_patch_proposal_artifact(capsys.readouterr().out).changes


def test_command_uses_no_llm_client_httpx_or_github_client(
    tmp_path, monkeypatch, capsys
):
    import ai_dev_orchestrator.github.client as github_client
    import ai_dev_orchestrator.llm.client as llm_client
    import ai_dev_orchestrator.llm.config as llm_config

    def _blocked(*args, **kwargs):
        raise AssertionError(
            "generate-patch-proposal must not build a client or read llm config"
        )

    monkeypatch.setattr(github_client.GitHubClient, "__init__", _blocked)
    monkeypatch.setattr(github_client.GitHubClient, "get_issue", _blocked)
    monkeypatch.setattr(llm_client.LLMClient, "__init__", _blocked)
    monkeypatch.setattr(llm_config, "load_llm_client_config_from_env", _blocked)
    monkeypatch.setattr(cli, "_build_real_llm_client", _blocked)
    monkeypatch.setattr(cli, "_read_real_llm_env", _blocked)

    _run(tmp_path)

    assert parse_patch_proposal_artifact(capsys.readouterr().out).changes


def test_command_writes_no_files_and_stamps_no_approval(tmp_path, capsys):
    config_path = _write_config(tmp_path)
    artifact_path = _write_artifact(tmp_path)
    before = sorted(p.name for p in tmp_path.iterdir())
    artifact_before = artifact_path.read_text(encoding="utf-8")

    _run(tmp_path, project_config=config_path, approved_plan=artifact_path)

    capsys.readouterr()
    # No proposal file was written, no approval was stamped, nothing rewritten.
    assert sorted(p.name for p in tmp_path.iterdir()) == before
    assert artifact_path.read_text(encoding="utf-8") == artifact_before


def test_helper_source_names_no_client_transport_or_env_symbol():
    import inspect

    source = inspect.getsource(cli._run_generate_patch_proposal) + inspect.getsource(
        cli.generate_patch_proposal
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
    ):
        assert forbidden not in source


def test_existing_commands_still_behave_the_same():
    smoke = runner.invoke(app, ["llm-smoke-test"])
    assert smoke.exit_code == 0
    assert "No real model was called." in smoke.output

    version = runner.invoke(app, ["version"])
    assert version.exit_code == 0
