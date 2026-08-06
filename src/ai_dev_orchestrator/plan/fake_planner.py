"""Deterministic fake/offline L1 planner engine.

Phase 4C: a pure, deterministic transformation from already-fetched issue and
project objects (:class:`~ai_dev_orchestrator.github.models.GitHubIssue`,
:class:`~ai_dev_orchestrator.github.issue_parser.ParsedIssue`,
:class:`~ai_dev_orchestrator.models.ProjectConfig`) into an
:class:`~ai_dev_orchestrator.plan.models.L1Plan`.

This module performs NO network calls, NO model calls, NO environment variable
reads, NO file reads, and NO workspace path resolution/stat/normalization. It
only reasons over the string content of objects it is given.
"""

from __future__ import annotations

import re

from ai_dev_orchestrator.github.issue_parser import (
    GOAL,
    NON_GOALS,
    REQUIRED_VERIFICATION,
    SCOPE,
    ParsedIssue,
)
from ai_dev_orchestrator.github.models import GitHubIssue
from ai_dev_orchestrator.models import ProjectConfig
from ai_dev_orchestrator.plan.models import L1Plan

_FALLBACK_SCOPE_SUMMARY = (
    "No Scope section was provided in the issue; scope is unclear."
)
_FALLBACK_REQUIRED_VERIFICATION = (
    "No Required Verification section was provided in the issue; "
    "verification requirements must be confirmed before proceeding."
)

_BULLET_PREFIX_RE = re.compile(r"^(?:[-*+]|\d+[.)])\s+")

# Matches path-like tokens (plain string scanning only — never resolved,
# stat'd, or checked against the real filesystem): either a slash-separated
# path, or a bare token ending in a short file extension.
_PATH_TOKEN_RE = re.compile(
    r"`?((?:[A-Za-z0-9_.\-]+/)+[A-Za-z0-9_.\-]+|\b[A-Za-z0-9_\-]+\.[A-Za-z0-9]{1,6}\b)`?"
)


def _parse_bullet_lines(text: str | None) -> list[str]:
    """Split section text into plain-string lines, stripping bullet markers."""
    if not text or not text.strip():
        return []
    lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = _BULLET_PREFIX_RE.sub("", line)
        lines.append(line)
    return lines


def _extract_path_mentions(text: str | None) -> list[str]:
    """Extract explicit path-like string tokens mentioned in section text."""
    if not text:
        return []
    found: list[str] = []
    for match in _PATH_TOKEN_RE.finditer(text):
        token = match.group(1)
        if token not in found:
            found.append(token)
    return found


class FakeL1Planner:
    """Deterministic, offline L1 planner: no model, network, env, or file IO."""

    def create_plan(
        self,
        issue: GitHubIssue,
        parsed: ParsedIssue,
        project: ProjectConfig,
    ) -> L1Plan:
        goal_text = parsed.sections.get(GOAL, "").strip()
        summary = goal_text if goal_text else issue.title

        scope_text = parsed.sections.get(SCOPE, "").strip()
        scope_summary = scope_text if scope_text else _FALLBACK_SCOPE_SUMMARY

        non_goals_text = parsed.sections.get(NON_GOALS, "")
        non_goals = _parse_bullet_lines(non_goals_text)

        required_verification_text = parsed.sections.get(REQUIRED_VERIFICATION, "")
        required_verification = _parse_bullet_lines(required_verification_text)
        if not required_verification:
            required_verification = [_FALLBACK_REQUIRED_VERIFICATION]

        files_likely_to_change = _extract_path_mentions(scope_text)

        files_forbidden_or_out_of_scope = list(project.forbidden_paths)
        for path in _extract_path_mentions(non_goals_text):
            if path not in files_forbidden_or_out_of_scope:
                files_forbidden_or_out_of_scope.append(path)

        risks: list[str] = []
        if parsed.missing_required:
            risks.append(
                "Issue is missing required section(s): "
                + ", ".join(parsed.missing_required)
                + "."
            )
        if project.protected_paths:
            risks.append(
                "Project defines protected paths that require explicit "
                "authorization before modification: "
                + ", ".join(project.protected_paths)
                + "."
            )

        open_questions: list[str] = []
        if not scope_text:
            open_questions.append(
                "The issue's Scope section is missing or empty; scope is unclear."
            )
        if not files_likely_to_change:
            open_questions.append(
                "No specific files could be inferred from the Scope section; "
                "file-level scope is unclear."
            )

        proposed_steps = [
            "Review the issue goal, scope, non-goals, and acceptance criteria.",
            "Identify the allowed in-scope files from the project config.",
            "Draft changes only within allowed paths and outside forbidden paths.",
            "Record the required verification listed in the issue for later "
            "human-approved execution.",
        ]

        return L1Plan(
            issue_number=issue.number,
            repo=project.repo.github_repo,
            title=issue.title,
            summary=summary,
            scope_summary=scope_summary,
            non_goals=non_goals,
            proposed_steps=proposed_steps,
            files_likely_to_change=files_likely_to_change,
            files_forbidden_or_out_of_scope=files_forbidden_or_out_of_scope,
            required_verification=required_verification,
            risks=risks,
            open_questions=open_questions,
        )
