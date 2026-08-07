"""Phase 4L tests: the gated ``generate-model-plan`` command.

The command *can* open a real socket and *does* transmit issue text when a human
runs it. **These tests never do either.** Every successful path goes through the
private ``_run_generate_model_plan`` helper with an injected literal environment
mapping and an injected ``httpx.MockTransport``-backed client, so no real
``AIDO_LITELLM_*`` value is read and no connection is attempted. The CLI-level
tests only exercise help output and fail-closed paths, which never reach the
environment, the body file, or a client at all — several of them replace the real
environment reader and the real client factory with functions that fail the test
if called.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess

import httpx
import pytest
import typer
from typer.testing import CliRunner

from ai_dev_orchestrator import cli
from ai_dev_orchestrator.cli import app
from ai_dev_orchestrator.llm.client import LLMAuthError, LLMClient, LLMTransportError
from ai_dev_orchestrator.llm.models import LLMClientConfig

runner = CliRunner()

# A fake, non-routable-looking endpoint. MockTransport short-circuits every
# request, so nothing ever resolves or connects to it.
FAKE_BASE_URL = "http://fake-litellm.invalid/v1"
FAKE_HOST = "fake-litellm.invalid"
ALLOWED_MODEL = "fake-planner-model"
ENV_DEFAULT_MODEL = "fake-env-default-model"
FAKE_API_KEY = "fake-key-not-a-real-secret"
FAKE_GITHUB_TOKEN = "fake-github-token-not-a-real-secret"

ISSUE_NUMBER = 42
ISSUE_TITLE = "Add currency formatting helper"

# Distinctive markers, so a test can prove what did and did not reach the model.
BODY_MARKER = "SENTINEL_BODY_TEXT_ONLY_IN_THE_BODY_FILE"
SCOPE_MARKER = "SENTINEL_SCOPE_SECTION_MARKER"
NON_GOALS_MARKER = "SENTINEL_NON_GOALS_SECTION_MARKER"

ISSUE_BODY = f"""\
# Goal

Format currency amounts consistently. {BODY_MARKER}

# Scope

Add a small helper plus unit tests. {SCOPE_MARKER}

# Non-goals

Locale negotiation. {NON_GOALS_MARKER}

# Acceptance Criteria

Amounts render with two decimal places.

# Required Verification

The helper's unit tests pass.
"""

CONFIG_TEMPLATE = """\
project_id: demo_project
display_name: Demo Project
repo:
  workspace_path: {workspace_path}
  github_repo: demo/widgets
  default_base_branch: main
  branch_prefix: ai/demo
allowed_paths:
  - "src/**"
forbidden_paths:
  - ".git/**"
{real_model_planning}
"""

ENABLED_BLOCK = """\
real_model_planning:
  enabled: true
  allowed_models:
    - fake-planner-model
  allow_prompt_audit_files: false
"""

DISABLED_BLOCK = """\
real_model_planning:
  enabled: false
  allowed_models:
    - fake-planner-model
  allow_prompt_audit_files: false
"""

EMPTY_ALLOWLIST_BLOCK = """\
real_model_planning:
  enabled: true
  allowed_models: []
  allow_prompt_audit_files: false
