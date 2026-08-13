"""**Strict** single-file unified diff application (Phase 5F2C) — no fuzz.

This is the smallest deterministic diff applier that Phase 5F2C's writer needs,
and deliberately nothing more. It transforms one already-validated ``modify``
diff over one in-memory list of lines and returns another list of lines.

**No external patch engine is invoked.** ``patch``, ``git apply``, ``patch-ng``,
``unidiff`` and every other fuzzy applier are absent by design, because their
whole value proposition — finding a place where a hunk *nearly* fits — is the
one behavior this project must not have. A writer whose input is "these exact
bytes become those exact bytes" cannot be allowed to apply a hunk somewhere the
human did not read.

So the rules are, without exception:

- The file headers must already name the declared path exactly
  (``--- a/<path>`` then ``+++ b/<path>``), on consecutive lines.
- A hunk header must be exactly ``@@ -a,b +c,d @@`` (or the ``,1``-elided GNU
  short forms). There is no trailing section heading, because nothing this
  project generates emits one.
- **Hunk locations are exact.** ``old_start`` is where the hunk applies, not
  where the search begins. There is no offset search, no fuzz factor, no
  nearest-match, no three-way merge, and no reordering.
- **Every context line and every deleted line must match the original
  exactly** — byte for byte after decoding, with no whitespace tolerance and no
  line-ending normalization.
- Hunks must appear in strictly increasing, non-overlapping order.
- The declared line counts must equal what the hunk body actually contains, and
  the declared ``new_start`` must equal the position the output has actually
  reached. A header that disagrees with its own body is malformed, not a hint.
- Anything malformed, overlapping, inconsistent, or unrecognized **fails
  closed**. Nothing is repaired, guessed, skipped, or partially applied.

The result is deterministic: the same original and the same diff always produce
the same output, or the same error.

This module opens no file, touches no workspace, runs no subprocess, calls no
model, reads no environment variable, and writes nothing. It is handed strings
and returns strings — proving the output is *correct* is the writer's job, and
it does so by hashing the result and comparing it against the digest the human
approved.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# A unified diff hunk header, and only this shape. The counts are optional
# because the GNU short form elides ``,1``; everything after the closing ``@@``
# is refused, since nothing in this project emits a section heading and a header
# this applier cannot fully account for is a header it must not act on.
_HUNK_HEADER_RE = re.compile(
    r"^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))? "
    r"\+(?P<new_start>\d+)(?:,(?P<new_count>\d+))? @@$"
)


class StrictDiffApplyError(Exception):
    """A diff could not be applied exactly, so it was not applied at all.

    Messages name the *category* of failure and, where it helps, the hunk
    ordinal and the line number. They never echo a context line, a deleted line,
    an added line, or any other file content: a mismatch is reported by
    position, never by quoting the bytes that did not match.

    There is deliberately no "applied with fuzz", no "applied with offset", and
    no partially-applied result in this module. Either the transformation was
    exact or this exception was raised.
    """


@dataclass(frozen=True)
class _Hunk:
    """One parsed hunk: its declared header numbers and its body lines."""

    ordinal: int
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    body: tuple[str, ...]


def _parse_hunks(unified_diff: str, path: str) -> tuple[_Hunk, ...]:
    """Split a validated single-file diff into hunks, or refuse.

    The headers are re-checked here rather than assumed from the Phase 5E2
    model, for the same reason every other invariant in this project is
    re-established at the boundary that depends on it: pydantic does not
    re-validate an instance it is handed, and this function is the last thing
    between an artifact and a real file's bytes.
    """
    lines = unified_diff.split("\n")

    expected_old = f"--- a/{path}"
    expected_new = f"+++ b/{path}"

    if len(lines) < 3:
        raise StrictDiffApplyError(
            "diff error: the unified diff is too short to contain file headers "
            "and a hunk."
        )
    if lines[0] != expected_old or lines[1] != expected_new:
        raise StrictDiffApplyError(
            "diff error: the unified diff's first two lines must be exactly "
            "'--- a/<path>' and '+++ b/<path>' naming the approved path. The "
            "diff was not applied."
        )

    hunks: list[_Hunk] = []
    index = 2
    ordinal = 0
    while index < len(lines):
        line = lines[index]
        if line == "" and index == len(lines) - 1:
            # The single trailing empty element produced by a diff string that
            # ends in a newline. Not a body line, and not an error.
            break
        match = _HUNK_HEADER_RE.match(line)
        if match is None:
            raise StrictDiffApplyError(
                f"diff error: line {index + 1} of the unified diff is neither a "
                "well-formed '@@ -a,b +c,d @@' hunk header nor part of a hunk "
                "body. The diff was not applied."
            )
        ordinal += 1
        old_count = (
            1 if match.group("old_count") is None else int(match.group("old_count"))
        )
        new_count = (
            1 if match.group("new_count") is None else int(match.group("new_count"))
        )

        index += 1
        body: list[str] = []
        while index < len(lines):
            candidate = lines[index]
            if candidate.startswith("@@"):
                break
            if candidate == "" and index == len(lines) - 1:
                # Trailing element again; a body line always carries a prefix
                # character, so an empty string here is the string split and
                # never a diff line.
                index += 1
                break
            if not candidate or candidate[0] not in (" ", "+", "-"):
                raise StrictDiffApplyError(
                    f"diff error: line {index + 1} of the unified diff is inside "
                    "hunk "
                    f"{ordinal} but does not begin with ' ', '+' or '-'. The "
                    "diff was not applied."
                )
            body.append(candidate)
            index += 1

        hunks.append(
            _Hunk(
                ordinal=ordinal,
                old_start=int(match.group("old_start")),
                old_count=old_count,
                new_start=int(match.group("new_start")),
                new_count=new_count,
                body=tuple(body),
            )
        )

    if not hunks:
        raise StrictDiffApplyError(
            "diff error: the unified diff contains no hunk. The diff was not "
            "applied."
        )
    return tuple(hunks)


def _check_hunk_body_matches_its_header(hunk: _Hunk) -> None:
    """Refuse a hunk whose declared counts disagree with its own body."""
    context = sum(1 for line in hunk.body if line[0] == " ")
    removed = sum(1 for line in hunk.body if line[0] == "-")
    added = sum(1 for line in hunk.body if line[0] == "+")

    if context + removed != hunk.old_count:
        raise StrictDiffApplyError(
            f"diff error: hunk {hunk.ordinal} declares {hunk.old_count} original "
            f"lines but its body accounts for {context + removed}. A header that "
            "disagrees with its own body is malformed, not a hint; the diff was "
            "not applied."
        )
    if context + added != hunk.new_count:
        raise StrictDiffApplyError(
            f"diff error: hunk {hunk.ordinal} declares {hunk.new_count} resulting "
            f"lines but its body accounts for {context + added}. The diff was not "
            "applied."
        )


def apply_strict_unified_diff(
    *, original_lines: list[str], unified_diff: str, path: str
) -> list[str]:
    """Apply one validated ``modify`` diff to one list of lines, exactly.

    Args:
        original_lines: The original file's content lines, **without** line
            terminators. Splitting the file into these and rejoining the result
            is the caller's job, because only the caller knows which line-ending
            convention the file uses and must preserve.
        unified_diff: The approved diff text. Must be exactly one single-file
            diff whose headers name ``path``.
        path: The approved relative path, used to verify the headers.

    Returns:
        A new list of lines, again without terminators. The input list is never
        mutated.

    Raises:
        StrictDiffApplyError: malformed headers, a malformed or unparseable hunk
            header, a body line without a prefix character, declared counts that
            disagree with the body, hunks out of order or overlapping, a hunk
            positioned past the end of the file, or **any** context or deleted
            line that does not match the original exactly. Nothing partial is
            returned.
    """
    hunks = _parse_hunks(unified_diff, path)

    output: list[str] = []
    cursor = 0  # 0-based index of the next unconsumed original line.

    for hunk in hunks:
        _check_hunk_body_matches_its_header(hunk)

        # Where this hunk applies, exactly. For a pure insertion the unified
        # format writes ``-N,0`` meaning "after original line N", so the
        # insertion point is index N; otherwise ``-N`` is 1-based and the index
        # is N - 1.
        if hunk.old_count == 0:
            start = hunk.old_start
        else:
            if hunk.old_start < 1:
                raise StrictDiffApplyError(
                    f"diff error: hunk {hunk.ordinal} declares original start "
                    f"{hunk.old_start}, which is not a 1-based line number. The "
                    "diff was not applied."
                )
            start = hunk.old_start - 1

        if start < cursor:
            raise StrictDiffApplyError(
                f"diff error: hunk {hunk.ordinal} starts at original line "
                f"{hunk.old_start}, at or before the end of a previous hunk. "
                "Overlapping or out-of-order hunks are refused, not reordered; "
                "the diff was not applied."
            )
        if start > len(original_lines):
            raise StrictDiffApplyError(
                f"diff error: hunk {hunk.ordinal} starts at original line "
                f"{hunk.old_start}, past the end of a file with "
                f"{len(original_lines)} lines. There is no offset search and no "
                "fuzz; the diff was not applied."
            )

        # Everything between the previous hunk and this one is carried through
        # untouched.
        output.extend(original_lines[cursor:start])
        cursor = start

        # The resulting line number this hunk claims to start at must be where
        # the output has actually reached. A diff whose two sides disagree about
        # position is refused rather than trusted on one side.
        expected_new_start = len(output) + 1 if hunk.new_count else len(output)
        if hunk.new_start != expected_new_start:
            raise StrictDiffApplyError(
                f"diff error: hunk {hunk.ordinal} declares resulting start "
                f"{hunk.new_start} but the applied output has reached "
                f"{expected_new_start}. The diff was not applied."
            )

        for offset, line in enumerate(hunk.body):
            marker, text = line[0], line[1:]
            if marker == "+":
                output.append(text)
                continue
            if cursor >= len(original_lines):
                raise StrictDiffApplyError(
                    f"diff error: hunk {hunk.ordinal} expects original line "
                    f"{cursor + 1}, past the end of a file with "
                    f"{len(original_lines)} lines. The diff was not applied."
                )
            if original_lines[cursor] != text:
                kind = "context" if marker == " " else "deleted"
                raise StrictDiffApplyError(
                    f"diff error: hunk {hunk.ordinal} body line {offset + 1} is a "
                    f"{kind} line that does not match original line "
                    f"{cursor + 1} exactly. Application is exact — there is no "
                    "fuzz, no offset search, and no whitespace tolerance — so "
                    "the diff was not applied. The mismatched text is not "
                    "echoed."
                )
            if marker == " ":
                output.append(text)
            cursor += 1

    output.extend(original_lines[cursor:])
    return output
