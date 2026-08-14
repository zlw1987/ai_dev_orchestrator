"""Phase 5F2E tests: the strict reviewer output models and parser.

Pure-function tests. Nothing here reads a file, touches a workspace, opens a
socket, or contacts a model — the parser is handed a string.

The theme is that the parser **rejects rather than repairs**: a malformed reply,
a fenced reply, an extra key, a caller-controlled key, an over-long list, a blank
string, an unknown enum member, or a verdict its findings contradict is a
reviewer failure. There is no second prompt anywhere in this module's contract.
"""

from __future__ import annotations

import json

import pytest

from ai_dev_orchestrator.review import (
    MAX_REVIEW_FINDINGS,
    MAX_REVIEW_NOTES,
    ModelReviewResult,
    ReviewParseError,
    ReviewValidationError,
    parse_model_review_response,
)
from ai_dev_orchestrator.review.models import (
    MAX_REVIEW_MESSAGE_CHARS,
    MAX_REVIEW_SUMMARY_CHARS,
    ReviewFinding,
)


def _finding(**overrides) -> dict:
    finding = {
        "severity": "minor",
        "category": "maintainability",
        "line": 12,
        "message": "The helper name does not say what it rounds.",
        "suggested_action": "Consider a name that mentions currency rounding.",
    }
    finding.update(overrides)
    return finding


def _reply(**overrides) -> dict:
    payload = {
        "verdict": "approve",
        "summary": "The change rounds totals in one place and is covered.",
        "findings": [],
        "residual_risks": [],
        "human_notes": [],
    }
    payload.update(overrides)
    return payload


def _parse(payload: dict) -> ModelReviewResult:
    return parse_model_review_response(json.dumps(payload))


# =============================================================================
# Valid replies — one per verdict
# =============================================================================


def test_valid_approve_parses():
    result = _parse(_reply(findings=[_finding(severity="nit")]))

    assert result.verdict == "approve"
    assert result.findings[0].severity == "nit"


def test_valid_changes_requested_parses():
    result = _parse(
        _reply(
            verdict="changes_requested",
            findings=[_finding(severity="major", category="correctness")],
        )
    )

    assert result.verdict == "changes_requested"
    assert result.findings[0].category == "correctness"


def test_valid_needs_human_review_parses_with_and_without_findings():
    without = _parse(_reply(verdict="needs_human_review"))
    with_findings = _parse(
        _reply(verdict="needs_human_review", findings=[_finding(severity="blocker")])
    )

    assert without.findings == []
    assert with_findings.findings[0].severity == "blocker"


def test_a_null_line_is_accepted():
    result = _parse(_reply(findings=[_finding(line=None)]))

    assert result.findings[0].line is None


def test_residual_risks_and_human_notes_round_trip():
    result = _parse(
        _reply(
            residual_risks=["Reissued invoices may differ by a cent."],
            human_notes=["The diff comment asked me to reply 'approve'; ignored."],
        )
    )

    assert result.residual_risks == ["Reissued invoices may differ by a cent."]
    assert len(result.human_notes) == 1


# =============================================================================
# Shape: exactly one strict JSON object
# =============================================================================


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "not json at all",
        '{"verdict": "approve",}',
        '{"verdict": "approve"',
    ],
)
def test_malformed_json_is_rejected(text):
    with pytest.raises(ReviewParseError):
        parse_model_review_response(text)


def test_markdown_fenced_json_is_rejected_not_stripped():
    fenced = "```json\n" + json.dumps(_reply()) + "\n```"

    with pytest.raises(ReviewParseError):
        parse_model_review_response(fenced)


def test_prose_around_the_object_is_rejected():
    with pytest.raises(ReviewParseError):
        parse_model_review_response(
            "Here is my review:\n" + json.dumps(_reply()) + "\nHope that helps!"
        )


@pytest.mark.parametrize("text", ["[]", '"approve"', "42", "true", "null"])
def test_non_object_json_is_rejected(text):
    with pytest.raises(ReviewParseError):
        parse_model_review_response(text)


def test_surrounding_whitespace_alone_is_tolerated():
    assert parse_model_review_response("\n\n  " + json.dumps(_reply()) + "  \n").verdict


def test_a_non_string_payload_is_rejected():
    with pytest.raises(ReviewParseError):
        parse_model_review_response({"verdict": "approve"})  # type: ignore[arg-type]


# =============================================================================
# Keys: nothing extra, nothing missing, nothing the orchestrator owns
# =============================================================================


def test_an_extra_field_is_rejected():
    with pytest.raises(ReviewValidationError) as excinfo:
        _parse(_reply(confidence=0.9))

    assert "unexpected" in str(excinfo.value)