"""

# A well-formed model reply. Deliberately free of any phrase the Phase 4F policy
# guard rejects: it describes work for a human, never work the model will do.
VALID_PLAN_JSON = json.dumps(
    {
        "summary": "Add a helper that formats currency amounts.",
        "scope_summary": "Introduce a formatting helper plus unit tests.",
        "non_goals": ["Locale negotiation stays out of scope."],
        "proposed_steps": [
            "Describe the desired formatting behaviour for each amount type.",
            "Outline the unit test cases the helper should satisfy.",
        ],
        "files_likely_to_change": ["src/helpers/currency.py"],
        "files_forbidden_or_out_of_scope": ["secrets/**"],
        "required_verification": ["The helper's unit tests pass."],
        "risks": ["The rounding rule is not stated in the issue."],
        "open_questions": ["Which currencies must be supported?"],
    }
)


def _workspace_path(tmp_path):
    """A workspace path that is a **string only**: never created or touched."""
    return tmp_path / "never_touched_workspace"


def _write_config(tmp_path, block: str = ENABLED_BLOCK):
    """Write a temp project config inside the test's own tmp dir.

    ``workspace_path`` is a **string in the config only**: no test resolves,
    stats, lists, or reads it, and it deliberately points at a directory that is
    never created.
    """
    path = tmp_path / "project.yaml"
    path.write_text(
        CONFIG_TEMPLATE.format(
            workspace_path=str(_workspace_path(tmp_path)).replace("\\", "\\\\"),
            real_model_planning=block,
        ),
        encoding="utf-8",
    )
    return path


def _write_body(tmp_path, text: str = ISSUE_BODY):
    """Write the local issue body **outside** the configured workspace path."""
    path = tmp_path / "issue_body.md"
    path.write_text(text, encoding="utf-8")
    return path


def _env(**overrides) -> dict[str, str]:
    """A literal environment mapping. Never read from the real environment."""
    values = {
        "AIDO_LITELLM_BASE_URL": FAKE_BASE_URL,
        "AIDO_LITELLM_API_KEY": FAKE_API_KEY,
        # Deliberately different from the requested model.
        "AIDO_LITELLM_DEFAULT_MODEL": ENV_DEFAULT_MODEL,
        "AIDO_LITELLM_TIMEOUT_SECONDS": "5",
        "AIDO_LITELLM_MAX_RETRIES": "0",
    }
    for key, value in overrides.items():
        if value is None:
            values.pop(key, None)
        else:
            values[key] = value
    return values


def _mock_client_factory(seen: list[dict] | None = None, content: str = VALID_PLAN_JSON):
    """Build a client factory returning a MockTransport-backed client."""

    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(json.loads(request.content.decode("utf-8")))
        return httpx.Response(
            200,
            json={
                "model": ALLOWED_MODEL,
                "choices": [
                    {
                        "message": {"role": "assistant", "content": content},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 123,
                    "completion_tokens": 45,
                    "total_tokens": 168,
                },
            },
        )

    def factory(config: LLMClientConfig) -> LLMClient:
        return LLMClient(
            config,
            transport=httpx.MockTransport(handler),
            sleep=lambda _seconds: None,
        )

    return factory


def _failing_client_factory(status: int = 401):
    """A factory whose endpoint always rejects the request."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"error": "nope"})

    def factory(config: LLMClientConfig) -> LLMClient:
        return LLMClient(
            config,
            transport=httpx.MockTransport(handler),
            sleep=lambda _seconds: None,
        )

    return factory


