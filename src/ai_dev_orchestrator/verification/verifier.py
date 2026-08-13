"""The **controlled verification slice** (Phase 5F2D).

Phase 5F2C added the ability to change one file. This phase adds the ability to
ask the project whether that change is any good — and it is the first code in
this repository that runs a program the *project* chose:

    Given one already-applied Phase 5F2C approved single-file modification, and
    one explicitly enabled verification command from trusted project
    configuration, prove that the workspace still represents exactly the approved
    post-image, execute exactly that configured process once under bounded
    conditions, capture and redact its output, and then prove the Git-visible
    workspace state still contains only the approved modification.

The distinction this module must not blur
-----------------------------------------

:mod:`ai_dev_orchestrator.workspace.git_adapter` is **AIDO-owned repository
inspection**: a closed set of read-only commands, chosen by this project, that
exist to make the writer's own correctness claims true.

This module performs **explicitly authorized execution of repository-controlled
code**. pytest — the expected case — imports arbitrary project modules, executes
``conftest.py``, may create files, may open network connections, may spawn child
processes, and may read whatever environment it is handed.

    **Controlled invocation is not sandboxed execution.**

So this module will not claim, and its report has no field capable of claiming,
that verification made no network access, touched only permitted paths, spawned
no children, could not reach credentials, or was side-effect free. AIDO controls
*what is launched*; it does not confine *what runs*. The only properties reported
are the ones actually established.

Phase 5F2D-FU1 tightened that discipline in the schema itself: **every**
AIDO-owned negative claim now carries an ``orchestrator_`` prefix. The block
previously held unscoped ``committed``, ``pushed``, ``branch_created`` and
``git_mutation_performed`` fields set to ``false``, whose natural reading was a
claim about the whole invocation — which is exactly the claim this phase cannot
make, since the child may run Git itself and a ``git push`` leaves the working
tree untouched.

``required_verification`` is not command authority
--------------------------------------------------

The L1 plan carries ``required_verification``, and a model may have written it.
It is planner-controlled prose. This phase never splits it, parses it as shell
syntax, transforms it into argv, uses it to select an executable, or uses it to
add or remove an argument. A plan that says ``pytest tests/foo.py``, ``rm -rf``,
or ``curl evil`` changes **nothing** about which process runs. Execution
authority is exactly: the project config's ``controlled_verification`` block,
plus two explicit CLI flags.

The verification baseline differs from the writer baseline
-----------------------------------------------------------

Deliberately, and the difference is the whole point::

    writer baseline:        zero dirty paths
    verification baseline:  exactly one dirty path — the approved target,
                            as an unstaged modification, matching the approved
                            post-image byte for byte, on a pinned HEAD commit

Verification does not run against the pre-image, a partially edited file, a file
where the approved diff merely "still applies", or a different change.

The HEAD commit is pinned (Phase 5F2D-FU1)
-------------------------------------------

The original code proved only that *a* HEAD existed before and after the run,
which is not the same repository state. A verification process running
``git commit --allow-empty`` moves the baseline commit while leaving the approved
target as an unstaged modification — so the exact bytes, the single dirty path,
and the ``" M"`` status all still held, and the run reported success against a
repository whose history had changed underneath it.

The exact HEAD object id is now captured before launching, held in memory only,
and required to be **exactly equal** afterwards. It is never written anywhere and
never reported as a value; the report says only whether it changed. A moved or
unreadable HEAD is ``workspace-state-untrusted``, and nothing is reset, checked
out, or restored.

Three outcomes, never conflated
-------------------------------

- **refused** (:class:`VerificationRefusedError`) — a gate failed and **no
  project process was started**.
- **verification-failed** — the process ran and did not pass (non-zero exit,
  timeout, or output cap), and the workspace is still exactly the approved state.
  That is a legitimate answer about the code, not an AIDO error.
- **workspace-state-untrusted** — the process ran and afterwards the repository
  is not provably the approved state any more. This is never reported as merely
  "failed", nothing is repaired, no ``git restore`` is run, and a human must
  inspect the repository.
"""

from __future__ import annotations

import hashlib
import os
import stat as stat_module
import sys
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from ai_dev_orchestrator.file_editing.models import (
    ApprovedDiffProposalArtifact,
    _summarize_validation_error,
)
from ai_dev_orchestrator.models import ProjectConfig
from ai_dev_orchestrator.redaction import redact_secret_like_text
from ai_dev_orchestrator.verification.runner import (
    CONFIGURED_ARGS_TRUST_NOTE,
    DIRECT_CHILD_REAP_GRACE_SECONDS,
    ENVIRONMENT_FORWARDING_POLICY,
    WAIT_BOUND_POLICY,
    VerificationExecutableError,
    VerificationExecution,
    VerificationLaunchError,
    decode_verification_output,
    run_configured_verification,
    validate_verification_executable,
)
from ai_dev_orchestrator.workspace import (
    CanonicalPathError,
    GitAdapterError,
    PathClassification,
    PathPolicy,
    canonicalize_write_target_under_workspace,
    find_unsupported_config_keys,
    parse_config_name_only,
    parse_config_scoped_name_only,
    parse_ls_files_stage,
    parse_ls_files_verbose,
    parse_status_porcelain,
    resolve_git_executable,
    run_fixed_git_operation,
    status_record_path,
)

VERIFICATION_SCHEMA_VERSION = "verification-result.v1"
VERIFICATION_MODE = "controlled-verification"

# Git index modes accepted for the approved target: an ordinary file, or an
# ordinary executable file. Symlink (120000) and gitlink (160000) are not here.
_ORDINARY_BLOB_MODES = ("100644", "100755")

# The fixed Git operations this phase uses, in the one safe order: safe metadata,
# then the configuration gate, then the index gate, and only then anything that
# reads working-tree content. Identical in shape to the writer's contract,
# because the reason for the order is identical — a repository-configured clean
# filter runs during `git status`, so a repository that could execute one is
# refused before Git is asked to look at a working file.
VERIFICATION_GIT_OPERATIONS: tuple[str, ...] = (
    "rev_parse_show_toplevel",
    "rev_parse_head",
    "config_list_local",
    "config_list_scoped",
    "ls_files_stage",
    "ls_files_verbose",
    "status_porcelain",
)

