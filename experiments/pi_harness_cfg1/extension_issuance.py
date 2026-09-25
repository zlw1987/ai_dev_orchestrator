"""CFG1's extension-issuance registry -- the L11 authority object (FU1 AM-9).

Design ``PHASE_5F3B_HARNESS_CFG1_L1_BOUNDARY_FU1_DESIGN.md`` (R6) Sec. 9.2a
(E10, L14/L15/L24) and Sec. 9.2c-B/C/D.

The frozen ``ar2.pi_config.write_disposable_extension`` and
``scrub_generated_extension_config`` have no issuance, no file identity and no
handle-bound deletion: the scrubber derives ``ar2_config.ts`` BY PATHNAME and
unlinks whatever answers there. A pathname plus containment is not authority
over the object currently at that name. CFG1 therefore no longer calls either
function (both stay byte-for-byte as shipped for AR2's own callers) and uses
this registry instead, exactly mirroring :mod:`config_issuance`'s shape:

* registration requires the unforgeable L11 proofs -- a parentage proof and
  the exact children it was minted for -- minted inside an OPEN interval of
  kind ``extension``, which only the bound CFG1 extension writer's own code
  object can open (AM-10); a config interval is refused here;
* the record binds the directory's and EVERY child's ``(volume_serial,
  file_id)`` and every child's read-back SHA-256, and registration REFUSES
  unless each static child's digest equals its independent pin literal and
  ``ar2_config.ts``'s equals the verified-template output the writer produced
  (AM-14);
* there is no parameter naming a path anywhere here: every path is a pure
  function of a genuine, ACTIVE ``Cfg1RunWorkspace``, re-verified each time.

The token is process-local, in-memory only, never persisted, never an evidence
field, and never rendered. **A bool is evidence, never deletion authority**:
nothing here deletes anything.

**AMEND2 (Y6) supersedes AM-12's L24 mechanism.** L24 no longer unlinks
``ar2_config.ts``: each issuance privately owns ONE zero-access retained handle
to the exact ``ar2_config.ts`` object (acquired from the creating handle before
that handle is released) and L24 performs a handle-bound CONTENT scrub through
it (``win_config_authority.scrub_retire_retained``). No pathname grants L24
authority, ``NumberOfLinks`` is never a decision input, and namespace cleanup
is L27's alone.
"""

from __future__ import annotations

import hashlib
import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

from ai_dev_orchestrator.workspace.canonical import _is_symlink_or_reparse_point

from . import win_config_authority as win
from .extension_pins import (
    EXTENSION_SOURCE_NAMES,
    GENERATED_CONFIG_NAME,
    PINNED_EXTENSION_SOURCES,
)
from .run_workspace import (
    Cfg1RunWorkspace,
    Cfg1WorkspaceAuthorityError,
    verify_cfg1_run_workspace,
    workspace_is_registered,
)

#: The directory CFG1 creates inside the run's own owned workspace root --
#: the same name the frozen writer used, so ``build_pi_argv``'s extension entry
#: keeps its frozen shape.
CFG1_EXTENSION_DIR_NAME = "pi_extension"

#: Every child the L11 writer creates, in creation order: the four static
#: sources, then the token-bearing generated file LAST.
EXTENSION_CHILD_NAMES: tuple[str, ...] = EXTENSION_SOURCE_NAMES + (GENERATED_CONFIG_NAME,)

#: The frozen extension entry file (``build_pi_argv``'s ``--extension``).
EXTENSION_ENTRY_NAME = "index.ts"


