"""Canonical workspace path guard (Phase 5D0) — **library only**.

This module implements the on-disk canonicalization step sketched in §6.4 of
[PHASE_5_L2_IMPLEMENTER_BOUNDARY_DESIGN.md](../../../docs/PHASE_5_L2_IMPLEMENTER_BOUNDARY_DESIGN.md)
and nothing else. That section records the decision that the Phase 1 *lexical*
path policy — :mod:`ai_dev_orchestrator.workspace.path_policy`, which reasons
about path strings and never touches disk — stops being a complete answer the
moment anything actually reads a workspace, and that closing the gap is a
**prerequisite** for the first read-only-inspection phase rather than a
follow-up to it.

So this module is the second gate: given an already-approved workspace root and
one candidate path, it canonicalizes both on disk and re-verifies containment.
It is a **library**, wired into nothing.

What this module deliberately does not do:

- **No CLI behavior.** Importing it adds no command and no option, and no
  shipped command calls it. Nothing here is reachable from
  ``l2-dry-run``, ``generate-plan``, ``generate-model-plan``, or any other
  command.
- **No workspace inspection.** It never reads file contents, never lists a
  directory, never globs, and never walks a tree. It answers exactly one
  question about exactly one path that the caller already named.
- **No mutation.** It creates nothing, deletes nothing, and writes nothing —
  including no changes to the strings it is handed.
- **No model call, no network call, no environment read, no command
  execution.** ``httpx``, ``requests``, ``LLMClient``, ``LLMClientConfig``,
  ``load_llm_client_config_from_env``, ``GitHubClient``, ``typer``,
  ``socket`` and ``subprocess`` are not imported, so no code path here can
  reach any of them.
- **No policy decisions.** Containment is not permission. A returned
  :class:`CanonicalWorkspacePath` says "this existing path is genuinely inside
  this existing workspace root"; whether the path is *allowed* remains
  :class:`~ai_dev_orchestrator.workspace.path_policy.PathPolicy`'s question, and
  a future caller must satisfy both.

Order of operations, cheapest and most conservative first:

1. **Type and blank checks** on both inputs.
2. **A fail-closed lexical precheck** (§5 of the phase scope) rejecting
   ambiguous or unsafe Windows path forms — UNC, extended-length ``\\\\?\\``,
   device ``\\\\.\\``, components ending in a space or a dot, and
   8.3-short-name-looking components. This runs **before any filesystem call**,
   so an ambiguous string is refused without ever being stat'd or resolved.
3. **Existence and kind checks**, via :func:`os.lstat` / :func:`os.stat` only.
4. **Symlink / reparse-point checks** honoring ``allow_symlinks``.
5. **Strict canonicalization** of both paths.
6. **Containment re-verification** of the *resolved* candidate against the
   *resolved* root, using :func:`os.path.commonpath` on platform-normalized
   paths rather than a string prefix test.

Any failure raises — there is no "warn and continue", and no repair. The
lexical precheck in particular is **deliberately conservative** and may reject
paths that are valid on Windows but ambiguous to reason about: the cost of
refusing an awkward path is a clearer error, and the cost of accepting one is
potentially reading another project's source.

**Time of check is not time of use.** A returned decision describes the
filesystem as it was during the call. Per design §6.4 a future caller must
re-establish containment immediately before each read, not cache one answer and
reuse it.
"""

from __future__ import annotations

import os
import re
import stat as stat_module
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


class CanonicalPathError(Exception):
    """Base class for canonical workspace path guard failures.

    Messages name the failed **category** and the **path role** that failed.
    They never read or echo file contents, and they never carry environment or
    model data.
    """


class CanonicalPathInputError(CanonicalPathError):
    """An input was the wrong type, blank, missing on disk, or the wrong kind."""


class CanonicalPathResolutionError(CanonicalPathError):
    """Strict on-disk canonicalization of a path failed."""


class CanonicalPathContainmentError(CanonicalPathError):
    """A path is not inside the workspace root once both are canonicalized."""


class CanonicalPathSymlinkError(CanonicalPathError):
    """A symlink or reparse point was encountered while ``allow_symlinks`` is false."""