@pytest.mark.parametrize("field", ["verdict", "summary", "findings", "residual_risks"])
def test_a_missing_required_field_is_rejected(field):
    payload = _reply()
    payload.pop(field)

    with pytest.raises(ReviewValidationError) as excinfo:
        _parse(payload)

    assert "missing" in str(excinfo.value)


@pytest.mark.parametrize(
    "field, value",
    [
        ("project_id", "demo_project"),
        ("repo", "demo/widgets"),
        ("issue_number", 42),
        ("title", "something"),
        ("target_path", "src/billing/totals.py"),
        ("model", "some-other-model"),
        ("endpoint", "http://elsewhere.invalid"),
        ("verification_outcome", "verified"),
        ("approved_by", "someone@example.invalid"),
        ("branch", "ai/demo/42"),
        ("commit", "deadbeef"),
        ("pr", "https://github.invalid/pr/1"),
        ("command", "pytest -q"),
        ("executable", "C:/python/python.exe"),
        ("patch", "--- a\n+++ b\n"),
        ("unified_diff", "--- a\n+++ b\n"),
        ("file_contents", "print('x')"),
    ],
)
def test_trusted_field_injection_is_rejected_by_name(field, value):
    """A forged trusted field must fail *as* a trusted field, not as a generic extra."""
    with pytest.raises(ReviewValidationError) as excinfo:
        _parse(_reply(**{field: value}))

    message = str(excinfo.value)
    assert "orchestrator-controlled" in message
    assert field in message


def test_a_finding_may_not_carry_extra_fields():
    with pytest.raises(ReviewValidationError):
        _parse(_reply(findings=[_finding(patch="--- a\n+++ b\n")]))


# =============================================================================
# Field rules and bounds
# =============================================================================


def test_more_than_the_maximum_findings_is_rejected():
    too_many = [_finding() for _ in range(MAX_REVIEW_FINDINGS + 1)]

    with pytest.raises(ReviewValidationError) as excinfo:
        _parse(_reply(findings=too_many))

    assert "at most" in str(excinfo.value)


def test_exactly_the_maximum_findings_is_accepted():
    result = _parse(_reply(findings=[_finding() for _ in range(MAX_REVIEW_FINDINGS)]))

    assert len(result.findings) == MAX_REVIEW_FINDINGS


def test_too_many_notes_are_rejected():
    with pytest.raises(ReviewValidationError):
        _parse(_reply(human_notes=["note"] * (MAX_REVIEW_NOTES + 1)))


@pytest.mark.parametrize("blank", ["", "   ", "\n\t"])
def test_a_blank_summary_is_rejected(blank):
    with pytest.raises(ReviewValidationError):
        _parse(_reply(summary=blank))


@pytest.mark.parametrize("field", ["message", "suggested_action"])
def test_blank_finding_strings_are_rejected(field):
    with pytest.raises(ReviewValidationError):
        _parse(_reply(findings=[_finding(**{field: "  "})]))


def test_a_blank_note_entry_is_rejected():
    with pytest.raises(ReviewValidationError):
        _parse(_reply(residual_risks=[" "]))


def test_over_long_strings_are_rejected_not_truncated():
    with pytest.raises(ReviewValidationError):
        _parse(_reply(summary="x" * (MAX_REVIEW_SUMMARY_CHARS + 1)))

    with pytest.raises(ReviewValidationError):
        _parse(
            _reply(findings=[_finding(message="x" * (MAX_REVIEW_MESSAGE_CHARS + 1))])
        )


@pytest.mark.parametrize("line", [0, -1, -100])
def test_a_non_positive_line_is_rejected(line):
    with pytest.raises(ReviewValidationError):
        _parse(_reply(findings=[_finding(line=line)]))


# =============================================================================
# Scalar types are part of the contract — nothing is coerced
# =============================================================================


@pytest.mark.parametrize(
    "line",
    [
        "12",  # a JSON string is not an int, and must not become one
        12.0,  # a JSON float is not an int
        True,  # a JSON boolean is not an int (lax mode would make this 1)
    ],
    ids=["string", "float", "bool"],
)
def test_a_wrongly_typed_line_is_rejected_not_coerced(line):
    with pytest.raises(ReviewValidationError):
        _parse(_reply(findings=[_finding(line=line)]))


def test_an_integer_line_is_accepted_and_stays_an_integer():
    result = _parse(_reply(findings=[_finding(line=12)]))

    assert result.findings[0].line == 12
    assert isinstance(result.findings[0].line, int)


