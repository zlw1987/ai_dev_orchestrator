"""Phase 2 tests: issue body parser."""

from ai_dev_orchestrator.github.issue_parser import (
    REQUIRED_SECTIONS,
    parse_issue_body,
)

FULL_BODY = """\
Some preamble text that is not a section.

## Goal
Build the issue reader.

## Current Context
Phase 1 is done.

## Scope
- client
- parser

## Non-goals
No writes.

## Acceptance Criteria
- [ ] tests pass

## Required Verification
Run pytest.

## AI Instructions
Be careful.

## Automation Authorization
L1
"""


def test_extracts_known_sections():
    parsed = parse_issue_body(FULL_BODY)
    assert "Goal" in parsed.sections
    assert "Scope" in parsed.sections
    assert "Automation Authorization" in parsed.sections
    assert parsed.has_all_required() is True
    assert parsed.missing_required == []
    # All eight canonical sections present.
    assert len(parsed.present_sections) == 8


def test_preserves_section_markdown():
    parsed = parse_issue_body(FULL_BODY)
    assert parsed.sections["Scope"] == "- client\n- parser"
    assert parsed.sections["Goal"] == "Build the issue reader."


def test_case_insensitive_and_extra_whitespace():
    body = "##   gOaL  \nhi\n###  SCOPE\nx\n## non goals\nnone\n"
    parsed = parse_issue_body(body)
    assert "Goal" in parsed.sections
    assert "Scope" in parsed.sections
    # 'non goals' (space instead of hyphen) maps to canonical 'Non-goals'.
    assert "Non-goals" in parsed.sections


def test_reports_missing_required_sections():
    body = "## Goal\nonly a goal here\n"
    parsed = parse_issue_body(body)
    assert parsed.has_all_required() is False
    missing = set(parsed.missing_required)
    assert missing == set(REQUIRED_SECTIONS) - {"Goal"}


def test_empty_or_none_body_reports_all_required_missing():
    for body in (None, "", "   "):
        parsed = parse_issue_body(body)
        assert parsed.present_sections == []
        assert set(parsed.missing_required) == set(REQUIRED_SECTIONS)


def test_unrecognized_heading_ignored():
    body = "## Goal\nkeep\n## Random Heading\ndropped\n## Scope\nkept\n"
    parsed = parse_issue_body(body)
    assert parsed.sections["Goal"] == "keep"
    assert parsed.sections["Scope"] == "kept"
    assert "Random Heading" not in parsed.sections


def test_nested_subheadings_preserved_in_section():
    body = (
        "## Scope\n"
        "Intro\n"
        "### Allowed files\n"
        "- README.md\n"
        "### Forbidden files\n"
        "- secrets\n"
        "\n"
        "## Non-goals\n"
        "No writes\n"
        "\n"
        "## Goal\n"
        "Do it\n"
        "\n"
        "## Acceptance Criteria\n"
        "- passes\n"
        "\n"
        "## Required Verification\n"
        "- pytest\n"
    )
    parsed = parse_issue_body(body)

    scope = parsed.sections["Scope"]
    assert "Intro" in scope
    assert "### Allowed files" in scope
    assert "- README.md" in scope
    assert "### Forbidden files" in scope
    assert "- secrets" in scope

    # The next recognized heading still starts a new section.
    assert parsed.sections["Non-goals"] == "No writes"
    assert parsed.has_all_required() is True


def test_peer_level_unrecognized_heading_not_appended():
    body = (
        "## Scope\n"
        "In scope\n"
        "## Notes\n"
        "Should not be appended to Scope\n"
        "## Non-goals\n"
        "No writes\n"
    )
    parsed = parse_issue_body(body)
    assert parsed.sections["Scope"] == "In scope"
    assert "Notes" not in parsed.sections
    assert "Should not be appended" not in parsed.sections["Scope"]
    assert parsed.sections["Non-goals"] == "No writes"
