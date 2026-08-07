"""Phase 5C tests: the ``l2-dry-run`` command.

The command validates a human-approved L1 plan artifact and prints the scope a
**future** L2 would be bounded by. It performs no L2 action, so these tests
assert absence far more than presence: no target project workspace is read,
listed, stat'd, or resolved; no path named in a plan is touched; no
``required_verification`` entry is executed; no environment variable is read; no
socket is opened; no model is called; and nothing is fetched from or written to
GitHub.

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
STEP_MARKER = "SENTINEL_PROPOSED_STEP"
RISK_MARKER = "SENTINEL_RISK"
QUESTION_MARKER = "SENTINEL_OPEN_QUESTION"
VERIFICATION_MARKER = "SENTINEL_VERIFICATION_TEXT"

# Path-shaped plan strings. A plan is a list of *hints to validate*, never a
# list of paths to trust, and this phase does not even validate them: the tests
# below assert these strings are never opened, stat'd, listed, or resolved.
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
    "proposed_steps": [
        f"Review where invoice totals are formatted today. {STEP_MARKER}",
        "Describe a single shared helper for a human to implement.",
    ],
    "files_likely_to_change": [PLAN_FILE_A, PLAN_FILE_B],
    "files_forbidden_or_out_of_scope": [PLAN_FORBIDDEN],
    "required_verification": [f"pytest -q {VERIFICATION_MARKER}"],
    "risks": [f"Rounding differences on reissued invoices. {RISK_MARKER}"],
    "open_questions": [f"Which locale should totals use? {QUESTION_MARKER}"],
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


def _write_config(tmp_path, *, project_id: str = PROJECT_ID, github_repo: str = REPO):
    """Write a temp project config inside the test's own tmp dir.

    ``workspace_path`` is a **string in the config only**: it points at a
    directory that is normally never created, and no test reads anything under
    it.
    """
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


def _write_artifact(tmp_path, artifact: dict | str | None = None, name: str = "approved_plan.json"):
    """Write an approved-plan artifact **outside** the configured workspace."""
    path = tmp_path / name
    text = artifact if isinstance(artifact, str) else json.dumps(
        _artifact() if artifact is None else artifact
    )
    path.write_text(text, encoding="utf-8")
    return path


def _run(tmp_path, **overrides):
    """Call the private helper directly, so file reads can be tracked."""
    kwargs = {
        "project_config": overrides.pop("project_config", None) or _write_config(tmp_path),
        "approved_plan": overrides.pop("approved_plan", None) or _write_artifact(tmp_path),
        "apply_approved_plan": True,
    }
    kwargs.update(overrides)
    return cli._run_l2_dry_run(**kwargs)


def _invoke(config_path, artifact_path, *, apply_flag: bool = True):
    args = [
        "l2-dry-run",
        "--project-config",
        str(config_path),
        "--approved-plan",
        str(artifact_path),
    ]
    if apply_flag:
        args.append("--apply-approved-plan")
    return runner.invoke(app, args)


def _track_read_text(monkeypatch, path_type, sink: list[str]):
    """Record every ``Path.read_text`` call while still performing it."""
    real_read_text = path_type.read_text

    def tracking_read_text(self, *args, **kwargs):
        sink.append(str(self))
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(path_type, "read_text", tracking_read_text)


# -- 1..7. CLI surface ---------------------------------------------------------


def test_l2_dry_run_appears_in_root_help():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "l2-dry-run" in result.output


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
    ):
        assert command in result.output


def test_l2_dry_run_help_exposes_its_options():
    result = runner.invoke(app, ["l2-dry-run", "--help"])

    assert result.exit_code == 0
    for present in ("--project-config", "--approved-plan", "--apply-approved-plan"):
        assert present in result.output


def test_l2_dry_run_help_hides_forbidden_options():
    result = runner.invoke(app, ["l2-dry-run", "--help"])

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
    ):
        assert absent not in result.output

    # Passing one is an error, not a silently ignored argument.
    rejected = runner.invoke(app, ["l2-dry-run", "--real-model"])
    assert rejected.exit_code != 0


def test_generate_plan_help_unchanged_and_offline_only():
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
        "--real",
        "--real-model",
        "--model",
        "--approved-plan",
        "--apply-approved-plan",
        "--github",
        "--fetch",
        "--audit-dir",
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
    for absent in ("--approved-plan", "--apply-approved-plan", "--github", "--fetch"):
        assert absent not in result.output


def test_real_llm_smoke_test_help_unchanged():
    result = runner.invoke(app, ["real-llm-smoke-test", "--help"])

    assert result.exit_code == 0
    for present in ("--project-config", "--model", "--real-model"):
        assert present in result.output
    for absent in (
        "--approved-plan",
        "--apply-approved-plan",
        "--issue",
        "--body-file",
        "--title",
        "--github",
        "--fetch",
    ):
        assert absent not in result.output


# -- 8..10. fail closed: flag, workspace guard, unreadable artifact ------------


def test_missing_flag_fails_before_any_file_is_read(tmp_path, monkeypatch):
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


def test_missing_flag_fails_with_the_injected_helper(tmp_path):
    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, apply_approved_plan=False)

    assert excinfo.value.exit_code == 1


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
    assert "The approved plan artifact was not read." in result.stderr
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


def test_missing_artifact_outside_workspace_fails_cleanly(tmp_path, capsys):
    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, approved_plan=tmp_path / "does_not_exist.json")

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert "could not read --approved-plan" in captured.err
    assert captured.out.strip() == ""


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
    assert "The approved plan artifact was not read." in result.stderr
    assert result.stdout.strip() == ""
    assert read == [str(bad_config)]


# -- 11..14. parse, validation, and identity failures --------------------------


@pytest.mark.parametrize(
    "text",
    [
        "not json at all",
        '{"approval": ',
        "```json\n{}\n```",
        "[]",
        "",
    ],
)
def test_invalid_json_artifact_fails_with_the_parse_category(tmp_path, capsys, text):
    artifact_path = _write_artifact(tmp_path, text)

    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, approved_plan=artifact_path)

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert "ApprovedPlanParseError" in captured.err
    assert "parse failure" in captured.err
    assert captured.out.strip() == ""


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(lambda a: a.pop("approval"), id="approval-missing"),
        pytest.param(lambda a: a["approval"].update(approved_by="  "), id="blank-approver"),
        pytest.param(
            lambda a: a["approval"].update(approval_text="I approve this plan"),
            id="paraphrased-approval",
        ),
        pytest.param(
            lambda a: a["approval"].update(source="automatic"), id="non-manual-source"
        ),
        pytest.param(
            lambda a: a["approval"].update(approved_at="whenever"), id="unparseable-date"
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
def test_malformed_approval_fails_with_the_validation_category(
    tmp_path, capsys, mutate
):
    artifact = _artifact()
    mutate(artifact)
    artifact_path = _write_artifact(tmp_path, artifact)

    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, approved_plan=artifact_path)

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert "ApprovedPlanValidationError" in captured.err
    assert "validation failure" in captured.err
    assert captured.out.strip() == ""
    # The category is loud; the content stays quiet.
    assert SUMMARY_MARKER not in captured.err
    assert STEP_MARKER not in captured.err


def test_project_id_mismatch_fails(tmp_path, capsys):
    config_path = _write_config(tmp_path, project_id="a_different_project")

    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, project_config=config_path)

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert "does not match this project config" in captured.err
    assert "Mismatch in project_id" in captured.err
    assert captured.out.strip() == ""


def test_repo_mismatch_fails_on_every_identity_field(tmp_path, capsys):
    config_path = _write_config(tmp_path, github_repo="someone-else/widgets")

    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, project_config=config_path)

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    for field in ("Mismatch in repo", "Mismatch in plan.repo", "Mismatch in plan_provenance.repo"):
        assert field in captured.err
    assert captured.out.strip() == ""


def test_identity_matching_is_exact_not_case_folded(tmp_path, capsys):
    config_path = _write_config(tmp_path, github_repo=REPO.upper())

    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, project_config=config_path)

    assert excinfo.value.exit_code == 1
    assert capsys.readouterr().out.strip() == ""


# -- 15..17. the success path ---------------------------------------------------


def _success_payload(tmp_path, capsys, **overrides) -> dict:
    _run(tmp_path, **overrides)
    return json.loads(capsys.readouterr().out)


def test_valid_artifact_prints_the_dry_run_scope(tmp_path, capsys):
    payload = _success_payload(tmp_path, capsys)

    assert payload["mode"] == "l2-dry-run"

    notice = payload["notice"]
    assert "DRY RUN ONLY" in notice
    for claim in (
        "no workspace was read",
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

    project = payload["project"]
    assert project["project_id"] == PROJECT_ID
    assert project["repo"] == REPO
    assert project["workspace_policy"] == {
        "deny_outside_workspace": True,
        "allow_symlinks": False,
        "max_changed_files": 20,
    }

    scope = payload["intended_scope"]
    assert scope["files_likely_to_change"] == [PLAN_FILE_A, PLAN_FILE_B]
    assert scope["files_forbidden_or_out_of_scope"] == [PLAN_FORBIDDEN]
    assert scope["required_verification"] == VALID_PLAN["required_verification"]
    assert scope["proposed_steps"] == VALID_PLAN["proposed_steps"]
    assert scope["risks"] == VALID_PLAN["risks"]
    assert scope["open_questions"] == VALID_PLAN["open_questions"]

    assert "explicitly authorized" in payload["next_authorization_required"]
    assert "Phase 5D" in payload["next_authorization_required"]


def test_success_through_the_cli_matches_the_helper(tmp_path):
    config_path = _write_config(tmp_path)
    artifact_path = _write_artifact(tmp_path)

    result = _invoke(config_path, artifact_path)

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["mode"] == "l2-dry-run"
    assert payload["approved_plan"]["approved_by"] == APPROVER


def test_output_excludes_secrets_workspace_path_and_raw_artifact(tmp_path, capsys):
    _run(tmp_path)
    stdout = capsys.readouterr().out
    payload = json.loads(stdout)

    # No raw artifact text: the wrapper's own envelope keys are absent, and so
    # is the fixed approval phrase (it conveys nothing beyond who/when).
    assert set(payload) == {
        "notice",
        "mode",
        "project",
        "approved_plan",
        "intended_scope",
        "next_authorization_required",
    }
    assert REQUIRED_APPROVAL_TEXT not in stdout
    assert "approval_text" not in stdout
    assert "plan_provenance" not in stdout

    # No endpoint base URL, no API key, no GitHub token.
    for absent in ("api_key", "AIDO_LITELLM", "http://", "https://", "Bearer "):
        assert absent not in stdout

    # No workspace path, in any form.
    workspace = _workspace_path(tmp_path)
    assert str(workspace) not in stdout
    assert workspace.name not in stdout
    assert "workspace_path" not in stdout

    # No source file contents: the plan's path strings appear as *strings*, and
    # nothing was read from them.
    assert payload["intended_scope"]["files_likely_to_change"] == [
        PLAN_FILE_A,
        PLAN_FILE_B,
    ]


def test_required_verification_is_labelled_plan_text_and_not_executed(
    tmp_path, capsys, monkeypatch
):
    def _blocked(*args, **kwargs):
        raise AssertionError("l2-dry-run must never execute a command")

    monkeypatch.setattr(subprocess, "Popen", _blocked)
    monkeypatch.setattr(subprocess, "run", _blocked)
    monkeypatch.setattr(os, "system", _blocked)

    payload = _success_payload(tmp_path, capsys)

    note = payload["intended_scope"]["note"]
    assert "Plan text only" in note
    assert "did not execute" in note
    assert "never acted on" in note
    # The verification entry is carried verbatim as text, not run.
    assert payload["intended_scope"]["required_verification"] == [
        f"pytest -q {VERIFICATION_MARKER}"
    ]


# -- 18..21. no workspace IO, no network, no env, no model ---------------------


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


def test_command_reads_only_the_two_explicit_files(tmp_path, monkeypatch, capsys):
    config_path = _write_config(tmp_path)
    artifact_path = _write_artifact(tmp_path)
    read: list[str] = []
    _track_read_text(monkeypatch, type(config_path), read)

    _run(tmp_path, project_config=config_path, approved_plan=artifact_path)

    capsys.readouterr()
    # Exactly two file reads, both named on the command line, config first.
    assert read == [str(config_path), str(artifact_path)]


def test_no_workspace_listing_or_resolution_happens(tmp_path, monkeypatch, capsys):
    config_path = _write_config(tmp_path)
    artifact_path = _write_artifact(tmp_path)

    # Warm the lazy imports first, so the detonators below catch the command's
    # own behavior rather than the import machinery's.
    _run(tmp_path, project_config=config_path, approved_plan=artifact_path)
    capsys.readouterr()

    def _blocked(*args, **kwargs):
        raise AssertionError("l2-dry-run must not inspect the filesystem")

    monkeypatch.setattr(os, "listdir", _blocked)
    monkeypatch.setattr(os, "scandir", _blocked)
    monkeypatch.setattr(os, "walk", _blocked)
    monkeypatch.setattr(os.path, "realpath", _blocked)
    monkeypatch.setattr(os, "stat", _blocked)

    _run(tmp_path, project_config=config_path, approved_plan=artifact_path)

    assert json.loads(capsys.readouterr().out)["mode"] == "l2-dry-run"


def test_no_env_read_no_socket_and_no_subprocess(tmp_path, monkeypatch, capsys):
    def _blocked(*args, **kwargs):
        raise AssertionError("l2-dry-run must not read env, network, or processes")

    monkeypatch.setattr(os, "getenv", _blocked)
    monkeypatch.setattr(os.environ, "get", _blocked)
    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket, "getaddrinfo", _blocked)
    monkeypatch.setattr(socket, "gethostbyname", _blocked)
    monkeypatch.setattr(subprocess, "Popen", _blocked)

    _run(tmp_path)

    assert json.loads(capsys.readouterr().out)["mode"] == "l2-dry-run"


def test_command_uses_no_llm_client_httpx_or_github_client(tmp_path, monkeypatch, capsys):
    import ai_dev_orchestrator.github.client as github_client
    import ai_dev_orchestrator.llm.client as llm_client
    import ai_dev_orchestrator.llm.config as llm_config

    def _blocked(*args, **kwargs):
        raise AssertionError("l2-dry-run must not build a client or read llm config")

    monkeypatch.setattr(github_client.GitHubClient, "__init__", _blocked)
    monkeypatch.setattr(github_client.GitHubClient, "get_issue", _blocked)
    monkeypatch.setattr(llm_client.LLMClient, "__init__", _blocked)
    monkeypatch.setattr(llm_config, "load_llm_client_config_from_env", _blocked)
    monkeypatch.setattr(cli, "_build_real_llm_client", _blocked)
    monkeypatch.setattr(cli, "_read_real_llm_env", _blocked)

    _run(tmp_path)

    assert json.loads(capsys.readouterr().out)["mode"] == "l2-dry-run"


def test_helper_source_names_no_client_or_transport_symbol():
    import inspect

    source = inspect.getsource(cli._run_l2_dry_run) + inspect.getsource(cli.l2_dry_run)

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


# -- 22..27. nothing else changed ----------------------------------------------


def test_command_writes_no_files_and_stamps_no_approval(tmp_path, capsys):
    config_path = _write_config(tmp_path)
    artifact_path = _write_artifact(tmp_path)
    before = sorted(p.name for p in tmp_path.iterdir())
    artifact_before = artifact_path.read_text(encoding="utf-8")

    _run(tmp_path, project_config=config_path, approved_plan=artifact_path)

    capsys.readouterr()
    # No artifact was written, no approval was stamped, nothing was rewritten.
    assert sorted(p.name for p in tmp_path.iterdir()) == before
    assert artifact_path.read_text(encoding="utf-8") == artifact_before


def test_existing_commands_still_behave_the_same():
    # The fake-provider smoke test still runs offline and says so.
    smoke = runner.invoke(app, ["llm-smoke-test"])
    assert smoke.exit_code == 0
    assert "No real model was called." in smoke.output

    version = runner.invoke(app, ["version"])
    assert version.exit_code == 0

    # No existing command gained an approved-plan path.
    for command in (
        "generate-plan",
        "generate-model-plan",
        "real-llm-smoke-test",
        "llm-smoke-test",
        "inspect-issue",
    ):
        result = runner.invoke(app, [command, "--help"])
        assert result.exit_code == 0
        assert "--approved-plan" not in result.output
        assert "--apply-approved-plan" not in result.output
        assert "--apply" not in result.output
