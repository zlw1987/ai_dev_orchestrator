"""**Dry-run file-edit preview** models and a pure builder (Phase 5F1).

Phase 5F0 typed the human approval a future file-editing phase would have to be
handed. Nothing consumed it. Phase 5F1 is the first thing that reads one — and
it reads it only to say, out loud and in JSON, *what a future write phase would
be allowed to attempt*.

**Phase 5F1 is not file editing.** It is not diff application, not an
apply-cleanliness check, not command execution, not model-backed L2, and not L2.
There is no writer here, no applier, no runner, and no git helper. A preview is
a description of a hypothetical, produced without touching the thing it
describes.

What the preview actually establishes
-------------------------------------

Three things, and no more:

1. the Phase 5F0 approval is a **real, exactly-worded file-edit approval** of one
   concrete diff proposal — established by
   :class:`~ai_dev_orchestrator.file_editing.models.ApprovedDiffProposalArtifact`
   validation, never inferred here from anything else;
2. the artifact is **this project's**, matched by exact string equality in every
   direction the two objects can disagree;
3. every path the approved diff names passes the **lexical** Phase 1
   :class:`~ai_dev_orchestrator.workspace.path_policy.PathPolicy` write check,
   and the change count fits inside ``workspace_policy.max_changed_files``.

What it deliberately does **not** establish is everything that would require
looking at the workspace: whether any of those paths exists, what it currently
contains, whether the canonical path resolves back inside the workspace root,
and whether the diff would apply. Those questions are unanswered here **because
answering them means touching a target workspace**, and this phase does not.

What this module deliberately cannot do
---------------------------------------

- **No workspace access at all.** No target project workspace is read, listed,
  stat'd, globbed, walked, resolved, or canonicalized, and
  ``project.repo.workspace_path`` is never even consulted — the path policy is
  handed the rules and the root as *strings*, which is what makes it safe to
  evaluate paths for a workspace nobody may look at.
- **No file IO of any kind.** The builder is handed two already-loaded objects.
  It opens nothing, writes nothing, and writes no artifact file: the Phase 5F1
  command prints to stdout instead.
- **No file editing, no diff application, no apply-cleanliness check.** No patch
  tooling is imported, so no code path here can apply anything, and
  ``applies_cleanly_checked`` is ``False`` because the question was never asked.
- **No command execution.** ``required_verification`` is plan prose that this
  module never reads as a command and never runs.
- **No model call, no network call, no environment read.** ``httpx``,
  ``requests``, ``LLMClient``, ``LLMClientConfig``,
  ``load_llm_client_config_from_env`` and ``GitHubClient`` are not imported.
- **No git action.** There is no branch, commit, push, or PR field on any model
  here except the ``False`` flags in ``checks_not_performed`` that record their
  absence.
- **No clock.** ``approved_at`` is *copied* from the approval and never produced
  here, so the same inputs always produce a byte-identical report.
- **No approval.** Nothing here stamps, writes, widens, or infers an approval.

Every model is ``extra="forbid"``, and the report carries **no unified diff
text, no source contents, no approval text, no raw artifact text, no workspace
path, and no resolved absolute path** — a diff is summarized as counts, and the
counts are computed by scanning the string the artifact already carried.

A preview authorizes nothing. Phase 5F2 and beyond remain proposed and not
authorized, and nothing in this repository writes a byte into a target
workspace.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ai_dev_orchestrator.file_editing.models import (
    ApprovedDiffProposalArtifact,
    _summarize_validation_error,
)
from ai_dev_orchestrator.models import ProjectConfig
from ai_dev_orchestrator.workspace.path_policy import (
    PathClassification,
    PathPolicy,
)


class FileEditPreviewError(Exception):
    """A preview could not be built, and none was.

    Raised for an identity mismatch between the approved diff proposal and the
    project config, a duplicate proposed path, a change count above
    ``workspace_policy.max_changed_files``, a path the lexical write policy
    refuses (forbidden, unlisted, protected, or escaping the workspace root),
    and any failure of :class:`FileEditPreviewReport` validation.

    Messages name the *category* of failure and the field or path that failed.
    They never echo the artifact text, the approval text, the unified diff, or
    any file content.

    There is deliberately **no apply error, no edit error, no command error, and
    no git error** in this hierarchy: this phase applies nothing, edits nothing,
    runs nothing, and touches no repository, so there is no failure of that kind
    to report.
    """


# The report's schema identity. Compared with ``==`` through a ``Literal``: a
# different version is a different report and is rejected, not upgraded.
FILE_EDIT_PREVIEW_SCHEMA_VERSION = "file-edit-preview.v1"

# What this report *is*. There is one mode and it is the harmless one: a
# description of what a future phase would be allowed to attempt. There is no
# "apply" mode and no "edit" mode; adding one would be a separately authorized
# phase, not a new enum member.
FILE_EDIT_PREVIEW_MODE = "dry-run-preview-only"

# Where the previewed paths came from. Matched with ``==`` through a
# ``Literal``: the candidates are the approved diff's own changes and nothing
# else — not a directory listing, not a glob, not the plan's file list.
FILE_EDIT_PREVIEW_CANDIDATE_SOURCE = "approved_diff.diff_proposal.changes"

# What a human must authorize before anything beyond this report happens.
# Carried in the report itself so the boundary travels with it.
NEXT_AUTHORIZATION_REQUIRED = (
    "Phase 5F2 or later must be explicitly authorized before any file is "
    "written, any diff is applied, any apply-cleanliness check is performed, "
    "any command is run, or any branch, commit, push, or PR is created. This "
    "preview authorizes none of them."
)

# Per-change prose, fixed so the same inputs always produce the same report.
_MODIFY_NOTE = (
    "A future write phase would attempt to apply this diff to an existing "
    "file. Whether that file exists, what it currently contains, and whether "
    "the diff would apply were all not checked."
)

_CREATE_NOTE = (
    "A future write phase would attempt to create this file. Whether a file "
    "already exists at this path was not checked."
)


class _Strict(BaseModel):
    """Base model that rejects unknown fields, so forged extras fail loudly."""

    model_config = ConfigDict(extra="forbid")


class FileEditPreviewDiffStats(_Strict):
    """Counts describing one diff, standing in for the diff itself.

    The diff text is deliberately **not** carried here or anywhere else in the
    report: it is already in the artifact the human approved, and reprinting it
    would put source lines into a document whose whole purpose is to describe a
    write without performing one. Counts are enough to see the *size* of what a
    future phase would attempt.

    Every field is derived by scanning the existing ``unified_diff`` string.
    Nothing is re-derived from a file, and ``difflib`` is not imported: no diff
    is generated, modified, normalized, or checked for applicability here.
    """

    diff_bytes_utf8: int
    diff_lines: int
    hunk_count: int
    added_lines: int
    removed_lines: int
    context_lines: int


class FileEditPreviewChange(_Strict):
    """One path a future write phase would be permitted to attempt.

    ``policy_result`` is ``Literal["allowed"]`` with no other member on purpose.
    A path that the lexical write policy refuses does not appear here with a
    ``"denied"`` result — it fails the **whole** preview, so a report either
    describes a fully permitted change set or does not exist. A partially
    permitted preview would be an invitation to apply the permitted part.

    ``protected_path`` is therefore always ``False`` in this phase: a protected
    path is refused outright, and Phase 5F1 deliberately ships no
    allow-protected flag. The field exists so that a later, separately
    authorized phase cannot quietly introduce protected writes without the
    report saying so.

    ``would_attempt_write_in_future_phase`` is ``Literal[True]`` with no
    default. It is a statement about a **hypothetical** phase that does not
    exist: no write is attempted, scheduled, or authorized by this report.

    There is no ``unified_diff``, ``before_content``, ``after_content``,
    ``current_content``, ``exists``, ``applies_cleanly``, ``command``,
    ``workspace_path``, or ``resolved_path`` field, so a payload carrying one is
    rejected as an extra rather than stored.
    """

    path: str
    change_type: Literal["modify", "create"]
    policy_result: Literal["allowed"]
    protected_path: bool
    diff_stats: FileEditPreviewDiffStats
    would_attempt_write_in_future_phase: Literal[True]
    notes: list[str] = Field(default_factory=list)


class FileEditPreviewWorkspacePolicy(_Strict):
    """The coarse workspace switches the preview was evaluated against.

    ``workspace_path`` is deliberately **absent**: it is the one config value
    that names a real directory, this phase never touches it, and printing it
    would put a target project's location into a report about that project.
    """

    deny_outside_workspace: bool
    allow_symlinks: bool
    max_changed_files: int


class FileEditPreviewProject(_Strict):
    """Which project this preview is for, by identity only."""

    project_id: str
    repo: str
    workspace_policy: FileEditPreviewWorkspacePolicy


class FileEditPreviewApprovedDiff(_Strict):
    """Which approval this preview rests on, and what it covered.

    ``approval_text`` is omitted: it is required to equal a fixed phrase
    exactly, so echoing it conveys nothing the ``approved_by``/``approved_at``
    pair does not already carry, and echoing an approval sentence in a generated
    report is the kind of thing a later reader could mistake for one.

    ``change_count`` is the number of changes the approved diff proposal
    carried, which is also the number of paths this preview evaluated.
    """

    approved_by: str
    approved_at: datetime
    source: Literal["manual"]
    issue_number: int
    title: str
    change_count: int


class FileEditPreviewBlock(_Strict):
    """The preview proper: what a future write phase would be allowed to touch.

    ``omitted_paths`` is copied from the approved diff proposal — paths the
    proposal itself recorded as considered and not diffed. They are **not**
    write candidates and carry no diff, so they are named and nothing more.
    """

    candidate_source: Literal[FILE_EDIT_PREVIEW_CANDIDATE_SOURCE]  # type: ignore[valid-type]
    paths_count: int
    changes: list[FileEditPreviewChange]
    omitted_paths: list[str]


class FileEditPreviewChecksPerformed(_Strict):
    """The five things this preview actually established.

    Every field is ``Literal[True]``: a report that could not honestly claim one
    of them is not produced at all, because each is a precondition of building
    one rather than an observation recorded afterwards.
    """

    approved_diff_approval_validated: Literal[True]
    diff_proposal_validated: Literal[True]
    project_identity_matched: Literal[True]
    lexical_write_policy_checked: Literal[True]
    max_changed_files_checked: Literal[True]


class FileEditPreviewChecksNotPerformed(_Strict):
    """The thirteen things this preview did **not** do, stated explicitly.

    Every field is ``Literal[False]``. This block is the point of the report: a
    reader must be able to see, without reading this source, that a preview
    listing paths and diff sizes has not looked at a workspace, has not asked
    whether a diff applies, and has not run, written, committed, or pushed
    anything.

    ``canonicalization_checked`` deserves naming on its own. The Phase 5D0
    canonical guard is not called here, so the lexical policy result below is
    **lexical only** — a path that passes it could still resolve, on a real
    filesystem, somewhere the policy would refuse. Closing that gap requires
    touching the workspace, which is exactly what this phase does not do.
    """

    workspace_touched: Literal[False]
    canonicalization_checked: Literal[False]
    current_file_contents_read: Literal[False]
    current_file_existence_checked: Literal[False]
    diff_applied: Literal[False]
    applies_cleanly_checked: Literal[False]
    commands_run: Literal[False]
    verification_run: Literal[False]
    branch_created: Literal[False]
    commit_created: Literal[False]
    pushed: Literal[False]
    pr_opened: Literal[False]
    model_called: Literal[False]


class FileEditPreviewReport(_Strict):
    """A dry-run description of the writes a future phase would be allowed.

    The top-level flags repeat, deliberately, what ``checks_not_performed``
    already says. They are the fields a reader — or a future consumer — is
    likeliest to look at first, and each is ``Literal[False]`` (or
    ``Literal[True]`` for ``requires_future_authorization``) so that a document
    claiming a write happened cannot be a valid preview report.

    There is **no field** for a unified diff, source contents, an approval text,
    raw artifact text, a workspace path, a resolved absolute path, a command or
    its output, an apply result, an API key, a base URL, a prompt, a completion,
    a branch, a commit, or a PR URL. Each is rejected as an extra.

    Producing this report never means anything may be *done*.
    """

    schema_version: Literal[FILE_EDIT_PREVIEW_SCHEMA_VERSION]  # type: ignore[valid-type]
    mode: Literal[FILE_EDIT_PREVIEW_MODE]  # type: ignore[valid-type]
    project: FileEditPreviewProject
    approved_diff: FileEditPreviewApprovedDiff
    preview: FileEditPreviewBlock
    checks_performed: FileEditPreviewChecksPerformed
    checks_not_performed: FileEditPreviewChecksNotPerformed
    files_edited: Literal[False]
    commands_run: Literal[False]
    applies_cleanly_checked: Literal[False]
    workspace_touched: Literal[False]
    requires_future_authorization: Literal[True]
    next_authorization_required: str


def _check_identity(
    approved_diff: ApprovedDiffProposalArtifact, project: ProjectConfig
) -> None:
    """Refuse an approved diff that is not this project's, exactly.

    Six comparisons, because there are six places the artifact records who it is
    for: the wrapper itself, the proposal's provenance, and the approved plan
    nested inside the proposal. The Phase 5F0 model already requires the three
    to agree with each other; what it cannot know is whether they agree with
    *this* config, which is a separate input that can disagree.

    String equality only — no normalization, no case folding, no prefix
    matching. An approval given for one project or repo grants nothing for
    another, and the mismatch is reported by *field name*: the differing values
    are never echoed.
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
            (
                "diff_proposal.approved_plan.repo",
                proposal.approved_plan.repo,
                repo,
            ),
        )
        if left != right
    ]
    if mismatched:
        raise FileEditPreviewError(
            "the approved diff proposal does not match this project config "
            "exactly; mismatched fields: "
            + ", ".join(mismatched)
            + ". An approval given for one project or repo previews nothing for "
            "another."
        )


