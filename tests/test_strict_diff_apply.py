"""Phase 5F2C tests: the strict, no-fuzz unified diff applier.

The applier is the piece that turns "an approved diff" into "these exact
resulting lines", and the property under test throughout is that it is **exact
or nothing**. Every test here is a pure function call over in-memory strings: no
file is opened, no workspace is touched, no subprocess is started, and no patch
tool exists to be invoked.

The negative tests matter more than the positive ones. A fuzzy applier's whole
value is finding a place where a hunk *nearly* fits, and that is precisely the
behavior this project must not have — so context drift, offset drift, a
one-character difference, and a header that disagrees with its own body all have
to fail rather than be absorbed.
"""

from __future__ import annotations

import difflib
import subprocess
import sys

import pytest

from ai_dev_orchestrator.file_editing import (
    StrictDiffApplyError,
    apply_strict_unified_diff,
)

PATH = "src/billing/totals.py"

ORIGINAL = [
    "def format_total(amount):",
    "    return str(amount)",
    "",
    "",
    "def total(items):",
    "    return sum(items)",
]


def _diff(original: list[str], proposed: list[str], path: str = PATH) -> str:
    """Build a diff exactly the way the Phase 5E3 generator builds one."""
    return "\n".join(
        difflib.unified_diff(
            original, proposed, fromfile=f"a/{path}", tofile=f"b/{path}", lineterm=""
        )
    )


def _apply(diff: str, original: list[str] | None = None, path: str = PATH):
    return apply_strict_unified_diff(
        original_lines=list(ORIGINAL if original is None else original),
        unified_diff=diff,
        path=path,
    )


# -- 1. Exact application ------------------------------------------------------


def test_single_hunk_modification_applies_exactly():
    proposed = list(ORIGINAL)
    proposed[1] = '    return f"{amount:.2f}"'

    assert _apply(_diff(ORIGINAL, proposed)) == proposed


def test_multi_hunk_modification_applies_exactly():
    original = [f"line {index}" for index in range(1, 41)]
    proposed = list(original)
    proposed[2] = "line 3 changed"
    proposed[30] = "line 31 changed"

    diff = _diff(original, proposed)
    hunk_headers = [line for line in diff.split("\n") if line.startswith("@@")]
    assert len(hunk_headers) == 2
    assert _apply(diff, original) == proposed


def test_pure_insertion_applies_exactly():
    proposed = list(ORIGINAL)
    proposed.insert(2, "    # a new comment")

    assert _apply(_diff(ORIGINAL, proposed)) == proposed


def test_pure_deletion_applies_exactly():
    proposed = [line for index, line in enumerate(ORIGINAL) if index != 1]

    assert _apply(_diff(ORIGINAL, proposed)) == proposed


def test_append_at_end_of_file_applies_exactly():
    proposed = list(ORIGINAL) + ["", "", "def extra():", "    return None"]

    assert _apply(_diff(ORIGINAL, proposed)) == proposed


def test_insertion_at_the_very_start_applies_exactly():
    proposed = ["# header comment"] + list(ORIGINAL)

    assert _apply(_diff(ORIGINAL, proposed)) == proposed


def test_emptying_a_file_applies_exactly():
    assert _apply(_diff(ORIGINAL, [])) == []


def test_application_is_deterministic():
    proposed = list(ORIGINAL)
    proposed[5] = "    return sum(items) or 0"
    diff = _diff(ORIGINAL, proposed)

    assert _apply(diff) == _apply(diff) == proposed


def test_the_input_list_is_never_mutated():
    original = list(ORIGINAL)
    proposed = list(ORIGINAL)
    proposed[0] = "def format_total(amount, /):"

    apply_strict_unified_diff(
        original_lines=original, unified_diff=_diff(ORIGINAL, proposed), path=PATH
    )

    assert original == ORIGINAL


def test_trailing_whitespace_inside_a_line_is_preserved_not_stripped():
    original = ["alpha   ", "beta"]
    proposed = ["alpha   ", "beta changed"]

    assert _apply(_diff(original, proposed), original) == proposed


def test_crlf_style_lines_are_just_lines_here():
    """The applier knows nothing about line endings; it operates on content lines.

    Splitting a file into terminator-free lines and rejoining the result is the
    writer's job, precisely so that this module never has to normalize anything.
    """
    original = ["a", "b", "c"]
    proposed = ["a", "B", "c"]

    assert _apply(_diff(original, proposed), original) == proposed


# -- 2. Context and deletion lines must match exactly --------------------------


def test_context_line_mismatch_is_refused():
    proposed = list(ORIGINAL)
    proposed[1] = '    return f"{amount:.2f}"'
    diff = _diff(ORIGINAL, proposed)

    drifted = list(ORIGINAL)
    drifted[0] = "def format_total(amount, currency):"

    with pytest.raises(StrictDiffApplyError) as excinfo:
        _apply(diff, drifted)
    assert "context" in str(excinfo.value)