# What this phase's post-execution Git check can and cannot see. Carried in the
# report so the limitation travels with the result rather than living only here.
POST_EXECUTION_DETECTION_LIMITS = (
    "The post-execution check proves the Git-visible state of this repository: "
    "the approved target's exact bytes, that the HEAD commit is exactly the one "
    "the run started from, and that no other staged, unstaged, untracked, "
    "deleted, renamed, unmerged or submodule state appeared. It does NOT detect "
    "changes to Git-ignored files, changes anywhere outside this repository, "
    "pushes or other remote operations, network activity, registry or system "
    "changes, services or child processes the verification left running, or any "
    "filesystem effect Git does not report. The verification process was not "
    "sandboxed."
)

# The concurrency contract, unchanged in substance from Phase 5F2C's and carried
# here because verification widens the window: a project process is running
# inside the workspace while these claims are being made.
VERIFICATION_SINGLE_ACTOR_CONTRACT = (
    "Phase 5F2D supports one AIDO invocation against a workspace no human or "
    "other process is editing. There is no lock, no filesystem watcher, and no "
    "cross-invocation mutual exclusion. The workspace state is proved "
    "immediately before the verification process is launched and again after it "
    "terminates; anything a concurrent actor does in between is detected only if "
    "it is still visible to Git afterwards. Concurrency is not solved."
)

NEXT_STEP_REQUIRES_HUMAN_REVIEW = (
    "AIDO left the approved change uncommitted in the working tree for human "
    "review. AIDO did not create a branch, commit, push, open a PR, call a "
    "model, contact GitHub, or run a reviewer. The verification child was NOT "
    "sandboxed: effects outside the post-execution Git-visible state — including "
    "network activity, pushes, and processes left running — are not "
    "comprehensively observed, and this report makes no claim about them. Phase "
    "5F2E (reviewer integration) must be explicitly authorized before this "
    "result flows any further."
)


class VerificationError(Exception):
    """Base class for Phase 5F2D failures.

    Messages name the failure **category** and, where it helps, the relative
    path. They never echo file contents, diff text, the approval text, the raw
    artifact, an absolute path, an environment value, or a credential.
    """

    category = "verification-failure"


class VerificationRefusedError(VerificationError):
    """Refused **before** any project process was started.

    Nothing was launched. The workspace is exactly as it was found.
    """

    category = "refused-before-execution"


class _WorkspaceStateError(Exception):
    """Internal: a workspace/Git state fact could not be established.

    Raised by the shared state-proving helpers so that the **same** proof can
    mean two different things depending on when it fails: before execution it is
    a refusal, after execution it is an untrusted workspace. The helpers do not
    decide which; the callers do.
    """


class _Strict(BaseModel):
    """Base model that rejects unknown fields, so forged extras fail loudly."""

    model_config = ConfigDict(extra="forbid")


# -- Report schema -------------------------------------------------------------


class VerificationTargetBlock(_Strict):
    """The one approved file this verification was bound to.

    Relative path and size only. There is no absolute path field, no content
    field, and no digest field: the report states that the identities *matched*
    rather than what they were.
    """

    path: str
    change_type: Literal["modify"]
    post_image_verified_before_execution: Literal[True]
    post_image_bytes: int


class VerificationCommandBlock(_Strict):
    """Where the executed command came from, and where it did **not** come from.

    ``plan_required_verification_executed`` is a ``Literal[False]`` rather than a
    ``bool`` on purpose: it is not an observation that happened to come out false
    this run, it is a property of a module that never reads that field for
    execution. ``plan_required_verification_entries`` records how many entries
    the approved plan carried — every one of which was ignored as command
    authority.
    """

    configured: Literal[True]
    executable_source: Literal["project_config"]
    executable_absolute: Literal[True]
    executable_outside_workspace: Literal[True]
    args_source: Literal["project_config"]
    arg_count: int
    shell: Literal[False]
    cwd_is_workspace_root: Literal[True]
    invocations: Literal[1]
    timeout_seconds: int
    max_output_bytes: int
    environment_forwarding: str
    # Phase 5F2D-FU1 narrowed this. It used to read
    # ``project_configured_secret_forwarding: false``, which was too broad: the
    # environment really is a non-configurable minimal allowlist, but the
    # configured argv is passed verbatim, so a project config could in principle
    # place a literal credential in ``args``. What is actually proved is that
    # there is no project-configurable *environment* forwarding mechanism, and
    # ``configured_args_trust_note`` states plainly what is not proved about
    # argument strings. No heuristic argv secret scanner was added.
    environment_forwarding_configurable: Literal[False]
    configured_args_trust_note: str
    plan_required_verification_executed: Literal[False]
    plan_required_verification_entries: int


class VerificationExecutionBlock(_Strict):
    """What the one invocation actually did.

    ``return_code`` is ``null`` whenever the child was killed, because the exit
    status of a killed process is not an answer about the code. ``passed`` is
    true only for a run that finished on its own terms, in time, in bounds, at
    zero.
    """

    started: bool
    completed: bool
    timed_out: bool
    output_limit_exceeded: bool
    return_code: int | None
    passed: bool
    # Phase 5F2D-FU1, made exact by FU2. ``aido_wait_bounded`` is the honest
    # positive claim: AIDO's wait was bounded, and ``wait_bound_policy`` below
    # states by what. It does NOT mean the function returned at the configured
    # deadline — the configured timeout bounds the execution/capture wait, and a
    # fixed direct-child reap grace may follow it. It is NOT a claim that the
    # verification stopped. ``direct_child_killed`` says exactly what was done —
    # AIDO sent at least one kill to the direct child, from whichever bound
    # fired — and ``descendant_processes_terminated`` is a fixed string rather
    # than a boolean because descendants are never enumerated, signalled, or
    # tracked.
    aido_wait_bounded: Literal[True]
    direct_child_killed: bool
    descendant_processes_terminated: Literal[
        "not tracked; descendants may still be running"
    ]
    # Phase 5F2D-FU2. The two numbers that make the timing claim exact: the
    # configured timeout bounds the execution/capture wait, and after it AIDO may
    # spend at most the fixed reap grace on the direct child's handle. Nothing
    # here is measured elapsed time, and no process id is exposed.
    configured_timeout_seconds: int
    direct_child_reap_grace_seconds: float
    wait_bound_policy: str