def _check_change_count(
    approved_diff: ApprovedDiffProposalArtifact, project: ProjectConfig
) -> None:
    """Refuse a change set larger than the project's own cap.

    ``max_changed_files`` is a Phase 1 workspace-policy ceiling, and it is
    checked here rather than left to a future write phase: a preview that
    described more writes than the project permits would describe something that
    could never happen, which is worse than describing nothing.

    A count of zero passes. An approved diff proposal may legitimately carry no
    changes, and a preview of it says a future phase would attempt no write.
    """
    count = len(approved_diff.diff_proposal.changes)
    limit = project.workspace_policy.max_changed_files
    if count > limit:
        raise FileEditPreviewError(
            f"the approved diff proposal names {count} changed files, above "
            f"this project's workspace_policy.max_changed_files of {limit}. "
            "The whole preview is refused; a cap is not a suggestion to "
            "preview the first few."
        )


def _check_no_duplicate_paths(approved_diff: ApprovedDiffProposalArtifact) -> None:
    """Re-establish path uniqueness rather than inherit it.

    :class:`ApprovedDiffProposalArtifact` and
    :class:`~ai_dev_orchestrator.diff_proposal.models.DiffProposalArtifact` both
    already reject duplicates. Both do so during **validation**, and pydantic
    does not re-validate a model instance it is handed — so an object mutated or
    hand-built after validation reaches this function with duplicates intact.
    Two entries for one path have no defined precedence, and a preview that
    silently kept one would understate what a future phase would attempt.
    """
    seen: set[str] = set()
    for change in approved_diff.diff_proposal.changes:
        if change.path in seen:
            raise FileEditPreviewError(
                "the approved diff proposal contains more than one change for "
                f"path {change.path!r}; duplicates are rejected, not merged."
            )
        seen.add(change.path)


