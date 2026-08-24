"""Discovery, as an AIDO-computed prompt manifest. EXPERIMENT ONLY.

    DECISION: no search, list, find, or glob operation exists in AR2.

There is no traversal primitive, so there is no recursion depth, no result cap,
no hidden-file policy, no ignore semantics, no symlink-walk question, and no byte
cap on results -- because there is nothing to traverse. ``search_text`` with a
model-supplied pattern would be, in effect, "return every line of this repository
that matches", and one broad pattern returns everything; ``list_directory`` leaks
the tree shape including paths the read domain excludes.

What replaces them: AIDO already enumerates tracked files with the accepted fixed
``ls_files_stage`` operation, inside the accepted preflight order, with **zero new
Git operations**. The bounded, exclusion-filtered, repository-relative list goes
into the prompt. The model still has to work out *which* file carries the defect
and read it -- what it loses is the ability to enumerate at will, which is not a
reasoning capability.

Caps: at most 200 entries and at most 8 KiB of manifest text. **A fixture that
exceeds either is refused BEFORE the model is invoked**, never silently trimmed.
"""

from __future__ import annotations

from dataclasses import dataclass

from .capability import StaticEligibilityDomain

MAX_MANIFEST_ENTRIES = 200
MAX_MANIFEST_TEXT_BYTES = 8 * 1024


class ManifestTooLargeError(Exception):
    """The fixture is too large for AR2's prompt manifest. Refused before launch."""


@dataclass(frozen=True)
class PromptManifest:
    """The bounded manifest text plus the counts that prove it stayed in bounds."""

    text: str
    readable_entry_count: int
    editable_entry_count: int
    text_bytes: int

    def as_dict(self) -> dict[str, object]:
        return {
            "readable_entry_count": self.readable_entry_count,
            "editable_entry_count": self.editable_entry_count,
            "text_bytes": self.text_bytes,
            "max_entries": MAX_MANIFEST_ENTRIES,
            "max_text_bytes": MAX_MANIFEST_TEXT_BYTES,
            "discovery_mechanism": "AIDO-computed prompt manifest",
            "list_tool": False,
            "find_tool": False,
            "grep_tool": False,
            "search_tool": False,
            "glob_tool": False,
        }


def build_prompt_manifest(sed: StaticEligibilityDomain) -> PromptManifest:
    """Render the bounded manifest, or refuse."""
    readable = sorted(sed.read_eligible)
    editable = sorted(sed.write_eligible)

    if len(readable) > MAX_MANIFEST_ENTRIES:
        raise ManifestTooLargeError(
            "refused: the fixture's readable file count exceeds the AR2 prompt "
            f"manifest cap of {MAX_MANIFEST_ENTRIES} entries"
        )

    lines = ["Files in this repository you may read:"]
    lines.extend("  " + entry for entry in readable)
    lines.append("")
    lines.append("Files you may edit: " + (", ".join(editable) if editable else "(none)"))
    lines.append(
        "Every other path is refused. There is no list, find, search or glob "
        "tool, and no shell."
    )
    text = "\n".join(lines)
    encoded = text.encode("utf-8")
    if len(encoded) > MAX_MANIFEST_TEXT_BYTES:
        raise ManifestTooLargeError(
            "refused: the fixture's prompt manifest text exceeds the AR2 cap of "
            f"{MAX_MANIFEST_TEXT_BYTES} bytes"
        )
    return PromptManifest(
        text=text,
        readable_entry_count=len(readable),
        editable_entry_count=len(editable),
        text_bytes=len(encoded),
    )


def compose_prompt(case_prompt: str, manifest: PromptManifest) -> str:
    """The ONE semantic prompt for a case: task text plus the bounded manifest.

    The manifest carries repository-relative paths only. It never carries the
    canonical root, an absolute host path, the pipe name, the capability id, or
    the token -- none of which ever enters a model prompt.
    """
    return (
        case_prompt
        + "\n\n"
        + manifest.text
        + "\n\n"
        + "Use aido_read to read a file and aido_edit to change one. aido_edit "
        "needs the sha256 that aido_read returned for that file."
    )