class VerificationOutputBlock(_Strict):
    """The captured output, bounded first and redacted second.

    ``complete`` is the honesty field. Output is bounded **during** capture, so
    when the cap is passed the child is killed and what was captured is a prefix
    — never presented as the whole output. Redaction is a best-effort backstop
    for obvious secret-like shapes and is not a guarantee; ``redaction_note``
    says so in the artifact itself.
    """

    redacted: Literal[True]
    redaction_count: int
    redaction_kinds: list[str]
    complete: bool
    bytes_captured: int
    decoded_with_replacement: bool
    combined_stdout_stderr: Literal[True]
    combined_text: str
    redaction_note: str


class VerificationWorkspacePreconditionBlock(_Strict):
    """What was proved **before** the verification process was launched.

    Every field is a ``Literal[True]``: each is a precondition of reaching the
    launch, not an observation recorded afterwards. A run that could not prove
    one of these never started a process and produced no report at all.
    """

    platform_supported: Literal[True]
    project_verification_enabled: Literal[True]
    project_identity_matched: Literal[True]
    exactly_one_change: Literal[True]
    change_type_is_modify: Literal[True]
    lexical_write_policy_checked: Literal[True]
    canonicalization_verified: Literal[True]
    target_is_regular_file: Literal[True]
    git_executable_resolved_absolute: Literal[True]
    git_config_execution_surface_supported: Literal[True]
    git_index_simple_and_submodule_free: Literal[True]
    target_tracked_as_ordinary_blob: Literal[True]
    exact_approved_post_image_present: Literal[True]
    only_approved_target_git_dirty: Literal[True]
    approved_target_is_unstaged_modification: Literal[True]
    # Phase 5F2D-FU1: the exact HEAD object id was captured before launching, and
    # is compared for equality afterwards. The id itself is never reported.
    head_object_id_recorded: Literal[True]


class VerificationWorkspacePostconditionBlock(_Strict):
    """What was proved **after** the verification process terminated.

    These are plain ``bool``s, unlike the precondition block, because a report
    is produced even when they are false — that is the exit-3 outcome, and
    suppressing the report would be exactly the wrong response to "the
    repository may have changed".

    ``detection_limits`` states what this check does not see. It is not a
    disclaimer bolted on; it is the boundary of the claim.
    """

    git_state_reestablished: bool
    exact_approved_target_still_present: bool
    exact_post_image_still_matches: bool
    # Phase 5F2D-FU1. Exact equality of the HEAD object id against the one
    # captured before launching. Without it, a verification process running
    # ``git commit --allow-empty`` moved the baseline commit while every other
    # postcondition here still reported success. The id is deliberately not
    # exposed; only whether it changed.
    head_unchanged: bool
    only_approved_target_git_dirty: bool
    no_additional_git_visible_changes: bool
    dirty_paths: list[str]
    failure_reason: str | None
    detection_limits: str


class VerificationCapabilityBoundaries(_Strict):
    """What AIDO itself did not do, and what it cannot say about the child.

    The two halves are typed differently on purpose.

    **Every** AIDO-owned negative claim is prefixed ``orchestrator_`` and is a
    ``Literal[False]``: a property of a module that imports no client, opens no
    socket, and has no Git-mutation, GitHub, branch, commit, push or PR
    capability at all.

    Phase 5F2D-FU1 corrected this block. It previously carried **unscoped**
    fields — ``committed``, ``pushed``, ``branch_created``,
    ``git_mutation_performed`` and others — set to ``false``. Under this phase's
    own explicit model that was misleading: the verification child is not
    sandboxed and may itself run Git, create a branch, commit, or push. Some of
    those effects are not inferable from the final working-tree state at all — a
    ``git push`` leaves it untouched. A reader scanning ``pushed: false`` would
    have taken it as a statement about the whole invocation, which AIDO cannot
    make. Every such field is now explicitly scoped to the orchestrator.

    The ``child_process_*`` fields are **strings**, and every one of them says
    ``"not sandboxed"``. There is deliberately no boolean here, because a boolean
    would invite ``false`` — and ``network_called: false`` as a claim about the
    whole invocation would be a lie. AIDO did not open a socket; the project's
    verification process may have.

    Nothing here attempts to *detect* the child's Git, network, or process
    effects. That would be sandbox and process-audit scope, and it is not
    authorized.
    """

    orchestrator_model_called: Literal[False]
    orchestrator_network_called: Literal[False]
    orchestrator_github_accessed: Literal[False]
    orchestrator_shell_invoked: Literal[False]
    orchestrator_files_written: Literal[False]
    orchestrator_git_mutation_performed: Literal[False]
    orchestrator_branch_created: Literal[False]
    orchestrator_committed: Literal[False]
    orchestrator_pushed: Literal[False]
    orchestrator_pr_created: Literal[False]
    orchestrator_retry_attempted: Literal[False]
    orchestrator_automatic_repair_attempted: Literal[False]
    orchestrator_rollback_or_restore_performed: Literal[False]
    orchestrator_reviewer_or_fixer_invoked: Literal[False]

    child_process_sandboxed: Literal[False]
    child_process_filesystem_effects: Literal["not sandboxed"]
    child_process_network_effects: Literal["not sandboxed"]
    child_process_subprocess_effects: Literal["not sandboxed"]
    child_process_git_effects: Literal["not sandboxed; not observed beyond the "
                                       "post-execution Git-visible state"]
    child_process_credential_access: Literal[
        "not sandboxed; child environment minimized, not confined"
    ]
    child_process_lifetime: Literal[
        "not sandboxed; descendants are not tracked and may still be running"
    ]