def _check_write_policy(path: str, policy: PathPolicy) -> None:
    """Refuse any path the **lexical** Phase 1 write policy does not permit.

    ``check_write`` is called with its default ``allow_protected=False``, and
    Phase 5F1 ships no flag to change that: a protected path is refused here
    exactly as a forbidden or unlisted one is. Permitting protected writes is a
    decision for a phase that actually writes, made with its own authorization.

    The check is **string reasoning only**. ``PathPolicy`` normalizes
    separators, resolves ``.``/``..`` lexically, and matches glob rules; it
    never reads, stats, resolves, or canonicalizes anything, which is what makes
    it safe to evaluate paths for a workspace this phase may not look at. The
    consequence is stated plainly in the report:
    ``canonicalization_checked`` is ``false``.

    Any refusal fails the **whole** preview, so a report never describes a
    partially permitted change set.
    """
    decision = policy.check_write(path)
    if decision.permitted:
        return

    if decision.classification is PathClassification.PROTECTED:
        raise FileEditPreviewError(
            f"path {path!r} is classified PROTECTED by this project's path "
            "rules. Phase 5F1 refuses protected paths outright and ships no "
            "flag to permit them; the whole preview was refused."
        )
    raise FileEditPreviewError(
        f"path {path!r} is refused by this project's lexical write policy "
        f"({decision.classification.value}: {decision.reason}). The whole "
        "preview was refused; a preview never describes a partially permitted "
        "change set."
    )


