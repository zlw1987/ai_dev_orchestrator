"""The **controlled single-file writer** (Phase 5F2C).

This is the first code in this repository that writes a byte into a target
project workspace, and the capability it adds is deliberately one sentence long:

    Given one explicitly human-approved concrete modification, transform one
    existing tracked ordinary UTF-8 file from one exact approved pre-image into
    one exact approved post-image, inside one clean supported Windows Git
    repository, prove the expected postcondition, and leave the result for human
    review.

Everything outside that sentence **fails closed**. That is the point: §27 of the
design doc records the roadmap decision that a narrow domain plus honest refusal
beats a general mutation engine built before the first useful write exists.

The supported input domain, exhaustively
----------------------------------------

Windows; a local Git working tree whose top level *is* the configured workspace
root; a valid ``HEAD``; a wholly clean repository; exactly one change;
``change_type == "modify"``; a target that is already tracked as one ordinary
stage-0 blob; an existing regular file with no reparse point, no unsupported
Windows attribute, and a hard-link count of exactly one; a project with
``allow_symlinks: false`` and ``deny_outside_workspace: true``; a non-protected,
non-forbidden, policy-allowed path that passes the Phase 5F2B canonical write
guard; ordinary UTF-8 text with one uniform line-ending convention and a
terminal newline, inside ``workspace_write.max_file_bytes``; an exact approved
pre-image digest that still matches the bytes on disk; and an exact approved
post-image digest that the strictly applied diff actually produces.

What this module does not have
------------------------------

- **No create, no delete, no rename, no mkdir, no mode or ownership change.**
  ``create`` is refused outright even though the approval schema can express it.
- **No multi-file write.** More than one change is refused before anything is
  touched, whatever ``max_changed_files`` allows.
- **No protected-path write**, and no flag or config field that could permit one.
- **No fuzzy patching.** ``patch``, ``git apply`` and every other fuzzy engine
  are absent; :mod:`ai_dev_orchestrator.file_editing.diff_apply` applies the diff
  exactly or refuses.
- **No project verification.** ``required_verification``, pytest, npm, make and
  every model-proposed command are unreachable from here. The only subprocess
  this module can cause is the fixed Git inspection set of
  :mod:`ai_dev_orchestrator.workspace.git_adapter`, which is part of the
  writer's own correctness contract rather than a repository-controlled
  capability.
- **No repository-controlled program execution** (Phase 5F2C-FU1). Git runs
  clean/smudge/process *filters* configured by the repository itself, from
  inside a perfectly fixed argv — including during ``git status`` on a clean
  tree. A repository whose effective Git configuration could cause that is
  **refused**, by a gate that runs before anything reads working-tree content.
- **No model call, no network call, no environment credential read, no GitHub
  access, no branch, no commit, no push, no PR.**
- **No transaction framework, no journal, no backup, no rollback, no crash
  recovery, and no concurrency control.** See :data:`SINGLE_WRITER_CONTRACT`.

Time of check, time of use
--------------------------

Phase 5F2B states plainly that its result is a point-in-time observation, not a
durable authorization, so nothing here caches one. The canonical guard, the file
metadata, the hard-link count, the pre-image bytes and the pre-image digest are
**all re-established immediately before the replacement**, and the Git baseline
is re-proved as well. That narrows the window; it does not close it, and this
module does not claim otherwise.

Failure semantics
-----------------

Two failure kinds, never conflated:

- :class:`WorkspaceWriteRefusedError` — raised **before any replacement was
  attempted**. The target is unchanged, and the report says so.
- :class:`WorkspaceWriteIndeterminateError` — raised **after** a replacement was
  attempted and its postconditions could not be completely proved. It never
  claims nothing changed. Nothing is retried, nothing is rolled back, no
  ``git restore`` is run, and the human is told that repository inspection is
  required. The clean Git baseline proved beforehand is the recovery reference.
"""

from __future__ import annotations

import hashlib
import os
import stat as stat_module
import sys
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from ai_dev_orchestrator.file_editing.diff_apply import (
    StrictDiffApplyError,
    apply_strict_unified_diff,
)
from ai_dev_orchestrator.file_editing.models import (
    ApprovedDiffProposalArtifact,
    _summarize_validation_error,
)
from ai_dev_orchestrator.models import ProjectConfig
from ai_dev_orchestrator.workspace import (
    CanonicalPathError,
    GitAdapterError,
    PathClassification,
    PathPolicy,
    canonicalize_write_target_under_workspace,
    find_unsupported_config_keys,
    ordered_preflight_operations,
    parse_config_name_only,
    parse_config_scoped_name_only,
    parse_ls_files_stage,
    parse_ls_files_verbose,
    parse_status_porcelain,
    resolve_git_executable,
    run_fixed_git_operation,
    status_record_path,
)

# The report's schema identity, compared with ``==`` through a ``Literal``.
WORKSPACE_WRITE_SCHEMA_VERSION = "workspace-write-result.v1"

# What this operation *is*. One mode, and it names its own narrowness.
WORKSPACE_WRITE_MODE = "controlled-single-file-modify"

# The concurrency contract, carried in the report so it travels with the result.
SINGLE_WRITER_CONTRACT = (
    "Phase 5F2C supports one AIDO writer operating against a quiescent "
    "workspace. Concurrent modification by a human, an editor, or another "
    "process is outside the supported execution contract. There is no lock, no "
    "filesystem watcher, and no cross-invocation mutual exclusion: interference "
    "is detected by immediate pre-write revalidation and immediate post-write "
    "verification, and detection means failing closed. Concurrency is not "
    "solved."
)

# What a human must do next, and what must be authorized before anything more.
NEXT_STEP_REQUIRES_HUMAN_REVIEW = (
    "The change is left uncommitted in the working tree for human review. "
    "This writer verified nothing by running the project's own checks, "
    "committed nothing, pushed nothing, and opened no PR. Running the project's "
    "verification and taking the result to a reviewer model are the separate, "
    "separately gated Phase 5F2D and Phase 5F2E commands, each of which a human "
    "invokes deliberately; nothing consumes this result automatically, and a "
    "reviewer verdict is advisory."
)