class VerificationResultReport(_Strict):
    """The structured, human-reviewable result of one controlled verification.

    Deliberately absent, because there is no field for any of them: the
    configured workspace path, any absolute path (including the verification
    executable's), any API key, any environment value, the approval text, the raw
    input artifact, the approved unified diff, and any unrelated source file. The
    one place project-controlled text appears is ``output.combined_text``, which
    is bounded during capture and redacted before it is stored.
    """

    schema_version: Literal[VERIFICATION_SCHEMA_VERSION]  # type: ignore[valid-type]
    mode: Literal[VERIFICATION_MODE]  # type: ignore[valid-type]
    outcome: Literal["verified", "verification-failed", "workspace-state-untrusted"]
    project_id: str
    repo: str
    issue_number: int
    title: str
    approved_by: str
    approved_at: datetime
    target: VerificationTargetBlock
    command: VerificationCommandBlock
    execution: VerificationExecutionBlock
    output: VerificationOutputBlock
    workspace_precondition: VerificationWorkspacePreconditionBlock
    workspace_postcondition: VerificationWorkspacePostconditionBlock
    capability_boundaries: VerificationCapabilityBoundaries
    single_actor_contract: str
    next_step: str


# -- Small helpers -------------------------------------------------------------


def _sha256_hex(data: bytes) -> str:
    """Digest exact bytes. No normalization of any kind happens first."""
    return hashlib.sha256(data).hexdigest()


def _read_bounded_file_bytes(path: str, *, limit: int) -> bytes:
    """Read at most ``limit`` bytes, refusing a file that exceeds the cap.

    ``limit + 1`` bytes are requested so "exactly at the cap" and "over the cap"
    are distinguishable without stat'ing first and trusting the answer.
    """
    try:
        with open(path, "rb") as handle:
            data = handle.read(limit + 1)
    except OSError as exc:
        raise _WorkspaceStateError(
            "the approved target could not be read, so its current bytes could "
            "not be established."
        ) from exc
    if len(data) > limit:
        raise _WorkspaceStateError(
            f"the approved target exceeds this project's "
            f"workspace_write.max_file_bytes of {limit}, so its exact bytes were "
            "not established. It is refused, never truncated."
        )
    return data


def _to_repo_relative_posix(relative_destination: str) -> str:
    """Render a canonical relative destination the way Git names it."""
    return relative_destination.replace(os.sep, "/").replace("\\", "/")


# -- Gate 1: identity, scope, and policy (no workspace touch yet) ---------------


def _check_platform() -> None:
    if sys.platform != "win32":
        raise VerificationRefusedError(
            "platform error: Phase 5F2D verifies a Phase 5F2C write, and that "
            "writer is Windows-only. It refuses here rather than pretending to "
            "be cross-platform. Nothing was launched."
        )


def _check_project_opt_in(project: ProjectConfig) -> None:
    if not project.controlled_verification.enabled:
        raise VerificationRefusedError(
            "opt-in error: this project's controlled_verification block is "
            "absent or disabled, so no verification process may be executed for "
            "it. No target workspace was touched and nothing was launched."
        )


def _check_identity(
    approved_diff: ApprovedDiffProposalArtifact, project: ProjectConfig
) -> None:
    """Refuse an approved diff that is not this project's, exactly.

    The same six comparisons the writer makes. An approval given for one project
    or repo authorizes verifying nothing in another, for the same reason it
    authorizes writing nothing there.
    """
    repo = project.repo.github_repo
    proposal = approved_diff.diff_proposal
    mismatched = [
        label
        for label, left, right in (
            ("project_id", approved_diff.project_id, project.project_id),
            ("repo", approved_diff.repo, repo),
            (
                "diff_proposal.provenance.project_id",
                proposal.provenance.project_id,
                project.project_id,
            ),
            ("diff_proposal.provenance.repo", proposal.provenance.repo, repo),
            (
                "diff_proposal.approved_plan.project_id",
                proposal.approved_plan.project_id,
                project.project_id,
            ),
            ("diff_proposal.approved_plan.repo", proposal.approved_plan.repo, repo),
        )
        if left != right
    ]
    if mismatched:
        raise VerificationRefusedError(
            "identity error: the approved diff proposal does not match this "
            "project config exactly; mismatched fields: "
            + ", ".join(mismatched)
            + ". Nothing was launched."
        )


def _check_single_modify_change(
    approved_diff: ApprovedDiffProposalArtifact, project: ProjectConfig
):
    """Require exactly one change, and require it to be a ``modify``.

    The same narrow artifact domain the writer accepts, because this phase
    verifies exactly what that writer is able to have produced.
    """
    changes = approved_diff.diff_proposal.changes
    limit = project.workspace_policy.max_changed_files

    if limit < 1:
        raise VerificationRefusedError(
            "scope error: this project's workspace_policy.max_changed_files is "
            f"{limit}, which permits no change at all, so there is no approved "
            "change to verify. Nothing was launched."
        )
    if len(changes) != 1:
        raise VerificationRefusedError(
            f"scope error: the approved diff proposal carries {len(changes)} "
            "changes. Phase 5F2D verifies exactly one applied single-file "
            "modification per invocation. Nothing was launched."
        )

    change = changes[0]
    if change.change_type != "modify":
        raise VerificationRefusedError(
            f"scope error: change_type is {change.change_type!r}. Phase 5F2D "
            "verifies 'modify' only, because that is the only thing Phase 5F2C "
            "can have applied. Nothing was launched."
        )
    if change.pre_image_sha256 is None:
        raise VerificationRefusedError(
            "approval error: the approved 'modify' change carries no "
            "pre_image_sha256, so there is no record of which exact bytes the "
            "human approved transforming. Nothing was launched."
        )
    return change


def _check_workspace_policy_flags(project: ProjectConfig) -> None:
    policy = project.workspace_policy
    if policy.allow_symlinks:
        raise VerificationRefusedError(
            "policy error: this project sets workspace_policy.allow_symlinks "
            "true. Phase 5F2D operates only in projects that refuse link "
            "traversal outright. Nothing was launched."
        )
    if not policy.deny_outside_workspace:
        raise VerificationRefusedError(
            "policy error: this project sets "
            "workspace_policy.deny_outside_workspace false. Phase 5F2D operates "
            "only in projects that keep the containment rule on. Nothing was "
            "launched."
        )