def _diff_stats(unified_diff: str) -> dict:
    """Summarize an existing diff string as counts. Pure string scanning.

    The diff is **read, never re-derived**: ``difflib`` is not imported, nothing
    is generated, nothing is normalized (line endings included), and
    applicability is never considered. A line is classified once, in this order:

    - ``@@`` starts a hunk header;
    - ``--- `` / ``+++ `` are the file headers, which are **excluded** from the
      added and removed counts — a diff of a two-line change would otherwise
      report three added lines;
    - a remaining ``+`` or ``-`` is an added or removed line;
    - anything else is context, including the blank line that ends many diffs.

    ``diff_bytes_utf8`` measures the encoded size of the string the artifact
    already carried. No file is opened to obtain or verify it.
    """
    lines = unified_diff.splitlines()

    hunk_count = 0
    added_lines = 0
    removed_lines = 0
    context_lines = 0

    for line in lines:
        if line.startswith("@@"):
            hunk_count += 1
        elif line.startswith("--- ") or line.startswith("+++ "):
            # A file header. Counted as neither a change nor context.
            continue
        elif line.startswith("+"):
            added_lines += 1
        elif line.startswith("-"):
            removed_lines += 1
        else:
            context_lines += 1

    return {
        "diff_bytes_utf8": len(unified_diff.encode("utf-8")),
        "diff_lines": len(lines),
        "hunk_count": hunk_count,
        "added_lines": added_lines,
        "removed_lines": removed_lines,
        "context_lines": context_lines,
    }


