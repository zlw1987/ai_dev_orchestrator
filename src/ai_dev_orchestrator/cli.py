"""Command-line interface for the AI Dev Orchestrator.

Commands are read-only / dry-run so far: a `version` command, `inspect-issue`
(read-only GitHub issue inspection), and `llm-smoke-test` (a fake-provider
dry-run of the Phase 3C LLM client — no real model call). No agent logic,
file editing, command execution, or GitHub writes are wired up.
"""

from __future__ import annotations

import typer

from ai_dev_orchestrator import __version__

app = typer.Typer(
    name="ai-dev-orchestrator",
    help="Controlled AI software development pipeline orchestrator.",
    no_args_is_help=True,
    add_completion=False,
)


@app.callback()
def main() -> None:
    """Controlled AI software development pipeline orchestrator."""


@app.command()
def version() -> None:
    """Print the orchestrator version."""
    typer.echo(__version__)


@app.command("inspect-issue")
def inspect_issue(
    repo: str = typer.Option(..., "--repo", help="Repository as owner/repo."),
    issue: int = typer.Option(..., "--issue", help="Issue number to inspect."),
) -> None:
    """Read a GitHub issue (read-only) and report its parsed sections.

    Read-only: does not write to GitHub, call any model, or read/write any
    configured project workspace.
    """
    # Imported lazily so the rest of the CLI works without httpx installed.
    from ai_dev_orchestrator.github.client import GitHubClient, GitHubError
    from ai_dev_orchestrator.github.issue_parser import parse_issue_body

    client = GitHubClient()
    try:
        gh_issue = client.get_issue(repo, issue)
    except GitHubError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)

    parsed = parse_issue_body(gh_issue.body)

    labels = ", ".join(gh_issue.labels) if gh_issue.labels else "(none)"
    found = ", ".join(parsed.present_sections) if parsed.present_sections else "(none)"
    missing = (
        ", ".join(parsed.missing_required) if parsed.missing_required else "(none)"
    )

    typer.echo(f"Issue #{gh_issue.number}: {gh_issue.title}")
    typer.echo(f"State: {gh_issue.state}")
    if gh_issue.is_pull_request:
        typer.echo("Note: this issue is actually a pull request.")
    typer.echo(f"Labels: {labels}")
    typer.echo(f"Sections found: {found}")
    typer.echo(f"Missing required sections: {missing}")


_FAKE_BASE_URL = "http://fake-litellm.local/v1"
_FAKE_API_KEY = "fake-api-key-for-dry-run-only"
_DEFAULT_MODEL = "minimax-m2.7"


@app.command("llm-smoke-test")
def llm_smoke_test(
    model: str = typer.Option(
        _DEFAULT_MODEL, "--model", help="Fake model name to send in the request."
    ),
    message: str = typer.Option(
        "ping", "--message", help="User message content to send."
    ),
) -> None:
    """Dry-run smoke test of the Phase 3C LLMClient against a fake provider.

    This is a **dry-run / fake-provider smoke test only**: it never reads
    environment variables, never loads real LiteLLM config, and never makes a
    real network call. All HTTP is faked with an in-process
    ``httpx.MockTransport`` that returns a deterministic response.
    """
    # Imported lazily, matching the inspect-issue command's pattern.
    from ai_dev_orchestrator.llm.client import LLMClient
    from ai_dev_orchestrator.llm.models import LLMClientConfig, LLMMessage, LLMRequest

    import httpx

    def fake_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": model,
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": f"[fake response] echo: {message}",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 1,
                    "completion_tokens": 1,
                    "total_tokens": 2,
                },
            },
        )

    config = LLMClientConfig(
        base_url=_FAKE_BASE_URL,
        api_key=_FAKE_API_KEY,
        default_model=model,
    )
    client = LLMClient(
        config,
        transport=httpx.MockTransport(fake_handler),
        sleep=lambda _seconds: None,
    )
    request = LLMRequest(
        model=model,
        messages=[LLMMessage(role="user", content=message)],
    )
    response = client.chat(request)

    typer.echo("=== LLM smoke test (dry-run / fake provider) ===")
    typer.echo("This is a dry-run using a fake provider. No real model was called.")
    typer.echo(f"Model: {response.model}")
    typer.echo(f"Response content: {response.content}")
    if response.usage is not None:
        typer.echo(
            "Token usage: prompt="
            f"{response.usage.prompt_tokens} completion="
            f"{response.usage.completion_tokens} total="
            f"{response.usage.total_tokens}"
        )


if __name__ == "__main__":
    app()