# The largest human-facing Git diff the report will carry. Beyond it the diff is
# omitted with a note rather than truncated mid-hunk.
MAX_REPORTED_GIT_DIFF_CHARS = 100_000

# Git index modes this writer accepts for its one target: an ordinary file, or
# an ordinary executable file. 120000 (symlink) and 160000 (gitlink) are not
# here, and neither is anything else.
_ORDINARY_BLOB_MODES = ("100644", "100755")

# The prefix of the single sibling temp file the writer may create. Distinctive
# so a leftover is unmistakably AIDO's, and always removed on a safe failure
# path or consumed by a successful replacement.
_TEMP_FILE_PREFIX = ".aido-write-"
_TEMP_FILE_SUFFIX = ".tmp"


class WorkspaceWriteError(Exception):
    """Base class for Phase 5F2C writer failures.

    Messages name the failure **category** and, where it helps, the relative
    path. They never echo file contents, diff text, the approval text, the raw
    artifact, an absolute path, an environment value, or a credential.
    """

    category = "workspace-write-failure"


class WorkspaceWriteRefusedError(WorkspaceWriteError):
    """Refused **before** any replacement was attempted; the target is unchanged."""

    category = "refused-before-write"


class WorkspaceWriteIndeterminateError(WorkspaceWriteError):
    """A replacement was attempted and its final state could not be proved.

    This is never raised for a failure that happened before the write. It exists
    so that "nothing changed" is never claimed when it might not be true.
    """

    category = "write-attempted-state-indeterminate"


class _Strict(BaseModel):
    """Base model that rejects unknown fields, so forged extras fail loudly."""

    model_config = ConfigDict(extra="forbid")


class WorkspaceWriteChecks(_Strict):
    """The postconditions this writer actually proved, each a ``Literal[True]``.

    A report that could not honestly claim one of these is never produced: each
    is a precondition of reaching the end of the operation, not an observation
    recorded afterwards.
    """

    platform_supported: Literal[True]
    project_write_enabled: Literal[True]
    project_identity_matched: Literal[True]
    exactly_one_change: Literal[True]
    change_type_is_modify: Literal[True]
    lexical_write_policy_checked: Literal[True]
    canonicalization_verified: Literal[True]
    target_is_regular_file: Literal[True]
    hard_link_count_is_one: Literal[True]
    file_attributes_supported: Literal[True]
    git_executable_resolved_absolute: Literal[True]
    git_config_execution_surface_supported: Literal[True]
    git_index_simple_and_submodule_free: Literal[True]
    git_baseline_clean: Literal[True]
    target_tracked: Literal[True]
    pre_image_verified: Literal[True]
    diff_applied_strictly: Literal[True]
    post_image_digest_matched_before_write: Literal[True]
    revalidated_immediately_before_write: Literal[True]
    post_image_verified_on_disk: Literal[True]
    only_approved_target_dirty: Literal[True]


class WorkspaceWriteExclusions(_Strict):
    """The capabilities this operation did **not** exercise, each ``Literal[False]``.

    This block is the point of the report. A reader must be able to see, without
    reading this source, that a command which wrote a file did not also run the
    project's tests, call a model, open a socket, or touch GitHub.

    Every field here is scoped to the **approved target**. Phase 5F2C-FU1
    renamed the file-lifecycle flags for exactly that reason: a blanket
    ``files_created: false`` was misleading, because a successful write always
    creates one ephemeral operational sibling temp file. That fact now lives in
    :class:`WorkspaceWriteOperationalFiles` where it can be read honestly.
    """

    project_verification_commands_run: Literal[False]
    arbitrary_commands_run: Literal[False]
    shell_invoked: Literal[False]
    model_called: Literal[False]
    network_called: Literal[False]
    github_accessed: Literal[False]
    target_files_created: Literal[False]
    target_files_deleted: Literal[False]
    target_files_renamed: Literal[False]
    directories_created: Literal[False]
    protected_path_written: Literal[False]
    branch_created: Literal[False]
    committed: Literal[False]
    pushed: Literal[False]
    pr_created: Literal[False]
    rollback_performed: Literal[False]
    backup_or_journal_written: Literal[False]


class WorkspaceWriteOperationalFiles(_Strict):
    """What this operation created on disk **besides** modifying the target.

    Phase 5F2C-FU1. The previous report said ``files_created: false``, which was
    not true: the writer stages the post-image into one sibling temp file before
    ``ReplaceFileW`` swaps it in. Nothing about that is unsafe, but a safety
    report that overstates its own inertness is worse than one that admits a
    detail, so the detail is stated.

    - ``temp_sibling_used`` — one temp file was created in the approved
      destination's own directory. It is the single narrowly authorized path
      outside the destination itself.
    - ``temp_sibling_consumed_by_replacement`` — a successful ``ReplaceFileW``
      *consumes* the replacement file, so on the success path nothing is left
      behind. (A pre-replacement failure deletes it; after a replacement attempt
      cleanup is forbidden, and that path produces no report at all.)
    - ``directories_created`` and ``backup_or_journal_files_created`` are
      ``False`` because neither capability exists in this phase.
    """

    temp_sibling_used: Literal[True]
    temp_sibling_consumed_by_replacement: Literal[True]
    temp_sibling_left_behind: Literal[False]
    directories_created: Literal[False]
    backup_or_journal_files_created: Literal[False]


class WorkspaceWriteTarget(_Strict):
    """The one file that changed, by relative path and by size only.

    There is no absolute path field, no content field, and no digest field: a
    digest of a small source file is a value a reader could confirm content
    against, so the report states that the identities *matched* rather than what
    they were.
    """

    path: str
    change_type: Literal["modify"]
    line_ending: Literal["lf", "crlf"]
    pre_image_bytes: int
    post_image_bytes: int


