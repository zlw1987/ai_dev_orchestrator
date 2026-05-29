"""Phase 2 tests: read-only GitHub client. All network calls are mocked."""

import httpx
import pytest

from ai_dev_orchestrator.github.client import GitHubClient, GitHubError

ISSUE_PAYLOAD = {
    "number": 6,
    "title": "Add issue reader",
    "body": "## Goal\nDo the thing\n",
    "state": "open",
    "html_url": "https://github.com/zlw1987/mis_project/issues/6",
    "labels": [{"name": "enhancement"}, {"name": "phase-2"}],
}


def _client_with(handler) -> GitHubClient:
    transport = httpx.MockTransport(handler)
    return GitHubClient(token=None, client=httpx.Client(transport=transport))


def test_builds_correct_get_request():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["accept"] = request.headers.get("Accept")
        captured["api_version"] = request.headers.get("X-GitHub-Api-Version")
        captured["user_agent"] = request.headers.get("User-Agent")
        return httpx.Response(200, json=ISSUE_PAYLOAD)

    issue = _client_with(handler).get_issue("zlw1987/mis_project", 6)

    assert captured["method"] == "GET"
    assert captured["url"] == "https://api.github.com/repos/zlw1987/mis_project/issues/6"
    assert captured["accept"] == "application/vnd.github+json"
    assert captured["api_version"] == "2022-11-28"
    assert captured["user_agent"] == "ai-dev-orchestrator"
    assert issue.number == 6
    assert issue.title == "Add issue reader"
    assert issue.labels == ["enhancement", "phase-2"]
    assert issue.is_pull_request is False


def test_includes_token_header_when_token_provided():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("Authorization")
        return httpx.Response(200, json=ISSUE_PAYLOAD)

    transport = httpx.MockTransport(handler)
    client = GitHubClient(token="secret-token", client=httpx.Client(transport=transport))
    client.get_issue("zlw1987/mis_project", 6)

    assert captured["auth"] == "Bearer secret-token"


def test_no_token_means_no_auth_header(monkeypatch):
    # Ensure the environment token does not leak into the request.
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("Authorization")
        return httpx.Response(200, json=ISSUE_PAYLOAD)

    transport = httpx.MockTransport(handler)
    client = GitHubClient(client=httpx.Client(transport=transport))
    client.get_issue("zlw1987/mis_project", 6)

    assert captured["auth"] is None


def test_pull_request_field_sets_is_pull_request():
    payload = {**ISSUE_PAYLOAD, "pull_request": {"url": "https://api.github.com/..."}}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    issue = _client_with(handler).get_issue("zlw1987/mis_project", 6)
    assert issue.is_pull_request is True


def test_http_error_raises_github_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "Not Found"})

    with pytest.raises(GitHubError) as exc:
        _client_with(handler).get_issue("zlw1987/mis_project", 999)
    assert "404" in str(exc.value)
    assert "Not Found" in str(exc.value)


def test_invalid_repo_name_raises():
    with pytest.raises(GitHubError):
        GitHubClient(token=None).get_issue("not-a-valid-repo", 1)
