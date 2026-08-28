"""I2B -- synthetic, qualification-minted Category-B workspace authority.

**OFFLINE ONLY. This module launches nothing, opens no socket, calls no
model, and reads no credential.** It creates and verifies ONE disposable
directory tree per run, under the approved scratch boundary, and nothing
else.

Why this module exists (5F3B-I2B-FU2, design FU3 Sec. 8)
--------------------------------------------------------

The unaccepted I2B-FU1 controller took ``workspace_root: str`` and
``experiment_root: str`` as ARBITRARY caller-supplied strings, validated
only as "non-blank". They flowed unverified into the broker capability
scope, the runtime launch, the artifact safety needle, and -- worst -- into
``write_qualification_pi_config(experiment_root, ...)``, which performs
``Path(experiment_root) / "i2_pi_config"`` followed by ``mkdir``. Naming a
real project directory there was a well-typed call. That is unacceptable
while real-workspace authority is NO-GO.

**The correction is the one AR2-FU1A already made once, reused rather than
reinvented: authority originates at CREATION, never from a string.**
:func:`mint_qualification_run_workspace` calls the frozen, unmodified
``ar2.fixtures.create_disposable_experiment_root`` -- which itself always
creates a brand-new ``tempfile.mkdtemp()`` root under
``ar2.capability.approved_scratch_boundary()`` and writes its
exclusive-create marker in the same step -- and then creates exactly the
one repository child that authority names.

**There is deliberately NO function anywhere that accepts an existing path
and returns a :class:`QualificationRunWorkspace`.** That absence is the
whole property. It is also why the controller no longer has a parameter
through which a real workspace, a sibling project, or a parent directory
could be named at all: a real workspace is not "denied" here, it is
structurally unreachable.

What is verified, and when
--------------------------

An object is not authority. Every consumption boundary -- generated-config
generation, broker creation, runtime launch -- calls
:func:`verify_run_workspace`, which re-reads the on-disk marker through the
FROZEN AR2 verification rather than trusting the object or a previous
validation. Relocation, deletion, marker tampering and path substitution
all fail closed there, not merely at mint time.

Cross-run reuse is refused by a SINGLE-USE claim
(:func:`claim_run_workspace`): one minted workspace nonce may be claimed by
exactly one ``run_id``, once. A second claim -- by the same run or any
other -- is refused.

Honest scope (unchanged from AR2-FU1A)
--------------------------------------

This defends against an AIDO configuration or programming mistake -- a
stale variable, a copy-paste error, a future refactor handing the wrong
object across. It is **not** a defense against a same-user adversary, who
could forge a marker file trivially and does not need this code path at
all. This is also **not** a step toward real-workspace authority; it is the
opposite, and real-workspace authority remains NO-GO.
"""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field

from ar2.capability import DisposableRootAuthority, RootAuthorityError

# The frozen AR2 verification, reused EXACTLY rather than forked. It is
# underscore-prefixed inside AR2, but it is precisely the check
# ``ar2.capability.mint_capability`` itself performs on every mint (marker
# re-read, scratch-boundary membership, canonical-path and structural
# agreement, symlink/reparse refusal, denylist diagnostic). Re-implementing
# it here would create exactly the divergence risk the FU3 design forbids,
# and AR2 is frozen, so it cannot be re-exported under a public name.
from ar2.capability import _verify_root_authority as _frozen_verify_root_authority
from ar2.fixtures import create_disposable_experiment_root, remove_disposable_tree

#: The experiment identity stamped into every marker this module mints.
#: Recorded in the marker at creation time and re-checked on every
#: verification, so a root minted by some other experiment's creator is not
#: silently usable here.
QUALIFICATION_EXPERIMENT_ID = "5F3B-I2B-CATEGORY-B"

#: The fixed case id component of the fresh ``mkdtemp`` prefix. Not
#: caller-supplied: there is no parameter on this module's minting function
#: that influences WHERE the root is created.
QUALIFICATION_CASE_ID = "i2b"

_NONCE_BYTES = 16


class WorkspaceAuthorityError(Exception):
    """A qualification run workspace could not be proven. Always fails closed.

    **Never echoes a path.** Only a fixed, bounded reason code, exactly as
    :class:`qualification.i2_issuance.IssuanceError` already does for the
    generated-config issuance registry.
    """

    def __init__(self, reason_code: str) -> None:
        super().__init__(f"qualification run workspace refused: {reason_code}")
        self.reason_code = reason_code