class CanonicalPathAmbiguityError(CanonicalPathError):
    """A path form or a containment comparison could not be reasoned about safely."""


@dataclass(frozen=True)
class CanonicalWorkspacePath:
    """A data-only record of one successful canonicalization.

    This object has no methods and touches no disk. It is constructed **only**
    on success, which is why ``is_inside_workspace`` is fixed to ``True``: a
    candidate that is not inside the workspace root raises instead of producing
    a decision with a false flag.

    It deliberately carries no file contents, no directory listing, no
    environment value, and no model data — only the two inputs as given, their
    canonical forms, and the relative path between them.
    """

    workspace_root_input: str
    candidate_input: str
    resolved_workspace_root: str
    resolved_candidate: str
    relative_path: str
    allow_symlinks: bool
    is_inside_workspace: Literal[True]


# An 8.3-style short name: a short base, a tilde, a small index, and an
# optional short extension — e.g. ``PROGRA~1`` or ``LONGFI~1.TXT``. Such a
# component names the same file as its long form with a different string, so it
# is refused rather than expanded.
_SHORT_NAME_RE = re.compile(r"^[^/\\.]{1,8}~[0-9]{1,3}(\.[^/\\.]{1,3})?$")

_SEPARATOR_CHARS = "\\/"


def _as_path_text(value: str | Path, *, role: str) -> str:
    """Return ``value`` as text without normalizing or mutating it."""
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, str):
        return value
    raise CanonicalPathInputError(
        f"input error: {role} must be a str or a pathlib.Path"
    )


def _split_components(raw: str) -> list[str]:
    """Split on either separator, dropping empties. Purely lexical."""
    return [part for part in raw.replace("\\", "/").split("/") if part]


def _reject_unsafe_lexical_form(raw: str, *, role: str) -> None:
    """Fail closed on ambiguous or unsafe path forms, before touching disk.

    This is intentionally conservative: it refuses rather than normalizes, and
    it may reject strings that name a real file on Windows. Every form here can
    denote the same location as some other string, which is precisely what
    makes containment reasoning unsound.
    """
    head = raw[:4]
    if len(head) >= 4 and head[0] in _SEPARATOR_CHARS and head[1] in _SEPARATOR_CHARS:
        if head[2] == "?" and head[3] in _SEPARATOR_CHARS:
            raise CanonicalPathAmbiguityError(
                f"ambiguity error: {role} uses an extended-length path prefix, "
                "which is refused rather than normalized"
            )
        if head[2] == "." and head[3] in _SEPARATOR_CHARS:
            raise CanonicalPathAmbiguityError(
                f"ambiguity error: {role} uses a device path prefix, "
                "which is refused rather than normalized"
            )
    if len(raw) >= 2 and raw[0] in _SEPARATOR_CHARS and raw[1] in _SEPARATOR_CHARS:
        raise CanonicalPathAmbiguityError(
            f"ambiguity error: {role} looks like a UNC path, "
            "which is refused rather than normalized"
        )

    for component in _split_components(raw):
        if component in (".", ".."):
            continue
        if component.endswith(" "):
            raise CanonicalPathAmbiguityError(
                f"ambiguity error: {role} has a path component ending in a space"
            )
        if component.endswith("."):
            raise CanonicalPathAmbiguityError(
                f"ambiguity error: {role} has a path component ending in a dot"
            )
        if _SHORT_NAME_RE.match(component):
            raise CanonicalPathAmbiguityError(
                f"ambiguity error: {role} has a path component that looks like an "
                "8.3 short name"
            )


def _lstat(path: str, *, role: str) -> os.stat_result:
    """Stat ``path`` without following a final symlink.

    ``lstat`` rather than ``stat`` on purpose: a dangling symlink must surface
    as a symlink decision, not as a missing path.
    """
    try:
        return os.lstat(path)
    except OSError as exc:
        raise CanonicalPathInputError(
            f"input error: {role} does not exist or cannot be examined"
        ) from exc


