"""The two delegated filesystem operations. EXPERIMENT ONLY.

Everything here runs **inside AIDO's own process**, after
:func:`ar2.candidate.evaluate_delegated_candidate` has accepted, and after the
fixed dynamic preconditions have been evaluated against AIDO-owned run state.

TOCTOU discipline (AR2D section 13.3), applied to both operations::

    canonical/path validation
        -> os.stat(resolved)
        -> os.open(resolved, binary | no-inherit)
        -> os.fstat(fd)  and require (st_dev, st_ino) equality
        -> perform EVERYTHING through that already-open handle

Writes additionally re-run the full L1-L3 chain immediately before the mutation,
and ``base_sha256`` is the content precondition that catches a swap the identity
check could not. **No transaction framework, no journal, no rollback, no crash
recovery, and no repair of a failed edit** -- the workspace is disposable, and
that is what disposability is for.

Read representation is **bounded UTF-8 text only** (AR2D section 14): no base64,
no raw bytes, no hexdump, no charset detection, no ``errors="replace"``, and
**no truncation ever** -- an over-cap file is refused, because a truncated read
would let the model edit against a picture that is missing content.

Writes are **in place, through the verified handle**. Atomic replace-via-rename
is correct for *promotion*, where a crash must not corrupt a real project file;
here it would create a new file identity and defeat the handle-identity check
while buying nothing. **This choice must not be carried into promotion.**
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass

from .capability import EDIT_FILE, READ_FILE, RunState, StaticEligibilityDomain
from .candidate import evaluate_delegated_candidate
from .wire import (
    ERR_BUDGET_EXHAUSTED,
    ERR_INTERNAL_ERROR,
    ERR_NO_UNIQUE_MATCH,
    ERR_NOT_TEXT,
    ERR_REFUSED,
    ERR_STALE_BASE,
    ERR_TOO_LARGE,
)

_OPEN_READ_FLAGS = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOINHERIT", 0)
_OPEN_WRITE_FLAGS = os.O_RDWR | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOINHERIT", 0)


@dataclass(frozen=True)
class OperationOutcome:
    """One operation's result. ``result`` and ``code`` are mutually exclusive."""

    ok: bool
    result: dict[str, object] | None
    code: str | None
    detail: str
    internal_reason: str
    relative_path: str | None


def _ok(result: dict[str, object], relative: str, reason: str) -> OperationOutcome:
    return OperationOutcome(
        ok=True, result=result, code=None, detail="", internal_reason=reason,
        relative_path=relative,
    )


def _fail(code: str, detail: str, reason: str, relative: str | None = None) -> OperationOutcome:
    return OperationOutcome(
        ok=False, result=None, code=code, detail=detail, internal_reason=reason,
        relative_path=relative,
    )


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _identity(stat_result: os.stat_result) -> tuple[int, int]:
    return (stat_result.st_dev, stat_result.st_ino)


def _open_verified(resolved: str, flags: int) -> tuple[int, str | None]:
    """Stat, open, fstat, and require identity equality. Fails closed."""
    try:
        before = os.stat(resolved)
    except OSError:
        return -1, "pre_open_stat_failed"
    try:
        descriptor = os.open(resolved, flags)
    except OSError:
        return -1, "open_failed"
    try:
        after = os.fstat(descriptor)
    except OSError:
        os.close(descriptor)
        return -1, "fstat_failed"
    if _identity(before) != _identity(after):
        os.close(descriptor)
        return -1, "handle_identity_changed_between_stat_and_open"
    return descriptor, None


