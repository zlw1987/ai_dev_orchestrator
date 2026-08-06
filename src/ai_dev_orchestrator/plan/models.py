"""Typed L1 plan models for the AI Dev Orchestrator.

Phase 4B: pure data models only. ``L1Plan`` describes the structured shape of
the plan-only artifact a future L1 planner (Phase 4C+) will produce. This
module is a plan artifact schema, not executable instructions: it performs no
file reads, no workspace path checks, no command execution, no GitHub writes,
and no model or network calls. Path-like fields (``files_likely_to_change``,
``files_forbidden_or_out_of_scope``) are kept as plain strings and are never
resolved, stat'd, or normalized here.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


def _require_non_blank(value: str, field_name: str) -> str:
    """Reject empty or whitespace-only strings."""
    if value is None or not value.strip():
        raise ValueError(f"{field_name} must not be empty or whitespace-only.")
    return value


def _require_non_blank_items(values: list[str], field_name: str) -> list[str]:
    """Reject lists containing empty or whitespace-only string items."""
    for item in values:
        if item is None or not item.strip():
            raise ValueError(
                f"{field_name} items must not be empty or whitespace-only."
            )
    return values


def _require_owner_repo(value: str) -> str:
    """Reject blank repo strings and anything not shaped like 'owner/repo'."""
    value = _require_non_blank(value, "repo")
    parts = value.split("/")
    if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
        raise ValueError("repo must look like 'owner/repo'.")
    return value


class L1PlanSource(BaseModel):
    """Optional pointer back to the GitHub issue an ``L1Plan`` was derived from."""

    issue_number: int
    repo: str
    title: str
    html_url: str
    labels: list[str] = Field(default_factory=list)

    @field_validator("issue_number")
    @classmethod
    def _issue_number_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("issue_number must be positive.")
        return value

    @field_validator("repo")
    @classmethod
    def _repo_valid(cls, value: str) -> str:
        return _require_owner_repo(value)

    @field_validator("title", "html_url")
    @classmethod
    def _not_blank(cls, value: str, info) -> str:
        return _require_non_blank(value, info.field_name)

    @field_validator("labels")
    @classmethod
    def _labels_items_not_blank(cls, value: list[str]) -> list[str]:
        return _require_non_blank_items(value, "labels")


class L1Plan(BaseModel):
    """A structured, human-reviewable plan produced by the (future) L1 planner.

    This is a plan artifact only, not executable instructions — nothing in
    this module interprets, applies, or executes any field. ``automation_level``
    is fixed to ``"L1"`` and ``requires_human_approval`` is always ``True``: an
    ``L1Plan`` can never self-escalate its automation level or mark itself as
    not requiring human review.
    """

    issue_number: int
    repo: str
    title: str
    summary: str
    scope_summary: str
    non_goals: list[str] = Field(default_factory=list)
    proposed_steps: list[str]
    files_likely_to_change: list[str] = Field(default_factory=list)
    files_forbidden_or_out_of_scope: list[str] = Field(default_factory=list)
    required_verification: list[str]
    risks: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    automation_level: Literal["L1"] = "L1"
    requires_human_approval: bool = True

    @field_validator("issue_number")
    @classmethod
    def _issue_number_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("issue_number must be positive.")
        return value

    @field_validator("repo")
    @classmethod
    def _repo_valid(cls, value: str) -> str:
        return _require_owner_repo(value)

    @field_validator("title", "summary", "scope_summary")
    @classmethod
    def _not_blank(cls, value: str, info) -> str:
        return _require_non_blank(value, info.field_name)

    @field_validator(
        "non_goals",
        "proposed_steps",
        "files_likely_to_change",
        "files_forbidden_or_out_of_scope",
        "required_verification",
        "risks",
        "open_questions",
    )
    @classmethod
    def _list_items_not_blank(cls, value: list[str], info) -> list[str]:
        return _require_non_blank_items(value, info.field_name)

    @field_validator("proposed_steps")
    @classmethod
    def _proposed_steps_not_empty(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("proposed_steps must contain at least one item.")
        return value

    @field_validator("required_verification")
    @classmethod
    def _required_verification_not_empty(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("required_verification must contain at least one item.")
        return value

    @field_validator("requires_human_approval")
    @classmethod
    def _requires_human_approval_always_true(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("requires_human_approval must always be True for L1 plans.")
        return value