@dataclass(frozen=True)
class _MintRecord:
    """One process-local minting fact. Never leaves this module.

    Holds the frozen :class:`~ar2.capability.DisposableRootAuthority` --
    including its marker nonce -- so verification re-derives authority from
    what AIDO's own creator recorded, never from fields a caller could place
    on the public value object.
    """

    authority: DisposableRootAuthority = field(repr=False)
    experiment_root: str = field(repr=False)
    workspace_root: str = field(repr=False)

    def __repr__(self) -> str:  # noqa: D105 - paths are never rendered
        return f"{type(self).__name__}(<bound>)"


#: Process-local, in-memory only. Never persisted, never an evidence field,
#: and carrying no claim of surviving a process restart. Keyed by the mint
#: nonce alone -- one nonce represents exactly one minted workspace.
_MINTED: dict[str, _MintRecord] = {}

#: nonce -> run_id. A SINGLE-USE claim; see :func:`claim_run_workspace`.
_CLAIMED: dict[str, str] = {}


@dataclass(frozen=True)
class QualificationRunWorkspace:
    """The ONE workspace identity a Category-B run has. Unforgeable by API.

    ``run_workspace_nonce`` is minted inside
    :func:`mint_qualification_run_workspace` and registered there BEFORE
    this object is constructed. ``__post_init__`` refuses any instance whose
    nonce is not registered, or whose paths do not match the ones registered
    with that nonce exactly -- so there is no supported way to obtain one of
    these for a directory this module did not create.

    ``experiment_root`` is the fresh disposable root; ``workspace_root`` is
    the repository child beneath it, and is the ONLY workspace identity the
    run has: the broker capability scope, the runtime launch, the generated
    Pi config's parent and the artifact safety needle all derive from this
    one object.

    Both paths are ``field(repr=False)`` *and* this class defines its own
    bounded ``__repr__`` -- two independent reasons an absolute path can
    never appear in a rendered value, matching this package's convention.
    """

    run_workspace_nonce: str
    experiment_root: str = field(repr=False)
    workspace_root: str = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.run_workspace_nonce, str) or not self.run_workspace_nonce:
            raise WorkspaceAuthorityError("MALFORMED_RUN_WORKSPACE_NONCE")
        record = _MINTED.get(self.run_workspace_nonce)
        if record is None:
            raise WorkspaceAuthorityError("NOT_MINTED_BY_QUALIFICATION")
        if (
            not isinstance(self.experiment_root, str)
            or not isinstance(self.workspace_root, str)
            or self.experiment_root != record.experiment_root
            or self.workspace_root != record.workspace_root
        ):
            raise WorkspaceAuthorityError("MINTED_PATH_MISMATCH")

    def __repr__(self) -> str:  # noqa: D105 - see class docstring
        return (
            f"{type(self).__name__}("
            f"run_workspace_nonce={self.run_workspace_nonce!r}, "
            "experiment_root=<bound>, workspace_root=<bound>)"
        )


def mint_qualification_run_workspace() -> QualificationRunWorkspace:
    """Create a FRESH disposable run workspace, and return its authority.

    **The one and only origin.** There is no parameter naming a path, a
    parent, a prefix or a root -- deliberately, so no caller can influence
    WHERE the tree is created. The location comes entirely from the frozen
    ``ar2.fixtures.create_disposable_experiment_root``
    (``tempfile.mkdtemp()`` under
    ``ar2.capability.approved_scratch_boundary()``), which also writes the
    exclusive-create marker every later verification re-reads.

    Exactly one directory is created beneath the fresh root: the
    ``repo_child_name`` child the authority itself names.
    """
    authority = create_disposable_experiment_root(
        case_id=QUALIFICATION_CASE_ID, experiment_id=QUALIFICATION_EXPERIMENT_ID
    )
    # Exactly the one prospective child the frozen authority names, and
    # nothing else. It cannot already exist: the root was created moments
    # ago by mkdtemp.
    os.mkdir(authority.repo_root)

    nonce = secrets.token_hex(_NONCE_BYTES)
    if nonce in _MINTED:  # pragma: no cover - a 128-bit collision
        raise WorkspaceAuthorityError("RUN_WORKSPACE_NONCE_ALREADY_MINTED")
    _MINTED[nonce] = _MintRecord(
        authority=authority,
        experiment_root=authority.experiment_root,
        workspace_root=authority.repo_root,
    )
    return QualificationRunWorkspace(
        run_workspace_nonce=nonce,
        experiment_root=authority.experiment_root,
        workspace_root=authority.repo_root,
    )