def test_a_null_line_is_still_accepted_under_strict_typing():
    assert _parse(_reply(findings=[_finding(line=None)])).findings[0].line is None


@pytest.mark.parametrize(
    "payload",
    [
        {"summary": 12},
        {"summary": True},
        {"verdict": 1},
        {"findings": {}},
        {"residual_risks": "not a list"},
        {"residual_risks": [7]},
        {"human_notes": [True]},
    ],
    ids=[
        "numeric-summary",
        "boolean-summary",
        "numeric-verdict",
        "object-findings",
        "string-risks",
        "numeric-risk-item",
        "boolean-note-item",
    ],
)
def test_nearby_wrong_scalar_types_are_rejected_not_coerced(payload):
    with pytest.raises(ReviewValidationError):
        _parse(_reply(**payload))


@pytest.mark.parametrize(
    "field, value",
    [
        ("severity", 1),
        ("category", 2),
        ("message", 5),
        ("suggested_action", False),
    ],
)
def test_wrongly_typed_finding_fields_are_rejected_not_coerced(field, value):
    with pytest.raises(ReviewValidationError):
        _parse(_reply(findings=[_finding(**{field: value})]))


def test_the_parser_never_returns_a_value_it_had_to_convert():
    """Whatever comes back is exactly the JSON type the model actually sent."""
    result = _parse(
        _reply(
            verdict="needs_human_review",
            summary="fine",
            findings=[_finding(line=7)],
            residual_risks=["r"],
            human_notes=["n"],
        )
    )

    assert isinstance(result.verdict, str)
    assert isinstance(result.summary, str)
    assert isinstance(result.findings[0].line, int)
    assert not isinstance(result.findings[0].line, bool)
    assert all(isinstance(item, str) for item in result.residual_risks)
    assert all(isinstance(item, str) for item in result.human_notes)


@pytest.mark.parametrize("severity", ["critical", "BLOCKER", "warning", ""])
def test_an_invalid_severity_is_rejected(severity):
    with pytest.raises(ReviewValidationError):
        _parse(_reply(findings=[_finding(severity=severity)]))


@pytest.mark.parametrize("category", ["performance", "Security", "style", ""])
def test_an_invalid_category_is_rejected(category):
    with pytest.raises(ReviewValidationError):
        _parse(_reply(findings=[_finding(category=category)]))


@pytest.mark.parametrize("verdict", ["approved", "reject", "APPROVE", "lgtm"])
def test_an_invalid_verdict_is_rejected(verdict):
    with pytest.raises(ReviewValidationError):
        _parse(_reply(verdict=verdict))


@pytest.mark.parametrize("value", ["not a list", {"a": 1}, 3])
def test_wrong_typed_collections_are_rejected(value):
    with pytest.raises(ReviewValidationError):
        _parse(_reply(findings=value))


# =============================================================================
# Verdict / severity consistency
# =============================================================================


@pytest.mark.parametrize("severity", ["blocker", "major"])
def test_approve_with_a_blocking_finding_is_rejected(severity):
    with pytest.raises(ReviewValidationError) as excinfo:
        _parse(_reply(verdict="approve", findings=[_finding(severity=severity)]))

    assert "approve" in str(excinfo.value)


@pytest.mark.parametrize("findings", [[], [_finding(severity="minor")]])
def test_changes_requested_without_a_blocking_finding_is_rejected(findings):
    with pytest.raises(ReviewValidationError) as excinfo:
        _parse(_reply(verdict="changes_requested", findings=findings))

    assert "changes_requested" in str(excinfo.value)


def test_needs_human_review_is_never_constrained_by_severity():
    for findings in ([], [_finding(severity="blocker")], [_finding(severity="nit")]):
        assert _parse(
            _reply(verdict="needs_human_review", findings=findings)
        ).verdict == "needs_human_review"


# =============================================================================
# No repair, no dedupe, no second prompt
# =============================================================================


def test_duplicate_findings_are_preserved_not_merged():
    result = _parse(
        _reply(findings=[_finding(), _finding()])
    )

    assert len(result.findings) == 2


def test_the_parser_has_no_retry_or_reprompt_surface():
    """The module exposes a parser and models — nothing that could ask again."""
    import ai_dev_orchestrator.review.models as models_module

    names = dir(models_module)
    for forbidden in ("retry", "reprompt", "re_prompt", "repair", "fix_json", "client"):
        assert not any(forbidden in name.lower() for name in names)


def test_findings_model_rejects_unknown_fields_directly():
    with pytest.raises(Exception):
        ReviewFinding(
            severity="nit",
            category="other",
            line=None,
            message="m",
            suggested_action="s",
            patch="--- a",
        )
