"""CFG1's run-workspace registry -- ownership by mint, claim, and re-proof.

Design Sec. 17 row 2 and Sec. 7.5 item 2. Mirrors the already-accepted
``qualification.i2b_workspace`` shape as NEW, CFG1-owned code, and follows that
module's own accepted precedent of a locally-aliased import of the frozen
``ar2.capability._verify_root_authority``. No frozen module is amended.

**The only origin of root authority is the frozen creator.** There is
deliberately no parameter naming a path, a parent, a prefix or a root, and
there is no ``stamp_this_existing_directory_as_disposable()`` under any name:
a directory that was not built through ``ar2.fixtures.build_case_repository``
can never become an authorized one. Ownership is provable only once the
authority object has been RETURNED -- which is exactly why Sec. 18 row 13's
partial mint leaves an orphan that is never deleted.
"""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field

from ar2.capability import DisposableRootAuthority, RootAuthorityError
from ar2.capability import _verify_root_authority as _frozen_verify_root_authority
from ar2.fixtures import BuiltFixture, build_case_repository, remove_disposable_tree

from .fixture import CFG1_T1
from .win_config_authority import Cfg1DirectoryAuthorityError, directory_identity_of_path


class Cfg1WorkspaceAuthorityError(Exception):
    """A run-workspace ownership claim could not be proven."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(f"cfg1 run workspace refused: {reason_code}")
        self.reason_code = reason_code


@dataclass(frozen=True)
class _WorkspaceMintRecord:
    """One process-local minting fact. Never leaves this module."""

    authority: DisposableRootAuthority = field(repr=False)
    experiment_root: str = field(repr=False)
    workspace_root: str = field(repr=False)
    head_before: str = field(repr=False)
    tracked_paths: tuple[str, ...] = field(repr=False)
    #: Sec. 37.3.1 step 1 (the FU15 L2 addendum). The owned root's
    #: ``(volume_serial, file_id)``, read at the instant the frozen creator
    #: returned it. From here on the owned root has an IDENTITY, not only a
    #: name, and L9 re-proves that identity from a handle before it creates
    #: anything -- so a root moved aside and replaced by an ordinary directory
    #: of the same name is refused rather than written into.
    experiment_root_identity: tuple[int, int] = field(repr=False)

    def __repr__(self) -> str:  # noqa: D105 - paths are never rendered
        return f"{type(self).__name__}(<bound>)"


_MINTED: dict[str, _WorkspaceMintRecord] = {}
_CLAIMED: dict[str, str] = {}

_NONCE_BYTES = 16


@dataclass(frozen=True)
class Cfg1RunWorkspace:
    """The ONE workspace identity a CFG1 run has. Unforgeable by API.

    ``__post_init__`` refuses any instance whose nonce is unregistered, or
    whose paths do not match the ones registered with that nonce exactly -- so
    there is no supported way to obtain one of these for a directory this
    module did not create.
    """

    run_workspace_nonce: str = field(repr=False)
    experiment_root: str = field(repr=False)
    workspace_root: str = field(repr=False)

    def __post_init__(self) -> None:
        if type(self.run_workspace_nonce) is not str or not self.run_workspace_nonce:
            raise Cfg1WorkspaceAuthorityError("MALFORMED_RUN_WORKSPACE_NONCE")
        record = _MINTED.get(self.run_workspace_nonce)
        if record is None:
            raise Cfg1WorkspaceAuthorityError("NOT_MINTED_BY_CFG1")
        if (
            self.experiment_root != record.experiment_root
            or self.workspace_root != record.workspace_root
        ):
            raise Cfg1WorkspaceAuthorityError("MINTED_PATH_MISMATCH")

    def __repr__(self) -> str:  # noqa: D105 - paths are never rendered
        return f"{type(self).__name__}(<bound>)"


def mint_cfg1_run_workspace(*, git_executable: str) -> tuple[Cfg1RunWorkspace, BuiltFixture]:
    """Build a FRESH disposable ``CFG1-T1`` repository and register its authority.

    Returns the ownership handle AND the frozen builder's own
    :class:`~ar2.fixtures.BuiltFixture`, because the run needs its
    ``head_before`` and tracked manifest for L3's baseline observation. The
    :class:`~ar2.capability.DisposableRootAuthority` itself is never returned,
    never stored on a public object, never logged, and never placed in an
    evidence field.
    """
    built = build_case_repository(CFG1_T1, git_executable=git_executable)
    # The FU15 L2 addendum, taken BEFORE the nonce exists, so a root whose
    # identity cannot be read never becomes a registered authority at all. A
    # failure here leaves the frozen creator's tree as the already-frozen
    # Sec. 18 row 13 orphan: unregistered, and therefore never deleted.
    try:
        root_identity = directory_identity_of_path(built.experiment_root)
    except Cfg1DirectoryAuthorityError as exc:
        raise Cfg1WorkspaceAuthorityError("ROOT_IDENTITY_UNREADABLE") from exc
    nonce = secrets.token_hex(_NONCE_BYTES)
    if nonce in _MINTED:  # pragma: no cover - a 128-bit collision
        raise Cfg1WorkspaceAuthorityError("RUN_WORKSPACE_NONCE_ALREADY_MINTED")
    _MINTED[nonce] = _WorkspaceMintRecord(
        authority=built.authority,
        experiment_root=built.experiment_root,
        workspace_root=built.repo_root,
        head_before=built.head_before,
        tracked_paths=tuple(built.tracked_paths),
        experiment_root_identity=root_identity,
    )
    workspace = Cfg1RunWorkspace(
        run_workspace_nonce=nonce,
        experiment_root=built.experiment_root,
        workspace_root=built.repo_root,
    )
    return workspace, built


def verify_cfg1_run_workspace(workspace: object) -> str:
    """Re-prove ``workspace`` AGAINST THE FILESYSTEM. Returns the repo root.

    Called at EVERY consumption boundary -- never once, and never trusted from
    a previous call. THE proof is the frozen AR2 marker verification,
    unmodified: a re-read of the exclusive-create nonce marker AIDO's own
    creator wrote, plus the scratch-boundary and canonical-path checks.
    """
    if type(workspace) is not Cfg1RunWorkspace:
        raise Cfg1WorkspaceAuthorityError("NOT_A_CFG1_RUN_WORKSPACE")
    record = _MINTED.get(workspace.run_workspace_nonce)
    if record is None:
        raise Cfg1WorkspaceAuthorityError("NOT_MINTED_BY_CFG1")
    if (
        workspace.experiment_root != record.experiment_root
        or workspace.workspace_root != record.workspace_root
    ):
        raise Cfg1WorkspaceAuthorityError("MINTED_PATH_MISMATCH")

    try:
        verified_repo_root = _frozen_verify_root_authority(record.authority)
    except RootAuthorityError:
        raise Cfg1WorkspaceAuthorityError("ROOT_AUTHORITY_UNVERIFIED") from None
    if verified_repo_root != workspace.workspace_root:
        raise Cfg1WorkspaceAuthorityError("VERIFIED_ROOT_MISMATCH")
    if not os.path.isdir(workspace.workspace_root):
        raise Cfg1WorkspaceAuthorityError("WORKSPACE_ROOT_MISSING")
    if os.path.realpath(workspace.workspace_root) != workspace.workspace_root:
        raise Cfg1WorkspaceAuthorityError("WORKSPACE_ROOT_NOT_CANONICAL")
    return verified_repo_root


def registered_authority(workspace: Cfg1RunWorkspace) -> DisposableRootAuthority:
    """The registered authority object, for the frozen capability mint only.

    Verified first, every time. Never returned to, or reachable from, anything
    outside this package's own run executor.
    """
    verify_cfg1_run_workspace(workspace)
    return _MINTED[workspace.run_workspace_nonce].authority


def registered_baseline(workspace: Cfg1RunWorkspace) -> tuple[str, tuple[str, ...]]:
    """``(head_before, tracked_paths)`` as the frozen creator recorded them."""
    verify_cfg1_run_workspace(workspace)
    record = _MINTED[workspace.run_workspace_nonce]
    return record.head_before, record.tracked_paths


def registered_root_identity(workspace: Cfg1RunWorkspace) -> tuple[int, int]:
    """The owned root's identity as it was at mint time (Sec. 37.3.1 step 1).

    Verified first, every time. This is the ONLY baseline L9's root pin is
    allowed to compare against: it was read before any adversary had a name to
    race against, and it is never re-derived from the path afterwards, because
    re-reading a name is exactly the racy re-proof Sec. 37.2 rejects.
    """
    verify_cfg1_run_workspace(workspace)
    return _MINTED[workspace.run_workspace_nonce].experiment_root_identity


def claim_cfg1_run_workspace(workspace: Cfg1RunWorkspace, *, run_id: str) -> None:
    """Verify, then claim this workspace for ``run_id`` -- exactly ONCE.

    Cross-run reuse and re-entry both fail closed: a nonce already claimed is
    refused regardless of which run presents it, including the run that claimed
    it. This is what binds one synthetic workspace to one invocation.
    """
    verify_cfg1_run_workspace(workspace)
    if type(run_id) is not str or not run_id:
        raise Cfg1WorkspaceAuthorityError("MALFORMED_RUN_ID")
    if workspace.run_workspace_nonce in _CLAIMED:
        raise Cfg1WorkspaceAuthorityError("RUN_WORKSPACE_ALREADY_CLAIMED")
    _CLAIMED[workspace.run_workspace_nonce] = run_id


def workspace_is_claimed_by(workspace: object, *, run_id: str) -> bool:
    """Whether this exact workspace is claimed by exactly this ``run_id``."""
    if type(workspace) is not Cfg1RunWorkspace:
        return False
    return _CLAIMED.get(workspace.run_workspace_nonce) == run_id


def discard_cfg1_run_workspace(workspace: object) -> None:
    """Forget a workspace's mint and claim records. Idempotent, no I/O."""
    if type(workspace) is not Cfg1RunWorkspace:
        return
    _MINTED.pop(workspace.run_workspace_nonce, None)
    _CLAIMED.pop(workspace.run_workspace_nonce, None)


def remove_cfg1_run_workspace(workspace: object) -> dict[str, object]:
    """L27 -- re-prove authority, then remove the tree, then forget the records.

    Removal is delegated to the frozen, unmodified
    ``ar2.fixtures.remove_disposable_tree``, which VERIFIES removal rather than
    assuming it. A root this registry cannot prove CFG1 created is never
    deleted, whatever its name looks like.
    """
    if type(workspace) is not Cfg1RunWorkspace:
        raise Cfg1WorkspaceAuthorityError("NOT_A_CFG1_RUN_WORKSPACE")
    verify_cfg1_run_workspace(workspace)
    result = remove_disposable_tree(workspace.experiment_root)
    discard_cfg1_run_workspace(workspace)
    return result


def minted_workspace_count() -> int:
    """How many run workspaces are still registered (Sec. 19.1 item 4)."""
    return len(_MINTED)
