"""The Phase 5D2 bounded workspace-content read, as a library function.

ALPHA-P1A extracted this from ``l2-read-workspace-files`` **unchanged**, so that
the supervised implementer could perform the shipped bounded read in-process
instead of trusting a saved, operator-supplied packet (DEC-SUP item 4). There is
still exactly **one** reader: the CLI command calls this function, and so does
the supervised implementer. Nothing here is a second implementation of the
Phase 5D2 gates, and the gate order and every refusal message are the ones the
command always printed.

What this module covers is the part of Phase 5D2 that comes **after** the
artifact has been parsed: exact identity matching, the candidate-count caps,
the lexical Phase 1 path policy for every candidate, the Phase 5D0 canonical
guard, ``stat``, the per-file and total byte caps, the bounded byte read,
strict UTF-8 decoding, and mandatory secret-like redaction. The consent flags,
the project-config load, the artifact-location guard and the strict artifact
parse stay with the caller, because they are about *which files* a caller
loaded, not about the workspace.

It lists no directory, globs nothing, walks no tree, produces no diff, edits no
file, runs no command, reads no environment variable, opens no socket and calls
no model. Its result goes back to the caller and nowhere else.

The canonical guard and the path policy are imported **inside** the reader, not
at module import, so that importing these small helpers (the CLI does, at
module level) does not load the workspace guard.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ai_dev_orchestrator.redaction import redact_secret_like_text

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ai_dev_orchestrator.handoff.models import ApprovedL1PlanArtifact
    from ai_dev_orchestrator.models import ProjectConfig


class WorkspaceContentReadRefused(Exception):
    """The bounded read refused, and nothing was returned.

    ``lines`` are the exact stderr lines ``l2-read-workspace-files`` prints for
    this refusal, in order. A caller that is not the CLI reports the category
    from the first line. No item and no file text is attached to a refusal.
    """

    def __init__(self, lines: tuple[str, ...]) -> None:
        super().__init__(lines[0] if lines else "workspace content read refused")
        self.lines = lines


@dataclass(frozen=True)
class WorkspaceContentReadResult:
    """What the bounded read produced: one row per candidate, plus a byte total.

    ``items`` has exactly the per-item shape Phase 5D2 always printed. Each row
    is a fresh ``dict``; the tuple keeps the order of ``files_likely_to_change``
    after de-duplication.
    """

    items: tuple[dict, ...]
    total_bytes_read: int


def _dedupe_preserving_order(values: list[str]) -> list[str]:
    """Drop exact duplicate strings, keeping the first occurrence's position."""
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _stat_kind_and_size(resolved_candidate: str) -> tuple[str, int | None]:
    """Classify an already-canonicalized path from its metadata alone.

    ``os.stat`` and nothing else: the path is never opened, never read, and
    never listed. A directory reports its kind and a ``None`` size — its
    entries are not enumerated.
    """
    import stat as stat_module

    result = os.stat(resolved_candidate)
    if stat_module.S_ISDIR(result.st_mode):
        return "directory", None
    if stat_module.S_ISREG(result.st_mode):
        return "file", result.st_size
    return "other", None


def _read_bounded_bytes(resolved_candidate: str, *, limit: int) -> bytes | None:
    """Read at most ``limit`` bytes from an already-canonicalized regular file.

    Returns ``None`` when the file holds more than ``limit`` bytes. The cap is
    enforced at the read itself rather than only against the size a previous
    ``stat`` reported, so a file that grew in between is still refused instead
    of being slurped whole.
    """
    with open(resolved_candidate, "rb") as handle:
        chunk = handle.read(limit + 1)
    return None if len(chunk) > limit else chunk


def _decode_utf8_text(chunk: bytes) -> str | None:
    """Decode strictly as UTF-8, or return ``None`` for anything else.

    An embedded NUL is rejected up front: such a file is binary in every sense
    that matters here even in the cases where its bytes happen to decode.
    """
    if b"\x00" in chunk:
        return None
    try:
        return chunk.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _empty_content_item(original: str, status: str, **overrides) -> dict:
    """One result row for a candidate whose contents were deliberately not read.

    Every status shares one shape, so a consumer never has to branch on which
    keys are present — the not-read cases simply carry a null ``content_text``
    and a zero ``bytes_read``.
    """
    item = {
        "original_plan_path": original,
        "canonical_relative_path": None,
        "status": status,
        "kind": None,
        "size_bytes": None,
        "bytes_read": 0,
        "encoding": None,
        "redacted": False,
        "redaction_count": 0,
        "redaction_kinds": [],
        "content_text": None,
    }
    item.update(overrides)
    return item


