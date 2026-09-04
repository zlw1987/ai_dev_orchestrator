"""I2B -- synthetic, qualification-minted Category-B workspace authority.

**OFFLINE ONLY. This module opens no socket, calls no model, and reads no
credential.** It creates and verifies ONE disposable directory tree per run,
under the approved scratch boundary.

Process abstinence -- NARROWED by 5F3B-LIVE1-C1, deliberately
--------------------------------------------------------------

This docstring previously opened with *"This module launches nothing."* That
sentence is no longer true, and it is corrected here rather than left to be
quietly falsified (design Sec. 2.6.5a, chosen option **A**). Exactly:

```text
Category-B path          launches nothing, exactly as before -- every
                         function used by run_category_b_controller and by
                         qualification.i2b_live_adapters' ORDINARY broker
                         creation runs zero subprocesses.

semantic issuance path   runs the accepted fixed, READ-ONLY Git observation
                         ONCE, through ar2.observation.observe_repository,
                         at the root verify_run_workspace JUST returned, with
                         the executable the accepted resolve_git_executable
                         independently resolves for that verified root
                         (C1-P12b). Nothing else.
```

Everything else this module refused, it still refuses: no socket, no model
call, no credential read, no environment read, no arbitrary process launch,
and -- the property that actually matters here -- still **no function
anywhere that converts an existing path into a**
:class:`QualificationRunWorkspace`. The process authority added above is
bound to the same unforgeable object as every other operation in this
module, so the path-authority property is untouched.

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

# -- 5F3B-LIVE1-C1: the EXACT, CLOSED set of process-capable dependencies ----
#
# These seven symbols are the whole of the widening Sec. 2.6.5a authorizes.
# Exactly ONE of them can launch a process -- ``observe_repository``; a
# second, ``resolve_git_executable``, decides WHICH program it launches; the
# remaining five are the frozen eligibility algorithm, its returned product,
# and three fail-closed error types. The strengthened purity test
# ``tests/test_i2b_controller.py::test_no_i2b_module_imports_a_live_io_primitive``
# pins them as an exact closed set: any other ``ar2`` symbol, and any other
# process-capable dependency, fails that test loudly rather than arriving
# transitively and silently.
from ai_dev_orchestrator.workspace.git_adapter import (
    GitExecutableError,
    resolve_git_executable,
)
from ar2.capability import CapabilityMintError, StaticEligibilityDomain, mint_capability
from ar2.observation import ObservationError, observe_repository

from .corpus import TASKS_BY_ID, QualificationTask

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
    """Forget a workspace's mint, claim, and semantic-issuance records.

    Idempotent, no I/O. **5F3B-LIVE1-C1-FU1:** also retires the
    workspace-level semantic capability-issuance authority (if any) for this
    nonce -- forward-referencing ``_WORKSPACE_SEMANTIC_ISSUANCE``, which this
    function's earlier accepted version predates. That name is resolved at
    CALL time, not at definition time, so this is not a load-order defect.
    """
    if type(workspace) is not QualificationRunWorkspace:
        return
    _MINTED.pop(workspace.run_workspace_nonce, None)
    _CLAIMED.pop(workspace.run_workspace_nonce, None)
    _WORKSPACE_SEMANTIC_ISSUANCE.pop(workspace.run_workspace_nonce, None)


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


# ===========================================================================
# 5F3B-LIVE1-C1 -- semantic capability issuance
# ===========================================================================
#
# WHY THIS EXISTS. ``qualification.i2b_live_adapters``'s ordinary broker
# capability is ``_build_inert_static_eligibility_domain`` -- "a real, valid,
# but STRUCTURALLY POWERLESS capability" (``manifest=()``,
# ``read_eligible=frozenset()``, ``write_eligible=frozenset()``). That is
# exactly right for Category-B, which sends zero prompts by definition, and
# unusable for a semantic task, under which ``ar2.candidate`` would refuse
# EVERY read and EVERY edit at layer L2 -- a refusal that would then read as
# candidate behaviour rather than as harness inertness.
#
# WHAT IS AND IS NOT DERIVED. Every authority fact below is DERIVED, never
# accepted (design Sec. 2.6.3 / Sec. 2.6.5):
#
#   authority                  this workspace's own ``_MINTED`` record
#   tracked_manifest           AIDO's own Git observation of THIS repository
#   protected_patterns         task.case.protected_patterns
#   verification_witness_paths task.case.verification_witness_paths
#   caps                       ar2.capability.CapDefinitions() defaults
#   canonical_root             produced INSIDE mint_capability
#   the git executable         resolve_git_executable(workspace_root=...)
#
# There is deliberately NO parameter through which a caller can supply a
# manifest, a protected set, a witness set, a canonical root, a
# ``CapDefinitions`` override, a capability id, a
# :class:`~ar2.capability.StaticEligibilityDomain`, a git executable, or a
# factory/callback of any of those. A caller that could name the manifest
# could name any manifest; a caller that could pass a domain factory could
# pass any domain at all. Both shapes were considered and REFUSED.
#
# WHAT IS RETURNED. The freshly minted
# :class:`~ar2.capability.StaticEligibilityDomain` -- the mint's PRODUCT, the
# one value ``BrokerRequestHandler`` genuinely consumes. The
# :class:`~ar2.capability.DisposableRootAuthority` itself is never returned,
# never stored on a public object, never logged, and never placed in an
# evidence field, and nothing here returns a value from which one could be
# reconstructed (C1-P2).

#: The module-private key :class:`SemanticCapabilityGrant`'s constructor
#: demands. Never exported, never a string, never derivable -- the exact
#: ``_IDENTITY_ISSUER_KEY`` discipline ``i2b_live_adapters`` already uses for
#: its one-shot runtime-identity issuance.
_SEMANTIC_GRANT_ISSUER_KEY = object()


@dataclass
class _SemanticGrantRecord:
    """One semantic issuance grant. ``consumed`` makes the grant ONE-SHOT.

    Holds the FROZEN corpus :class:`~qualification.corpus.QualificationTask`
    object itself -- not a copy, and not a caller-authored description of
    one -- plus the identity snapshot taken when the grant was made, so
    consumption can prove the task did not drift underneath it.
    """

    task: QualificationTask = field(repr=False)
    task_id: str = ""
    task_revision: str = ""
    consumed: bool = False
    #: Audit-only, written at consumption. Never a path, never an authority.
    bound_run_workspace_nonce: str | None = None
    bound_run_id: str | None = None
    bound_capability_id: str | None = None

    def __repr__(self) -> str:  # noqa: D105 - the task contract is never rendered
        return f"{type(self).__name__}(<bound>)"


#: Process-local, in-memory only. Never persisted, never an evidence field,
#: and carrying no claim of surviving a process restart -- the identical
#: shape ``_MINTED`` / ``_CLAIMED`` above already use.
_SEMANTIC_GRANTS: dict[str, _SemanticGrantRecord] = {}


@dataclass
class _WorkspaceSemanticIssuanceRecord:
    """One workspace's semantic capability-issuance authority (5F3B-LIVE1-C1-FU1).

    **C1-P8 is workspace-level, not merely grant-level.** The grant's own
    ``consumed`` flag (above) proves a SPECIFIC ``SemanticCapabilityGrant``
    object cannot be replayed twice. It does NOT, by itself, prove that a
    *workspace* can bear only one semantic issuance: nothing stopped a second,
    DISTINCT, genuinely-minted grant for the same task from being presented
    against the same already-issued workspace. This record closes that gap.

    It is consumed EXACTLY ONCE per workspace nonce, by
    :func:`_consume_workspace_semantic_issuance_authority`, unconditionally of
    which grant presented it and BEFORE Git resolution, observation or
    minting -- so a later failure at any of those steps can never let a
    second, fresh grant retry issuance against the same workspace. Holds only
    the consuming ``run_id``, for audit; it is never returned, logged, or
    placed in an evidence field.
    """

    run_id: str = field(repr=False)


#: Process-local, in-memory only -- the identical shape ``_MINTED`` /
#: ``_CLAIMED`` / ``_SEMANTIC_GRANTS`` above already use. Keyed by workspace
#: nonce, so it is orthogonal to (and enforced independently of) which grant
#: token was consumed.
_WORKSPACE_SEMANTIC_ISSUANCE: dict[str, _WorkspaceSemanticIssuanceRecord] = {}


def _consume_workspace_semantic_issuance_authority(
    workspace: QualificationRunWorkspace, *, run_id: str
) -> None:
    """Consume THIS workspace's one-and-only semantic issuance authority.

    Called once per :func:`issue_semantic_broker_capability` invocation, after
    the workspace has been verified and its claim by ``run_id`` re-proved, but
    BEFORE any Git resolution, observation or minting -- so a second call for
    the same workspace nonce refuses immediately, regardless of whether the
    first call's issuance goes on to succeed or to fail at a later step.
    """
    nonce = workspace.run_workspace_nonce
    if nonce in _WORKSPACE_SEMANTIC_ISSUANCE:
        raise WorkspaceAuthorityError("WORKSPACE_SEMANTIC_ISSUANCE_ALREADY_CONSUMED")
    _WORKSPACE_SEMANTIC_ISSUANCE[nonce] = _WorkspaceSemanticIssuanceRecord(run_id=run_id)


class SemanticCapabilityGrant:
    """An OPAQUE, one-shot authorization to issue ONE semantic capability.

    It carries an issuance token and nothing else. Every authority fact --
    the task, its protected patterns, its verification witnesses -- lives in
    this module's private registry, never on the object, so no caller-authored
    value can reach :func:`mint_capability`. ``repr()`` renders no path, no
    token and no task contract.

    A caller cannot construct one: the constructor demands a module-private
    key object. :func:`grant_semantic_capability_issuance` is the only mint,
    and it accepts only a task that IS one of the frozen corpus singletons.
    """

    __slots__ = ("_grant_token",)

    def __init__(self, issuer_key: object, *, grant_token: str) -> None:
        if issuer_key is not _SEMANTIC_GRANT_ISSUER_KEY:
            raise WorkspaceAuthorityError("SEMANTIC_GRANT_NOT_MINTED_BY_QUALIFICATION")
        self._grant_token = grant_token

    def __repr__(self) -> str:  # noqa: D105 - see class docstring
        return f"{type(self).__name__}(granted=True)"


def grant_semantic_capability_issuance(task: QualificationTask) -> SemanticCapabilityGrant:
    """Authorize exactly ONE later semantic capability issuance, for ``task``.

    ``task`` must BE one of the frozen ``qualification.corpus`` singletons --
    identity, not equality, exactly as
    ``qualification.semantic_controller.run_semantic_task_attempt`` already
    requires. A caller-constructed or ``dataclasses.replace``'d copy is
    refused here, which is what makes the protected-pattern and
    verification-witness policy underivable by a caller: a task whose
    ``protected_patterns`` were emptied is not the frozen singleton and can
    never reach :func:`mint_capability` through this path.

    Grants no workspace authority and reads no filesystem. The workspace and
    the run do not exist yet at this point (design Sec. 2.6.4a EVENT 1 vs
    EVENT 2); they are bound at consumption.
    """
    if type(task) is not QualificationTask:
        raise WorkspaceAuthorityError("NOT_A_QUALIFICATION_TASK")
    if TASKS_BY_ID.get(task.task_id) is not task:
        raise WorkspaceAuthorityError("NOT_A_FROZEN_CORPUS_TASK")
    token = secrets.token_hex(_NONCE_BYTES)
    if token in _SEMANTIC_GRANTS:  # pragma: no cover - a 128-bit collision
        raise WorkspaceAuthorityError("SEMANTIC_GRANT_TOKEN_ALREADY_MINTED")
    _SEMANTIC_GRANTS[token] = _SemanticGrantRecord(
        task=task, task_id=task.task_id, task_revision=task.task_revision
    )
    return SemanticCapabilityGrant(_SEMANTIC_GRANT_ISSUER_KEY, grant_token=token)


def issue_semantic_broker_capability(
    grant: object,
    *,
    workspace: QualificationRunWorkspace,
    run_id: str,
) -> StaticEligibilityDomain:
    """Consume ``grant`` ONCE and mint THIS task's genuine broker capability.

    Called from exactly one place: ``qualification.i2b_live_adapters``'
    ``create_broker``, on the narrow semantic construction path, with the
    ``run_id`` and ``workspace`` the frozen ``BrokerCreationRequest`` itself
    carries (design Sec. 2.6.4a EVENT 2). ``read_connection`` is not widened,
    ``BrokerCreationRequest`` is not widened, and no ambient state carries the
    run or the workspace here.

    **This is the ONE path in this module that launches a process** -- the
    accepted fixed, read-only Git observation, once, at the verified root,
    with the independently resolved executable (C1-P12b). See the module
    docstring.

    Every failure -- an unminted or already-consumed grant, a task that
    drifted, an unverifiable workspace, a workspace not claimed by this run,
    an unresolvable Git executable, a failed observation, an empty manifest, a
    manifest that disagrees with the task's own intended file set, or a
    ``CapabilityMintError`` -- raises :class:`WorkspaceAuthorityError` with a
    bounded reason code and NO capability. It never falls back to the inert
    Category-B domain, and never falls back to a wider one.
    """
    if type(grant) is not SemanticCapabilityGrant:
        raise WorkspaceAuthorityError("NOT_A_SEMANTIC_CAPABILITY_GRANT")
    token = grant._grant_token
    record = _SEMANTIC_GRANTS.get(token) if type(token) is str else None
    if record is None:
        raise WorkspaceAuthorityError("SEMANTIC_GRANT_NOT_IN_ISSUANCE_REGISTRY")
    if record.consumed:
        raise WorkspaceAuthorityError("SEMANTIC_GRANT_ALREADY_CONSUMED")
    # Burn FIRST, exactly as ``_claim_issued_runtime_identity`` does: an
    # issuance that is subsequently refused is still spent, so a rejected
    # attempt can never re-present the same grant to a second issuance.
    record.consumed = True

    # -- the task contract, re-proved rather than trusted from grant time --
    task = record.task
    if TASKS_BY_ID.get(record.task_id) is not task:
        raise WorkspaceAuthorityError("NOT_A_FROZEN_CORPUS_TASK")
    if task.task_id != record.task_id or task.task_revision != record.task_revision:
        raise WorkspaceAuthorityError("SEMANTIC_TASK_IDENTITY_DRIFTED")

    # -- workspace + run identity, re-proved against the filesystem --------
    verified_repo_root = verify_run_workspace(workspace)
    mint_record = _MINTED.get(workspace.run_workspace_nonce)
    if mint_record is None:  # pragma: no cover - verify_run_workspace proves this
        raise WorkspaceAuthorityError("NOT_MINTED_BY_QUALIFICATION")
    if not isinstance(run_id, str) or not run_id:
        raise WorkspaceAuthorityError("MALFORMED_RUN_ID")
    if not run_workspace_is_claimed_by(workspace, run_id=run_id):
        raise WorkspaceAuthorityError("RUN_WORKSPACE_NOT_CLAIMED_BY_THIS_RUN")

    # -- C1-P8 (FU1): consume this WORKSPACE's one-shot semantic issuance
    # authority, BEFORE any Git resolution, observation or minting. This is
    # independent of -- and in addition to -- the grant-level one-shot burn
    # above: a second, DISTINCT, genuinely-minted grant for the same task
    # must still refuse against an already-issued workspace, and a failure at
    # any step below must never let a fresh grant retry on this workspace.
    _consume_workspace_semantic_issuance_authority(workspace, run_id=run_id)

    # -- C1-P12b: the git executable is AIDO's own resolution, independently
    # re-derived against the root just verified. Never a carried string, never
    # a bare name, and with no fallback of any kind.
    try:
        trusted_git = resolve_git_executable(workspace_root=verified_repo_root)
    except GitExecutableError:
        raise WorkspaceAuthorityError("GIT_EXECUTABLE_UNRESOLVED") from None

    # -- C1-P4: the manifest is OBSERVED, never asserted --------------------
    try:
        snapshot = observe_repository(
            git_executable=trusted_git, workspace_root=verified_repo_root
        )
    except ObservationError:
        raise WorkspaceAuthorityError("REPOSITORY_OBSERVATION_FAILED") from None
    observed_manifest = tuple(sorted(entry.path for entry in snapshot.index_entries))
    if not observed_manifest:
        raise WorkspaceAuthorityError("OBSERVED_MANIFEST_EMPTY")

    # The task's own intended file set is a CROSS-CHECK, never the authority.
    # A disagreement means the populated fixture is not the fixture this
    # revision names, so neither side is preferred: the issuance refuses.
    intended_manifest = tuple(sorted(task.case.files))
    if observed_manifest != intended_manifest:
        raise WorkspaceAuthorityError("INTENDED_AND_OBSERVED_MANIFEST_DISAGREE")

    # -- C1-P10: the FROZEN, UNMODIFIED eligibility algorithm ---------------
    try:
        sed = mint_capability(
            authority=mint_record.authority,
            tracked_manifest=observed_manifest,
            protected_patterns=task.case.protected_patterns,
            verification_witness_paths=task.case.verification_witness_paths,
        )
    except CapabilityMintError:
        raise WorkspaceAuthorityError("CAPABILITY_MINT_REFUSED") from None

    record.bound_run_workspace_nonce = workspace.run_workspace_nonce
    record.bound_run_id = run_id
    record.bound_capability_id = sed.capability_id
    return sed


def discard_semantic_capability_grants() -> None:
    """Forget every semantic GRANT. Never touches workspace-issuance state.

    Test/teardown convenience, no I/O. **5F3B-LIVE1-C1-FU3 correction:** the
    FU2 report claimed clearing ``_WORKSPACE_SEMANTIC_ISSUANCE`` here was a
    correction; it was itself a defect. ``_WORKSPACE_SEMANTIC_ISSUANCE`` is
    not grant-test bookkeeping -- it is the C1-P8 WORKSPACE-level one-shot
    authority, and it belongs to the workspace's own lifecycle, not to the
    grant registry's teardown. Clearing it here let a still-alive, already-
    issued workspace accept a second, freshly minted grant after nothing but
    a call to this helper -- a live one-shot bypass. This function now clears
    ONLY ``_SEMANTIC_GRANTS``. The one authority that may retire a workspace's
    semantic-issuance record remains :func:`discard_run_workspace` (and, by
    delegation, :func:`remove_run_workspace`), which retire it bound to that
    SAME workspace nonce's mint/claim retirement -- never as a side effect of
    discarding unrelated grants.
    """
    _SEMANTIC_GRANTS.clear()