def _check_lexical_write_policy(path: str, project: ProjectConfig) -> None:
    """Run the Phase 1 lexical write check, with no protected-path escape hatch.

    A path this project would not have permitted writing is not one whose
    already-applied modification this phase will bless by verifying it.
    """
    policy = PathPolicy.from_project_config(project)
    decision = policy.check_write(path)
    if decision.permitted:
        return
    if decision.classification is PathClassification.PROTECTED:
        raise VerificationRefusedError(
            f"policy error: path {path!r} is classified PROTECTED by this "
            "project's path rules. Phase 5F2D refuses protected targets outright "
            "and ships no flag and no config field to permit one. Nothing was "
            "launched."
        )
    raise VerificationRefusedError(
        f"policy error: path {path!r} is refused by this project's lexical write "
        f"policy ({decision.classification.value}: {decision.reason}). Nothing "
        "was launched."
    )


# -- Gate 2: the canonical target ----------------------------------------------


def _canonicalize(path: str, project: ProjectConfig):
    """Re-run the Phase 5F2B write-target guard, read-only.

    ``change_type="modify"`` because the target must already exist: this phase
    binds to an applied change, so a destination that does not exist is not a
    verification case at all. Nothing is created, opened for writing, or
    modified by this call.
    """
    return canonicalize_write_target_under_workspace(
        project.repo.workspace_path,
        path,
        change_type="modify",
        allow_symlinks=False,
    )


def _check_target_is_ordinary_file(resolved_destination: str) -> None:
    """Prove the approved target is still an existing regular file.

    ``lstat`` rather than ``stat``: a symlink that now points at a regular file
    must not pass a check whose whole purpose is that the approved name still
    denotes the approved ordinary file. The Phase 5F2B guard already refuses
    reparse points on the resolved path; this is the cheap direct restatement.
    """
    try:
        lstat_result = os.lstat(resolved_destination)
    except OSError as exc:
        raise _WorkspaceStateError(
            "the approved target could not be examined."
        ) from exc
    if not stat_module.S_ISREG(lstat_result.st_mode):
        raise _WorkspaceStateError("the approved target is not a regular file.")


# -- Gate 3: the Git contract --------------------------------------------------


def _git(
    operation: str,
    workspace_root: str,
    *,
    git_executable: str,
    path: str | None = None,
    allowed_returncodes: tuple[int, ...] = (0,),
):
    try:
        return run_fixed_git_operation(
            operation,
            git_executable=git_executable,
            workspace_root=workspace_root,
            repo_relative_path=path,
            allowed_returncodes=allowed_returncodes,
        )
    except GitAdapterError as exc:
        raise _WorkspaceStateError(f"git error: {exc}") from exc


def _prove_worktree_root_and_head(workspace_root: str, *, git_executable: str) -> str:
    """Safe metadata only: no working-tree content is read, so no filter can run.

    Returns the **exact HEAD object id**. Phase 5F2D-FU1: the original code ran
    ``rev-parse --verify HEAD`` and discarded the answer, proving only that *a*
    HEAD existed on each side of the run. That is not the same repository state.
    A verification process running ``git commit --allow-empty`` moves HEAD while
    leaving the approved target as an unstaged modification, so every other
    postcondition — exact approved bytes, exactly one dirty path, ``" M"`` — still
    held and the run reported success against a repository whose baseline commit
    had changed underneath it.

    The object id is kept as in-memory state and compared for exact equality
    afterwards. It is **not** reported: the report says whether HEAD was
    unchanged, not what it was.
    """
    toplevel = _git(
        "rev_parse_show_toplevel", workspace_root, git_executable=git_executable
    ).stdout.strip()
    if not toplevel:
        raise _WorkspaceStateError(
            "the configured workspace is not inside a Git working tree."
        )
    if os.path.normcase(os.path.realpath(toplevel)) != os.path.normcase(
        os.path.realpath(workspace_root)
    ):
        raise _WorkspaceStateError(
            "the Git working-tree top level is not the configured workspace root."
        )

    head = _git(
        "rev_parse_head", workspace_root, git_executable=git_executable
    ).stdout.strip()
    if not head:
        raise _WorkspaceStateError(
            "the repository has no resolvable HEAD commit, so there is no "
            "baseline commit to pin the verification against."
        )
    return head


def _prove_supported_git_configuration(
    workspace_root: str, *, git_executable: str
) -> None:
    """Refuse a repository whose Git config can execute or indirect.

    Inherited unchanged in substance from the Phase 5F2C-FU1 gate, and it must
    still run **before** any operation that reads working-tree content: a
    repository-configured ``filter.<driver>.clean`` is executed by Git itself
    during ``git status``, including on a tree AIDO would otherwise consider
    understood. Only key *names* are read, so no configuration value enters this
    process and no refusal can leak one.
    """
    local_keys = parse_config_name_only(
        _git(
            "config_list_local",
            workspace_root,
            git_executable=git_executable,
            allowed_returncodes=(0, 1),
        ).stdout
    )
    unsupported = find_unsupported_config_keys(local_keys)
    if unsupported:
        raise _WorkspaceStateError(
            "this repository's own Git configuration defines keys that can cause "
            "Git to execute a program or follow configuration indirection, so "
            "the repository is unsupported: "
            + ", ".join(unsupported)
            + ". No configuration value was read."
        )

    scoped_keys = parse_config_scoped_name_only(
        _git(
            "config_list_scoped",
            workspace_root,
            git_executable=git_executable,
            allowed_returncodes=(0, 1),
        ).stdout
    )
    unsupported = find_unsupported_config_keys(scoped_keys)
    if unsupported:
        raise _WorkspaceStateError(
            "the Git configuration in effect for this repository defines keys "
            "that can cause Git to execute a program or follow configuration "
            "indirection, so the repository is unsupported here: "
            + ", ".join(unsupported)
            + ". This includes configuration inherited from the user's global "
            "Git config. No configuration value was read."
        )