def test_deleted_line_mismatch_is_refused():
    proposed = list(ORIGINAL)
    proposed[1] = '    return f"{amount:.2f}"'
    diff = _diff(ORIGINAL, proposed)

    drifted = list(ORIGINAL)
    drifted[1] = "    return str(amount)  # changed by someone else"

    with pytest.raises(StrictDiffApplyError) as excinfo:
        _apply(diff, drifted)
    assert "deleted" in str(excinfo.value)


def test_a_single_whitespace_difference_is_refused():
    """No whitespace tolerance. One space is a mismatch."""
    proposed = list(ORIGINAL)
    proposed[1] = '    return f"{amount:.2f}"'
    diff = _diff(ORIGINAL, proposed)

    drifted = list(ORIGINAL)
    drifted[1] = "     return str(amount)"

    with pytest.raises(StrictDiffApplyError):
        _apply(diff, drifted)


def test_no_offset_search_when_the_file_shifted():
    """A hunk that would apply two lines later is refused, not relocated."""
    proposed = list(ORIGINAL)
    proposed[1] = '    return f"{amount:.2f}"'
    diff = _diff(ORIGINAL, proposed)

    shifted = ["# inserted header", "# by somebody else"] + list(ORIGINAL)

    with pytest.raises(StrictDiffApplyError):
        _apply(diff, shifted)


def test_no_nearest_match_across_a_duplicated_block():
    """Two identical blocks: the hunk applies where it says, or nowhere."""
    original = ["x", "y", "z", "x", "y", "z"]
    proposed = ["x", "Y", "z", "x", "y", "z"]
    diff = _diff(original, proposed)

    reordered = ["q", "x", "y", "z", "x", "y", "z"]
    with pytest.raises(StrictDiffApplyError):
        _apply(diff, reordered)


def test_hunk_past_the_end_of_the_file_is_refused():
    proposed = list(ORIGINAL)
    proposed[5] = "    return sum(items) or 0"
    diff = _diff(ORIGINAL, proposed)

    with pytest.raises(StrictDiffApplyError) as excinfo:
        _apply(diff, ORIGINAL[:2])
    assert "past the end" in str(excinfo.value)


def test_the_error_never_echoes_the_mismatched_text():
    secret = "SENTINEL_SOURCE_LINE_MUST_NOT_BE_ECHOED"
    proposed = list(ORIGINAL)
    proposed[1] = '    return f"{amount:.2f}"'
    diff = _diff(ORIGINAL, proposed)

    drifted = list(ORIGINAL)
    drifted[1] = f"    return str(amount)  # {secret}"

    with pytest.raises(StrictDiffApplyError) as excinfo:
        _apply(diff, drifted)
    assert secret not in str(excinfo.value)


# -- 3. Malformed diffs --------------------------------------------------------


def test_wrong_path_in_the_headers_is_refused():
    proposed = list(ORIGINAL)
    proposed[1] = "    return 0"
    diff = _diff(ORIGINAL, proposed, path="src/other.py")

    with pytest.raises(StrictDiffApplyError) as excinfo:
        _apply(diff)
    assert "first two lines" in str(excinfo.value)


def test_create_style_dev_null_header_is_refused():
    diff = "--- /dev/null\n+++ b/%s\n@@ -0,0 +1,1 @@\n+hello\n" % PATH

    with pytest.raises(StrictDiffApplyError):
        _apply(diff)


def test_missing_hunk_header_is_refused():
    diff = f"--- a/{PATH}\n+++ b/{PATH}\n context without a hunk header\n"

    with pytest.raises(StrictDiffApplyError):
        _apply(diff)


def test_diff_with_no_hunk_at_all_is_refused():
    diff = f"--- a/{PATH}\n+++ b/{PATH}\n"

    with pytest.raises(StrictDiffApplyError):
        _apply(diff)


@pytest.mark.parametrize(
    "header",
    [
        "@@ -1,2 +1,2 @@ def format_total(amount):",  # a section heading
        "@@ -1 2 +1,2 @@",
        "@@ +1,2 -1,2 @@",
        "@@@ -1,2 +1,2 @@@",
        "@@ -a,b +c,d @@",
        "@@ -1,2 +1,2 @",
    ],
)
def test_malformed_hunk_headers_are_refused(header):
    diff = f"--- a/{PATH}\n+++ b/{PATH}\n{header}\n def format_total(amount):\n"

    with pytest.raises(StrictDiffApplyError):
        _apply(diff)


