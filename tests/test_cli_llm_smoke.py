"""Phase 3D tests: llm-smoke-test CLI command.

The command is a dry-run / fake-provider smoke test over the Phase 3C
``LLMClient``. All HTTP is faked internally with ``httpx.MockTransport`` — no
socket is ever opened, no ``AIDO_LITELLM_*`` env var is read, and no real
model is called.
"""

from typer.testing import CliRunner

from ai_dev_orchestrator.cli import app

runner = CliRunner()


def test_llm_smoke_test_succeeds_with_defaults():
    result = runner.invoke(app, ["llm-smoke-test"])
    assert result.exit_code == 0


def test_llm_smoke_test_states_dry_run_and_no_real_model():
    result = runner.invoke(app, ["llm-smoke-test"])
    assert result.exit_code == 0
    assert "dry-run" in result.output.lower()
    assert "fake provider" in result.output.lower()
    assert "no real model was called" in result.output.lower()


def test_llm_smoke_test_default_model_and_response():
    result = runner.invoke(app, ["llm-smoke-test"])
    assert result.exit_code == 0
    assert "minimax-m2.7" in result.output
    assert "[fake response] echo: ping" in result.output


def test_llm_smoke_test_custom_model_and_message():
    result = runner.invoke(
        app,
        ["llm-smoke-test", "--model", "qwen3.6-27b", "--message", "hello there"],
    )
    assert result.exit_code == 0
    assert "qwen3.6-27b" in result.output
    assert "[fake response] echo: hello there" in result.output


def test_llm_smoke_test_does_not_require_env_vars(monkeypatch):
    for name in (
        "AIDO_LITELLM_BASE_URL",
        "AIDO_LITELLM_API_KEY",
        "AIDO_LITELLM_DEFAULT_MODEL",
        "AIDO_LITELLM_TIMEOUT_SECONDS",
        "AIDO_LITELLM_MAX_RETRIES",
    ):
        monkeypatch.delenv(name, raising=False)

    result = runner.invoke(app, ["llm-smoke-test"])
    assert result.exit_code == 0


def test_llm_smoke_test_does_not_print_fake_api_key():
    result = runner.invoke(app, ["llm-smoke-test"])
    assert result.exit_code == 0
    assert "fake-api-key-for-dry-run-only" not in result.output


def test_llm_smoke_test_help_runs():
    result = runner.invoke(app, ["llm-smoke-test", "--help"])
    assert result.exit_code == 0
    assert "--model" in result.output
    assert "--message" in result.output


def test_cli_still_has_existing_commands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "version" in result.output
    assert "inspect-issue" in result.output
    assert "llm-smoke-test" in result.output


def test_llm_smoke_test_makes_no_real_network_call(monkeypatch):
    """Any real socket connect attempt fails the test instead of hanging."""

    def boom(*args, **kwargs):
        raise AssertionError("real network connection attempted")

    monkeypatch.setattr("socket.socket.connect", boom)

    result = runner.invoke(app, ["llm-smoke-test"])
    assert result.exit_code == 0
