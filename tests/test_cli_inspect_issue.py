"""Phase 2 tests: inspect-issue CLI command. No real network calls."""

from typer.testing import CliRunner

from ai_dev_orchestrator.cli import app
from ai_dev_orchestrator.github.client import GitHubError
from ai_dev_orchestrator.github.models import GitHubIssue

runner = CliRunner()

SAMPLE_ISSUE = GitHubIssue(
    number=6,
    title="Add issue reader",
    body="## Goal\nDo it\n## Scope\nnarrow\n",
    state="open",
    html_url="https://github.com/zlw1987/mis_project/issues/6",
    labels=["enhancement"],
)


def test_inspect_issue_help_runs():
    result = runner.invoke(app, ["inspect-issue", "--help"])
    assert result.exit_code == 0
    assert "--repo" in result.output
    assert "--issue" in result.output


def test_inspect_issue_prints_summary(monkeypatch):
    def fake_get_issue(self, repo, issue):
        assert repo == "zlw1987/mis_project"
        assert issue == 6
        return SAMPLE_ISSUE

    monkeypatch.setattr(
        "ai_dev_orchestrator.github.client.GitHubClient.get_issue", fake_get_issue
    )

    result = runner.invoke(
        app, ["inspect-issue", "--repo", "zlw1987/mis_project", "--issue", "6"]
    )
    assert result.exit_code == 0
    assert "Issue #6: Add issue reader" in result.output
    assert "State: open" in result.output
    assert "enhancement" in result.output
    assert "Goal" in result.output
    assert "Scope" in result.output
    # Required sections that are absent should be reported as missing.
    assert "Non-goals" in result.output


def test_inspect_issue_handles_api_error(monkeypatch):
    def boom(self, repo, issue):
        raise GitHubError("GitHub returned 404")

    monkeypatch.setattr(
        "ai_dev_orchestrator.github.client.GitHubClient.get_issue", boom
    )

    result = runner.invoke(
        app, ["inspect-issue", "--repo", "owner/repo", "--issue", "1"]
    )
    assert result.exit_code != 0
    assert "Error" in result.output
    assert "404" in result.output