def verify_run_workspace(workspace: QualificationRunWorkspace) -> str:
    """Re-prove ``workspace`` AGAINST THE FILESYSTEM. Returns the repo root.

    Called at EVERY consumption boundary -- never once, and never trusted
    from a previous call. Raises :class:`WorkspaceAuthorityError` on any
    discrepancy: a forged or non-minted object, a path that no longer
    matches what was minted, a missing/tampered/relocated marker (via the
    frozen AR2 verification), a root that has left the approved scratch
    boundary, or a repository root that is no longer an existing directory.
    """
    if type(workspace) is not QualificationRunWorkspace:
        raise WorkspaceAuthorityError("NOT_A_QUALIFICATION_RUN_WORKSPACE")
    record = _MINTED.get(workspace.run_workspace_nonce)
    if record is None:
        raise WorkspaceAuthorityError("NOT_MINTED_BY_QUALIFICATION")
    if (
        workspace.experiment_root != record.experiment_root
        or workspace.workspace_root != record.workspace_root
    ):
        raise WorkspaceAuthorityError("MINTED_PATH_MISMATCH")

    # THE PROOF: the frozen AR2 marker verification, unmodified.
    try:
        verified_repo_root = _frozen_verify_root_authority(record.authority)
    except RootAuthorityError:
        raise WorkspaceAuthorityError("ROOT_AUTHORITY_UNVERIFIED") from None
    if verified_repo_root != workspace.workspace_root:
        raise WorkspaceAuthorityError("VERIFIED_ROOT_MISMATCH")

    # The repository root must still BE a directory: the frozen check proves
    # the marker and the structural relationship, not that the child AIDO
    # created is still there and still a directory.
    if not os.path.isdir(workspace.workspace_root):
        raise WorkspaceAuthorityError("WORKSPACE_ROOT_MISSING")
    if os.path.realpath(workspace.workspace_root) != workspace.workspace_root:
        raise WorkspaceAuthorityError("WORKSPACE_ROOT_NOT_CANONICAL")
    return verified_repo_root


def claim_run_workspace(workspace: QualificationRunWorkspace, *, run_id: str) -> None:
    """Verify, then claim this workspace for ``run_id`` -- exactly ONCE.

    Cross-run reuse and re-entry both fail closed: a nonce already claimed
    is refused regardless of which run presents it, including the run that
    claimed it. This preserves the controller's own per-run ``run_id`` nonce
    rather than replacing it, and is what binds one synthetic workspace to
    one invocation.
    """
    verify_run_workspace(workspace)
    if not isinstance(run_id, str) or not run_id:
        raise WorkspaceAuthorityError("MALFORMED_RUN_ID")
    if workspace.run_workspace_nonce in _CLAIMED:
        raise WorkspaceAuthorityError("RUN_WORKSPACE_ALREADY_CLAIMED")
    _CLAIMED[workspace.run_workspace_nonce] = run_id


def run_workspace_is_claimed_by(workspace: QualificationRunWorkspace, *, run_id: str) -> bool:
    """Whether this exact workspace is claimed by exactly this ``run_id``.

    A pure read. Consumed by the run-scoped request value objects so a
    workspace that belongs to another run -- or to no run at all -- cannot
    be bound into a broker creation or a runtime launch.
    """
    if type(workspace) is not QualificationRunWorkspace:
        return False
    return _CLAIMED.get(workspace.run_workspace_nonce) == run_id


def discard_run_workspace(workspace: QualificationRunWorkspace) -> None:
    """Forget a workspace's mint and claim records. Idempotent, no I/O."""
    if type(workspace) is not QualificationRunWorkspace:
        return
    _MINTED.pop(workspace.run_workspace_nonce, None)
    _CLAIMED.pop(workspace.run_workspace_nonce, None)


def remove_run_workspace(workspace: QualificationRunWorkspace) -> dict[str, object]:
    """Remove one disposable run workspace tree, then forget its records.

    Removal is delegated to the frozen, unmodified
    ``ar2.fixtures.remove_disposable_tree``, which VERIFIES removal rather
    than assuming it. This is a fixture/teardown convenience for the offline
    suite; the controller never calls it.
    """
    if type(workspace) is not QualificationRunWorkspace:
        raise WorkspaceAuthorityError("NOT_A_QUALIFICATION_RUN_WORKSPACE")
    result = remove_disposable_tree(workspace.experiment_root)
    discard_run_workspace(workspace)
    return result