def _is_symlink_or_reparse_point(stat_result: os.stat_result) -> bool:
    """Best-effort detection of a symlink, NTFS junction, or other reparse point.

    POSIX symlinks show up in ``st_mode``. Windows junctions and mount points
    are directory reparse points that ``stat`` follows silently, so the
    ``st_file_attributes`` reparse bit and ``st_reparse_tag`` are checked too —
    both are Windows-only attributes and are simply absent elsewhere.
    """
    if stat_module.S_ISLNK(stat_result.st_mode):
        return True

    attributes = getattr(stat_result, "st_file_attributes", None)
    if attributes is not None:
        reparse_flag = getattr(stat_module, "FILE_ATTRIBUTE_REPARSE_POINT", 0x0400)
        if attributes & reparse_flag:
            return True

    return bool(getattr(stat_result, "st_reparse_tag", 0))


def _strict_resolve(absolute_path: str, *, role: str) -> str:
    """Canonicalize an existing absolute path, failing closed on any error."""
    try:
        return str(Path(absolute_path).resolve(strict=True))
    except OSError as exc:
        raise CanonicalPathResolutionError(
            f"resolution error: {role} could not be canonicalized on disk"
        ) from exc
    except ValueError as exc:
        raise CanonicalPathResolutionError(
            f"resolution error: {role} is not a resolvable path form"
        ) from exc


def _lexical_relative_components(root_absolute: str, candidate_absolute: str) -> list[str] | None:
    """Components of ``candidate_absolute`` under ``root_absolute``, or ``None``.

    Compared component-by-component after :func:`os.path.normcase`, so a
    sibling sharing a string prefix (``repo`` vs ``repo_evil``) is *not* under
    the root. Purely lexical — no disk access, and no symlink following.
    """
    root_parts = _split_components(os.path.normcase(root_absolute))
    candidate_parts = _split_components(os.path.normcase(candidate_absolute))
    if candidate_parts[: len(root_parts)] != root_parts:
        return None
    return _split_components(candidate_absolute)[len(root_parts):]


def _relative_path_inside(resolved_root: str, resolved_candidate: str) -> str:
    """Verify containment of two resolved paths and return the relative path.

    Containment uses :func:`os.path.commonpath` on platform-normalized paths,
    not a string prefix test. A drive or path-form mismatch makes the two
    incomparable, and that is treated as ambiguity — refused, never guessed.
    """
    root_key = os.path.normcase(resolved_root)
    candidate_key = os.path.normcase(resolved_candidate)

    if root_key != candidate_key:
        try:
            common = os.path.commonpath([root_key, candidate_key])
        except ValueError as exc:
            raise CanonicalPathAmbiguityError(
                "ambiguity error: resolved candidate and resolved workspace_root "
                "cannot be compared (drive or path-form mismatch)"
            ) from exc
        if common != root_key:
            raise CanonicalPathContainmentError(
                "containment error: resolved candidate is not inside the resolved "
                "workspace_root"
            )

    relative = os.path.relpath(resolved_candidate, resolved_root)
    escapes = relative == ".." or relative.startswith(
        (".." + os.sep, "../")
    )
    if os.path.isabs(relative) or escapes:
        raise CanonicalPathContainmentError(
            "containment error: the relative path from the resolved workspace_root "
            "to the resolved candidate escapes the workspace_root"
        )
    return relative


