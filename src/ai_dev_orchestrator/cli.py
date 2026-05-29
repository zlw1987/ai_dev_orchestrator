"""Command-line interface for the AI Dev Orchestrator.

Phase 0: only `--help` and a `version` command are implemented. No GitHub,
LiteLLM, agent, or execution behavior is wired up.
"""

from __future__ import annotations

import typer

from ai_dev_orchestrator import __version__

app = typer.Typer(
    name="ai-dev-orchestrator",
    help="Controlled AI software development pipeline orchestrator (Phase 0 skeleton).",
    no_args_is_help=True,
    add_completion=False,
)


@app.callback()
def main() -> None:
    """Controlled AI software development pipeline orchestrator (Phase 0 skeleton)."""


@app.command()
def version() -> None:
    """Print the orchestrator version."""
    typer.echo(__version__)


if __name__ == "__main__":
    app()