def read_approved_plan_workspace_contents(
    *, project: ProjectConfig, artifact: ApprovedL1PlanArtifact
) -> WorkspaceContentReadResult:
    """Run the Phase 5D2 bounded read for an already-parsed approved plan.

    The caller has already loaded ``project`` and strictly parsed ``artifact``.
    Everything from exact identity matching onwards happens here, in the shipped
    order: every cheap, disk-free check first, the workspace touched only after
    all of them pass, and a file opened only after the canonical guard and a
    ``stat`` agree it is a regular file inside the configured byte caps.

    Raises:
        WorkspaceContentReadRefused: any gate refused. ``lines`` carries the
            exact text the command prints. No partial result is returned.
    """
    # Through the package, exactly as the command always imported them, so the
    # names resolve at call time to whatever the package exposes.
    from ai_dev_orchestrator.workspace import (
        CanonicalPathError,
        CanonicalPathInputError,
        PathClassification,
        PathPolicy,
        canonicalize_existing_path_under_workspace,
    )

    content_policy = project.read_only_workspace_content
    # The command refuses a disabled block before it even reads the artifact,
    # so this check never fires from there. It exists so that no other caller
    # can reach a workspace read without the same project opt-in.
    if content_policy.enabled is not True:
        raise WorkspaceContentReadRefused(
            (
                "Error: this project does not enable read-only workspace content "
                "reads. Set read_only_workspace_content.enabled to true in the "
                "project config to permit bounded file-content inspection.",
                "No workspace was touched.",
            )
        )

    # 8. Exact identity matching against the config (design §3.5). A plan
    #    approved for one project/repo grants nothing for another — and here
    #    that mistake would mean printing another project's source.
    mismatches = [
        f"{label}: artifact has {artifact_value!r}, project config has "
        f"{config_value!r}"
        for label, artifact_value, config_value in (
            ("project_id", artifact.project_id, project.project_id),
            ("repo", artifact.repo, project.repo.github_repo),
            ("plan.repo", artifact.plan.repo, project.repo.github_repo),
            (
                "plan_provenance.repo",
                artifact.plan_provenance.repo,
                project.repo.github_repo,
            ),
        )
        if artifact_value != config_value
    ]
    if mismatches:
        raise WorkspaceContentReadRefused(
            (
                "Error: the approved plan does not match this project config "
                "exactly. A plan approved for one project/repo grants nothing for "
                "another.",
                *(f"  Mismatch in {mismatch}" for mismatch in mismatches),
                "No workspace was touched.",
            )
        )

    plan = artifact.plan

    # 9. Candidates come from files_likely_to_change and nowhere else.
    #    files_forbidden_or_out_of_scope is never read — naming a path as out of
    #    scope must not become a way to have it printed — and proposed_steps /
    #    required_verification / risks / open_questions are prose that is never
    #    treated as a path.
    candidates = _dedupe_preserving_order(list(plan.files_likely_to_change))

    if len(candidates) > content_policy.max_files:
        raise WorkspaceContentReadRefused(
            (
                f"Error: the approved plan names {len(candidates)} distinct paths, "
                "which exceeds read_only_workspace_content.max_files "
                f"({content_policy.max_files}). No workspace was touched.",
            )
        )

    if len(candidates) > project.workspace_policy.max_changed_files:
        raise WorkspaceContentReadRefused(
            (
                f"Error: the approved plan names {len(candidates)} distinct paths, "
                "which exceeds workspace_policy.max_changed_files "
                f"({project.workspace_policy.max_changed_files}). No workspace was "
                "touched.",
            )
        )

    # 10. The lexical Phase 1 policy runs for EVERY candidate before any of them
    #     is canonicalized, stat'd, or opened. A single failure stops the whole
    #     run: a plan that names one forbidden path does not get the contents of
    #     its other paths printed.
    policy = PathPolicy.from_project_config(project)
    normalized: list[tuple[str, str]] = []
    refusals: list[str] = []
    for original in candidates:
        decision = policy.check_read(original)
        if decision.classification is PathClassification.PROTECTED:
            if not content_policy.allow_protected_paths:
                refusals.append(
                    f"{original!r}: classified protected, and "
                    "read_only_workspace_content.allow_protected_paths is false"
                )
                continue
        elif not decision.permitted:
            refusals.append(
                f"{original!r}: classified {decision.classification.value} "
                f"({decision.reason})"
            )
            continue
        normalized.append((original, decision.path))

    if refusals:
        raise WorkspaceContentReadRefused(
            (
                "Error: the approved plan names paths the project's path policy "
                "refuses to read. The whole run is abandoned; no path was "
                "canonicalized, stat'd, opened, or otherwise touched.",
                *(f"  Refused {refusal}" for refusal in refusals),
            )
        )

    # 11. Every candidate passed the lexical gate, so — and only so — the
    #     configured workspace may be touched. The root is canonicalized first,
    #     which proves it exists, is a directory, and satisfies the symlink
    #     policy before any candidate is resolved against it. With no candidates
    #     there is nothing to read and the workspace stays untouched.
    items: list[dict] = []
    total_bytes_read = 0
    allow_symlinks = project.workspace_policy.allow_symlinks

    if normalized:
        try:
            canonicalize_existing_path_under_workspace(
                project.repo.workspace_path,
                project.repo.workspace_path,
                allow_symlinks=allow_symlinks,
            )
        except CanonicalPathError as exc:
            raise WorkspaceContentReadRefused(
                (
                    "Error: the configured repo.workspace_path could not be "
                    f"canonicalized. {type(exc).__name__}: {exc}",
                    "No candidate path was read.",
                )
            ) from exc

    for original, candidate in normalized:
        try:
            resolved = canonicalize_existing_path_under_workspace(
                project.repo.workspace_path,
                candidate,
                allow_symlinks=allow_symlinks,
            )
        except CanonicalPathInputError:
            # The root was proven good above and the candidate is a non-blank
            # string that passed the lexical gate, so the only remaining input
            # failure is "this path does not exist". That is an ordinary,
            # reportable answer, not a boundary violation.
            items.append(_empty_content_item(original, "missing"))
            continue
        except CanonicalPathError as exc:
            # Containment, symlink, ambiguity, and resolution failures are
            # boundary violations. They stop the whole run.
            raise WorkspaceContentReadRefused(
                (
                    f"Error: {original!r} failed the canonical workspace path "
                    f"guard. {type(exc).__name__}: {exc}",
                    "The run is abandoned; no result is printed.",
                )
            ) from exc

        relative = resolved.relative_path.replace("\\", "/")

        try:
            kind, size_bytes = _stat_kind_and_size(resolved.resolved_candidate)
        except FileNotFoundError:
            # Time-of-check/time-of-use: the path existed a moment ago and does
            # not now. Reported as missing rather than as a violation.
            items.append(_empty_content_item(original, "missing"))
            continue
        except OSError as exc:
            raise WorkspaceContentReadRefused(
                (
                    f"Error: metadata for {original!r} could not be read after "
                    f"canonicalization. {type(exc).__name__}: {exc}",
                    "The run is abandoned; no result is printed.",
                )
            ) from exc

        # A directory is reported as one and its entries are never enumerated;
        # anything that is neither a regular file nor a directory is reported
        # and left alone rather than guessed at.
        if kind != "file":
            items.append(
                _empty_content_item(
                    original,
                    "directory_no_content" if kind == "directory" else "other_no_content",
                    canonical_relative_path=relative,
                    kind=kind,
                )
            )
            continue

        if size_bytes > content_policy.max_file_bytes:
            items.append(
                _empty_content_item(
                    original,
                    "too_large",
                    canonical_relative_path=relative,
                    kind=kind,
                    size_bytes=size_bytes,
                )
            )
            continue

        if total_bytes_read + size_bytes > content_policy.max_total_bytes:
            items.append(
                _empty_content_item(
                    original,
                    "skipped_total_limit",
                    canonical_relative_path=relative,
                    kind=kind,
                    size_bytes=size_bytes,
                )
            )
            continue

        # 12. Only now is a file opened, and only up to the per-file cap.
        try:
            chunk = _read_bounded_bytes(
                resolved.resolved_candidate, limit=content_policy.max_file_bytes
            )
        except FileNotFoundError:
            items.append(_empty_content_item(original, "missing"))
            continue
        except OSError as exc:
            raise WorkspaceContentReadRefused(
                (
                    f"Error: {original!r} could not be read after it was stat'd. "
                    f"{type(exc).__name__}: {exc}",
                    "The run is abandoned; no result is printed.",
                )
            ) from exc

        if chunk is None:
            # The file grew past the per-file cap between the stat and the read.
            items.append(
                _empty_content_item(
                    original,
                    "too_large",
                    canonical_relative_path=relative,
                    kind=kind,
                    size_bytes=size_bytes,
                )
            )
            continue

        text = _decode_utf8_text(chunk)
        if text is None:
            items.append(
                _empty_content_item(
                    original,
                    "binary_or_non_utf8",
                    canonical_relative_path=relative,
                    kind=kind,
                    size_bytes=size_bytes,
                )
            )
            continue

        content_text, redaction_kinds = redact_secret_like_text(text)
        total_bytes_read += len(chunk)
        items.append(
            {
                "original_plan_path": original,
                "canonical_relative_path": relative,
                "status": "read",
                "kind": kind,
                "size_bytes": size_bytes,
                "bytes_read": len(chunk),
                "encoding": "utf-8",
                "redacted": bool(redaction_kinds),
                "redaction_count": len(redaction_kinds),
                "redaction_kinds": _dedupe_preserving_order(redaction_kinds),
                "content_text": content_text,
            }
        )

    return WorkspaceContentReadResult(
        items=tuple(items), total_bytes_read=total_bytes_read
    )