def canonicalize_existing_path_under_workspace(
    workspace_root: str | Path,
    candidate: str | Path,
    *,
    allow_symlinks: bool = False,
) -> CanonicalWorkspacePath:
    """Prove that one existing path is genuinely inside one existing workspace root.

    Intended for a **future** read-only workspace inspection phase, which would
    call this immediately before reading any workspace path. Nothing shipped
    calls it today.

    ``candidate`` may be either a path relative to ``workspace_root`` (joined to
    it before resolution) or an absolute path (never joined, always validated
    against the root). A candidate equal to the workspace root itself is
    **accepted**, with ``relative_path == "."``; callers that need a file rather
    than a directory must check that separately, since "inside the workspace"
    and "is a file" are different questions.

    Symlink policy:

    - ``allow_symlinks=False`` (the default) refuses a workspace root that is
      itself a symlink or reparse point, refuses any component between the root
      and the candidate that is one, and refuses a candidate that is not
      *lexically* under the root — so a link cannot be used to enter the
      workspace either. This is checked **before** the path is accepted, even
      when the link happens to point back inside the workspace.
    - ``allow_symlinks=True`` follows links, and then still verifies containment
      against the resolved root. A link resolving outside the workspace is
      rejected; one resolving inside may be accepted.

    Raises:
        CanonicalPathInputError: blank or wrongly-typed input, a missing path, or
            a workspace root that is not a directory.
        CanonicalPathAmbiguityError: an unsafe or ambiguous path form, or a
            containment comparison that cannot be made.
        CanonicalPathSymlinkError: a symlink or reparse point with
            ``allow_symlinks=False``.
        CanonicalPathResolutionError: strict canonicalization failed.
        CanonicalPathContainmentError: the resolved candidate is outside the
            resolved workspace root.
    """
    if not isinstance(allow_symlinks, bool):
        raise CanonicalPathInputError("input error: allow_symlinks must be a bool")

    root_input = _as_path_text(workspace_root, role="workspace_root")
    candidate_input = _as_path_text(candidate, role="candidate")

    if not root_input.strip():
        raise CanonicalPathInputError("input error: workspace_root must not be blank")
    if not candidate_input.strip():
        raise CanonicalPathInputError("input error: candidate must not be blank")

    # Lexical precheck first: an ambiguous string is refused without being
    # stat'd or resolved.
    _reject_unsafe_lexical_form(root_input, role="workspace_root")
    _reject_unsafe_lexical_form(candidate_input, role="candidate")

    root_absolute = os.path.abspath(root_input)
    candidate_drive, _ = os.path.splitdrive(candidate_input)
    if os.path.isabs(candidate_input) or candidate_drive:
        candidate_absolute = os.path.abspath(candidate_input)
    else:
        candidate_absolute = os.path.abspath(os.path.join(root_absolute, candidate_input))

    root_lstat = _lstat(root_absolute, role="workspace_root")
    if not allow_symlinks and _is_symlink_or_reparse_point(root_lstat):
        raise CanonicalPathSymlinkError(
            "symlink error: workspace_root is itself a symlink or reparse point and "
            "allow_symlinks is False"
        )

    resolved_root = _strict_resolve(root_absolute, role="workspace_root")
    try:
        resolved_root_stat = os.stat(resolved_root)
    except OSError as exc:
        raise CanonicalPathResolutionError(
            "resolution error: the resolved workspace_root cannot be examined"
        ) from exc
    if not stat_module.S_ISDIR(resolved_root_stat.st_mode):
        raise CanonicalPathInputError("input error: workspace_root is not a directory")

    _lstat(candidate_absolute, role="candidate")

    if not allow_symlinks:
        relative_components = _lexical_relative_components(
            root_absolute, candidate_absolute
        )
        if relative_components is None:
            raise CanonicalPathContainmentError(
                "containment error: candidate is not lexically inside workspace_root, "
                "and allow_symlinks is False so link-mediated entry is refused"
            )
        walked = root_absolute
        for component in relative_components:
            walked = os.path.join(walked, component)
            component_lstat = _lstat(walked, role="candidate path component")
            if _is_symlink_or_reparse_point(component_lstat):
                raise CanonicalPathSymlinkError(
                    "symlink error: a path component between workspace_root and "
                    "candidate is a symlink or reparse point and allow_symlinks is "
                    "False"
                )

    resolved_candidate = _strict_resolve(candidate_absolute, role="candidate")
    relative_path = _relative_path_inside(resolved_root, resolved_candidate)

    return CanonicalWorkspacePath(
        workspace_root_input=root_input,
        candidate_input=candidate_input,
        resolved_workspace_root=resolved_root,
        resolved_candidate=resolved_candidate,
        relative_path=relative_path,
        allow_symlinks=allow_symlinks,
        is_inside_workspace=True,
    )