class WorkspaceWriteGitBlock(_Strict):
    """What was proved about the repository, and by which fixed operations.

    ``git_executable_absolute`` and ``git_executable_outside_workspace`` record
    the Phase 5F2C-FU1 executable contract: one absolute path, resolved before
    any workspace use and reused for every invocation in the run. The path
    itself is **not** reported — it is an absolute filesystem path, and this
    report carries none.

    ``unsupported_config_refused`` records that the configuration gate ran and
    found nothing execution-capable. A repository that *did* carry such a key
    never reaches a report at all.
    """

    baseline_clean: Literal[True]
    head_present: Literal[True]
    worktree_root_is_workspace_root: Literal[True]
    git_executable_absolute: Literal[True]
    git_executable_outside_workspace: Literal[True]
    git_executable_pinned_for_run: Literal[True]
    config_execution_surface_checked: Literal[True]
    unsupported_config_found: Literal[False]
    fixed_operations_used: list[str]
    dirty_paths_after_write: list[str]
    target_diff_available: bool
    target_diff: str | None = None


class WorkspaceWriteReport(_Strict):
    """The structured, human-reviewable result of one controlled write.

    Deliberately absent, because there is no field for any of them: the
    configured workspace path, any absolute path, any API key, any environment
    value, the approval text, the raw input artifact, the approved unified diff,
    any unrelated source file, and any arbitrary command output. The one place
    repository text may appear is ``git.target_diff``, which is Git's own diff
    for the single approved path, produced with external diff and textconv
    disabled, and bounded.
    """

    schema_version: Literal[WORKSPACE_WRITE_SCHEMA_VERSION]  # type: ignore[valid-type]
    mode: Literal[WORKSPACE_WRITE_MODE]  # type: ignore[valid-type]
    outcome: Literal["written-and-verified"]
    project_id: str
    repo: str
    issue_number: int
    title: str
    approved_by: str
    approved_at: datetime
    target: WorkspaceWriteTarget
    files_edited: Literal[1]
    checks: WorkspaceWriteChecks
    exclusions: WorkspaceWriteExclusions
    operational_files: WorkspaceWriteOperationalFiles
    git: WorkspaceWriteGitBlock
    single_writer_contract: str
    next_step: str


# -- Small helpers -------------------------------------------------------------


def _sha256_hex(data: bytes) -> str:
    """Digest exact bytes. No normalization of any kind happens first."""
    return hashlib.sha256(data).hexdigest()


def _read_bounded_file_bytes(path: str, *, limit: int) -> bytes:
    """Read at most ``limit`` bytes, refusing a file that exceeds the cap.

    ``limit + 1`` bytes are requested so that "exactly at the cap" and "over the
    cap" are distinguishable without stat'ing first and trusting the answer: a
    file that grew between a stat and an open would otherwise slip past.

    Module level and not a method, so a test can monkeypatch it to simulate a
    concurrent modification between the first read and the final pre-write
    re-read.
    """
    try:
        with open(path, "rb") as handle:
            data = handle.read(limit + 1)
    except OSError as exc:
        raise WorkspaceWriteRefusedError(
            "read error: the write destination could not be read, so its "
            "pre-image could not be established. Nothing was written."
        ) from exc
    if len(data) > limit:
        raise WorkspaceWriteRefusedError(
            f"size error: the write destination exceeds this project's "
            f"workspace_write.max_file_bytes of {limit}. It is refused, never "
            "truncated, and nothing was written."
        )
    return data


def _decode_supported_text(data: bytes, *, role: str) -> str:
    """Decode strictly as UTF-8 and refuse binary-looking content."""
    if b"\x00" in data:
        raise WorkspaceWriteRefusedError(
            f"content error: the {role} contains a NUL byte, so it is not the "
            "ordinary UTF-8 text this writer supports. Nothing was written."
        )
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise WorkspaceWriteRefusedError(
            f"content error: the {role} is not valid UTF-8. This writer supports "
            "ordinary UTF-8 text only, performs no encoding detection and no "
            "conversion, and refuses rather than guessing. Nothing was written."
        ) from exc


def _detect_uniform_line_ending(text: str) -> str:
    """Return ``"\\n"`` or ``"\\r\\n"``, or refuse a file outside the domain.

    Refused: mixed conventions, lone ``\\r`` (classic Mac), and a file with no
    line terminator at all. The last two are refusals rather than gaps — a
    writer that guessed would be reintroducing exactly the normalization this
    phase exists to avoid.
    """
    crlf = text.count("\r\n")
    lone_lf = text.count("\n") - crlf
    lone_cr = text.count("\r") - crlf

    if lone_cr:
        raise WorkspaceWriteRefusedError(
            "line-ending error: the write destination contains a bare carriage "
            "return. Only uniform LF or uniform CRLF text is supported, and "
            "nothing is normalized. Nothing was written."
        )
    if crlf and lone_lf:
        raise WorkspaceWriteRefusedError(
            "line-ending error: the write destination mixes CRLF and LF line "
            "endings. This writer preserves one uniform convention and refuses "
            "to choose between two. Nothing was written."
        )
    if crlf:
        return "\r\n"
    if lone_lf:
        return "\n"
    raise WorkspaceWriteRefusedError(
        "line-ending error: the write destination has no line terminator at "
        "all, so its line structure and terminal-newline state cannot be "
        "represented exactly. Nothing was written."
    )


def _split_content_lines(text: str, line_ending: str) -> list[str]:
    """Split text that is required to end in ``line_ending`` into content lines.

    Requiring a terminal newline is what makes the round trip exact: with it,
    ``line_ending.join(lines) + line_ending`` reproduces the original string
    byte for byte, so applying a diff over lines and rejoining cannot silently
    add or drop a trailing newline.
    """
    if not text.endswith(line_ending):
        raise WorkspaceWriteRefusedError(
            "line-ending error: the write destination does not end with a "
            "terminal newline. Phase 5F2C requires one so that line structure "
            "round-trips exactly, and adds nothing of its own. Nothing was "
            "written."
        )
    return text[: -len(line_ending)].split(line_ending)


def _join_content_lines(lines: list[str], line_ending: str) -> str:
    """The exact inverse of :func:`_split_content_lines`."""
    return line_ending.join(lines) + line_ending


# -- Gate 1: identity, scope, and policy (no workspace touch yet) ---------------