def build_file_edit_preview(
    *,
    approved_diff: ApprovedDiffProposalArtifact,
    project: ProjectConfig,
) -> FileEditPreviewReport:
    """Build a dry-run file-edit preview from two objects. Pure function.

    It is handed two already-loaded objects and returns a third. It performs no
    file IO, touches no workspace, reads no environment variable, calls no
    model, opens no socket, runs no command, contacts GitHub not at all, reads
    no clock, canonicalizes nothing, applies nothing, checks no
    apply-cleanliness, edits nothing, writes no artifact file, stamps no
    approval, and prints nothing.

    The result is **deterministic**: the same inputs always produce an identical
    report, down to the byte.

    Approval comes from the Phase 5F0 artifact and from nowhere else. It is
    never inferred from the wrapped L1 plan approval, from the proposal existing
    or parsing, from ``requires_human_review``, from a file being present, or
    from model output — and it is never stamped here.

    Args:
        approved_diff: A validated Phase 5F0 file-edit approval wrapping an
            untouched diff proposal snapshot.
        project: The project config that approval must match exactly.

    Returns:
        A validated :class:`FileEditPreviewReport`. ``preview.changes`` is
        **empty** when the approved proposal carried no changes — a well-formed
        statement that a future phase would attempt no write, not a defect.

    Raises:
        FileEditPreviewError: an identity mismatch against the project config, a
            duplicate proposed path, a change count above
            ``workspace_policy.max_changed_files``, a path the lexical write
            policy refuses (forbidden, unlisted, protected, or escaping the
            workspace root), or a report that failed its own validation. Nothing
            partial is returned and nothing is written.
    """
    _check_identity(approved_diff, project)
    _check_change_count(approved_diff, project)
    _check_no_duplicate_paths(approved_diff)

    # Built from the config's rule lists and root **string**. Constructing a
    # policy reads nothing: PathPolicy is lexical by design (Phase 1), which is
    # what lets a preview evaluate paths for a workspace it must not look at.
    policy = PathPolicy.from_project_config(project)

    proposal = approved_diff.diff_proposal
    changes: list[dict] = []
    for change in proposal.changes:
        _check_write_policy(change.path, policy)
        changes.append(
            {
                # The path exactly as the human approved it. Never normalized,
                # never joined to a workspace root, never resolved.
                "path": change.path,
                "change_type": change.change_type,
                # Reached only because the policy permitted it: a refusal above
                # fails the whole preview rather than landing here.
                "policy_result": "allowed",
                # Always false in this phase — a protected path is refused, and
                # there is no flag to permit one.
                "protected_path": False,
                "diff_stats": _diff_stats(change.unified_diff),
                "would_attempt_write_in_future_phase": True,
                "notes": [
                    _CREATE_NOTE if change.change_type == "create" else _MODIFY_NOTE
                ],
            }
        )

    approval = approved_diff.approval
    payload = {
        "schema_version": FILE_EDIT_PREVIEW_SCHEMA_VERSION,
        "mode": FILE_EDIT_PREVIEW_MODE,
        "project": {
            "project_id": project.project_id,
            "repo": project.repo.github_repo,
            "workspace_policy": {
                "deny_outside_workspace": (
                    project.workspace_policy.deny_outside_workspace
                ),
                "allow_symlinks": project.workspace_policy.allow_symlinks,
                "max_changed_files": project.workspace_policy.max_changed_files,
            },
        },
        "approved_diff": {
            "approved_by": approval.approved_by,
            "approved_at": approval.approved_at,
            "source": approval.source,
            "issue_number": approved_diff.issue_number,
            "title": approved_diff.title,
            "change_count": len(proposal.changes),
        },
        "preview": {
            "candidate_source": FILE_EDIT_PREVIEW_CANDIDATE_SOURCE,
            "paths_count": len(changes),
            "changes": changes,
            "omitted_paths": list(proposal.omitted_paths),
        },
        # Facts about *this function*: each is a precondition that was met
        # before any of the above was assembled.
        "checks_performed": {
            "approved_diff_approval_validated": True,
            "diff_proposal_validated": True,
            "project_identity_matched": True,
            "lexical_write_policy_checked": True,
            "max_changed_files_checked": True,
        },
        # Facts about what this function cannot do. None of these is a runtime
        # observation; each is a property of a module that imports no patch
        # tool, no client, no socket, and no subprocess.
        "checks_not_performed": {
            "workspace_touched": False,
            "canonicalization_checked": False,
            "current_file_contents_read": False,
            "current_file_existence_checked": False,
            "diff_applied": False,
            "applies_cleanly_checked": False,
            "commands_run": False,
            "verification_run": False,
            "branch_created": False,
            "commit_created": False,
            "pushed": False,
            "pr_opened": False,
            "model_called": False,
        },
        "files_edited": False,
        "commands_run": False,
        "applies_cleanly_checked": False,
        "workspace_touched": False,
        "requires_future_authorization": True,
        "next_authorization_required": NEXT_AUTHORIZATION_REQUIRED,
    }

    # Deliberately validated through the model rather than constructed field by
    # field: a forged extra, a wrong literal, or a slipped flag is caught by the
    # same rules that would guard a report arriving from outside this
    # repository. The builder gets no privileged path around them.
    try:
        return FileEditPreviewReport.model_validate(payload)
    except ValidationError as exc:
        raise FileEditPreviewError(
            "the generated file-edit preview failed its own validation and was "
            "discarded: " + _summarize_validation_error(exc)
        ) from exc
