"""Read-only GitHub REST client.

Phase 2 constraints (deliberate):

- Only reads a single issue: GET /repos/{owner}/{repo}/issues/{number}.
- No write API: no comments, labels, branches, or PRs are created.
- Uses GITHUB_TOKEN from the environment when present, but does not require it
  (public repos may be readable unauthenticated).
- Secrets are never written to disk; the token is read from the environment only.
"""

from __future__ import annotations

import os

import httpx

from ai_dev_orchestrator.github.models import GitHubIssue

GITHUB_API_BASE = "https://api.github.com"
_USER_AGENT = "ai-dev-orchestrator"
_API_VERSION = "2022-11-28"


class GitHubError(Exception):
    """Raised when a GitHub request fails or returns a non-success status."""


def _split_repo(repo_full_name: str) -> tuple[str, str]:
    parts = repo_full_name.split("/")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise GitHubError(
            f"Invalid repository name {repo_full_name!r}; expected 'owner/repo'."
        )
    return parts[0], parts[1]


class GitHubClient:
    """Minimal read-only GitHub API client."""

    def __init__(
        self,
        token: str | None = None,
        *,
        client: httpx.Client | None = None,
        base_url: str = GITHUB_API_BASE,
    ) -> None:
        # Token defaults to the environment; an explicit "" disables auth.
        self._token = token if token is not None else os.environ.get("GITHUB_TOKEN")
        self._base_url = base_url.rstrip("/")
        # An injected client (e.g. with httpx.MockTransport) keeps tests offline.
        self._client = client

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": _API_VERSION,
            "User-Agent": _USER_AGENT,
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def get_issue(self, repo_full_name: str, issue_number: int) -> GitHubIssue:
        """Fetch one issue and return it as a typed :class:`GitHubIssue`."""
        owner, repo = _split_repo(repo_full_name)
        url = f"{self._base_url}/repos/{owner}/{repo}/issues/{issue_number}"

        client = self._client or httpx.Client(timeout=30.0)
        try:
            response = client.get(url, headers=self._headers())
        except httpx.HTTPError as exc:
            raise GitHubError(f"Request to GitHub failed: {exc}") from exc
        finally:
            if self._client is None:
                client.close()

        if response.status_code >= 400:
            message = _extract_error_message(response)
            raise GitHubError(
                f"GitHub returned {response.status_code} for {owner}/{repo}"
                f"#{issue_number}: {message}"
            )

        return GitHubIssue.from_api(response.json())


def _extract_error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text or "no response body"
    if isinstance(payload, dict) and payload.get("message"):
        return str(payload["message"])
    return "unknown error"