def _transport_error_client_factory():
    """A factory whose transport raises, without ever touching a socket."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("simulated connection failure")

    def factory(config: LLMClientConfig) -> LLMClient:
        return LLMClient(
            config,
            transport=httpx.MockTransport(handler),
            sleep=lambda _seconds: None,
        )

    return factory


def _exploding_env_reader():
    def read_env():
        raise AssertionError("the environment must not be read on this path")

    return read_env


def _exploding_client_factory():
    def factory(config):
        raise AssertionError("no client may be constructed on this path")

    return factory


def _run(tmp_path, **overrides):
    """Call the private helper with everything injected."""
    kwargs = {
        "project_config": overrides.pop("project_config", None)
        or _write_config(tmp_path),
        "issue": ISSUE_NUMBER,
        "title": ISSUE_TITLE,
        "body_file": overrides.pop("body_file", None) or _write_body(tmp_path),
        "model": ALLOWED_MODEL,
        "real_model": True,
        "read_env": lambda: _env(),
        "client_factory": _mock_client_factory(),
    }
    kwargs.update(overrides)
    return cli._run_generate_model_plan(**kwargs)


# -- 1..7. CLI surface ---------------------------------------------------------


def test_generate_model_plan_appears_in_root_help():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "generate-model-plan" in result.output


def test_existing_commands_still_appear_in_root_help():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    for command in (
        "version",
        "inspect-issue",
        "llm-smoke-test",
        "generate-plan",
        "real-llm-smoke-test",
    ):
        assert command in result.output


def test_generate_plan_remains_offline_only():
    result = runner.invoke(app, ["generate-plan", "--help"])

    assert result.exit_code == 0
    for absent in (
        "--real",
        "--real-model",
        "--live",
        "--model",
        "--use-env",
        "--github",
        "--fetch",
        "--audit-dir",
    ):
        assert absent not in result.output


def test_llm_smoke_test_remains_fake_only_and_unchanged():
    result = runner.invoke(app, ["llm-smoke-test", "--help"])

    assert result.exit_code == 0
    # Its pre-existing --model still names a *fake* model.
    assert "Fake model name" in result.output
    for absent in ("--real", "--real-model", "--live", "--use-env", "--audit-dir"):
        assert absent not in result.output

    run = runner.invoke(app, ["llm-smoke-test"])
    assert run.exit_code == 0
    assert "No real model was called." in run.output


def test_real_llm_smoke_test_remains_smoke_test_only_and_unchanged():
    result = runner.invoke(app, ["real-llm-smoke-test", "--help"])

    assert result.exit_code == 0
    for present in ("--project-config", "--model", "--real-model"):
        assert present in result.output
    # Phase 4L adds a planner as a *separate* command; the smoke test still
    # cannot be handed issue text or reach GitHub.
    for absent in (
        "--issue",
        "--body-file",
        "--title",
        "--github",
        "--fetch",
        "--repo",
        "--audit-dir",
        "--message",
    ):
        assert absent not in result.output


def test_generate_model_plan_help_exposes_the_gated_options():
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


def test_generate_model_plan_help_hides_forbidden_options():
    result = runner.invoke(app, ["generate-model-plan", "--help"])

    assert result.exit_code == 0
    for absent in (
        "--github",
        "--fetch",
        "--repo",
        "--audit-dir",
        "--message",
        "--workspace",
        "--file",
        "--context-file",
    ):
        assert absent not in result.output

    # Passing one is an error, not a silently ignored argument.
    rejected = runner.invoke(app, ["generate-model-plan", "--fetch", "--real-model"])
    assert rejected.exit_code != 0


# -- 8..11. fail-closed: flag, project opt-in, allowlist -----------------------


def test_missing_real_model_flag_fails_before_env_body_or_client(tmp_path, monkeypatch):
    # Proves the ordering: neither the environment reader nor the client factory
    # is reachable without the flag.
    monkeypatch.setattr(cli, "_read_real_llm_env", _exploding_env_reader())
    monkeypatch.setattr(cli, "_build_real_llm_client", _exploding_client_factory())

    config_path = _write_config(tmp_path)
    body_path = _write_body(tmp_path)
    read: list[str] = []
    _track_read_text(monkeypatch, type(body_path), read)

    result = runner.invoke(
        app,
        [
            "generate-model-plan",
            "--project-config",
            str(config_path),
            "--issue",
            str(ISSUE_NUMBER),
            "--title",
            ISSUE_TITLE,
            "--body-file",
            str(body_path),
            "--model",
            ALLOWED_MODEL,
        ],
    )

    assert result.exit_code == 1
    assert "--real-model" in result.stderr
    assert result.stdout.strip() == ""
    # Nothing at all was read: not even the project config.
    assert read == []
    # No call was attempted, so neither post-call block is printed.
    assert "COMPLETED" not in result.stderr
    assert "FAILED" not in result.stderr


def test_missing_real_model_flag_fails_with_injected_helpers(tmp_path):
    with pytest.raises(typer.Exit) as excinfo:
        _run(
            tmp_path,
            real_model=False,
            read_env=_exploding_env_reader(),
            client_factory=_exploding_client_factory(),
        )

    assert excinfo.value.exit_code == 1


def _track_read_text(monkeypatch, path_type, sink: list[str]):
    """Record every ``Path.read_text`` call while still performing it."""
    real_read_text = path_type.read_text

    def tracking_read_text(self, *args, **kwargs):
        sink.append(str(self))
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(path_type, "read_text", tracking_read_text)


def _invoke_cli(config_path, body_path, model: str = ALLOWED_MODEL):
    return runner.invoke(
        app,
        [
            "generate-model-plan",
            "--project-config",
            str(config_path),
            "--issue",
            str(ISSUE_NUMBER),
            "--title",
            ISSUE_TITLE,
            "--body-file",
            str(body_path),
            "--model",
            model,
            "--real-model",
        ],
    )


def test_disabled_project_fails_closed_before_env_body_or_client(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "_read_real_llm_env", _exploding_env_reader())
    monkeypatch.setattr(cli, "_build_real_llm_client", _exploding_client_factory())

    config_path = _write_config(tmp_path, DISABLED_BLOCK)
    body_path = _write_body(tmp_path)
    read: list[str] = []
    _track_read_text(monkeypatch, type(body_path), read)

    result = _invoke_cli(config_path, body_path)

    assert result.exit_code == 1
    assert "does not enable real model planning" in result.stderr
    assert "The body file was not read" in result.stderr
    assert result.stdout.strip() == ""
    # Only the project config was read; the body file was not.
    assert read == [str(config_path)]


def test_empty_allowed_models_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "_read_real_llm_env", _exploding_env_reader())
    monkeypatch.setattr(cli, "_build_real_llm_client", _exploding_client_factory())

    config_path = _write_config(tmp_path, EMPTY_ALLOWLIST_BLOCK)
    body_path = _write_body(tmp_path)
    read: list[str] = []
    _track_read_text(monkeypatch, type(body_path), read)

    result = _invoke_cli(config_path, body_path)

    assert result.exit_code == 1
    assert "allowed_models is empty" in result.stderr
    assert result.stdout.strip() == ""
    assert read == [str(config_path)]


@pytest.mark.parametrize(
    "requested", ["other-model", "fake-planner", "FAKE-PLANNER-MODEL", "*"]
)
def test_non_allowlisted_model_fails_closed(tmp_path, monkeypatch, requested):
    monkeypatch.setattr(cli, "_read_real_llm_env", _exploding_env_reader())
    monkeypatch.setattr(cli, "_build_real_llm_client", _exploding_client_factory())

    config_path = _write_config(tmp_path)
    body_path = _write_body(tmp_path)
    read: list[str] = []
    _track_read_text(monkeypatch, type(body_path), read)

    result = _invoke_cli(config_path, body_path, model=requested)

    assert result.exit_code == 1
    assert "not in real_model_planning.allowed_models" in result.stderr
    assert result.stdout.strip() == ""
    assert read == [str(config_path)]


# -- 12..13. body-file guards --------------------------------------------------


def test_body_file_inside_workspace_is_rejected_before_it_is_read(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(cli, "_read_real_llm_env", _exploding_env_reader())
    monkeypatch.setattr(cli, "_build_real_llm_client", _exploding_client_factory())

    config_path = _write_config(tmp_path)
    workspace = _workspace_path(tmp_path)
    workspace.mkdir()
    inside = workspace / "issue_body.md"
    inside.write_text("SENTINEL_WORKSPACE_BODY_CONTENT\n", encoding="utf-8")

    read: list[str] = []
    _track_read_text(monkeypatch, type(inside), read)

    result = _invoke_cli(config_path, inside)

    assert result.exit_code == 1
    assert "is inside the project's configured repo.workspace_path" in result.stderr
    assert "The body file was not read" in result.stderr
    assert result.stdout.strip() == ""
    # The guard ran before the read, and the content never surfaced anywhere.
    assert read == [str(config_path)]
    assert "SENTINEL_WORKSPACE_BODY_CONTENT" not in result.output
    assert "SENTINEL_WORKSPACE_BODY_CONTENT" not in result.stderr


def test_body_file_in_a_workspace_subdirectory_is_also_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "_read_real_llm_env", _exploding_env_reader())
    monkeypatch.setattr(cli, "_build_real_llm_client", _exploding_client_factory())

    config_path = _write_config(tmp_path)
    nested = _workspace_path(tmp_path) / "docs" / "issues"
    nested.mkdir(parents=True)
    inside = nested / "issue_body.md"
    inside.write_text("SENTINEL_WORKSPACE_BODY_CONTENT\n", encoding="utf-8")

    result = _invoke_cli(config_path, inside)

    assert result.exit_code == 1
    assert "repo.workspace_path" in result.stderr
    assert result.stdout.strip() == ""


def test_missing_body_file_outside_workspace_fails_after_gate_before_client(
    tmp_path, capsys
):
    with pytest.raises(typer.Exit) as excinfo:
        _run(
            tmp_path,
            body_file=tmp_path / "does_not_exist.md",
            client_factory=_exploding_client_factory(),
        )

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert "could not read --body-file" in captured.err
    assert "No client was built and no network call was made." in captured.err
    assert captured.out.strip() == ""
    # No call was attempted, so no post-call block is printed.
    assert "COMPLETED" not in captured.err
    assert "a real call was attempted" not in captured.err


# -- 14..15. environment failures and secret hygiene ---------------------------


@pytest.mark.parametrize(
    "name",
    [
        "AIDO_LITELLM_BASE_URL",
        "AIDO_LITELLM_API_KEY",
        "AIDO_LITELLM_DEFAULT_MODEL",
    ],
)
def test_missing_env_value_fails_before_body_read_or_client(
    tmp_path, monkeypatch, name, capsys
):
    body_path = _write_body(tmp_path)
    read: list[str] = []
    _track_read_text(monkeypatch, type(body_path), read)
    config_path = _write_config(tmp_path)

    with pytest.raises(typer.Exit) as excinfo:
        _run(
            tmp_path,
            project_config=config_path,
            body_file=body_path,
            read_env=lambda: _env(**{name: None}),
            client_factory=_exploding_client_factory(),
        )

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert name in captured.err
    assert "The body file was not read" in captured.err
    assert captured.out.strip() == ""
    assert read == [str(config_path)]


def test_blank_env_value_fails_before_body_read_or_client(tmp_path, capsys):
    with pytest.raises(typer.Exit):
        _run(
            tmp_path,
            read_env=lambda: _env(AIDO_LITELLM_BASE_URL="   "),
            client_factory=_exploding_client_factory(),
        )

    captured = capsys.readouterr()
    assert captured.out.strip() == ""
    assert "COMPLETED" not in captured.err
    assert "a real call was attempted" not in captured.err


@pytest.mark.parametrize(
    "kwargs",
    [
        # Env failure (before the body file is read).
        {"read_env": lambda: _env(AIDO_LITELLM_DEFAULT_MODEL=None)},
        # Body-file failure (after the gate).
        {"body_file_missing": True},
        # Client failure (after a call was attempted).
        {"client_factory": _failing_client_factory(401)},
        # Parser failure (after a model reply).
        {"client_factory": _mock_client_factory(content="not json at all")},
    ],
)
def test_api_key_never_printed_on_any_failure_path(tmp_path, capsys, kwargs):
    overrides = dict(kwargs)
    if overrides.pop("body_file_missing", False):
        overrides["body_file"] = tmp_path / "does_not_exist.md"

    with pytest.raises(typer.Exit):
        _run(tmp_path, **overrides)

    captured = capsys.readouterr()
    assert FAKE_API_KEY not in captured.out
    assert FAKE_API_KEY not in captured.err
    # The full base URL is never echoed either — only the host.
    assert FAKE_BASE_URL not in captured.out
    assert FAKE_BASE_URL not in captured.err


def test_api_key_never_printed_on_success(tmp_path, capsys):
    _run(tmp_path)

    captured = capsys.readouterr()
    assert FAKE_API_KEY not in captured.out
    assert FAKE_API_KEY not in captured.err
    assert FAKE_BASE_URL not in captured.out
    assert FAKE_BASE_URL not in captured.err
    assert FAKE_HOST in captured.err


# -- 16..20. successful (mocked) real path ------------------------------------


def test_successful_run_prints_provenance_plan_and_usage(tmp_path, capsys):
    _run(tmp_path)

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert "REAL MODEL L1 PLAN ONLY" in payload["notice"]
    assert "human must review and approve" in payload["notice"]

    provenance = payload["provenance"]
    generated_at = provenance.pop("generated_at")
    assert provenance == {
        "engine": "real-model",
        "operation": "l1-plan",
        "real_call": True,
        "model": ALLOWED_MODEL,
        "endpoint_host": FAKE_HOST,
        "project_id": "demo_project",
        "repo": "demo/widgets",
        "issue_number": ISSUE_NUMBER,
        "title": ISSUE_TITLE,
    }
    # A UTC ISO-8601 stamp, e.g. 2026-08-06T12:34:56Z.
    assert generated_at.endswith("Z")
    assert len(generated_at) == 20

    plan = payload["plan"]
    assert plan["automation_level"] == "L1"
    assert plan["requires_human_approval"] is True
    assert plan["issue_number"] == ISSUE_NUMBER
    assert plan["repo"] == "demo/widgets"
    assert plan["title"] == ISSUE_TITLE
    assert plan["proposed_steps"]
    assert plan["required_verification"]
    # The project's own forbidden paths are merged in verbatim.
    assert ".git/**" in plan["files_forbidden_or_out_of_scope"]

    assert payload["usage"] == {
        "prompt_tokens": 123,
        "completion_tokens": 45,
        "total_tokens": 168,
    }

    # No secret, no full URL, and no raw prompt in the machine-readable output.
    assert FAKE_API_KEY not in captured.out
    assert FAKE_BASE_URL not in captured.out
    assert "UNTRUSTED_ISSUE_TEXT" not in captured.out
    assert str(_workspace_path(tmp_path)) not in captured.out


def test_successful_run_sends_the_explicit_model_not_the_env_default(tmp_path, capsys):
    seen: list[dict] = []
    _run(tmp_path, client_factory=_mock_client_factory(seen))

    capsys.readouterr()
    assert len(seen) == 1
    assert seen[0]["model"] == ALLOWED_MODEL
    assert seen[0]["model"] != ENV_DEFAULT_MODEL


def test_successful_run_sends_issue_text_but_no_files_or_secrets(tmp_path, capsys):
    seen: list[dict] = []
    _run(tmp_path, client_factory=_mock_client_factory(seen))

    capsys.readouterr()
    sent = json.dumps(seen[0])

    # The issue title, the body text, and the parsed sections all reach the model.
    assert ISSUE_TITLE in sent
    assert BODY_MARKER in sent
    assert SCOPE_MARKER in sent
    assert NON_GOALS_MARKER in sent
    # Issue-derived text is delimited as untrusted data, not instructions.
    assert "UNTRUSTED_ISSUE_TEXT" in sent

    # Path *patterns* are conveyed; the workspace path itself is not.
    assert "src/**" in sent
    assert str(_workspace_path(tmp_path)) not in sent
    assert "never_touched_workspace" not in sent
    assert str(tmp_path) not in sent

    # No credential of any kind travels in the request body.
    assert FAKE_API_KEY not in sent
    assert FAKE_GITHUB_TOKEN not in sent
    assert "GITHUB_TOKEN" not in sent
    assert "AIDO_LITELLM" not in sent


def test_successful_run_prints_the_before_call_warning_to_stderr(tmp_path, capsys):
    _run(tmp_path)

    captured = capsys.readouterr()
    assert "REAL MODEL L1 PLAN — a real network call is about to be made" in (
        captured.err
    )
    assert f"Endpoint host: {FAKE_HOST}" in captured.err
    assert f"Model:         {ALLOWED_MODEL}" in captured.err
    assert "Project:       demo_project" in captured.err
    assert "Repo:          demo/widgets" in captured.err
    assert f"Issue:         #{ISSUE_NUMBER} {ISSUE_TITLE}" in captured.err
    assert "WILL be transmitted" in captured.err
    assert "no source files" in captured.err
    assert "Nothing is fetched from or written to GitHub" in captured.err
    assert "no command is run" in captured.err
    # The banner goes to stderr only, so piping stdout to a file still leaves the
    # warning visible and keeps the JSON machine-parseable.
    assert "about to be made" not in captured.out
    assert "Endpoint host:" not in captured.out


def test_successful_run_prints_the_after_call_block_to_stderr(tmp_path, capsys):
    _run(tmp_path)

    captured = capsys.readouterr()
    assert "REAL MODEL L1 PLAN COMPLETED" in captured.err
    assert "FAILED" not in captured.err
    # Ordering: warn before the call, confirm after it.
    assert captured.err.index("about to be made") < captured.err.index("COMPLETED")


# -- 21..22. failures after a call was attempted -------------------------------


@pytest.mark.parametrize(
    "factory, expected",
    [
        (_failing_client_factory(401), LLMAuthError),
        (_transport_error_client_factory(), LLMTransportError),
    ],
)
def test_client_failure_prints_the_after_call_failure_block(
    tmp_path, capsys, factory, expected
):
    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, client_factory=factory)

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()

    assert "REAL MODEL L1 PLAN FAILED (a real call was attempted)" in captured.err
    assert expected.__name__ in captured.err
    assert f"Endpoint host: {FAKE_HOST}" in captured.err
    assert captured.out.strip() == ""
    assert FAKE_API_KEY not in captured.err


# A completion carrying a marker, so a test can prove it is never echoed.
_COMPLETION_MARKER = "SENTINEL_MODEL_COMPLETION_TEXT"

_BAD_COMPLETIONS = {
    # Not JSON at all.
    "parse-prose": (
        f"Here is the plan: {_COMPLETION_MARKER}",
        "ModelPlannerParseError",
    ),
    # A JSON object wrapped in a markdown fence.
    "parse-fenced": (
        f"```json\n{VALID_PLAN_JSON}\n```",
        "ModelPlannerParseError",
    ),
    # Valid JSON, missing required fields.
    "validation-missing": (
        json.dumps({"summary": _COMPLETION_MARKER}),
        "ModelPlannerValidationError",
    ),
    # Valid JSON that tries to set a caller-controlled ("trusted") field.
    "validation-injection": (
        json.dumps(
            {
                **json.loads(VALID_PLAN_JSON),
                "automation_level": "L3",
                "requires_human_approval": False,
            }
        ),
        "ModelPlannerValidationError",
    ),
    # Well-shaped, but proposes forbidden non-L1 behavior.
    "policy-commands": (
        json.dumps(
            {
                **json.loads(VALID_PLAN_JSON),
                "proposed_steps": [
                    "Run the shell command that regenerates the helper.",
                ],
            }
        ),
        "ModelPlannerPolicyError",
    ),
    "policy-escalation": (
        json.dumps(
            {
                **json.loads(VALID_PLAN_JSON),
                "risks": ["Proceed without human approval to save review time."],
            }
        ),
        "ModelPlannerPolicyError",
    ),
}


@pytest.mark.parametrize(
    "content, error_name",
    list(_BAD_COMPLETIONS.values()),
    ids=list(_BAD_COMPLETIONS),
)
def test_bad_model_output_prints_the_after_call_failure_block(
    tmp_path, capsys, content, error_name
):
    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, client_factory=_mock_client_factory(content=content))

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()

    assert "REAL MODEL L1 PLAN FAILED (a real call was attempted)" in captured.err
    # The failure category is identified by name, so parser, validation, and
    # policy failures are distinguishable.
    assert error_name in captured.err
    assert f"Endpoint host: {FAKE_HOST}" in captured.err
    assert "The model reply is not echoed" in captured.err

    # No JSON success output, no secret, and no raw completion.
    assert captured.out.strip() == ""
    assert FAKE_API_KEY not in captured.err
    assert _COMPLETION_MARKER not in captured.err
    assert _COMPLETION_MARKER not in captured.out


# -- 23..28. isolation guarantees ---------------------------------------------


def test_command_uses_no_github_client(tmp_path, monkeypatch, capsys):
    import ai_dev_orchestrator.github.client as github_client

    def _blocked(*args, **kwargs):
        raise AssertionError("this command must not use the GitHub client")

    monkeypatch.setattr(github_client.GitHubClient, "get_issue", _blocked)
    monkeypatch.setattr(github_client.GitHubClient, "__init__", _blocked)

    _run(tmp_path)

    payload = json.loads(capsys.readouterr().out)
    assert payload["provenance"]["operation"] == "l1-plan"
    # The synthetic issue is labelled as local, never as fetched from GitHub.
    assert "html_url" not in payload["plan"]


def test_command_reads_only_the_two_explicit_files(tmp_path, monkeypatch, capsys):
    config_path = _write_config(tmp_path)
    body_path = _write_body(tmp_path)
    read: list[str] = []
    _track_read_text(monkeypatch, type(config_path), read)

    def _blocked(*args, **kwargs):
        raise AssertionError("the command must not inspect the filesystem")

    monkeypatch.setattr(os, "listdir", _blocked)
    monkeypatch.setattr(os, "scandir", _blocked)
    monkeypatch.setattr(os.path, "realpath", _blocked)

    _run(tmp_path, project_config=config_path, body_file=body_path)

    capsys.readouterr()
    # Exactly two file reads, both named on the command line, config first.
    assert read == [str(config_path), str(body_path)]
    # The configured workspace path was never created, and never touched.
    assert not _workspace_path(tmp_path).exists()


def test_no_real_network_call_is_made(tmp_path, monkeypatch, capsys):
    def _blocked(*args, **kwargs):
        raise AssertionError("no real socket may be opened by the test suite")

    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket, "getaddrinfo", _blocked)
    monkeypatch.setattr(socket, "gethostbyname", _blocked)
    monkeypatch.setattr(subprocess, "Popen", _blocked)

    _run(tmp_path)

    payload = json.loads(capsys.readouterr().out)
    assert payload["provenance"]["real_call"] is True


def test_tests_never_read_the_real_environment(tmp_path, monkeypatch, capsys):
    def _blocked(*args, **kwargs):
        raise AssertionError("the injected mapping is the only environment source")

    monkeypatch.setattr(os, "getenv", _blocked)
    monkeypatch.setattr(os.environ, "get", _blocked)

    _run(tmp_path)

    assert json.loads(capsys.readouterr().out)["provenance"]["real_call"] is True


def test_env_reader_is_shared_and_touches_only_the_five_aido_names(monkeypatch):
    # The real reader is exercised against a *replaced* os.environ, so no real
    # value is read here either.
    fake_environ = {
        "AIDO_LITELLM_BASE_URL": FAKE_BASE_URL,
        "AIDO_LITELLM_API_KEY": FAKE_API_KEY,
        "AIDO_LITELLM_DEFAULT_MODEL": ENV_DEFAULT_MODEL,
        "GITHUB_TOKEN": FAKE_GITHUB_TOKEN,
        "PATH": "should-not-be-read",
        "AIDO_SOMETHING_ELSE": "should-not-be-read",
    }
    monkeypatch.setattr(cli.os, "environ", fake_environ)

    snapshot = cli._read_real_llm_env()

    assert set(snapshot) == {
        "AIDO_LITELLM_BASE_URL",
        "AIDO_LITELLM_API_KEY",
        "AIDO_LITELLM_DEFAULT_MODEL",
    }
    assert "GITHUB_TOKEN" not in snapshot


def test_usage_recorder_keeps_counts_and_never_the_completion():
    """The wrapper that exposes token usage must not retain prompt or reply text."""
    from ai_dev_orchestrator.llm.models import LLMRequest, LLMResponse, LLMUsage

    reply = LLMResponse(
        model=ALLOWED_MODEL,
        content="SENTINEL_COMPLETION_THAT_MUST_NOT_BE_RETAINED",
        usage=LLMUsage(prompt_tokens=1, completion_tokens=2, total_tokens=3),
    )

    class _Inner:
        def chat(self, request):
            return reply

    inner = _Inner()
    wrapper = cli._UsageRecordingClient(inner)
    request = LLMRequest(
        model=ALLOWED_MODEL,
        messages=[{"role": "user", "content": "SENTINEL_PROMPT_TEXT"}],
    )

    assert wrapper.chat(request) is reply
    assert wrapper.usage == reply.usage
    # The only attributes are the delegate and the token counts — nothing that
    # could hold the prompt or the completion.
    assert set(vars(wrapper)) == {"_client", "usage"}
    assert vars(wrapper)["_client"] is inner


def test_command_writes_no_audit_or_output_files(tmp_path, capsys):
    config_path = _write_config(tmp_path)
    body_path = _write_body(tmp_path)
    before = sorted(p.name for p in tmp_path.iterdir())

    _run(tmp_path, project_config=config_path, body_file=body_path)

    capsys.readouterr()
    assert sorted(p.name for p in tmp_path.iterdir()) == before