def _prove_simple_index(
    workspace_root: str, relative_path: str, *, git_executable: str
) -> None:
    """Prove the index is simple, submodule-free, and holds the target once.

    Runs before ``git status`` so the status walk has no submodule to descend
    into. Neither operation reads working-tree content.
    """
    entries = parse_ls_files_stage(
        _git("ls_files_stage", workspace_root, git_executable=git_executable).stdout
    )
    for entry in entries:
        if entry.mode == "160000":
            raise _WorkspaceStateError(
                "the index contains a gitlink (submodule) entry, so this "
                "repository's state is not the simple one this phase supports."
            )
        if entry.stage != 0:
            raise _WorkspaceStateError("the index contains an unmerged entry.")

    for tag, _entry_path in parse_ls_files_verbose(
        _git("ls_files_verbose", workspace_root, git_executable=git_executable).stdout
    ):
        if tag == "H":
            continue
        if tag.islower():
            raise _WorkspaceStateError(
                "the index contains an assume-unchanged entry, which tells Git "
                "to stop noticing that a file changed."
            )
        if tag == "S":
            raise _WorkspaceStateError(
                "the index contains a skip-worktree entry."
            )
        raise _WorkspaceStateError(
            f"the index contains an entry with status tag {tag!r}, which is not "
            "the ordinary cached state this phase supports."
        )

    matching = [entry for entry in entries if entry.path == relative_path]
    if not matching:
        raise _WorkspaceStateError(
            f"path {relative_path!r} is not tracked by Git."
        )
    if len(matching) != 1:
        raise _WorkspaceStateError(
            f"path {relative_path!r} has more than one index entry, so its "
            "tracked state is ambiguous."
        )
    if matching[0].mode not in _ORDINARY_BLOB_MODES:
        raise _WorkspaceStateError(
            f"path {relative_path!r} is tracked with index mode "
            f"{matching[0].mode}, not an ordinary file blob."
        )


def _prove_exactly_the_approved_target_is_dirty(
    workspace_root: str, relative_path: str, *, git_executable: str
) -> list[str]:
    """Prove the Git-visible dirty state is **exactly** the approved target.

    This is where the verification baseline departs from the writer baseline. The
    writer requires zero dirty paths; this phase requires exactly one, and
    requires it to be the approved path reported as an **unstaged modification**
    (``" M"``). A staged change, an untracked file, a deletion, a rename, an
    unmerged entry or dirty submodule state all refuse: each means the workspace
    holds something other than the one approved modification, and this phase has
    no authority to run a project's code against that.

    Returns the sorted dirty paths so the caller can report them.
    """
    records = parse_status_porcelain(
        _git("status_porcelain", workspace_root, git_executable=git_executable).stdout
    )
    dirty_paths = sorted({status_record_path(record) for record in records})

    if not records:
        raise _WorkspaceStateError(
            "the repository is clean, so the approved modification is not present "
            "in the working tree. Phase 5F2D verifies an already-applied approved "
            "change; it does not apply one, and it does not verify an unchanged "
            "repository."
        )
    if dirty_paths != [relative_path]:
        raise _WorkspaceStateError(
            f"git reports {len(dirty_paths)} changed or untracked path(s), not "
            "exactly the one approved path. The workspace holds more than the "
            "approved modification."
        )
    for record in records:
        if record[:2] != " M":
            raise _WorkspaceStateError(
                "the approved path is not reported as a plain unstaged "
                "modification. Staged, deleted, renamed, unmerged and copied "
                "states are all refused."
            )
    return dirty_paths


def _prove_git_state(
    workspace_root: str, relative_path: str, *, git_executable: str
) -> tuple[str, list[str]]:
    """Run every Git gate, in the one order that is safe.

    Returns ``(head_object_id, dirty_paths)``. The HEAD id is the baseline commit
    the verification is pinned to; the caller retains it and requires exact
    equality afterwards.
    """
    head = _prove_worktree_root_and_head(
        workspace_root, git_executable=git_executable
    )
    _prove_supported_git_configuration(workspace_root, git_executable=git_executable)
    _prove_simple_index(workspace_root, relative_path, git_executable=git_executable)
    dirty_paths = _prove_exactly_the_approved_target_is_dirty(
        workspace_root, relative_path, git_executable=git_executable
    )
    return head, dirty_paths


def _prove_exact_post_image(
    resolved_destination: str, *, expected_digest: str, limit: int
) -> bytes:
    """Require the target's current bytes to be exactly the approved post-image.

    Not "the diff still applies", not "the file looks edited", and not the
    pre-image: verification is authorized for the exact already-applied approved
    change and for nothing else.
    """
    data = _read_bounded_file_bytes(resolved_destination, limit=limit)
    if _sha256_hex(data) != expected_digest:
        raise _WorkspaceStateError(
            "the approved target's current bytes do not hash to the approved "
            "post_image_sha256, so the workspace does not represent the exact "
            "approved change."
        )
    return data


# -- The operation -------------------------------------------------------------


