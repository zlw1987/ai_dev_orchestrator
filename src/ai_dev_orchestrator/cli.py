"""Command-line interface for the AI Dev Orchestrator.

Commands are read-only / dry-run / offline so far: a `version` command,
`inspect-issue` (read-only GitHub issue inspection), `llm-smoke-test` (a
fake-provider dry-run of the Phase 3C LLM client — no real model call), and
`generate-plan` (an offline fake/deterministic L1 plan generator — Phase 4D,
no GitHub fetch, no model call). No agent logic, file editing, command
execution, or GitHub writes are wired up.
"""

from __future__ import annotations

import enum
import json
import os
from pathlib import Path

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


class GeneratePlanFormat(str, enum.Enum):
    """Supported output formats for `generate-plan`. Only JSON exists so far."""

    json = "json"


def _is_same_or_under(candidate: Path, root: str) -> bool:
    """Report whether ``candidate`` is ``root`` itself or sits beneath it.

    **String/path normalization only.** Both operands are treated as opaque
    strings: neither is read, listed, stat'd, resolved, or otherwise touched
    on disk. ``os.path.abspath`` only joins against the current working
    directory and normalizes separators — it performs no filesystem access.
    """
    normalized_candidate = os.path.normcase(os.path.abspath(str(candidate)))
    normalized_root = os.path.normcase(os.path.abspath(str(root)))
    if normalized_candidate == normalized_root:
        return True
    return normalized_candidate.startswith(normalized_root + os.sep)


@app.command("generate-plan")
def generate_plan(
    project_config: Path = typer.Option(
        ...,
        "--project-config",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Path to a project config YAML file inside this repo, "
        "e.g. projects/mis_project.yaml.example.",
    ),
    repo: str = typer.Option(
        ..., "--repo", help="Repository as owner/repo for the synthetic issue."
    ),
    issue: int = typer.Option(
        ..., "--issue", help="Issue number for the synthetic issue."
    ),
    title: str = typer.Option(
        ..., "--title", help="Issue title for the synthetic issue."
    ),
    body_file: Path = typer.Option(
        ...,
        "--body-file",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Path to a local markdown/text file containing the issue body.",
    ),
    output_format: GeneratePlanFormat = typer.Option(
        GeneratePlanFormat.json,
        "--format",
        help="Output format. Only 'json' is currently supported.",
    ),
) -> None:
    """Build an offline, fake/deterministic L1 plan from local files only.

    **Offline-only (Phase 4D)**: reads only the two local files explicitly
    given via ``--project-config`` and ``--body-file``. Does not fetch the
    issue from GitHub, does not call any model, does not read
    ``AIDO_LITELLM_*`` or any other environment variable, and does not read
    the project's configured ``repo.workspace_path``.

    A ``--body-file`` that is the configured ``repo.workspace_path`` itself,
    or sits under it, is rejected before the file is read — enforced with
    string/path normalization only, never by touching that path on disk.

    The printed JSON is an **L1 (plan-only) artifact**: it always carries
    ``automation_level: "L1"`` and ``requires_human_approval: true``, and its
    ``proposed_steps`` are descriptive review steps, not executable
    instructions.
    """
    # Imported lazily, matching the inspect-issue/llm-smoke-test pattern.
    from ai_dev_orchestrator.config_loader import ConfigError, load_project_config
    from ai_dev_orchestrator.github.issue_parser import parse_issue_body
    from ai_dev_orchestrator.github.models import GitHubIssue
    from ai_dev_orchestrator.plan import FakeL1Planner

    try:
        project = load_project_config(project_config)
    except ConfigError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)

    # Refuse to read an issue body that lives inside the configured target
    # workspace. Checked BEFORE the body file is read, using string/path
    # normalization only — repo.workspace_path is never read, listed, stat'd,
    # resolved, or otherwise touched.
    if _is_same_or_under(body_file, project.repo.workspace_path):
        typer.echo(
            "Error: --body-file is inside the project's configured "
            f"repo.workspace_path ({project.repo.workspace_path}). "
            "generate-plan never reads target project workspaces; copy the "
            "issue body to a file outside that path and retry.",
            err=True,
        )
        raise typer.Exit(code=1)

    body_text = body_file.read_text(encoding="utf-8")

    synthetic_issue = GitHubIssue(
        number=issue,
        title=title,
        body=body_text,
        state="open",
        html_url=f"(offline synthetic issue, not fetched from GitHub) {repo}#{issue}",
    )
    parsed = parse_issue_body(synthetic_issue.body)

    plan = FakeL1Planner().create_plan(synthetic_issue, parsed, project)

    output = {
        "notice": (
            "L1 PLAN ONLY — generated offline by a fake/deterministic "
            "planner. This is not executable instructions. A human must "
            "review and approve before any implementation work proceeds."
        ),
        **plan.model_dump(),
    }
    typer.echo(json.dumps(output, indent=2))


if __name__ == "__main__":
    app()