class ExtensionIssuanceError(Exception):
    """An extension ownership claim could not be proven. Closed code only."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(f"cfg1 extension issuance refused: {reason_code}")
        self.reason_code = reason_code


@dataclass(frozen=True)
class _ExtensionIssuanceRecord:
    """One process-local extension issuance fact. Never leaves this module
    except as the read-only verified view :func:`verify_extension_issuance`
    returns to L14, L15 and L24."""

    run_workspace_nonce: str = field(repr=False)
    extension_dir: str = field(repr=False)
    entry_path: str = field(repr=False)
    config_path: str = field(repr=False)
    child_paths: tuple[tuple[str, str], ...] = field(repr=False)
    extension_dir_identity: tuple[int, int] = field(repr=False)
    child_identities: tuple[tuple[str, tuple[int, int]], ...] = field(repr=False)
    child_sha256: tuple[tuple[str, str], ...] = field(repr=False)
    #: **AMEND2 (Y6).** The private retained exact-object authority for
    #: ``ar2_config.ts`` (RA-5). Carries a nonce only; never rendered.
    retained: object = field(repr=False, default=None)

    @property
    def config_identity(self) -> tuple[int, int]:
        """The issued ``ar2_config.ts`` identity, as recorded at registration."""
        return dict(self.child_identities)[GENERATED_CONFIG_NAME]

    def __repr__(self) -> str:  # noqa: D105 - paths are never rendered
        return f"{type(self).__name__}(<bound>)"


#: token -> record. Process-local, in-memory only.
_ISSUED_EXTENSIONS: dict[str, _ExtensionIssuanceRecord] = {}

_TOKEN_BYTES = 16


def derive_cfg1_extension_paths(workspace: Cfg1RunWorkspace) -> tuple[str, dict[str, str]]:
    """The ONE derivation of one run's extension paths. No path parameter.

    Re-verifies ``workspace`` first; the directory is the workspace's own
    re-proven ``experiment_root`` plus the fixed literal ``pi_extension``, and
    each child is that directory plus its fixed name.
    """
    if type(workspace) is not Cfg1RunWorkspace:
        raise ExtensionIssuanceError("NOT_A_CFG1_RUN_WORKSPACE")
    try:
        verify_cfg1_run_workspace(workspace)
    except Cfg1WorkspaceAuthorityError as exc:
        raise ExtensionIssuanceError("WORKSPACE_AUTHORITY_UNVERIFIED") from exc
    extension_dir = str(Path(workspace.experiment_root) / CFG1_EXTENSION_DIR_NAME)
    children = {name: str(Path(extension_dir) / name) for name in EXTENSION_CHILD_NAMES}
    return extension_dir, children


def register_extension_issuance(
    *,
    workspace: Cfg1RunWorkspace,
    proven: win.ProvenConfigChildren,
    children: tuple,
    expected_config_sha256: str,
    retained: win.RetainedAuthority | None = None,
) -> str:
    """E10. Register the just-written extension -- the LAST step before return.

    ``children`` must be EXACTLY the five children the parentage proof was
    minted for, in creation order. Every digest is taken from bytes read back
    through the held descriptors, never by re-opening a pathname.

    **AMEND2 (Y6, RA-3/RA-5).** ``retained`` is the ``extension_token``
    authority acquired from the TOKEN child's creating handle only (static
    children get none). It must be the exact type and kind, minted in the same
    typed ``extension`` interval as the children, with an identity equal to
    ``ar2_config.ts``'s, and not already owned. The registry insert, which takes
    ownership, is the LAST statement.
    """
    extension_dir, child_paths = derive_cfg1_extension_paths(workspace)
    if type(proven) is not win.ProvenConfigChildren:
        raise ExtensionIssuanceError("PARENTAGE_NOT_PROVEN")
    if type(children) is not tuple or len(children) != len(EXTENSION_CHILD_NAMES):
        raise ExtensionIssuanceError("MALFORMED_CHILD_SET")
    for child in children:
        if type(child) is not win.ExclusiveChild:
            raise ExtensionIssuanceError("NOT_A_PROVEN_EXTENSION_CHILD")
    if type(expected_config_sha256) is not str or len(expected_config_sha256) != 64:
        raise ExtensionIssuanceError("MALFORMED_EXPECTED_DIGEST")
    # ORIGIN first, and typed: only an OPEN extension interval qualifies.
    try:
        win.require_extension_issuance_provenance(proven, children)
    except win.Cfg1DirectoryAuthorityError as exc:
        raise ExtensionIssuanceError("ISSUANCE_PROVENANCE_NOT_PROVEN") from exc
    try:
        win.require_proven_children(proven, children)
        extension_dir_identity = win.proven_config_identity(proven)
        names = tuple(win.child_name(child) for child in children)
        if names != EXTENSION_CHILD_NAMES:
            raise ExtensionIssuanceError("EXTENSION_CHILD_NAME_MISMATCH")
        identities = []
        digests = []
        for name, child in zip(names, children):
            identities.append((name, win.child_identity(child)))
            digests.append((name, hashlib.sha256(win.read_child_bytes(child)).hexdigest()))
    except win.Cfg1DirectoryAuthorityError as exc:
        raise ExtensionIssuanceError("GENERATED_FILES_UNREADABLE") from exc

    by_name = dict(digests)
    for name in EXTENSION_SOURCE_NAMES:
        if by_name[name] != PINNED_EXTENSION_SOURCES[name][1]:
            raise ExtensionIssuanceError("STATIC_CHILD_DIGEST_NOT_PINNED")
    if by_name[GENERATED_CONFIG_NAME] != expected_config_sha256:
        raise ExtensionIssuanceError("GENERATED_CONFIG_DIGEST_MISMATCH")

    try:
        if type(retained) is not win.RetainedAuthority:
            raise ExtensionIssuanceError("RETAINED_AUTHORITY_NOT_BOUND")
        if win.retained_kind(retained) != win.RETAINED_KIND_EXTENSION_TOKEN:
            raise ExtensionIssuanceError("RETAINED_AUTHORITY_NOT_BOUND")
        if win.retained_interval_nonce(retained) != win.child_interval_nonce(children[-1]):
            raise ExtensionIssuanceError("RETAINED_AUTHORITY_NOT_BOUND")
        if win.retained_identity(retained) != dict(identities)[GENERATED_CONFIG_NAME]:
            raise ExtensionIssuanceError("RETAINED_AUTHORITY_NOT_BOUND")
    except win.Cfg1DirectoryAuthorityError as exc:
        raise ExtensionIssuanceError("RETAINED_AUTHORITY_NOT_BOUND") from exc
    if any(
        record.retained is not None and record.retained.nonce == retained.nonce
        for record in _ISSUED_EXTENSIONS.values()
    ):
        raise ExtensionIssuanceError("RETAINED_AUTHORITY_ALREADY_OWNED")

    token = secrets.token_hex(_TOKEN_BYTES)
    if token in _ISSUED_EXTENSIONS:  # pragma: no cover - a 128-bit collision
        raise ExtensionIssuanceError("ISSUANCE_TOKEN_ALREADY_REGISTERED")
    # The insert, which takes ownership of ``retained``, is the LAST statement.
    _ISSUED_EXTENSIONS[token] = _ExtensionIssuanceRecord(
        run_workspace_nonce=workspace.run_workspace_nonce,
        extension_dir=extension_dir,
        entry_path=child_paths[EXTENSION_ENTRY_NAME],
        config_path=child_paths[GENERATED_CONFIG_NAME],
        child_paths=tuple((name, child_paths[name]) for name in EXTENSION_CHILD_NAMES),
        extension_dir_identity=extension_dir_identity,
        child_identities=tuple(identities),
        child_sha256=tuple(digests),
        retained=retained,
    )
    return token


def _digest(path: str) -> str:
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def _require_not_redirected(path: str) -> os.stat_result:
    try:
        lexical = os.lstat(path)
    except OSError as exc:
        raise ExtensionIssuanceError("GENERATED_FILES_UNREADABLE") from exc
    if _is_symlink_or_reparse_point(lexical):
        raise ExtensionIssuanceError("GENERATED_PATH_REDIRECTED")
    return lexical


def verify_extension_issuance(*, token: str, workspace: Cfg1RunWorkspace) -> _ExtensionIssuanceRecord:
    """Re-prove the issuance at a consumption boundary (L14, L15, L24). Fresh each time.

    Every path is re-derived from ``workspace`` -- never read from a
    caller-mutable attribute -- and must equal the recorded one; the workspace
    nonce must match; the directory must still be unredirected AND still the
    issued directory object by file id; every static child must still be
    present, unredirected, and hash to its issued digest; ``ar2_config.ts`` is
    re-digested while it is still present (after L24's scrub it is zero-length,
    but no consumer verifies after L24: the entry is gone by then).
    Residual, stated not closed: the check->use sliver after this re-digest.
    """
    if type(token) is not str or not token:
        raise ExtensionIssuanceError("MALFORMED_ISSUANCE_TOKEN")
    record = _ISSUED_EXTENSIONS.get(token)
    if record is None:
        raise ExtensionIssuanceError("UNKNOWN_ISSUANCE_TOKEN")
    if (
        type(workspace) is not Cfg1RunWorkspace
        or workspace.run_workspace_nonce != record.run_workspace_nonce
    ):
        raise ExtensionIssuanceError("ISSUANCE_WORKSPACE_MISMATCH")
    extension_dir, child_paths = derive_cfg1_extension_paths(workspace)
    if extension_dir != record.extension_dir or tuple(
        (name, child_paths[name]) for name in EXTENSION_CHILD_NAMES
    ) != record.child_paths:
        raise ExtensionIssuanceError("ISSUANCE_PATH_MISMATCH")

    lexical_dir = _require_not_redirected(extension_dir)
    if (lexical_dir.st_dev, lexical_dir.st_ino) != record.extension_dir_identity:
        raise ExtensionIssuanceError("EXTENSION_DIR_IDENTITY_MISMATCH")

    recorded = dict(record.child_sha256)
    try:
        for name in EXTENSION_CHILD_NAMES:
            path = child_paths[name]
            if name == GENERATED_CONFIG_NAME and not os.path.lexists(path):
                continue
            _require_not_redirected(path)
            if _digest(path) != recorded[name]:
                raise ExtensionIssuanceError("EXTENSION_CONTENT_MISMATCH")
    except OSError as exc:
        raise ExtensionIssuanceError("GENERATED_FILES_UNREADABLE") from exc
    return record


def reclaim_extension_issuance(retained: object) -> bool:
    """RECLAIM (writer only): take a registered retained authority back. No I/O.

    Keyed by the retained authority ITSELF, never by a token string or a path
    (RA-5), so a registration that committed without the writer learning its
    token is still found. Idempotent.
    """
    if type(retained) is not win.RetainedAuthority:
        return False
    for token, record in list(_ISSUED_EXTENSIONS.items()):
        held = record.retained
        if held is not None and held.nonce == retained.nonce:
            _ISSUED_EXTENSIONS.pop(token, None)
            return True
    return False


def scrub_extension_issuance(*, token: object, workspace: object) -> bool:
    """L24 for ``ar2_config.ts``: retire the issuance WITH a handle-bound scrub.

    The exact counterpart of :func:`config_issuance.scrub_config_issuance`: the
    authority is the genuine ACTIVE entry of THIS kind whose
    ``run_workspace_nonce`` equals the run's genuine, still-registered
    workspace; no pathname, path field, identity or digest is consulted; the
    entry is removed first (single-shot); ``True`` only after SCRUB-R completed
    and every handle it had to release was released. Any ownership failure is
    ``False`` with the entry untouched and no I/O.
    """
    if type(token) is not str or not token:
        return False
    record = _ISSUED_EXTENSIONS.get(token)
    if record is None:
        return False
    if (
        not workspace_is_registered(workspace)
        or workspace.run_workspace_nonce != record.run_workspace_nonce
    ):
        return False
    _ISSUED_EXTENSIONS.pop(token, None)
    return win.scrub_retire_retained(record.retained)


def discard_extension_issuance(token: object) -> bool:
    """Retire one extension issuance for cleanup, scrubbing rather than popping.

    A pure pop would strand the retained handle (RA-6). No L24 ownership check;
    idempotent, and an unknown token does nothing and returns ``False``.
    """
    if type(token) is not str:
        return False
    record = _ISSUED_EXTENSIONS.pop(token, None)
    if record is None:
        return False
    return win.scrub_retire_retained(record.retained)


def issued_extension_token_count() -> int:
    """How many extension issuances are still registered (Sec. 19.1 item 4)."""
    return len(_ISSUED_EXTENSIONS)
