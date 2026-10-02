"""The OFFLINE evidence-reference verifier (PE-2b, PE-1 Sec. 9.9).

Review support ONLY. Runtime eligibility never depends on it, and the runtime
policy loader (:mod:`pi_profile_policy_loader`) never imports or calls it: the
loader checks a reference's SYNTAX only and never opens it.

For one ``{"repo_path", "sha256"}`` reference this composes PE-0 Sec. 4.14
exactly, and nothing broader:

1. the ``repo_path`` grammar (string checks only, before any filesystem
   access);
2. ``canonicalize_existing_path_under_workspace(<checkout root>, repo_path,
   allow_symlinks=False)`` -- lexical refusal of drive, UNC, device and other
   ambiguous forms, structural containment, and no link or reparse component --
   where the checkout root is derived from THIS module's own location, never
   from an argument;
3. a no-follow, one-handle read that must classify as a regular file, whose
   SHA-256 must equal the reference.

Digests are over the COMMITTED blob bytes (PE-1 Sec. 7.4 item 4): a checkout
whose working-tree bytes differ from the committed blob -- for example after
an end-of-line conversion -- fails this verifier CLOSED. It never normalizes.

It writes nothing, reads no environment variable, starts no process and runs
no Git: tracked state is verified by the reviewer's read-only Git procedure.
"""

from __future__ import annotations

from pathlib import Path

from ai_dev_orchestrator.workspace.canonical import (
    CanonicalPathAmbiguityError,
    CanonicalPathError,
    CanonicalPathInputError,
    CanonicalPathSymlinkError,
    canonicalize_existing_path_under_workspace,
)

from . import pi_fs_leaves
from .pi_fs_leaves import CLASSIFICATION_REGULAR_FILE, PayloadFileRead
from .pi_payload import is_lowercase_hex64
from .pi_profile_policy_loader import repo_path_is_valid

#: ``<ROOT>`` -- the checkout containing this module (two levels above the
#: CFG1 package directory), exactly as ``pi_identity`` derives its own.
_CHECKOUT_ROOT: str = str(Path(__file__).resolve().parents[2])

#: A resource bound on one referenced document read, not a product limit.
MAX_EVIDENCE_DOCUMENT_BYTES = 1073741824

EVIDENCE_REFERENCE_VERIFIED = "EVIDENCE_REFERENCE_VERIFIED"


class Cfg1EvidenceReferenceError(Exception):
    """One evidence reference failed offline verification. Closed code only."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(f"cfg1 pi evidence reference refused: {reason_code}")
        self.reason_code = reason_code


def _verify_reference_under(checkout_root: str, repo_path: object, sha256: object) -> str:
    if not repo_path_is_valid(repo_path):
        raise Cfg1EvidenceReferenceError("EVIDENCE_REPO_PATH_GRAMMAR")
    if not is_lowercase_hex64(sha256):
        raise Cfg1EvidenceReferenceError("EVIDENCE_DIGEST_MALFORMED")
    try:
        located = canonicalize_existing_path_under_workspace(
            checkout_root, repo_path, allow_symlinks=False
        )
    except CanonicalPathSymlinkError:
        raise Cfg1EvidenceReferenceError("EVIDENCE_PATH_LINK_COMPONENT") from None
    except CanonicalPathAmbiguityError:
        raise Cfg1EvidenceReferenceError("EVIDENCE_PATH_AMBIGUOUS") from None
    except CanonicalPathInputError:
        raise Cfg1EvidenceReferenceError("EVIDENCE_PATH_MISSING_OR_INVALID") from None
    except CanonicalPathError:
        raise Cfg1EvidenceReferenceError("EVIDENCE_PATH_NOT_CONTAINED") from None
    read = pi_fs_leaves.read_payload_file_digest(
        str(located.resolved_candidate), MAX_EVIDENCE_DOCUMENT_BYTES
    )
    if type(read) is not PayloadFileRead or read.classification != CLASSIFICATION_REGULAR_FILE:
        raise Cfg1EvidenceReferenceError("EVIDENCE_NOT_A_REGULAR_FILE")
    if read.within_bound is not True or read.stable is not True:
        raise Cfg1EvidenceReferenceError("EVIDENCE_UNREADABLE")
    if read.sha256 != sha256:
        raise Cfg1EvidenceReferenceError("EVIDENCE_DIGEST_MISMATCH")
    return EVIDENCE_REFERENCE_VERIFIED


def verify_evidence_reference(repo_path: object, sha256: object) -> str:
    """Verify ONE reference against this checkout. Raises on any failure."""
    return _verify_reference_under(_CHECKOUT_ROOT, repo_path, sha256)


def verify_evidence_references(refs: object) -> int:
    """Verify every ``{"repo_path", "sha256"}`` reference in a list, in order.

    Returns the number verified; the first failure raises.
    """
    if type(refs) is not list:
        raise Cfg1EvidenceReferenceError("EVIDENCE_REFS_MALFORMED")
    for item in refs:
        if type(item) is not dict or frozenset(item) != frozenset({"repo_path", "sha256"}):
            raise Cfg1EvidenceReferenceError("EVIDENCE_REFS_MALFORMED")
        verify_evidence_reference(item["repo_path"], item["sha256"])
    return len(refs)
