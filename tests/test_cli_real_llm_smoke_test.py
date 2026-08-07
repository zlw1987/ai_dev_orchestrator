"""Phase 4K tests: the gated ``real-llm-smoke-test`` command.

The command *can* open a real socket when a human runs it. **These tests never
do.** Every successful path goes through the private
``_run_real_llm_smoke_test`` helper with an injected literal environment mapping
and an injected ``httpx.MockTransport``-backed client, so no real
``AIDO_LITELLM_*`` value is read and no connection is attempted. The CLI-level
tests only exercise help output and fail-closed paths, which never reach the
environment or a client at all — several of them replace the real environment
reader and the real client factory with functions that fail the test if called.
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
SMOKE_REPLY = "AIDO_REAL_SMOKE_OK"

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


def _write_config(tmp_path, block: str = ENABLED_BLOCK):
    """Write a temp project config inside the test's own tmp dir.

    ``workspace_path`` is a **string in the config only**: no test resolves,
    stats, lists, or reads it, and it deliberately points at a directory that is
    never created.
    """
    path = tmp_path / "project.yaml"
    path.write_text(
        CONFIG_TEMPLATE.format(
            workspace_path=str(tmp_path / "never_touched_workspace").replace(
                "\\", "\\\\"
            ),
            real_model_planning=block,
        ),
        encoding="utf-8",
    )
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


def _mock_client_factory(seen: list[dict] | None = None, content: str = SMOKE_REPLY):
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
                    "prompt_tokens": 11,
                    "completion_tokens": 7,
                    "total_tokens": 18,
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
        "model": ALLOWED_MODEL,
        "real_model": True,
        "read_env": lambda: _env(),
        "client_factory": _mock_client_factory(),
    }
    kwargs.update(overrides)
    return cli._run_real_llm_smoke_test(**kwargs)


# -- 1..5. CLI surface ---------------------------------------------------------


def test_real_smoke_command_appears_in_root_help():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "real-llm-smoke-test" in result.output


def test_existing_commands_still_appear_in_root_help():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    for command in ("version", "inspect-issue", "llm-smoke-test", "generate-plan"):
        assert command in result.output

    # Phase 4K added a smoke test, not a planner. (Phase 4L later added the
    # planner as a *separate* command, `generate-model-plan`; these names have
    # never existed.)
    for absent in ("real-generate-plan", "plan-from-model"):
        assert absent not in result.output


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

    # And it still runs entirely offline with the same dry-run wording.
    run = runner.invoke(app, ["llm-smoke-test"])
    assert run.exit_code == 0
    assert "No real model was called." in run.output


def test_real_smoke_help_exposes_only_the_gated_options():
    result = runner.invoke(app, ["real-llm-smoke-test", "--help"])

    assert result.exit_code == 0
    for present in ("--project-config", "--model", "--real-model"):
        assert present in result.output
    for absent in (
        "--github",
        "--fetch",
        "--issue",
        "--body-file",
        "--audit-dir",
        "--message",
        "--repo",
        "--title",
    ):
        assert absent not in result.output


# -- 6..9. fail-closed paths ---------------------------------------------------


def test_missing_real_model_flag_fails_before_env_or_client(tmp_path, monkeypatch):
    # Proves the ordering: neither the environment reader nor the client factory
    # is reachable without the flag.
    monkeypatch.setattr(cli, "_read_real_llm_env", _exploding_env_reader())
    monkeypatch.setattr(cli, "_build_real_llm_client", _exploding_client_factory())

    config_path = _write_config(tmp_path)
    result = runner.invoke(
        app,
        [
            "real-llm-smoke-test",
            "--project-config",
            str(config_path),
            "--model",
            ALLOWED_MODEL,
        ],
    )

    assert result.exit_code == 1
    assert "--real-model" in result.stderr
    assert result.stdout.strip() == ""
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


def test_disabled_project_fails_closed_before_env_or_client(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "_read_real_llm_env", _exploding_env_reader())
    monkeypatch.setattr(cli, "_build_real_llm_client", _exploding_client_factory())

    config_path = _write_config(tmp_path, DISABLED_BLOCK)
    result = runner.invoke(
        app,
        [
            "real-llm-smoke-test",
            "--project-config",
            str(config_path),
            "--model",
            ALLOWED_MODEL,
            "--real-model",
        ],
    )

    assert result.exit_code == 1
    assert "does not enable real model planning" in result.stderr
    assert "No environment variable was read" in result.stderr
    assert result.stdout.strip() == ""


def test_empty_allowed_models_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "_read_real_llm_env", _exploding_env_reader())
    monkeypatch.setattr(cli, "_build_real_llm_client", _exploding_client_factory())

    config_path = _write_config(tmp_path, EMPTY_ALLOWLIST_BLOCK)
    result = runner.invoke(
        app,
        [
            "real-llm-smoke-test",
            "--project-config",
            str(config_path),
            "--model",
            ALLOWED_MODEL,
            "--real-model",
        ],
    )

    assert result.exit_code == 1
    assert "allowed_models is empty" in result.stderr
    assert result.stdout.strip() == ""


@pytest.mark.parametrize(
    "requested", ["other-model", "fake-planner", "FAKE-PLANNER-MODEL", "*"]
)
def test_non_allowlisted_model_fails_closed(tmp_path, monkeypatch, requested):
    monkeypatch.setattr(cli, "_read_real_llm_env", _exploding_env_reader())
    monkeypatch.setattr(cli, "_build_real_llm_client", _exploding_client_factory())

    config_path = _write_config(tmp_path)
    result = runner.invoke(
        app,
        [
            "real-llm-smoke-test",
            "--project-config",
            str(config_path),
            "--model",
            requested,
            "--real-model",
        ],
    )

    assert result.exit_code == 1
    assert "not in real_model_planning.allowed_models" in result.stderr
    assert result.stdout.strip() == ""


def test_unreadable_project_config_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "_read_real_llm_env", _exploding_env_reader())

    result = runner.invoke(
        app,
        [
            "real-llm-smoke-test",
            "--project-config",
            str(tmp_path / "does_not_exist.yaml"),
            "--model",
            ALLOWED_MODEL,
            "--real-model",
        ],
    )

    # Typer's own `exists=True` check rejects it before the command body runs.
    assert result.exit_code != 0
    assert result.stdout.strip() == ""


# -- 10..11. environment failures ---------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "AIDO_LITELLM_BASE_URL",
        "AIDO_LITELLM_API_KEY",
        "AIDO_LITELLM_DEFAULT_MODEL",
    ],
)
def test_missing_env_value_fails_before_client_construction(tmp_path, name, capsys):
    with pytest.raises(typer.Exit) as excinfo:
        _run(
            tmp_path,
            read_env=lambda: _env(**{name: None}),
            client_factory=_exploding_client_factory(),
        )

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert name in captured.err
    assert "No client was built and no network call was made." in captured.err
    assert captured.out.strip() == ""


def test_blank_env_value_fails_before_client_construction(tmp_path, capsys):
    with pytest.raises(typer.Exit):
        _run(
            tmp_path,
            read_env=lambda: _env(AIDO_LITELLM_BASE_URL="   "),
            client_factory=_exploding_client_factory(),
        )

    captured = capsys.readouterr()
    assert captured.out.strip() == ""
    # No call was attempted, so no post-call block is printed.
    assert "COMPLETED" not in captured.err
    assert "a real call was attempted" not in captured.err


def test_api_key_never_printed_on_env_or_gate_failure(tmp_path, capsys):
    with pytest.raises(typer.Exit):
        _run(
            tmp_path,
            read_env=lambda: _env(AIDO_LITELLM_DEFAULT_MODEL=None),
            client_factory=_exploding_client_factory(),
        )

    captured = capsys.readouterr()
    assert FAKE_API_KEY not in captured.out
    assert FAKE_API_KEY not in captured.err


def test_api_key_never_printed_on_client_failure(tmp_path, capsys):
    with pytest.raises(typer.Exit):
        _run(tmp_path, client_factory=_failing_client_factory(401))

    captured = capsys.readouterr()
    assert FAKE_API_KEY not in captured.out
    assert FAKE_API_KEY not in captured.err
    # The full base URL is never echoed either — only the host.
    assert FAKE_BASE_URL not in captured.err
    assert FAKE_HOST in captured.err


# -- 12..15. successful (mocked) real path ------------------------------------


def test_successful_run_prints_provenance_json(tmp_path, capsys):
    _run(tmp_path)

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert payload["provenance"] == {
        "engine": "real-model",
        "operation": "smoke-test",
        "real_call": True,
        "model": ALLOWED_MODEL,
        "endpoint_host": FAKE_HOST,
        "project_id": "demo_project",
    }
    assert payload["response_content"] == SMOKE_REPLY
    assert payload["usage"] == {
        "prompt_tokens": 11,
        "completion_tokens": 7,
        "total_tokens": 18,
    }
    assert "REAL MODEL SMOKE TEST ONLY" in payload["notice"]

    # No secret, no full URL, and no prompt text in the machine-readable output.
    assert FAKE_API_KEY not in captured.out
    assert FAKE_BASE_URL not in captured.out
    assert cli._REAL_SMOKE_SYSTEM_PROMPT not in captured.out
    assert cli._REAL_SMOKE_USER_PROMPT not in captured.out


def test_successful_run_sends_the_explicit_model_and_a_fixed_prompt(tmp_path, capsys):
    seen: list[dict] = []
    _run(tmp_path, client_factory=_mock_client_factory(seen))

    capsys.readouterr()
    assert len(seen) == 1
    sent = seen[0]

    # The explicit --model value, never the environment's default model.
    assert sent["model"] == ALLOWED_MODEL
    assert sent["model"] != ENV_DEFAULT_MODEL

    # A fixed, harmless prompt: no issue text, no project data, no paths.
    assert [message["role"] for message in sent["messages"]] == ["system", "user"]
    assert sent["messages"][0]["content"] == cli._REAL_SMOKE_SYSTEM_PROMPT
    assert sent["messages"][1]["content"] == cli._REAL_SMOKE_USER_PROMPT
    assert sent["max_tokens"] == cli._REAL_SMOKE_MAX_TOKENS
    assert sent["temperature"] == 0.0
    for leaked in ("demo_project", "demo/widgets", "workspace", "src/**"):
        assert leaked not in json.dumps(sent)


def test_successful_run_prints_the_before_call_warning_to_stderr(tmp_path, capsys):
    _run(tmp_path)

    captured = capsys.readouterr()
    assert "REAL MODEL SMOKE TEST — a real network call is about to be made" in (
        captured.err
    )
    assert f"Endpoint host: {FAKE_HOST}" in captured.err
    assert f"Model:         {ALLOWED_MODEL}" in captured.err
    assert "Project:       demo_project" in captured.err
    assert "No issue text is sent" in captured.err
    assert "No files, workspaces, or GitHub data are read or written." in captured.err
    # The banner goes to stderr only, so piping stdout to a file still leaves
    # the warning visible and keeps the JSON machine-parseable.
    assert "a real network call is about to be made" not in captured.out
    assert "Endpoint host:" not in captured.out


def test_successful_run_prints_the_after_call_block_to_stderr(tmp_path, capsys):
    _run(tmp_path)

    captured = capsys.readouterr()
    assert "REAL MODEL SMOKE TEST COMPLETED" in captured.err
    assert "FAILED" not in captured.err
    # Ordering: warn before the call, confirm after it.
    assert captured.err.index("about to be made") < captured.err.index("COMPLETED")


# -- 16. client failure after the call was attempted --------------------------


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

    assert "REAL MODEL SMOKE TEST FAILED (a real call was attempted)" in captured.err
    assert expected.__name__ in captured.err
    assert f"Endpoint host: {FAKE_HOST}" in captured.err
    # No JSON success output.
    assert captured.out.strip() == ""
    assert FAKE_API_KEY not in captured.err


# -- 17..21. isolation guarantees ---------------------------------------------


def test_command_has_no_issue_github_or_workspace_options():
    result = runner.invoke(app, ["real-llm-smoke-test", "--help"])

    # No option can supply issue text, GitHub access, or a workspace path. (The
    # prose in the help text says as much; these assert the *options*.)
    for absent in (
        "--issue",
        "--body-file",
        "--github",
        "--fetch",
        "--repo",
        "--title",
        "--workspace",
        "--audit-dir",
        "--message",
        "--file",
        "--context-file",
    ):
        assert absent not in result.output

    # Invoking it with one is an error, not a silently ignored argument.
    rejected = runner.invoke(
        app, ["real-llm-smoke-test", "--issue", "42", "--real-model"]
    )
    assert rejected.exit_code != 0


def test_command_reads_only_the_project_config_file(tmp_path, monkeypatch, capsys):
    config_path = _write_config(tmp_path)
    opened: list[str] = []

    real_read_text = type(config_path).read_text

    def tracking_read_text(self, *args, **kwargs):
        opened.append(str(self))
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(type(config_path), "read_text", tracking_read_text)

    def _blocked(*args, **kwargs):
        raise AssertionError("the command must not inspect the filesystem")

    monkeypatch.setattr(os, "listdir", _blocked)
    monkeypatch.setattr(os, "scandir", _blocked)
    monkeypatch.setattr(os, "stat", _blocked)
    monkeypatch.setattr(os.path, "realpath", _blocked)

    _run(tmp_path, project_config=config_path)

    capsys.readouterr()
    # Exactly one file read: the config explicitly named on the command line.
    assert opened == [str(config_path)]
    # The configured workspace path was never created, and never touched.
    assert not (tmp_path / "never_touched_workspace").exists()


def test_no_real_network_call_is_made(tmp_path, monkeypatch, capsys):
    factory = _mock_client_factory()

    def _blocked(*args, **kwargs):
        raise AssertionError("no real socket may be opened by the test suite")

    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket, "getaddrinfo", _blocked)
    monkeypatch.setattr(socket, "gethostbyname", _blocked)
    monkeypatch.setattr(subprocess, "Popen", _blocked)

    _run(tmp_path, client_factory=factory)

    payload = json.loads(capsys.readouterr().out)
    assert payload["response_content"] == SMOKE_REPLY


def test_tests_never_read_the_real_environment(tmp_path, monkeypatch, capsys):
    def _blocked(*args, **kwargs):
        raise AssertionError("the injected mapping is the only environment source")

    monkeypatch.setattr(os, "getenv", _blocked)
    monkeypatch.setattr(os.environ, "get", _blocked)

    _run(tmp_path)

    assert json.loads(capsys.readouterr().out)["provenance"]["real_call"] is True


def test_real_env_reader_touches_only_the_five_aido_names(monkeypatch):
    # The real reader is exercised against a *replaced* os.environ, so no real
    # value is read here either.
    fake_environ = {
        "AIDO_LITELLM_BASE_URL": FAKE_BASE_URL,
        "AIDO_LITELLM_API_KEY": FAKE_API_KEY,
        "AIDO_LITELLM_DEFAULT_MODEL": ENV_DEFAULT_MODEL,
        "AIDO_LITELLM_MAX_RETRIES": "0",
        "PATH": "should-not-be-read",
        "GITHUB_TOKEN": "should-not-be-read",
        "AIDO_SOMETHING_ELSE": "should-not-be-read",
    }
    monkeypatch.setattr(cli.os, "environ", fake_environ)

    snapshot = cli._read_real_llm_env()

    assert set(snapshot) == {
        "AIDO_LITELLM_BASE_URL",
        "AIDO_LITELLM_API_KEY",
        "AIDO_LITELLM_DEFAULT_MODEL",
        "AIDO_LITELLM_MAX_RETRIES",
    }
    assert set(cli._REAL_SMOKE_ENV_NAMES) >= set(snapshot)
    # An absent optional variable is simply omitted, never defaulted.
    assert "AIDO_LITELLM_TIMEOUT_SECONDS" not in snapshot


def test_command_imports_no_github_client(tmp_path, monkeypatch, capsys):
    import ai_dev_orchestrator.github.client as github_client

    def _blocked(*args, **kwargs):
        raise AssertionError("this command must not use the GitHub client")

    monkeypatch.setattr(github_client.GitHubClient, "get_issue", _blocked)
    monkeypatch.setattr(github_client.GitHubClient, "__init__", _blocked)

    _run(tmp_path)

    assert json.loads(capsys.readouterr().out)["provenance"]["operation"] == (
        "smoke-test"
    )
