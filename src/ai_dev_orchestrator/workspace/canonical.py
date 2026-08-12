"""Canonical workspace path guard (Phase 5D0 / 5F2B) — **library only**.

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

Phase 5F2B — the create-aware write-target guard
------------------------------------------------

§26.3 of the design doc records why the Phase 5D0 entry point is not enough for
a *write* destination: it ``lstat``s the candidate and resolves it with
``strict=True``, so **a destination that does not yet exist cannot be passed to
it at all**. Correct for a read-only inspector, useless for a writer.

:func:`canonicalize_write_target_under_workspace` is the second entry point.
It answers exactly one more question — "could this one path be the destination
of one declared change, right now?" — and it is **still library only**: no
command, no option, no config field, no caller, and above all **no write**. It
creates no file, creates no directory, opens nothing, lists nothing, and walks
nothing. Returning a result is not authorization to write; it is a description
of the filesystem at the moment of the call, and §26.3 requires a future writer
to re-canonicalize immediately before the individual write rather than reuse an
earlier answer. Phase 5F2B does not solve time-of-check/time-of-use and does not
claim to.

The change type is **declared by the caller and never inferred from disk**: an
approved artifact that says ``modify`` against a destination that has since
vanished is a reason to stop, not to quietly upgrade the operation to a
``create``. Only ``"modify"`` and ``"create"`` exist; delete, rename, mkdir,
chmod and ownership changes are not operations this guard knows how to reason
about, so they are refused as inputs.

One writer-specific rule sits on top of the Phase 5D0 symlink policy: the
**final component of a write destination may never be a symlink or reparse
point, in either ``allow_symlinks`` mode**. ``allow_symlinks`` is a policy about
*traversal*; this is a rule about *destinations*, because writing through a link
writes bytes to a path the human did not read and did not approve — even when
that path is inside the workspace.

Phase 5F2B-FU1 adds a **write-target-only** lexical gate on top of the Phase 5D0
one, for the remaining Win32 namespace aliases that stat and resolve like an
ordinary file: NTFS alternate data streams (``file.py:stream``,
``file.py::$DATA``), drive-relative paths (``C:file.py``), reserved device names
(``NUL``, ``CON.txt``, ``COM1``, ``LPT9``), and the reserved characters
``< > " | ? *`` and control characters. Phase 5E2 rejects colon-bearing paths
upstream; this guard does not rely on that invariant holding at its own
boundary. The gate is layered — :func:`_reject_unsafe_write_target_form` calls
:func:`_reject_unsafe_lexical_form` and adds to it — so the Phase 5D0 read guard
and its caller keep exactly the semantics they shipped with.
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


class CanonicalPathWriteTargetError(CanonicalPathError):
    """A destination's on-disk state contradicts the declared change type.

    Phase 5F2B. This is the one failure the Phase 5D0 hierarchy cannot express:
    the string is fine, it resolves, it is contained, and no symlink policy was
    violated — the world simply does not agree with what the caller declared.
    ``modify`` against a path that is absent or is not a regular file, and
    ``create`` against a path that already exists, both land here. So does a
    ``create`` whose parent directory does not exist, because no directory is
    ever created to make one fit.
    """


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


WriteChangeType = Literal["modify", "create"]

WRITE_CHANGE_TYPES: tuple[str, ...] = ("modify", "create")


@dataclass(frozen=True)
class CanonicalWriteTarget:
    """A data-only record of one successful write-target validation (Phase 5F2B).

    Constructed **only** on success, which is why ``is_inside_workspace`` is
    fixed to ``True``. It carries only what the guard actually proved:

    - ``resolved_workspace_root`` — the canonical root every comparison used.
    - ``resolved_parent`` — the canonical directory the destination sits in.
      For ``create`` this is the directory that must already have existed; for
      ``modify`` it is the canonical parent of the existing destination.
    - ``resolved_destination`` — the existing destination for ``modify``, and
      the **prospective** (non-existent) destination for ``create``.
    - ``relative_destination`` — that destination relative to the canonical
      root.
    - ``change_type`` and ``target_existed`` — what the caller declared, and
      what the filesystem said at the time of the call.

    It carries no file contents, no diff text, no approval data, no project
    config, no command, no Git state, and no write/apply/rollback status.
    **Holding one of these is not permission to write anything**; per §26.3 a
    future writer must re-run this check immediately before the individual
    write.
    """

    workspace_root_input: str
    candidate_input: str
    change_type: str
    resolved_workspace_root: str
    resolved_parent: str
    resolved_destination: str
    relative_destination: str
    allow_symlinks: bool
    target_existed: bool
    is_inside_workspace: Literal[True]


# An 8.3-style short name: a short base, a tilde, a small index, and an
# optional short extension — e.g. ``PROGRA~1`` or ``LONGFI~1.TXT``. Such a
# component names the same file as its long form with a different string, so it
# is refused rather than expanded.
_SHORT_NAME_RE = re.compile(r"^[^/\\.]{1,8}~[0-9]{1,3}(\.[^/\\.]{1,3})?$")

_SEPARATOR_CHARS = "\\/"

# A bare drive designator, as a whole path component: ``C:``.
_DRIVE_COMPONENT_RE = re.compile(r"^[A-Za-z]:$")

# Win32 reserved device names. These are not files: opening ``NUL`` or ``COM1``
# reaches a device no matter which directory the name appears in, and an
# extension does not make it a file — ``CON.txt`` is still the console. The
# superscript-digit ``COM¹``/``LPT²`` spellings are recognized by Windows too,
# so they are listed rather than left as a gap.
_RESERVED_DEVICE_RE = re.compile(
    r"^(CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|(COM|LPT)[1-9¹²³])$",
    re.IGNORECASE,
)

# Characters Windows reserves in a file name. The colon is handled separately,
# because exactly one colon is legitimate — the drive designator — and the
# separators are legitimate between components.
_RESERVED_NAME_CHARS = '<>"|?*'


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


def _reject_unsafe_colon_form(raw: str, *, role: str) -> None:
    """Refuse every colon except the one in a fully-qualified drive designator.

    Phase 5F2B-FU1, and **write-target only** — the Phase 5D0 read guard is
    unchanged. Two distinct Win32 namespace aliases hide behind a colon:

    - ``file.py:stream`` and ``file.py::$DATA`` name an **NTFS alternate data
      stream**, a separate byte container that shares the base file's name. A
      writer handed one would write bytes nobody reviewed, at a path that stats
      and resolves like the approved file. It is refused, never normalized down
      to the base file.
    - ``C:file.py`` is **drive-relative**: it means "``file.py`` in whatever
      directory that drive's per-process current directory happens to be", which
      is ambient state this project cannot reason about. ``C:\\...`` is
      fully-qualified and continues through the normal machinery.

    Phase 5E2 already rejects colon-bearing paths upstream. This guard does not
    rely on that invariant holding at its own boundary.
    """
    if ":" not in raw:
        return

    has_drive_prefix = (
        len(raw) >= 2 and raw[1] == ":" and raw[0].isascii() and raw[0].isalpha()
    )
    if has_drive_prefix:
        if len(raw) < 3 or raw[2] not in _SEPARATOR_CHARS:
            raise CanonicalPathAmbiguityError(
                f"ambiguity error: {role} is drive-relative (a drive letter and a "
                "colon with no root separator), which depends on ambient per-drive "
                "current-directory state and is refused rather than resolved"
            )
        remainder = raw[2:]
    else:
        remainder = raw

    if ":" in remainder:
        raise CanonicalPathAmbiguityError(
            f"ambiguity error: {role} has a colon outside a fully-qualified drive "
            "designator, which is alternate-data-stream syntax and is refused "
            "rather than normalized to the base file"
        )


def _reject_unsafe_write_name_form(raw: str, *, role: str) -> None:
    """Refuse reserved device names and reserved characters in a write path.

    Phase 5F2B-FU1, and **write-target only**. §26.3 describes a create leaf as
    a plain file name; these are the Win32 spellings that look like one and are
    not. Applied to every component, because a directory named ``CON`` is as
    unopenable as a file named ``CON``, and applied on **every platform** rather
    than only on Windows: an approval naming a Windows destination must not
    validate as safe merely because the check ran somewhere else.

    Nothing here probes, resolves, or opens a name to discover what it means —
    the decision is made on the string, and nothing is repaired or stripped.
    """
    for character in raw:
        if character in _RESERVED_NAME_CHARS:
            raise CanonicalPathAmbiguityError(
                f"ambiguity error: {role} contains the reserved character "
                f"{character!r}, which is refused rather than stripped"
            )
        if ord(character) < 32:
            raise CanonicalPathAmbiguityError(
                f"ambiguity error: {role} contains a control character "
                f"(0x{ord(character):02x}), which is refused rather than stripped"
            )

    for index, component in enumerate(_split_components(raw)):
        if component in (".", ".."):
            continue
        if index == 0 and _DRIVE_COMPONENT_RE.match(component):
            continue
        # Windows resolves the device from the name before the first dot, so an
        # extension does not make ``NUL.txt`` a file.
        device_candidate = component.split(".")[0]
        if _RESERVED_DEVICE_RE.match(device_candidate):
            raise CanonicalPathAmbiguityError(
                f"ambiguity error: {role} has a path component that is a reserved "
                f"Windows device name ({device_candidate!r}), which names a device "
                "rather than a file and is refused without being probed"
            )


def _reject_unsafe_write_target_form(raw: str, *, role: str) -> None:
    """The full write-destination lexical gate: Phase 5D0's rules, plus FU1's.

    Layered on :func:`_reject_unsafe_lexical_form` rather than folded into it,
    so :func:`canonicalize_existing_path_under_workspace` and its caller keep
    exactly the Phase 5D0 read semantics they shipped with.
    """
    _reject_unsafe_lexical_form(raw, role=role)
    _reject_unsafe_colon_form(raw, role=role)
    _reject_unsafe_write_name_form(raw, role=role)


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


def _absolute_candidate(root_absolute: str, candidate_input: str) -> str:
    """Make a candidate absolute: relative forms are joined to the root, never guessed."""
    candidate_drive, _ = os.path.splitdrive(candidate_input)
    if os.path.isabs(candidate_input) or candidate_drive:
        return os.path.abspath(candidate_input)
    return os.path.abspath(os.path.join(root_absolute, candidate_input))


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
    candidate_absolute = _absolute_candidate(root_absolute, candidate_input)

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


# -- Phase 5F2B: the create-aware write-target guard ---------------------------


def _check_final_component_is_a_plain_file_name(
    candidate_input: str, final_name: str
) -> None:
    """Refuse anything that is not one plain file name, before it is used.

    Checked against both the string the caller wrote and the basename derived
    from it, because normalization can hide a directory-shaped tail: ``src/``
    and ``src/.`` both name a directory, and neither is a create destination.
    """
    if candidate_input[-1] in _SEPARATOR_CHARS:
        raise CanonicalPathWriteTargetError(
            "write target error: the create destination ends in a path separator, "
            "so it names a directory rather than a file"
        )

    raw_components = _split_components(candidate_input)
    if raw_components and raw_components[-1] in (".", ".."):
        raise CanonicalPathWriteTargetError(
            "write target error: the create destination's final component is "
            f"{raw_components[-1]!r}, which is not a file name"
        )

    if not final_name or final_name in (".", ".."):
        raise CanonicalPathWriteTargetError(
            "write target error: the create destination has no usable file name"
        )
    if any(separator in final_name for separator in _SEPARATOR_CHARS):
        raise CanonicalPathWriteTargetError(
            "write target error: the create destination's file name contains a "
            "path separator"
        )
    # The same ambiguity rules as the full string, applied once more to the leaf
    # that is about to be joined onto an already-canonical parent.
    _reject_unsafe_write_target_form(final_name, role="create destination file name")


def _lstat_or_none(path: str, *, role: str) -> os.stat_result | None:
    """Return the ``lstat`` of ``path``, or ``None`` only on a genuine ENOENT.

    ``os.path.exists`` is deliberately not used as the security decision: it
    follows links, so it calls a **dangling** symlink absent, while an
    ``open(..., "x")`` through that link would write outside the workspace.
    ``lstat`` does not follow, and any error that is not "this name does not
    exist" fails closed rather than being converted into "missing".
    """
    try:
        return os.lstat(path)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise CanonicalPathWriteTargetError(
            f"write target error: the state of the {role} could not be established"
        ) from exc
    except ValueError as exc:
        raise CanonicalPathAmbiguityError(
            f"ambiguity error: the {role} is not a form that can be examined on disk"
        ) from exc


def canonicalize_write_target_under_workspace(
    workspace_root: str | Path,
    candidate: str | Path,
    *,
    change_type: str,
    allow_symlinks: bool = False,
) -> CanonicalWriteTarget:
    """Prove that one path could be the destination of one declared change.

    Phase 5F2B, and the create-aware counterpart to
    :func:`canonicalize_existing_path_under_workspace`, which cannot be handed a
    destination that does not exist yet. Intended for a **future** write
    preflight and a **future** writer; nothing shipped calls it, and it writes,
    creates, opens and lists nothing.

    ``change_type`` is declared by the caller and is **never inferred from the
    filesystem**. Exactly two values exist:

    - ``"modify"`` — the destination must already exist, must be a regular
      file, and the whole Phase 5D0 machinery applies to it unchanged:
      containment of the resolved destination inside the resolved root, no
      reparse point at the root, and none on any component between root and
      destination when ``allow_symlinks`` is false. A destination that is
      absent is **not** upgraded to a create.
    - ``"create"`` — the destination must **not** exist. Its **parent
      directory** is canonicalized instead and must already exist and be a
      directory genuinely inside the resolved root; the final component must be
      one plain file name; and absence is established with ``lstat``, requiring
      a genuine ``ENOENT``. A regular file, a directory, a symlink, a reparse
      point, or a **dangling** symlink at that name all refuse the write.
      **No directory is ever created** — a missing parent is a failure.

    The destination string passes a **write-target-only** lexical gate before
    any filesystem call: the Phase 5D0 rules (UNC, extended-length, device
    prefix, trailing dot or space, 8.3-looking components) plus the Phase
    5F2B-FU1 rules — alternate-data-stream colon syntax, drive-relative
    ``C:file`` forms, reserved Windows device names such as ``NUL`` and
    ``COM1`` (including with an extension), and the reserved characters
    ``< > " | ? *`` and control characters. A fully-qualified ``C:\\...``
    destination is unaffected. Nothing is normalized, stripped, or probed.

    ``allow_symlinks`` keeps its Phase 5D0 meaning for *traversal* (false
    refuses a linked root, a linked intermediate component, and a candidate not
    lexically under the root; true follows links and then re-verifies
    containment against the resolved root). It gains one rule it may **not**
    relax: the final component of a write destination is never permitted to be
    a symlink or reparse point, in either mode.

    **This is not authorization to write.** The result describes the filesystem
    at the time of this call and nothing more; per design §26.3 a future writer
    must re-run this check immediately before each individual write. Phase 5F2B
    does not solve time-of-check/time-of-use.

    Raises:
        CanonicalPathInputError: blank or wrongly-typed input, an unknown
            ``change_type``, or a workspace root that is missing or not a
            directory.
        CanonicalPathWriteTargetError: the destination's state contradicts the
            declared change type, or a ``create`` parent does not exist.
        CanonicalPathAmbiguityError: an unsafe or ambiguous path form, or a
            containment comparison that cannot be made.
        CanonicalPathSymlinkError: the destination itself is a symlink or
            reparse point, or traversal met one with ``allow_symlinks`` false.
        CanonicalPathResolutionError: strict canonicalization failed.
        CanonicalPathContainmentError: the destination or its parent is outside
            the resolved workspace root.
    """
    if not isinstance(allow_symlinks, bool):
        raise CanonicalPathInputError("input error: allow_symlinks must be a bool")
    if not isinstance(change_type, str) or change_type not in WRITE_CHANGE_TYPES:
        raise CanonicalPathInputError(
            "input error: change_type must be exactly 'modify' or 'create'"
        )

    root_input = _as_path_text(workspace_root, role="workspace_root")
    candidate_input = _as_path_text(candidate, role="candidate")

    if not root_input.strip():
        raise CanonicalPathInputError("input error: workspace_root must not be blank")
    if not candidate_input.strip():
        raise CanonicalPathInputError("input error: candidate must not be blank")

    # Lexical precheck first, on the *whole* destination string: an ambiguous
    # string is refused without ever being stat'd or resolved. The root gets the
    # Phase 5D0 rules plus the colon rule — a drive-relative root is as ambient
    # as a drive-relative destination — and the destination gets the full
    # write-target gate.
    _reject_unsafe_lexical_form(root_input, role="workspace_root")
    _reject_unsafe_colon_form(root_input, role="workspace_root")
    _reject_unsafe_write_target_form(candidate_input, role="candidate")

    root_absolute = os.path.abspath(root_input)
    candidate_absolute = _absolute_candidate(root_absolute, candidate_input)

    # The root is proved first, by the Phase 5D0 guard itself, so no destination
    # is examined on behalf of a root that was never valid.
    root_decision = canonicalize_existing_path_under_workspace(
        root_input, root_absolute, allow_symlinks=allow_symlinks
    )
    resolved_root = root_decision.resolved_workspace_root

    if change_type == "modify":
        destination_lstat = _lstat_or_none(
            candidate_absolute, role="modify destination"
        )
        if destination_lstat is None:
            raise CanonicalPathWriteTargetError(
                "write target error: change_type is 'modify' but the destination "
                f"does not exist: {candidate_input}"
            )
        if _is_symlink_or_reparse_point(destination_lstat):
            raise CanonicalPathSymlinkError(
                "symlink error: the write destination itself is a symlink or "
                "reparse point, which is refused regardless of allow_symlinks"
            )
        if not stat_module.S_ISREG(destination_lstat.st_mode):
            raise CanonicalPathWriteTargetError(
                "write target error: change_type is 'modify' but the destination "
                f"is not a regular file: {candidate_input}"
            )

        # The full Phase 5D0 machinery, unchanged: containment, intermediate
        # symlink policy, strict resolution.
        decision = canonicalize_existing_path_under_workspace(
            root_input, candidate_input, allow_symlinks=allow_symlinks
        )
        resolved_destination = decision.resolved_candidate
        relative_destination = decision.relative_path
        resolved_parent = os.path.dirname(resolved_destination)
        if not resolved_parent:
            raise CanonicalPathAmbiguityError(
                "ambiguity error: the resolved destination has no parent directory"
            )
        _relative_path_inside(resolved_root, resolved_parent)

        return CanonicalWriteTarget(
            workspace_root_input=root_input,
            candidate_input=candidate_input,
            change_type=change_type,
            resolved_workspace_root=decision.resolved_workspace_root,
            resolved_parent=resolved_parent,
            resolved_destination=resolved_destination,
            relative_destination=relative_destination,
            allow_symlinks=allow_symlinks,
            target_existed=True,
            is_inside_workspace=True,
        )

    # change_type == "create"
    if os.path.normcase(candidate_absolute) == os.path.normcase(root_absolute):
        raise CanonicalPathWriteTargetError(
            "write target error: the workspace root itself is not a create "
            "destination"
        )

    parent_absolute = os.path.dirname(candidate_absolute)
    final_name = os.path.basename(candidate_absolute)
    if not parent_absolute or parent_absolute == candidate_absolute:
        raise CanonicalPathWriteTargetError(
            "write target error: the create destination has no parent directory "
            "inside the workspace"
        )
    _check_final_component_is_a_plain_file_name(candidate_input, final_name)

    # The parent must already exist. It is canonicalized by the Phase 5D0 guard,
    # which is also what applies the intermediate symlink policy. Nothing here
    # creates it.
    try:
        parent_decision = canonicalize_existing_path_under_workspace(
            root_input, parent_absolute, allow_symlinks=allow_symlinks
        )
    except CanonicalPathInputError as exc:
        raise CanonicalPathWriteTargetError(
            "write target error: the create destination's parent directory does "
            f"not exist, and no directory is created: {candidate_input}"
        ) from exc
    resolved_parent = parent_decision.resolved_candidate

    try:
        parent_stat = os.stat(resolved_parent)
    except OSError as exc:
        raise CanonicalPathResolutionError(
            "resolution error: the resolved parent directory cannot be examined"
        ) from exc
    if not stat_module.S_ISDIR(parent_stat.st_mode):
        raise CanonicalPathWriteTargetError(
            "write target error: the create destination's parent is not a directory"
        )

    # Containment of the parent is re-established against the resolved root
    # before the parent is used to build anything.
    _relative_path_inside(resolved_root, resolved_parent)

    prospective_destination = os.path.join(resolved_parent, final_name)
    existing = _lstat_or_none(prospective_destination, role="create destination")
    if existing is not None:
        if _is_symlink_or_reparse_point(existing):
            raise CanonicalPathSymlinkError(
                "symlink error: the create destination already exists as a symlink "
                "or reparse point, which is refused regardless of allow_symlinks"
            )
        raise CanonicalPathWriteTargetError(
            "write target error: change_type is 'create' but the destination "
            f"already exists: {candidate_input}"
        )

    # Containment for a path that does not exist, and is not required to: it is
    # built from an already-canonical parent plus one validated plain name, and
    # compared with the same commonpath-based check.
    relative_destination = _relative_path_inside(resolved_root, prospective_destination)

    return CanonicalWriteTarget(
        workspace_root_input=root_input,
        candidate_input=candidate_input,
        change_type=change_type,
        resolved_workspace_root=resolved_root,
        resolved_parent=resolved_parent,
        resolved_destination=prospective_destination,
        relative_destination=relative_destination,
        allow_symlinks=allow_symlinks,
        target_existed=False,
        is_inside_workspace=True,
    )