def perform_read(
    sed: StaticEligibilityDomain, run_state: RunState, path_candidate: str
) -> OperationOutcome:
    """One bounded read. Refuses rather than truncating, and never guesses."""
    decision = evaluate_delegated_candidate(sed, READ_FILE, path_candidate)
    if not decision.permitted:
        return _fail(
            ERR_REFUSED,
            "operation_not_permitted",
            decision.internal_reason,
            decision.relative_path,
        )

    relative = decision.relative_path or ""
    resolved = decision.resolved_path or ""

    descriptor, failure = _open_verified(resolved, _OPEN_READ_FLAGS)
    if failure is not None:
        return _fail(ERR_REFUSED, "operation_not_permitted", failure, relative)

    try:
        size = os.fstat(descriptor).st_size
        if size > sed.caps.max_read_bytes_per_file:
            return _fail(
                ERR_TOO_LARGE, "file_exceeds_per_file_read_cap", "per_file_read_cap", relative
            )
        budget_failure = run_state.read_budget_allows(size)
        if budget_failure is not None:
            return _fail(ERR_BUDGET_EXHAUSTED, "run_budget_exhausted", budget_failure, relative)

        payload = os.read(descriptor, size) if size else b""
        # A short read means the file changed under the verified handle. Refuse
        # rather than report a partial picture as complete.
        if len(payload) != size:
            return _fail(
                ERR_REFUSED, "operation_not_permitted", "short_read_under_handle", relative
            )
    except OSError:
        return _fail(ERR_INTERNAL_ERROR, "broker_failure", "read_raised_oserror", relative)
    finally:
        os.close(descriptor)

    if b"\x00" in payload:
        return _fail(ERR_NOT_TEXT, "content_is_not_utf8_text", "nul_byte_present", relative)
    try:
        text = payload.decode("utf-8", "strict")
    except UnicodeDecodeError:
        return _fail(ERR_NOT_TEXT, "content_is_not_utf8_text", "strict_utf8_decode_failed", relative)

    digest = _sha256(payload)
    run_state.record_read(relative, digest, size)
    return _ok(
        {
            "text": text,
            "encoding": "utf-8",
            "bytes": size,
            "sha256": digest,
            "contains_crlf": b"\r\n" in payload,
        },
        relative,
        "read permitted and performed through an identity-verified handle",
    )