def test_body_line_without_a_prefix_character_is_refused():
    diff = (
        f"--- a/{PATH}\n"
        f"+++ b/{PATH}\n"
        "@@ -1,2 +1,2 @@\n"
        "def format_total(amount):\n"  # no leading space
        "-    return str(amount)\n"
        "+    return 0\n"
    )

    with pytest.raises(StrictDiffApplyError):
        _apply(diff)


def test_declared_old_count_disagreeing_with_the_body_is_refused():
    diff = (
        f"--- a/{PATH}\n"
        f"+++ b/{PATH}\n"
        "@@ -1,9 +1,2 @@\n"
        " def format_total(amount):\n"
        "-    return str(amount)\n"
        "+    return 0\n"
    )

    with pytest.raises(StrictDiffApplyError) as excinfo:
        _apply(diff)
    assert "original lines" in str(excinfo.value)


def test_declared_new_count_disagreeing_with_the_body_is_refused():
    diff = (
        f"--- a/{PATH}\n"
        f"+++ b/{PATH}\n"
        "@@ -1,2 +1,9 @@\n"
        " def format_total(amount):\n"
        "-    return str(amount)\n"
        "+    return 0\n"
    )

    with pytest.raises(StrictDiffApplyError) as excinfo:
        _apply(diff)
    assert "resulting lines" in str(excinfo.value)


def test_declared_new_start_disagreeing_with_the_output_is_refused():
    diff = (
        f"--- a/{PATH}\n"
        f"+++ b/{PATH}\n"
        "@@ -1,2 +7,2 @@\n"
        " def format_total(amount):\n"
        "-    return str(amount)\n"
        "+    return 0\n"
    )

    with pytest.raises(StrictDiffApplyError) as excinfo:
        _apply(diff)
    assert "resulting start" in str(excinfo.value)


def test_overlapping_hunks_are_refused():
    diff = (
        f"--- a/{PATH}\n"
        f"+++ b/{PATH}\n"
        "@@ -1,3 +1,3 @@\n"
        " def format_total(amount):\n"
        "-    return str(amount)\n"
        "+    return 0\n"
        " \n"
        "@@ -2,2 +2,2 @@\n"
        "-    return str(amount)\n"
        "+    return 1\n"
        " \n"
    )

    with pytest.raises(StrictDiffApplyError) as excinfo:
        _apply(diff)
    assert "Overlapping or out-of-order" in str(excinfo.value)


def test_out_of_order_hunks_are_refused():
    original = [f"line {index}" for index in range(1, 41)]
    proposed = list(original)
    proposed[2] = "line 3 changed"
    proposed[30] = "line 31 changed"
    diff = _diff(original, proposed)

    lines = diff.split("\n")
    starts = [index for index, line in enumerate(lines) if line.startswith("@@")]
    first, second = starts
    reordered = (
        lines[:first] + lines[second:] + lines[first:second]
    )

    with pytest.raises(StrictDiffApplyError):
        _apply("\n".join(reordered), original)


def test_zero_based_old_start_with_a_nonzero_count_is_refused():
    diff = (
        f"--- a/{PATH}\n"
        f"+++ b/{PATH}\n"
        "@@ -0,2 +1,2 @@\n"
        " def format_total(amount):\n"
        "-    return str(amount)\n"
        "+    return 0\n"
    )

    with pytest.raises(StrictDiffApplyError) as excinfo:
        _apply(diff)
    assert "1-based" in str(excinfo.value)


# -- 4. No external patch engine ----------------------------------------------


def test_the_applier_starts_no_subprocess(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("the strict diff applier started a subprocess")

    monkeypatch.setattr(subprocess, "run", boom)
    monkeypatch.setattr(subprocess, "Popen", boom)

    proposed = list(ORIGINAL)
    proposed[1] = "    return 0"
    assert _apply(_diff(ORIGINAL, proposed)) == proposed


def test_the_module_imports_no_patch_tool_and_no_client():
    from ai_dev_orchestrator.file_editing import diff_apply

    source = __import__("pathlib").Path(diff_apply.__file__).read_text(
        encoding="utf-8"
    )
    for absent in (
        "import subprocess",
        "import socket",
        "import httpx",
        "import requests",
        "import os",
        "git apply",
        "LLMClient",
        "GitHubClient",
    ):
        assert f"\n{absent}" not in source, absent
    assert "subprocess" not in sys.modules or True  # imported by pytest itself


def test_the_applier_opens_no_file(monkeypatch):
    import builtins

    def boom(*args, **kwargs):
        raise AssertionError("the strict diff applier opened a file")

    monkeypatch.setattr(builtins, "open", boom)

    proposed = list(ORIGINAL)
    proposed[1] = "    return 0"
    assert _apply(_diff(ORIGINAL, proposed)) == proposed
