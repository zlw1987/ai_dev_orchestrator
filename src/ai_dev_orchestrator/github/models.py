"""Typed model for a fetched GitHub issue.

Phase 2: read-only. This model describes the subset of the GitHub issue API
response the orchestrator needs. It performs no network calls itself.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class GitHubIssue(BaseModel):
    """A GitHub issue as fetched read-only from the REST API."""

    number: int
    title: str
    body: str | None = None
    state: str
    html_url: str
    labels: list[str] = Field(default_factory=list)
    is_pull_request: bool = False

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "GitHubIssue":
        """Build a :class:`GitHubIssue` from a raw issue API response payload."""
        raw_labels = data.get("labels") or []
        labels: list[str] = []
        for label in raw_labels:
            if isinstance(label, dict):
                name = label.get("name")
                if name:
                    labels.append(name)
            elif isinstance(label, str):
                labels.append(label)

        return cls(
            number=data["number"],
            title=data.get("title", ""),
            body=data.get("body"),
            state=data.get("state", ""),
            html_url=data.get("html_url", ""),
            labels=labels,
            # The issues endpoint includes a "pull_request" object only for PRs.
            is_pull_request="pull_request" in data,
        )