def perform_edit(
    sed: StaticEligibilityDomain,
    run_state: RunState,
    path_candidate: str,
    *,
    base_sha256: str,
    old_text: str,
    new_text: str,
) -> OperationOutcome:
    """One exact, unique find/replace, pinned by a pre-image hash.

    ``old_text`` must be non-empty and occur EXACTLY ONCE. There is no fuzzy
    matching, no whole-file replacement, no patch/hunk fuzz, and no repair of a
    bad request.
    """
    decision = evaluate_delegated_candidate(sed, EDIT_FILE, path_candidate)
    if not decision.permitted:
        return _fail(
            ERR_REFUSED,
            "operation_not_permitted",
            decision.internal_reason,
            decision.relative_path,
        )

    relative = decision.relative_path or ""
    resolved = decision.resolved_path or ""

    # -- fixed dynamic preconditions, evaluated against AIDO-owned run state --
    if not run_state.has_read_receipt(relative):
        return _fail(
            ERR_REFUSED,
            "operation_not_permitted",
            "write_after_read_precondition_unsatisfied",
            relative,
        )
    if not run_state.receipt_matches(relative, base_sha256):
        return _fail(
            ERR_STALE_BASE,
            "base_sha256_does_not_match_the_latest_read",
            "presented_base_does_not_match_aido_receipt",
            relative,
        )
    if not old_text:
        return _fail(
            ERR_NO_UNIQUE_MATCH, "old_text_must_be_non_empty", "empty_old_text", relative
        )

    descriptor, failure = _open_verified(resolved, _OPEN_WRITE_FLAGS)
    if failure is not None:
        return _fail(ERR_REFUSED, "operation_not_permitted", failure, relative)

    try:
        identity_before = _identity(os.fstat(descriptor))
        size = os.fstat(descriptor).st_size
        if size > sed.caps.max_read_bytes_per_file:
            return _fail(
                ERR_TOO_LARGE, "file_exceeds_per_file_cap", "pre_image_over_cap", relative
            )
        os.lseek(descriptor, 0, os.SEEK_SET)
        pre_image = os.read(descriptor, size) if size else b""
        if len(pre_image) != size:
            return _fail(
                ERR_REFUSED, "operation_not_permitted", "short_read_under_handle", relative
            )

        if b"\x00" in pre_image:
            return _fail(ERR_NOT_TEXT, "content_is_not_utf8_text", "nul_byte_present", relative)
        try:
            pre_text = pre_image.decode("utf-8", "strict")
        except UnicodeDecodeError:
            return _fail(
                ERR_NOT_TEXT, "content_is_not_utf8_text", "strict_utf8_decode_failed", relative
            )

        pre_digest = _sha256(pre_image)
        if pre_digest.lower() != base_sha256.lower():
            return _fail(
                ERR_STALE_BASE,
                "the file's current bytes do not match base_sha256",
                "on_disk_bytes_do_not_match_presented_base",
                relative,
            )

        occurrences = pre_text.count(old_text)
        if occurrences != 1:
            return _fail(
                ERR_NO_UNIQUE_MATCH,
                "old_text must occur exactly once",
                f"occurrence_count_{occurrences}",
                relative,
            )

        offset = pre_text.index(old_text)
        post_text = pre_text[:offset] + new_text + pre_text[offset + len(old_text):]
        post_image = post_text.encode("utf-8")

        if len(post_image) > sed.caps.max_post_image_bytes:
            return _fail(
                ERR_TOO_LARGE, "post_image_exceeds_cap", "post_image_over_cap", relative
            )
        budget_failure = run_state.edit_budget_allows(relative, len(post_image))
        if budget_failure is not None:
            return _fail(ERR_BUDGET_EXHAUSTED, "run_budget_exhausted", budget_failure, relative)

        # -- revalidate the FULL chain immediately before the mutation --------
        revalidation = evaluate_delegated_candidate(sed, EDIT_FILE, path_candidate)
        if not revalidation.permitted or revalidation.relative_path != relative:
            return _fail(
                ERR_REFUSED,
                "operation_not_permitted",
                "revalidation_before_mutation_failed",
                relative,
            )
        if _identity(os.fstat(descriptor)) != identity_before:
            # This can only trip if the descriptor itself somehow changed
            # identity mid-call, which os.fstat on a still-open handle cannot
            # observe on its own -- kept as a cheap, harmless belt-and-braces
            # check. It is NOT the TOCTOU proof; the next check is.
            return _fail(
                ERR_REFUSED, "operation_not_permitted", "handle_identity_changed", relative
            )

        # THE actual TOCTOU proof this revalidation exists for. The checks
        # above prove the STRING the second validation resolved still names the
        # same relative path, and that the open HANDLE's own identity has not
        # somehow drifted -- neither proves that the PATH still names the SAME
        # FILESYSTEM OBJECT the handle has open. A rename-and-replace, a
        # delete-and-recreate, or any other component swap in the window
        # between the initial open and this instant would leave the handle
        # pointing at the OLD (possibly now-unlinked) file while a fresh
        # ``os.stat`` of the resolved path would report the NEW one -- and
        # their identities would differ. Compare a FRESH, independent stat of
        # the just-revalidated resolved path against the open handle's own
        # identity; any mismatch refuses before a single byte is touched, and
        # the already-open, already-identity-verified handle is never reopened
        # to "fix" this -- a mismatch is terminal for this edit.
        try:
            fresh_stat = os.stat(revalidation.resolved_path)
        except OSError:
            return _fail(
                ERR_REFUSED,
                "operation_not_permitted",
                "resolved_path_could_not_be_restat_ed_before_mutation",
                relative,
            )
        if _identity(fresh_stat) != _identity(os.fstat(descriptor)):
            return _fail(
                ERR_REFUSED,
                "operation_not_permitted",
                "resolved_path_no_longer_names_the_open_handle",
                relative,
            )

        os.lseek(descriptor, 0, os.SEEK_SET)
        os.truncate(descriptor, 0)
        written = os.write(descriptor, post_image)
        if written != len(post_image):
            return _fail(
                ERR_INTERNAL_ERROR, "broker_failure", "short_write_under_handle", relative
            )
        os.fsync(descriptor)
    except OSError:
        return _fail(ERR_INTERNAL_ERROR, "broker_failure", "edit_raised_oserror", relative)
    finally:
        os.close(descriptor)

    post_digest = _sha256(post_image)
    run_state.record_edit(relative, post_digest, len(post_image))
    return _ok(
        {
            "applied": True,
            "bytes_after": len(post_image),
            "sha256_after": post_digest,
        },
        relative,
        f"edit applied at offset {offset}; receipt replaced with the post-image hash",
    )