def verify_approved_file_edit(
    *,
    approved_diff: ApprovedDiffProposalArtifact,
    project: ProjectConfig,
) -> VerificationResultReport:
    """Verify one already-applied approved single-file modification, or refuse.

    Args:
        approved_diff: The same validated Phase 5F0 approval the writer consumed
            (schema ``approved-diff-proposal.v2``).
        project: The project config the approval must match exactly, and whose
            ``controlled_verification`` block must be enabled and must name the
            one command that may run.

    Returns:
        A validated :class:`VerificationResultReport`. **Returning one does not
        mean verification passed** — it means a verification process was started
        and an honest result was produced. Read ``outcome``.

    Raises:
        VerificationRefusedError: a gate failed and **no project process was
            started**. The workspace is exactly as it was found.
    """
    # ---- Gates that touch nothing --------------------------------------------
    _check_platform()
    _check_project_opt_in(project)
    _check_identity(approved_diff, project)
    change = _check_single_modify_change(approved_diff, project)
    _check_workspace_policy_flags(project)
    _check_lexical_write_policy(change.path, project)

    settings = project.controlled_verification
    limit = project.workspace_write.max_file_bytes

    # ---- The canonical target, and the executable it does NOT supply ---------
    try:
        target = _canonicalize(change.path, project)
    except CanonicalPathError as exc:
        raise VerificationRefusedError(
            f"canonicalization error: {type(exc).__name__}: {exc} Nothing was "
            "launched."
        ) from exc

    workspace_root = target.resolved_workspace_root
    relative_path = _to_repo_relative_posix(target.relative_destination)

    # The command's identity is settled before any state is read, so a project
    # that could never have run anything fails fast — and so that the
    # inside-the-workspace refusal happens against the canonical root.
    try:
        executable = validate_verification_executable(
            settings.executable, workspace_root=workspace_root
        )
    except VerificationExecutableError as exc:
        raise VerificationRefusedError(f"{exc}") from exc

    # ---- Pre-execution state binding -----------------------------------------
    try:
        _check_target_is_ordinary_file(target.resolved_destination)
        git_executable = resolve_git_executable(workspace_root=workspace_root)
        post_image_bytes = _prove_exact_post_image(
            target.resolved_destination,
            expected_digest=change.post_image_sha256,
            limit=limit,
        )
        # The baseline commit this verification is pinned to. Held in memory
        # only, never written anywhere, never reported as a value.
        head_before, _dirty_before = _prove_git_state(
            workspace_root, relative_path, git_executable=git_executable
        )
    except (_WorkspaceStateError, GitAdapterError) as exc:
        raise VerificationRefusedError(
            f"workspace state error: {exc} Verification is authorized only for "
            "the exact already-applied approved change, so nothing was launched."
        ) from exc

    # ---- The one execution ---------------------------------------------------
    # Everything above proved the workspace *is* the approved state. Only now is
    # a project-controlled program launched, and it is launched exactly once.
    try:
        execution = run_configured_verification(
            executable=executable,
            args=list(settings.args),
            cwd=workspace_root,
            timeout_seconds=settings.timeout_seconds,
            max_output_bytes=settings.max_output_bytes,
        )
    except (VerificationExecutableError, VerificationLaunchError) as exc:
        raise VerificationRefusedError(f"{exc}") from exc

    # ---- Post-execution state proof ------------------------------------------
    postcondition = _reprove_workspace_after_execution(
        project=project,
        change=change,
        expected_workspace_root=workspace_root,
        relative_path=relative_path,
        limit=limit,
        git_executable=git_executable,
        expected_head=head_before,
    )

    return _build_report(
        approved_diff=approved_diff,
        project=project,
        change=change,
        settings=settings,
        execution=execution,
        post_image_bytes=post_image_bytes,
        postcondition=postcondition,
    )


def _reprove_workspace_after_execution(
    *,
    project: ProjectConfig,
    change,
    expected_workspace_root: str,
    relative_path: str,
    limit: int,
    git_executable: str,
    expected_head: str,
) -> VerificationWorkspacePostconditionBlock:
    """Re-establish the workspace state after the process terminated.

    Nothing established before the execution is reused as authority — with one
    deliberate exception, ``expected_head``, which is retained precisely so it
    can be compared. The target is re-canonicalized, its bytes are re-read and
    re-hashed, every Git gate runs again, and the **HEAD object id must be
    exactly the one the run started from** (Phase 5F2D-FU1). This deliberately
    catches a verification process that altered tracked or untracked Git-visible
    repository state, or that moved the baseline commit — which is what an
    accidentally destructive test suite, or a ``git commit`` in a ``conftest.py``,
    looks like.

    **Nothing is repaired.** No ``git restore``, no ``git checkout``, no delete,
    no cleanup command, and no retry. A failed postcondition is reported to a
    human, who decides.

    It runs after a timeout kill and an output-overflow kill too: a killed
    process may well have changed the tree before it died, so skipping the proof
    in exactly the cases where the run went wrong would be backwards.
    """
    reason: str | None = None
    target_present = False
    post_image_matches = False
    head_unchanged = False
    git_reestablished = False
    only_target_dirty = False
    dirty_paths: list[str] = []

    try:
        revalidated = _canonicalize(change.path, project)
        if revalidated.resolved_workspace_root != expected_workspace_root:
            raise _WorkspaceStateError(
                "the canonical workspace root changed across the verification "
                "run."
            )
        _check_target_is_ordinary_file(revalidated.resolved_destination)
        target_present = True

        _prove_exact_post_image(
            revalidated.resolved_destination,
            expected_digest=change.post_image_sha256,
            limit=limit,
        )
        post_image_matches = True

        head_after = _prove_worktree_root_and_head(
            expected_workspace_root, git_executable=git_executable
        )
        if head_after != expected_head:
            raise _WorkspaceStateError(
                "the repository's HEAD commit is not the one this verification "
                "started from. The working tree may still look like the approved "
                "change, but the baseline commit moved underneath it, so this is "
                "not the approved repository state. Nothing was reset, checked "
                "out, or restored."
            )
        head_unchanged = True

        _prove_supported_git_configuration(
            expected_workspace_root, git_executable=git_executable
        )
        _prove_simple_index(
            expected_workspace_root, relative_path, git_executable=git_executable
        )
        git_reestablished = True

        dirty_paths = _prove_exactly_the_approved_target_is_dirty(
            expected_workspace_root, relative_path, git_executable=git_executable
        )
        only_target_dirty = True
    except CanonicalPathError as exc:
        reason = (
            f"the approved target could not be re-canonicalized after the "
            f"verification process: {type(exc).__name__}: {exc}"
        )
    except (_WorkspaceStateError, GitAdapterError) as exc:
        reason = str(exc)

    return VerificationWorkspacePostconditionBlock(
        git_state_reestablished=git_reestablished,
        exact_approved_target_still_present=target_present,
        exact_post_image_still_matches=post_image_matches,
        head_unchanged=head_unchanged,
        only_approved_target_git_dirty=only_target_dirty,
        no_additional_git_visible_changes=only_target_dirty,
        dirty_paths=dirty_paths,
        failure_reason=reason,
        detection_limits=POST_EXECUTION_DETECTION_LIMITS,
    )


def _dedupe_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


