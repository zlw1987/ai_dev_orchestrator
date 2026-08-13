"""The project's one deterministic secret-like redaction backstop.

Phase 5D2 introduced this as a private helper inside the CLI so that bounded
workspace file contents could not be printed raw. Phase 5F2D needs exactly the
same treatment for a different kind of text — the captured output of a project
verification process — and the choice there was between writing a second
detector and extracting this one.

A second detector would be the worse outcome by a wide margin. Two redactors
drift, and the one that drifts is the one that silently stops catching a shape
the other still catches. So the smallest possible pure function moved here
**unchanged in behavior**, and both call sites use it. Phase 5D2's behavior is
not weakened, narrowed, or made configurable by the move.

What this is, stated plainly so no caller over-trusts it:

    A small, deterministic backstop for three obvious shapes. It is **not**
    reliable secret detection, it has no off switch, and it does not make output
    safe to publish. Callers must say so in their own reports rather than
    claiming redaction guarantees anything.

Bounding is the caller's job and must happen **first**: redacting text that was
already truncated does not make the truncation honest, and Phase 5F2D therefore
bounds output during capture and reports incompleteness explicitly.
"""

from __future__ import annotations

import re

REDACTION_PLACEHOLDER = "[REDACTED]"
API_KEY_PLACEHOLDER = "[REDACTED_API_KEY]"

# The redaction rules are deliberately three simple, deterministic patterns
# rather than an attempt at real secret detection. They catch the shapes that
# show up in config-ish source and in test output often enough to be worth
# catching; they will miss others, and every consumer says so rather than
# claiming to be clean.
#
# Word boundaries are hand-rolled as `(?<![A-Za-z0-9])` / `(?![A-Za-z0-9])`
# instead of `\b` so that an underscore-prefixed name like `MY_API_KEY` still
# matches — `_` is a word character, so `\b` would not fire there.
SECRET_ASSIGNMENT_RE = re.compile(
    r"(?<![A-Za-z0-9])(api[_-]?key|token|secret|password|passwd|pwd)"
    r"(?![A-Za-z0-9])(\s*[:=]\s*)"
    r"(\"[^\"\n]*\"|'[^'\n]*'|[^\s,;]+)",
    re.IGNORECASE,
)

BEARER_TOKEN_RE = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]+=*", re.IGNORECASE)

OPENAI_STYLE_KEY_RE = re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{8,}")


def _replace_assignment_value(match: re.Match) -> str:
    """Redact only the value half of a ``key = value`` pair, keeping any quotes."""
    key, separator, value = match.group(1), match.group(2), match.group(3)
    if len(value) >= 2 and value[0] in "\"'" and value[-1] == value[0]:
        redacted = f"{value[0]}{REDACTION_PLACEHOLDER}{value[0]}"
    else:
        redacted = REDACTION_PLACEHOLDER
    return f"{key}{separator}{redacted}"


def redact_secret_like_text(text: str) -> tuple[str, list[str]]:
    """Blank out obvious secret-like substrings before any text is reported.

    Returns the redacted text and one kind label **per redaction made**, so the
    caller can report both a count and the distinct kinds. Redaction is
    mandatory wherever it is used — there is no configuration option that turns
    it off.

    This is not, and does not claim to be, reliable secret detection. It is a
    small deterministic backstop for the three shapes above, applied
    assignment-first so that a key like ``API_KEY=sk-...`` is counted once
    rather than twice.
    """
    kinds: list[str] = []
    redacted = text
    for kind, pattern, replacement in (
        ("secret_assignment", SECRET_ASSIGNMENT_RE, _replace_assignment_value),
        ("bearer_token", BEARER_TOKEN_RE, f"Bearer {REDACTION_PLACEHOLDER}"),
        ("openai_style_key", OPENAI_STYLE_KEY_RE, API_KEY_PLACEHOLDER),
    ):
        redacted, count = pattern.subn(replacement, redacted)
        kinds.extend([kind] * count)
    return redacted, kinds
