"""Phase 5F2D tests: the one shared secret-like redaction backstop.

Phase 5D2 introduced this as a private CLI helper. Phase 5F2D needs the same
treatment for verification output, and extracted the helper rather than writing a
second detector — because two redactors drift, and the one that drifts is the one
that quietly stops catching a shape the other still catches.

So these tests assert two things: the behavior Phase 5D2 shipped is unchanged,
and there is exactly **one** implementation that both call sites use.
"""

from __future__ import annotations

from pathlib import Path

from ai_dev_orchestrator import cli, redaction
from ai_dev_orchestrator.redaction import redact_secret_like_text
from ai_dev_orchestrator.verification import verifier as verifier_module


# -- One implementation --------------------------------------------------------


def test_the_cli_helper_is_the_shared_function_itself_not_a_copy():
    assert cli._redact_secret_like_text is redact_secret_like_text
    assert cli._SECRET_ASSIGNMENT_RE is redaction.SECRET_ASSIGNMENT_RE
    assert cli._BEARER_TOKEN_RE is redaction.BEARER_TOKEN_RE
    assert cli._OPENAI_STYLE_KEY_RE is redaction.OPENAI_STYLE_KEY_RE
    assert cli._REDACTION_PLACEHOLDER == redaction.REDACTION_PLACEHOLDER
    assert cli._API_KEY_PLACEHOLDER == redaction.API_KEY_PLACEHOLDER


def test_the_verifier_uses_the_shared_function_and_defines_no_pattern_of_its_own():
    source = Path(verifier_module.__file__).read_text(encoding="utf-8")

    assert "redact_secret_like_text" in source
    # No second detector: no regex, no placeholder constant, no pattern list.
    assert "re.compile" not in source
    assert "REDACTED" not in source
    assert "\nimport re\n" not in source


def test_the_cli_defines_no_redaction_pattern_of_its_own():
    source = Path(cli.__file__).read_text(encoding="utf-8")

    assert "re.compile" not in source


# -- Unchanged Phase 5D2 behavior ----------------------------------------------


def test_a_quoted_assignment_value_is_redacted_and_the_quotes_are_kept():
    redacted, kinds = redact_secret_like_text('password: "hunter2"\n')

    assert redacted == 'password: "[REDACTED]"\n'
    assert kinds == ["secret_assignment"]


def test_an_unquoted_assignment_value_is_redacted():
    redacted, kinds = redact_secret_like_text("token = plain-value\n")

    assert redacted == "token = [REDACTED]\n"
    assert kinds == ["secret_assignment"]


def test_an_underscore_prefixed_key_still_matches():
    redacted, _ = redact_secret_like_text("MY_API_KEY = abc123\n")

    assert "abc123" not in redacted


def test_a_bearer_token_is_redacted():
    redacted, kinds = redact_secret_like_text("Authorization: Bearer abc.def-ghi\n")

    assert "abc.def-ghi" not in redacted
    assert kinds == ["bearer_token"]


def test_an_openai_style_key_is_redacted():
    redacted, kinds = redact_secret_like_text("key is sk-abcdefghijklmnop here\n")

    assert "sk-abcdefghijklmnop" not in redacted
    assert redacted == "key is [REDACTED_API_KEY] here\n"
    assert kinds == ["openai_style_key"]


def test_an_assignment_of_an_openai_key_is_counted_once_not_twice():
    """Assignment-first ordering, exactly as Phase 5D2 shipped it."""
    _redacted, kinds = redact_secret_like_text("API_KEY=sk-abcdefghijklmnop\n")

    assert kinds == ["secret_assignment"]


def test_ordinary_text_is_returned_untouched():
    text = "def total(items):\n    return sum(items)\n"
    redacted, kinds = redact_secret_like_text(text)

    assert redacted == text
    assert kinds == []


def test_redaction_is_deterministic():
    text = 'api_key = "abc"\nBearer xyz123\nsk-abcdefghijkl\n'

    assert redact_secret_like_text(text) == redact_secret_like_text(text)


def test_there_is_no_way_to_turn_redaction_off():
    """No flag, no keyword argument, no configuration field."""
    import inspect

    signature = inspect.signature(redact_secret_like_text)

    assert list(signature.parameters) == ["text"]
