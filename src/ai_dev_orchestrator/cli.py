"""Command-line interface for the AI Dev Orchestrator.

Commands are read-only so far: a `version` command and `inspect-issue`
(read-only GitHub issue inspection). No LiteLLM/model calls, agent logic,
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


if __name__ == "__main__":
    app()