def _build_report(
    *,
    approved_diff: ApprovedDiffProposalArtifact,
    project: ProjectConfig,
    change,
    settings,
    execution: VerificationExecution,
    post_image_bytes: bytes,
    postcondition: VerificationWorkspacePostconditionBlock,
) -> VerificationResultReport:
    """Assemble the typed result. Bound first, redact second, claim last.

    The outcome ordering is deliberate: an untrusted workspace outranks a failed
    test run. A suite that fails *and* leaves the repository changed is not
    reported as "verification failed" — the repository state is the more serious
    fact, and it is the one a human must act on first.
    """
    combined_text, replaced = decode_verification_output(execution.output_bytes)
    redacted_text, redaction_kinds = redact_secret_like_text(combined_text)

    workspace_trusted = (
        postcondition.exact_approved_target_still_present
        and postcondition.exact_post_image_still_matches
        and postcondition.head_unchanged
        and postcondition.only_approved_target_git_dirty
        and postcondition.git_state_reestablished
    )
    if not workspace_trusted:
        outcome = "workspace-state-untrusted"
    elif execution.passed:
        outcome = "verified"
    else:
        outcome = "verification-failed"

    approval = approved_diff.approval
    # Bound solely so its length can be reported. It is never split, parsed,
    # indexed, formatted into a command, or passed anywhere near an argv.
    required_verification = (
        approved_diff.diff_proposal.approved_plan.plan.required_verification
    )

    payload = {
        "schema_version": VERIFICATION_SCHEMA_VERSION,
        "mode": VERIFICATION_MODE,
        "outcome": outcome,
        "project_id": project.project_id,
        "repo": project.repo.github_repo,
        "issue_number": approved_diff.issue_number,
        "title": approved_diff.title,
        "approved_by": approval.approved_by,
        "approved_at": approval.approved_at,
        "target": {
            "path": change.path,
            "change_type": "modify",
            "post_image_verified_before_execution": True,
            "post_image_bytes": len(post_image_bytes),
        },
        "command": {
            "configured": True,
            "executable_source": "project_config",
            "executable_absolute": True,
            "executable_outside_workspace": True,
            "args_source": "project_config",
            "arg_count": len(settings.args),
            "shell": False,
            "cwd_is_workspace_root": True,
            "invocations": 1,
            "timeout_seconds": settings.timeout_seconds,
            "max_output_bytes": settings.max_output_bytes,
            "environment_forwarding": ENVIRONMENT_FORWARDING_POLICY,
            "environment_forwarding_configurable": False,
            "configured_args_trust_note": CONFIGURED_ARGS_TRUST_NOTE,
            # A property of this module, not an observation: the plan's
            # required_verification is never read for execution authority.
            "plan_required_verification_executed": False,
            "plan_required_verification_entries": len(required_verification),
        },
        "execution": {
            "started": execution.started,
            "completed": execution.completed,
            "timed_out": execution.timed_out,
            "output_limit_exceeded": execution.output_limit_exceeded,
            "return_code": execution.return_code,
            "passed": execution.passed,
            # AIDO's own wait was bounded: the configured timeout bounds the
            # execution and output-capture wait, and a fixed direct-child reap
            # grace may follow it. See `wait_bound_policy` below for the exact
            # contract. This is NOT a claim that the verification stopped.
            "aido_wait_bounded": True,
            "direct_child_killed": execution.direct_child_killed,
            "descendant_processes_terminated": (
                "not tracked; descendants may still be running"
            ),
            "configured_timeout_seconds": settings.timeout_seconds,
            "direct_child_reap_grace_seconds": DIRECT_CHILD_REAP_GRACE_SECONDS,
            "wait_bound_policy": WAIT_BOUND_POLICY,
        },
        "output": {
            "redacted": True,
            "redaction_count": len(redaction_kinds),
            "redaction_kinds": _dedupe_preserving_order(redaction_kinds),
            "complete": execution.output_complete,
            "bytes_captured": len(execution.output_bytes),
            "decoded_with_replacement": replaced,
            "combined_stdout_stderr": True,
            "combined_text": redacted_text,
            "redaction_note": (
                "Output was bounded during capture and then passed through basic "
                "secret-like redaction. Redaction is a best-effort backstop, not "
                "a guarantee, and this text is project-controlled."
            ),
        },
        "workspace_precondition": {
            "platform_supported": True,
            "project_verification_enabled": True,
            "project_identity_matched": True,
            "exactly_one_change": True,
            "change_type_is_modify": True,
            "lexical_write_policy_checked": True,
            "canonicalization_verified": True,
            "target_is_regular_file": True,
            "git_executable_resolved_absolute": True,
            "git_config_execution_surface_supported": True,
            "git_index_simple_and_submodule_free": True,
            "target_tracked_as_ordinary_blob": True,
            "exact_approved_post_image_present": True,
            "only_approved_target_git_dirty": True,
            "approved_target_is_unstaged_modification": True,
            "head_object_id_recorded": True,
        },
        "workspace_postcondition": postcondition.model_dump(),
        "capability_boundaries": {
            "orchestrator_model_called": False,
            "orchestrator_network_called": False,
            "orchestrator_github_accessed": False,
            "orchestrator_shell_invoked": False,
            "orchestrator_files_written": False,
            # Every one of these is scoped to AIDO. The child is not sandboxed
            # and may itself run Git, branch, commit, or push; a push in
            # particular leaves no trace in the post-execution working tree.
            "orchestrator_git_mutation_performed": False,
            "orchestrator_branch_created": False,
            "orchestrator_committed": False,
            "orchestrator_pushed": False,
            "orchestrator_pr_created": False,
            "orchestrator_retry_attempted": False,
            "orchestrator_automatic_repair_attempted": False,
            "orchestrator_rollback_or_restore_performed": False,
            "orchestrator_reviewer_or_fixer_invoked": False,
            # The honest half. AIDO controlled what was launched; it did not
            # confine what ran, and it will not pretend otherwise.
            "child_process_sandboxed": False,
            "child_process_filesystem_effects": "not sandboxed",
            "child_process_network_effects": "not sandboxed",
            "child_process_subprocess_effects": "not sandboxed",
            "child_process_git_effects": (
                "not sandboxed; not observed beyond the post-execution "
                "Git-visible state"
            ),
            "child_process_credential_access": (
                "not sandboxed; child environment minimized, not confined"
            ),
            "child_process_lifetime": (
                "not sandboxed; descendants are not tracked and may still be "
                "running"
            ),
        },
        "single_actor_contract": VERIFICATION_SINGLE_ACTOR_CONTRACT,
        "next_step": NEXT_STEP_REQUIRES_HUMAN_REVIEW,
    }

    try:
        return VerificationResultReport.model_validate(payload)
    except ValidationError as exc:  # pragma: no cover - defensive
        raise VerificationError(
            "report error: the generated verification result failed its own "
            "validation: " + _summarize_validation_error(exc)
        ) from exc
