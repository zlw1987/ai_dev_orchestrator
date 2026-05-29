"""Parse a GitHub issue body into structured Markdown sections.

Phase 2: structural parsing only. This module:

- splits the body on Markdown headings (``#`` .. ``######``),
- maps recognized heading names to canonical section names (case-insensitive,
  tolerant of extra whitespace),
- preserves each section's text as raw Markdown,
- reports which required sections are missing.

It deliberately does NOT interpret checkboxes, validate automation levels, or
do any project/workspace validation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Canonical section names.
GOAL = "Goal"
CURRENT_CONTEXT = "Current Context"
SCOPE = "Scope"
NON_GOALS = "Non-goals"
ACCEPTANCE_CRITERIA = "Acceptance Criteria"
REQUIRED_VERIFICATION = "Required Verification"
AI_INSTRUCTIONS = "AI Instructions"
AUTOMATION_AUTHORIZATION = "Automation Authorization"

REQUIRED_SECTIONS: tuple[str, ...] = (
    GOAL,
    SCOPE,
    NON_GOALS,
    ACCEPTANCE_CRITERIA,
    REQUIRED_VERIFICATION,
)

OPTIONAL_SECTIONS: tuple[str, ...] = (
    CURRENT_CONTEXT,
    AI_INSTRUCTIONS,
    AUTOMATION_AUTHORIZATION,
)


def _normalize(heading: str) -> str:
    """Lowercase, collapse whitespace, and treat hyphens as spaces."""
    text = heading.strip().casefold().replace("-", " ")
    return re.sub(r"\s+", " ", text)


# Map normalized heading text -> canonical name.
_LOOKUP: dict[str, str] = {
    _normalize(name): name for name in (*REQUIRED_SECTIONS, *OPTIONAL_SECTIONS)
}

_HEADING_RE = re.compile(r"^\s*(#{1,6})\s+(.*\S)\s*$")


@dataclass
class ParsedIssue:
    """Result of parsing an issue body."""

    sections: dict[str, str] = field(default_factory=dict)

    @property
    def present_sections(self) -> list[str]:
        """Canonical names of recognized sections found, in canonical order."""
        order = (*REQUIRED_SECTIONS, *OPTIONAL_SECTIONS)
        return [name for name in order if name in self.sections]

    @property
    def missing_required(self) -> list[str]:
        """Required canonical sections that were not found."""
        return [name for name in REQUIRED_SECTIONS if name not in self.sections]

    def has_all_required(self) -> bool:
        return not self.missing_required


def parse_issue_body(body: str | None) -> ParsedIssue:
    """Parse an issue body into recognized Markdown sections."""
    parsed = ParsedIssue()
    if not body:
        return parsed

    current: str | None = None
    current_level = 0
    buffer: list[str] = []

    def flush() -> None:
        if current is not None:
            parsed.sections[current] = "\n".join(buffer).strip("\n")

    for line in body.splitlines():
        match = _HEADING_RE.match(line)
        if match:
            level = len(match.group(1))
            canonical = _LOOKUP.get(_normalize(match.group(2)))
            if canonical is not None:
                # A recognized heading always starts a new canonical section.
                flush()
                current = canonical
                current_level = level
                buffer = []
                continue
            # Unrecognized heading deeper than the current section is a nested
            # subheading: preserve it as raw Markdown inside the section.
            if current is not None and level > current_level:
                buffer.append(line)
                continue
            # Otherwise it is a peer/higher heading: it ends recognized content.
            flush()
            current = None
            buffer = []
            continue
        if current is not None:
            buffer.append(line)

    flush()
    return parsed