def _check_platform() -> None:
    if sys.platform != "win32":
        raise WorkspaceWriteRefusedError(
            "platform error: the Phase 5F2C writer is Windows-only. It refuses "
            "here rather than pretending to be cross-platform, and no target "
            "workspace was touched."
        )


def _check_project_opt_in(project: ProjectConfig) -> None:
    if not project.workspace_write.enabled:
        raise WorkspaceWriteRefusedError(
            "opt-in error: this project's workspace_write block is absent or "
            "disabled, so no file may be written for it. No target workspace "
            "was touched."
        )


def _check_identity(
    approved_diff: ApprovedDiffProposalArtifact, project: ProjectConfig
) -> None:
    """Refuse an approved diff that is not this project's, exactly.

    Six comparisons, matching the Phase 5F1 preview: the wrapper, the proposal's
    provenance, and the approved plan nested inside it. String equality only,
    reported by field name, echoing no value.
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
        raise WorkspaceWriteRefusedError(
            "identity error: the approved diff proposal does not match this "
            "project config exactly; mismatched fields: "
            + ", ".join(mismatched)
            + ". An approval given for one project or repo authorizes no write "
            "in another. Nothing was written."
        )


def _check_single_modify_change(
    approved_diff: ApprovedDiffProposalArtifact, project: ProjectConfig
):
    """Require exactly one change, and require it to be a ``modify``."""
    changes = approved_diff.diff_proposal.changes
    limit = project.workspace_policy.max_changed_files

    if limit < 1:
        raise WorkspaceWriteRefusedError(
            "scope error: this project's workspace_policy.max_changed_files is "
            f"{limit}, which permits no write at all. Nothing was written."
        )
    if len(changes) != 1:
        raise WorkspaceWriteRefusedError(
            f"scope error: the approved diff proposal carries {len(changes)} "
            "changes. Phase 5F2C writes exactly one file per invocation, "
            "regardless of a larger configured max_changed_files, and it does "
            "not apply a subset. Nothing was written."
        )

    change = changes[0]
    if change.change_type != "modify":
        raise WorkspaceWriteRefusedError(
            f"scope error: change_type is {change.change_type!r}. Phase 5F2C "
            "supports 'modify' only; creating a file is a separately authorized "
            "capability this writer does not have. Nothing was written."
        )
    if change.pre_image_sha256 is None:
        raise WorkspaceWriteRefusedError(
            "approval error: the approved 'modify' change carries no "
            "pre_image_sha256, so there is no record of which exact bytes the "
            "human approved transforming. Nothing was written."
        )
    return change


def _check_workspace_policy_flags(project: ProjectConfig) -> None:
    policy = project.workspace_policy
    if policy.allow_symlinks:
        raise WorkspaceWriteRefusedError(
            "policy error: this project sets workspace_policy.allow_symlinks "
            "true. Phase 5F2C writes only into projects that refuse link "
            "traversal outright. Nothing was written."
        )
    if not policy.deny_outside_workspace:
        raise WorkspaceWriteRefusedError(
            "policy error: this project sets "
            "workspace_policy.deny_outside_workspace false. Phase 5F2C writes "
            "only into projects that keep the containment rule on. Nothing was "
            "written."
        )


def _check_lexical_write_policy(path: str, project: ProjectConfig) -> None:
    """Run the Phase 1 lexical write check, with no protected-path escape hatch."""
    policy = PathPolicy.from_project_config(project)
    decision = policy.check_write(path)
    if decision.permitted:
        return
    if decision.classification is PathClassification.PROTECTED:
        raise WorkspaceWriteRefusedError(
            f"policy error: path {path!r} is classified PROTECTED by this "
            "project's path rules. Phase 5F2C refuses protected destinations "
            "outright and ships no flag and no config field to permit one. "
            "Nothing was written."
        )
    raise WorkspaceWriteRefusedError(
        f"policy error: path {path!r} is refused by this project's lexical "
        f"write policy ({decision.classification.value}: {decision.reason}). "
        "Nothing was written."
    )


# -- Gate 2: the canonical write target and its filesystem metadata ------------


def _canonicalize(path: str, project: ProjectConfig):
    try:
        return canonicalize_write_target_under_workspace(
            project.repo.workspace_path,
            path,
            change_type="modify",
            allow_symlinks=False,
        )
    except CanonicalPathError as exc:
        raise WorkspaceWriteRefusedError(
            f"canonicalization error: {type(exc).__name__}: {exc} Nothing was "
            "written."
        ) from exc


def _check_target_filesystem_state(resolved_destination: str) -> int:
    """Prove the destination is an ordinary, single-linked, supported file.

    Returns the Windows attribute mask, so the caller can require the same mask
    to still be present after the replacement — which is the observable half of
    the metadata-preservation claim ``ReplaceFileW`` makes.
    """
    from ai_dev_orchestrator.file_editing.windows_write import (
        WindowsWriteError,
        describe_unsupported_attributes,
        query_windows_file_info,
    )

    try:
        lstat_result = os.lstat(resolved_destination)
    except OSError as exc:
        raise WorkspaceWriteRefusedError(
            "target error: the write destination could not be examined. Nothing "
            "was written."
        ) from exc
    if not stat_module.S_ISREG(lstat_result.st_mode):
        raise WorkspaceWriteRefusedError(
            "target error: the write destination is not a regular file. Nothing "
            "was written."
        )

    try:
        information = query_windows_file_info(resolved_destination)
    except WindowsWriteError as exc:
        raise WorkspaceWriteRefusedError(
            f"target error: {exc} Nothing was written."
        ) from exc

    unsupported = describe_unsupported_attributes(information.attributes)
    if unsupported:
        raise WorkspaceWriteRefusedError(
            "target error: the write destination carries Windows file "
            f"attributes this writer does not support ({', '.join(unsupported)}). "
            "Preserving semantics it has not reasoned about is not something it "
            "can claim to do, so it refuses. Nothing was written."
        )

    if information.link_count != 1:
        raise WorkspaceWriteRefusedError(
            f"target error: the write destination has {information.link_count} "
            "hard links. Replacement rebinds only the approved name, so the "
            "other names would keep the old content and the approved path would "
            "silently leave the link set — which is not the in-place change a "
            "reviewer expects. Nothing was written."
        )

    return information.attributes


# -- Gate 3: the Git contract --------------------------------------------------


def _resolve_git(workspace_root: str) -> str:
    """Pin one absolute Git executable for the whole run, before any Git call."""
    try:
        return resolve_git_executable(workspace_root=workspace_root)
    except GitAdapterError as exc:
        raise WorkspaceWriteRefusedError(f"{exc} Nothing was written.") from exc


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
        raise WorkspaceWriteRefusedError(
            f"git error: {exc} Nothing was written."
        ) from exc


def _prove_worktree_root_and_head(workspace_root: str, *, git_executable: str) -> None:
    """Safe metadata only: no working-tree content is read, so no filter can run.

    This is the first Git the writer runs, and it is deliberately the two
    questions that cannot cause Git to open a tracked file.
    """
    toplevel = _git(
        "rev_parse_show_toplevel", workspace_root, git_executable=git_executable
    ).stdout.strip()
    if not toplevel:
        raise WorkspaceWriteRefusedError(
            "git error: the configured workspace is not inside a Git working "
            "tree. Nothing was written."
        )
    if os.path.normcase(os.path.realpath(toplevel)) != os.path.normcase(
        os.path.realpath(workspace_root)
    ):
        raise WorkspaceWriteRefusedError(
            "git error: the Git working-tree top level is not the configured "
            "workspace root. Phase 5F2C writes only when the two are exactly "
            "the same directory. Nothing was written."
        )

    _git("rev_parse_head", workspace_root, git_executable=git_executable)


def _prove_supported_git_configuration(
    workspace_root: str, *, git_executable: str
) -> None:
    """Refuse a repository whose Git config can execute or indirect (5F2C-FU1).

    This is the gate that closes the filter escape, and it must run **before**
    any operation that reads working-tree content. A repository-configured
    ``filter.<driver>.clean`` is executed by Git itself during ``git status`` —
    including on a clean tree, whenever a tracked path's cached stat data is
    stale — so "fixed argv plus ``shell=False``" never prevented it.

    Two fixed operations, in this order and for this reason:

    1. ``config --list --local --no-includes`` answers "does this repository ask
       us to follow configuration somewhere else, and does its own file define
       anything execution-capable?" — **without following the indirection**, so
       the decision about whether includes are allowed is not itself made by
       processing them.
    2. Only once that passes, ``config --list --show-scope`` covers every scope
       Git would actually apply, catching an execution-capable key inherited
       from the user's global config (git-lfs's ``filter.lfs.*`` is the common
       real-world case). This module's own ``-c`` hardening flags arrive in the
       ``command`` scope and are excluded.

    Only key **names** are read — ``--name-only`` — so no configuration value
    ever enters this process and no refusal can leak one.

    A repository carrying such a key is **unsupported**, not repaired and not
    worked around. Deciding which configured command would be safe to run is
    exactly the judgement this phase declines to make.
    """
    # A repository with no local config file at all makes `--list --local` exit
    # 1 with no output. That is "nothing configured", not a failure.
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
        raise WorkspaceWriteRefusedError(
            "git config error: this repository's own Git configuration defines "
            "keys that can cause Git to execute a program or follow "
            "configuration indirection, so the repository is unsupported: "
            + ", ".join(unsupported)
            + ". Phase 5F2C refuses such a repository rather than deciding "
            "which configured command would be safe to run. No configuration "
            "value was read. Nothing was written."
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
        raise WorkspaceWriteRefusedError(
            "git config error: the Git configuration in effect for this "
            "repository defines keys that can cause Git to execute a program "
            "or follow configuration indirection, so the repository is "
            "unsupported here: "
            + ", ".join(unsupported)
            + ". This includes configuration inherited from the user's global "
            "Git config. Phase 5F2C refuses rather than deciding which "
            "configured command would be safe to run. No configuration value "
            "was read. Nothing was written."
        )


def _prove_simple_index(
    workspace_root: str, relative_path: str, *, git_executable: str
) -> None:
    """Prove the index is simple, submodule-free, and holds the target once.

    Runs **before** ``git status`` (Phase 5F2C-FU1). The old order asked
    ``status --ignore-submodules=none`` first, which meant the status walk could
    descend into a submodule the writer was going to refuse a moment later. The
    first-writer domain already rejects gitlinks; now the rejection happens
    before anything can walk into one.

    Neither operation here reads working-tree content, so neither can run a
    clean filter. The whole repository is rejected when the simple contract
    cannot be proved, which is the preferred MVP behavior: an assume-unchanged
    or skip-worktree entry anywhere means Git's answers about this tree have a
    caveat, and a writer that proceeded would be relying on an answer it knows
    is qualified. No custom Git index parser is built — this is Git's own
    reporting, read.
    """
    entries = parse_ls_files_stage(
        _git("ls_files_stage", workspace_root, git_executable=git_executable).stdout
    )
    for entry in entries:
        if entry.mode == "160000":
            raise WorkspaceWriteRefusedError(
                "git error: the index contains a gitlink (submodule) entry, so "
                "this repository's state is not the simple one this writer "
                "supports. It is refused entirely, before any working-tree "
                "inspection could descend into it. Nothing was written."
            )
        if entry.stage != 0:
            raise WorkspaceWriteRefusedError(
                "git error: the index contains an unmerged entry. The "
                "repository is refused rather than written to. Nothing was "
                "written."
            )

    for tag, _entry_path in parse_ls_files_verbose(
        _git("ls_files_verbose", workspace_root, git_executable=git_executable).stdout
    ):
        if tag == "H":
            continue
        if tag.islower():
            raise WorkspaceWriteRefusedError(
                "git error: the index contains an assume-unchanged entry, which "
                "tells Git to stop noticing that a file changed. The repository "
                "is refused rather than written to. Nothing was written."
            )
        if tag == "S":
            raise WorkspaceWriteRefusedError(
                "git error: the index contains a skip-worktree entry. The "
                "repository is refused rather than written to. Nothing was "
                "written."
            )
        raise WorkspaceWriteRefusedError(
            f"git error: the index contains an entry with status tag {tag!r}, "
            "which is not the ordinary cached state this writer supports. The "
            "repository is refused rather than written to. Nothing was written."
        )

    matching = [entry for entry in entries if entry.path == relative_path]
    if not matching:
        raise WorkspaceWriteRefusedError(
            f"git error: path {relative_path!r} is not tracked by Git. Phase "
            "5F2C modifies tracked files only. Nothing was written."
        )
    if len(matching) != 1:
        raise WorkspaceWriteRefusedError(
            f"git error: path {relative_path!r} has more than one index entry, "
            "so its tracked state is ambiguous. Nothing was written."
        )
    entry = matching[0]
    if entry.mode not in _ORDINARY_BLOB_MODES:
        raise WorkspaceWriteRefusedError(
            f"git error: path {relative_path!r} is tracked with index mode "
            f"{entry.mode}, not an ordinary file blob. A symlink or submodule "
            "index mode is refused. Nothing was written."
        )


def _prove_clean_worktree(workspace_root: str, *, git_executable: str) -> None:
    """Prove the whole working tree is clean. **Reads working-tree content.**

    This is the last gate, because it is the first operation that can make Git
    open and hash a tracked file — which is what would run a clean filter.
    Everything that could make that dangerous has already been refused: the
    configuration gate proved no filter driver exists, and the index gate proved
    there is no submodule to descend into.

    Any Git-visible deviation refuses the run. Staged and unstaged changes,
    untracked files, deleted tracked files, renames, unmerged entries and dirty
    submodule state all surface as porcelain records, and one record is enough:
    Phase 5F2C does not interpret the status letters, because for its purposes
    they all mean the same thing.
    """
    records = parse_status_porcelain(
        _git("status_porcelain", workspace_root, git_executable=git_executable).stdout
    )
    if records:
        raise WorkspaceWriteRefusedError(
            f"git error: the repository is not clean ({len(records)} entries "
            "reported by git status: staged, unstaged, untracked, deleted, "
            "renamed, unmerged or dirty-submodule state). Phase 5F2C writes only "
            "into a wholly clean repository, so that a human has a known "
            "recovery reference. Nothing was written."
        )


def _run_git_preflight(
    workspace_root: str, relative_path: str, *, git_executable: str
) -> None:
    """Run every Git gate, in the one order that is safe (Phase 5F2C-FU1).

    The order is the safety property, and :func:`ordered_preflight_operations`
    states it as data so a test can check it: safe metadata, then the
    configuration gate, then the index gate, and only then anything that reads
    working-tree content.
    """
    _prove_worktree_root_and_head(workspace_root, git_executable=git_executable)
    _prove_supported_git_configuration(workspace_root, git_executable=git_executable)
    _prove_simple_index(workspace_root, relative_path, git_executable=git_executable)
    _prove_clean_worktree(workspace_root, git_executable=git_executable)


# -- The operation -------------------------------------------------------------


def _to_repo_relative_posix(relative_destination: str) -> str:
    """Render a canonical relative destination the way Git names it."""
    return relative_destination.replace(os.sep, "/").replace("\\", "/")


def _establish_pre_image(
    *, resolved_destination: str, expected_digest: str, limit: int
) -> bytes:
    """Read the destination and require it to be exactly the approved pre-image.

    A mismatch is **not** followed by "but does the diff still apply anyway?".
    The human approved transforming *these* bytes; different bytes are a
    different transformation, and nobody approved it.
    """
    data = _read_bounded_file_bytes(resolved_destination, limit=limit)
    if _sha256_hex(data) != expected_digest:
        raise WorkspaceWriteRefusedError(
            "pre-image error: the write destination's current bytes do not hash "
            "to the approved pre_image_sha256. The approval covers a "
            "transformation of specific bytes, and these are not those bytes. "
            "No attempt was made to apply the diff anyway, and nothing was "
            "written."
        )
    return data


def apply_approved_file_edit(
    *,
    approved_diff: ApprovedDiffProposalArtifact,
    project: ProjectConfig,
) -> WorkspaceWriteReport:
    """Apply one approved single-file modification, or refuse.

    Args:
        approved_diff: A validated Phase 5F0 file-edit approval (schema
            ``approved-diff-proposal.v2``) wrapping an untouched
            ``diff-proposal.v2`` snapshot.
        project: The project config the approval must match exactly, and whose
            ``workspace_write`` block must be enabled.

    Returns:
        A validated :class:`WorkspaceWriteReport`. Returning one means the write
        happened **and** every postcondition was proved.

    Raises:
        WorkspaceWriteRefusedError: any gate failed before a replacement was
            attempted. The target is unchanged.
        WorkspaceWriteIndeterminateError: a replacement was attempted and the
            final state could not be completely proved. **Nothing is retried,
            nothing is rolled back**, and the human must inspect the repository.
    """
    # ---- Gates that touch nothing --------------------------------------------
    _check_platform()
    _check_project_opt_in(project)
    _check_identity(approved_diff, project)
    change = _check_single_modify_change(approved_diff, project)
    _check_workspace_policy_flags(project)
    _check_lexical_write_policy(change.path, project)

    limit = project.workspace_write.max_file_bytes

    # ---- Gates that look at the filesystem -----------------------------------
    target = _canonicalize(change.path, project)
    attributes_before = _check_target_filesystem_state(target.resolved_destination)
    workspace_root = target.resolved_workspace_root
    relative_path = _to_repo_relative_posix(target.relative_destination)

    # ---- Gates that ask Git --------------------------------------------------
    # One absolute executable, resolved before any Git runs and reused for every
    # invocation below. It may not live inside the workspace being edited.
    git_executable = _resolve_git(workspace_root)
    _run_git_preflight(
        workspace_root, relative_path, git_executable=git_executable
    )

    # ---- The approved transformation, computed but not yet performed ---------
    pre_image_bytes = _establish_pre_image(
        resolved_destination=target.resolved_destination,
        expected_digest=change.pre_image_sha256,
        limit=limit,
    )
    pre_image_text = _decode_supported_text(pre_image_bytes, role="write destination")
    line_ending = _detect_uniform_line_ending(pre_image_text)
    original_lines = _split_content_lines(pre_image_text, line_ending)

    try:
        post_lines = apply_strict_unified_diff(
            original_lines=original_lines,
            unified_diff=change.unified_diff,
            path=change.path,
        )
    except StrictDiffApplyError as exc:
        raise WorkspaceWriteRefusedError(
            f"apply error: {exc} There is no fuzzy fallback and no repair. "
            "Nothing was written."
        ) from exc

    post_image_text = _join_content_lines(post_lines, line_ending)
    post_image_bytes = post_image_text.encode("utf-8")

    if len(post_image_bytes) > limit:
        raise WorkspaceWriteRefusedError(
            "size error: the resulting post-image exceeds this project's "
            f"workspace_write.max_file_bytes of {limit}. Nothing was written."
        )
    if _sha256_hex(post_image_bytes) != change.post_image_sha256:
        raise WorkspaceWriteRefusedError(
            "post-image error: applying the approved diff to the approved "
            "pre-image produced bytes that do not hash to the approved "
            "post_image_sha256. The artifact's diff and its declared result "
            "disagree, which is an internal inconsistency and not something to "
            "reconcile. Nothing was written."
        )

    # ---- Final revalidation, immediately before mutation ---------------------
    # Nothing above is reused as durable authority: Phase 5F2B says plainly that
    # its result describes one moment, so every filesystem fact is re-established
    # here, and the Git baseline is re-proved as well.
    revalidated = _canonicalize(change.path, project)
    if (
        revalidated.resolved_destination != target.resolved_destination
        or revalidated.resolved_workspace_root != workspace_root
    ):
        raise WorkspaceWriteRefusedError(
            "revalidation error: the canonical write destination changed between "
            "the first check and the final one. Nothing was written."
        )
    attributes_now = _check_target_filesystem_state(revalidated.resolved_destination)
    if attributes_now != attributes_before:
        raise WorkspaceWriteRefusedError(
            "revalidation error: the destination's Windows file attributes "
            "changed between the first check and the final one. Nothing was "
            "written."
        )
    _establish_pre_image(
        resolved_destination=revalidated.resolved_destination,
        expected_digest=change.pre_image_sha256,
        limit=limit,
    )
    _run_git_preflight(
        workspace_root, relative_path, git_executable=git_executable
    )

    # ---- The one mutation ----------------------------------------------------
    from ai_dev_orchestrator.file_editing.windows_write import (
        WindowsReplacementAttemptedError,
        WindowsStagingError,
        WindowsWriteError,
        replace_file_with_bytes,
    )

    temp_name = f"{_TEMP_FILE_PREFIX}{uuid.uuid4().hex}{_TEMP_FILE_SUFFIX}"
    try:
        replace_file_with_bytes(
            destination=revalidated.resolved_destination,
            parent_directory=revalidated.resolved_parent,
            data=post_image_bytes,
            temp_name=temp_name,
        )
    except WindowsStagingError as exc:
        # Everything failed before ReplaceFileW was invoked, and the helper
        # removed its own temp file. The destination is untouched.
        raise WorkspaceWriteRefusedError(f"{exc} Nothing was written.") from exc
    except WindowsReplacementAttemptedError as exc:
        # ReplaceFileW was invoked and failed. Nothing was cleaned up, and this
        # writer must not clean up either: the filesystem is indeterminate.
        raise WorkspaceWriteIndeterminateError(
            f"{exc} A replacement was attempted, so this is NOT a claim that "
            "nothing changed. Nothing was retried, nothing was rolled back, and "
            "the operational temp file was deliberately left in place rather "
            "than deleted: inspect the repository against its clean baseline."
        ) from exc
    except WindowsWriteError as exc:
        # An unclassified failure from the write helper. It cannot be proved to
        # have happened before the replacement call, so it is treated as the
        # more serious outcome.
        raise WorkspaceWriteIndeterminateError(
            f"{exc} This failure could not be proved to have occurred before the "
            "replacement call, so it is reported as indeterminate rather than as "
            "a refusal. Nothing was retried and nothing was rolled back."
        ) from exc

    # ---- Post-write machine verification -------------------------------------
    return _verify_after_write(
        approved_diff=approved_diff,
        project=project,
        change=change,
        workspace_root=workspace_root,
        relative_path=relative_path,
        limit=limit,
        line_ending=line_ending,
        pre_image_bytes=pre_image_bytes,
        post_image_bytes=post_image_bytes,
        attributes_before=attributes_before,
        git_executable=git_executable,
    )


def _verify_after_write(
    *,
    approved_diff: ApprovedDiffProposalArtifact,
    project: ProjectConfig,
    change,
    workspace_root: str,
    relative_path: str,
    limit: int,
    line_ending: str,
    pre_image_bytes: bytes,
    post_image_bytes: bytes,
    attributes_before: int,
    git_executable: str,
) -> WorkspaceWriteReport:
    """Prove the postconditions, or raise the indeterminate failure.

    A successful ``ReplaceFileW`` is **not** proof that the write is correct.
    Machine truth here is three things: the destination's exact bytes hash to the
    approved post-image digest; exactly the approved path is Git-dirty; and no
    other staged, unstaged, untracked, unmerged or submodule state appeared.

    Git's own textual diff is deliberately **not** required to match the
    approved ``difflib`` text byte for byte — they are two renderings of the same
    change, produced by different tools with different context conventions. The
    diff in the report is for the human; the post-image digest is the
    correctness invariant.

    Every failure in this function is indeterminate, never a refusal: the write
    already happened.
    """

    def indeterminate(reason: str) -> WorkspaceWriteIndeterminateError:
        return WorkspaceWriteIndeterminateError(
            f"post-write verification error: {reason} A replacement was "
            "performed, so this is NOT a claim that nothing changed. Nothing "
            "was retried, nothing was rolled back, and no git restore was run: "
            "inspect the repository against the clean baseline this run proved "
            "beforehand."
        )

    try:
        revalidated = canonicalize_write_target_under_workspace(
            project.repo.workspace_path,
            change.path,
            change_type="modify",
            allow_symlinks=False,
        )
    except CanonicalPathError as exc:
        raise indeterminate(
            "the destination could not be re-canonicalized after the write."
        ) from exc

    try:
        with open(revalidated.resolved_destination, "rb") as handle:
            actual = handle.read(limit + 1)
    except OSError as exc:
        raise indeterminate(
            "the destination could not be re-read after the write."
        ) from exc

    if actual != post_image_bytes or _sha256_hex(actual) != change.post_image_sha256:
        raise indeterminate(
            "the destination's bytes after the write do not equal the approved "
            "post-image."
        )

    from ai_dev_orchestrator.file_editing.windows_write import (
        WindowsWriteError,
        query_windows_file_info,
    )

    try:
        attributes_after = query_windows_file_info(
            revalidated.resolved_destination
        ).attributes
    except WindowsWriteError as exc:
        raise indeterminate(
            "the destination's file attributes could not be re-read after the "
            "write."
        ) from exc
    if attributes_after != attributes_before:
        raise indeterminate(
            "the destination's Windows file attributes were not preserved across "
            "the replacement, so a content-only approved change did not stay "
            "content-only."
        )

    try:
        status = run_fixed_git_operation(
            "status_porcelain",
            git_executable=git_executable,
            workspace_root=workspace_root,
        )
        records = parse_status_porcelain(status.stdout)
        dirty_paths = sorted({status_record_path(record) for record in records})
    except GitAdapterError as exc:
        raise indeterminate(
            "repository state could not be re-established after the write."
        ) from exc

    if dirty_paths != [relative_path]:
        raise indeterminate(
            f"git reports {len(dirty_paths)} changed or untracked path(s) after "
            "the write, not exactly the one approved path."
        )
    for record in records:
        if record[:2] != " M":
            raise indeterminate(
                "the approved path is not reported as an unstaged modification "
                "after the write."
            )

    target_diff: str | None = None
    diff_available = False
    try:
        diff_result = run_fixed_git_operation(
            "diff_one_path",
            git_executable=git_executable,
            workspace_root=workspace_root,
            repo_relative_path=relative_path,
        )
    except GitAdapterError:
        # The human-facing diff is a convenience, not a correctness invariant.
        # Failing to render it does not make a verified write indeterminate.
        diff_result = None
    if diff_result is not None and len(diff_result.stdout) <= MAX_REPORTED_GIT_DIFF_CHARS:
        target_diff = diff_result.stdout
        diff_available = True

    approval = approved_diff.approval
    payload = {
        "schema_version": WORKSPACE_WRITE_SCHEMA_VERSION,
        "mode": WORKSPACE_WRITE_MODE,
        "outcome": "written-and-verified",
        "project_id": project.project_id,
        "repo": project.repo.github_repo,
        "issue_number": approved_diff.issue_number,
        "title": approved_diff.title,
        "approved_by": approval.approved_by,
        "approved_at": approval.approved_at,
        "target": {
            "path": change.path,
            "change_type": "modify",
            "line_ending": "crlf" if line_ending == "\r\n" else "lf",
            "pre_image_bytes": len(pre_image_bytes),
            "post_image_bytes": len(post_image_bytes),
        },
        "files_edited": 1,
        "checks": {
            "platform_supported": True,
            "project_write_enabled": True,
            "project_identity_matched": True,
            "exactly_one_change": True,
            "change_type_is_modify": True,
            "lexical_write_policy_checked": True,
            "canonicalization_verified": True,
            "target_is_regular_file": True,
            "hard_link_count_is_one": True,
            "file_attributes_supported": True,
            "git_executable_resolved_absolute": True,
            "git_config_execution_surface_supported": True,
            "git_index_simple_and_submodule_free": True,
            "git_baseline_clean": True,
            "target_tracked": True,
            "pre_image_verified": True,
            "diff_applied_strictly": True,
            "post_image_digest_matched_before_write": True,
            "revalidated_immediately_before_write": True,
            "post_image_verified_on_disk": True,
            "only_approved_target_dirty": True,
        },
        # Properties of a module that imports no client, no socket, no patch
        # tool, and whose only subprocess capability is a closed set of Git
        # inspection commands.
        "exclusions": {
            "project_verification_commands_run": False,
            "arbitrary_commands_run": False,
            "shell_invoked": False,
            "model_called": False,
            "network_called": False,
            "github_accessed": False,
            # Scoped to the approved target. One operational sibling temp file
            # IS created on the success path; that is recorded honestly in
            # `operational_files` rather than denied here.
            "target_files_created": False,
            "target_files_deleted": False,
            "target_files_renamed": False,
            "directories_created": False,
            "protected_path_written": False,
            "branch_created": False,
            "committed": False,
            "pushed": False,
            "pr_created": False,
            "rollback_performed": False,
            "backup_or_journal_written": False,
        },
        "operational_files": {
            # A successful replacement consumes the staged sibling, so reaching
            # this point means it was used and is gone.
            "temp_sibling_used": True,
            "temp_sibling_consumed_by_replacement": True,
            "temp_sibling_left_behind": False,
            "directories_created": False,
            "backup_or_journal_files_created": False,
        },
        "git": {
            "baseline_clean": True,
            "head_present": True,
            "worktree_root_is_workspace_root": True,
            "git_executable_absolute": True,
            "git_executable_outside_workspace": True,
            "git_executable_pinned_for_run": True,
            "config_execution_surface_checked": True,
            "unsupported_config_found": False,
            "fixed_operations_used": [
                *ordered_preflight_operations(),
                "diff_one_path",
            ],
            "dirty_paths_after_write": dirty_paths,
            "target_diff_available": diff_available,
            "target_diff": target_diff,
        },
        "single_writer_contract": SINGLE_WRITER_CONTRACT,
        "next_step": NEXT_STEP_REQUIRES_HUMAN_REVIEW,
    }

    try:
        return WorkspaceWriteReport.model_validate(payload)
    except ValidationError as exc:
        raise indeterminate(
            "the generated result report failed its own validation: "
            + _summarize_validation_error(exc)
        ) from exc
