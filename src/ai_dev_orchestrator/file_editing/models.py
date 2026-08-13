"""Typed **file-edit write gate** models and a strict parser (Phase 5F0).

This module implements the *approval wrapper* that any future file-editing phase
would have to be handed before it could write a single byte into a target
workspace. It is a schema plus a pure parser, in the Phase 4B/4F/5B/5E0/5E2
style, wired into no command.

**Phase 5F0 is not file editing.** There is no writer here, no applier, and no
apply-cleanliness check. Nothing in this module edits a file, applies a diff,
asks whether a diff *would* apply, reads a workspace, runs a command, creates a
branch, commits, pushes, or opens a PR. Constructing an
:class:`ApprovedDiffProposalArtifact` means a human wrote down an approval; it
does not mean anything may be *done*, because nothing in this repository
consumes the result and no editor exists to consume it.

Why a **second** approval exists
--------------------------------

Phase 5B's :data:`~ai_dev_orchestrator.handoff.models.REQUIRED_APPROVAL_TEXT`
records that a human approved an **L1 plan** for L2 implementation. That is an
approval of *intent* — a summary, a scope, a list of files that may change. It
is not an approval of the **concrete diff** a later phase generated from that
plan, which the human had not seen when they approved the plan and which Phase
5E3 produced deterministically without anyone reading it.

So Phase 5F0 requires a separate, differently worded approval of the diff
itself, and the orchestrator must never infer it from:

- the approved L1 plan artifact wrapped inside the proposal (that approval is a
  *different* approval of a *different* thing, and it is re-validated here, not
  reused);
- the diff proposal artifact existing, parsing, or setting
  ``requires_human_review`` — that flag is a *request* for review, never a
  record that review happened;
- a file being present on disk;
- issue prose or an ``Automation Authorization`` heading, which anyone who can
  edit an issue can write;
- model output of any kind.

Approval is written by a human, in this block, and nowhere else. Nothing here
stamps one.

What this module deliberately cannot do
---------------------------------------

- **No file editing, no diff application, no apply check.** There is no writer,
  no applier, and no patch tooling import. ``applies_cleanly_checked`` on the
  wrapped proposal must still be ``false``: whether the approved diff would
  apply is a question nobody has asked, and approving a diff does not answer it.
- **No file loading.** The parser is handed a string. It never opens a path and
  there is no loader function here.
- **No workspace access.** No target project workspace is read, listed, stat'd,
  globbed, walked, or resolved. Paths reach this module only as strings already
  validated by the wrapped Phase 5E2 models, and are compared as strings.
- **No command execution.** ``required_verification`` is not run.
- **No git action.** There is no ``branch``, ``commit``, ``push``, ``pr_url``,
  ``apply`` or ``auto_apply`` field, so a payload carrying one is rejected as an
  extra rather than stored.
- **No model call, no network call, no environment read.** ``httpx``,
  ``requests``, ``LLMClient``, ``LLMClientConfig``,
  ``load_llm_client_config_from_env`` and ``GitHubClient`` are not imported, so
  no code path here can construct one.
- **No clock.** ``approved_at`` is *parsed* when supplied and is never produced
  here. There is no "now" and no staleness comparison.
- **No artifact writing.** Nothing here writes a file or stamps an approval.
- **No CLI behavior.** Importing this package adds no command and no option.

The wrapper carries an **untouched** :class:`DiffProposalArtifact` snapshot —
the exact diffs the human approved, re-validated on every parse — and matches
identity against it **exactly**, in both directions: against the proposal's own
provenance and against the approved plan nested inside it. Every invariant the
proposal already guarantees (L1 level, human approval required, review required,
nothing edited, nothing run, nothing apply-checked, diffs actually generated, no
duplicate paths, every path inside the approved scope) is **re-checked here**,
because a gate must not depend on an upstream invariant staying true forever.

Every model is ``extra="forbid"``, and validation **rejects rather than
repairs**.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, model_validator

from ai_dev_orchestrator.diff_proposal.models import (
    DiffProposalArtifact,
    _require_image_digests_match_change_type,
)


class FileEditingApprovalError(Exception):
    """Base class for file-edit approval parsing and validation errors.

    Messages name the *category* of failure and the field that failed. They
    never echo the artifact text, the diff, source lines, the approval text, or
    any other supplied value.

    There is deliberately **no apply error, no edit error, no command error, and
    no git error** in this hierarchy: this phase applies nothing, edits nothing,
    runs nothing, and touches no repository, so there is no failure of that kind
    to report.
    """


class FileEditingApprovalParseError(FileEditingApprovalError):
    """The text was not exactly one strict JSON object."""


class FileEditingApprovalValidationError(FileEditingApprovalError):
    """The decoded object failed :class:`ApprovedDiffProposalArtifact` validation."""


# The exact sentence a human must write to approve one concrete diff proposal
# for workspace file editing. Compared with ``==`` — a paraphrase, a different
# case, extra whitespace, or trailing punctuation is not approval.
#
# This is deliberately **not** the Phase 5B plan-approval sentence. Approving a
# plan and approving the diff generated from it are two separate human acts, and
# the second may never be satisfied by evidence of the first.
REQUIRED_DIFF_EDIT_APPROVAL_TEXT = (
    "I approve this diff proposal for workspace file editing"
)

# The artifact's schema identity. Compared with ``==`` through a ``Literal``: a
# different version is a different artifact and is rejected, not upgraded.
#
# Phase 5F2C raised this from ``approved-diff-proposal.v1`` to
# ``approved-diff-proposal.v2``, in step with ``diff-proposal.v2``. The wrapper
# records **what a human approved**, and what they approve now includes the
# exact pre-image and post-image identities each change binds. A v1 wrapper
# wraps a v1 proposal that carries neither, so it is a different artifact and is
# rejected rather than upgraded — approving a transformation whose endpoints
# were never written down is not the approval this phase's writer requires.
APPROVED_DIFF_PROPOSAL_SCHEMA_VERSION = "approved-diff-proposal.v2"

# What this artifact *is*. There is one mode and it records an approval and
# nothing else. There is no "apply" mode and no "edit" mode; adding one would be
# a separately authorized phase, not a new enum member.
APPROVED_DIFF_PROPOSAL_MODE = "file-edit-approval-only"


def _require_non_blank(value: str, field_name: str) -> str:
    """Reject empty or whitespace-only strings."""
    if value is None or not value.strip():
        raise ValueError(f"{field_name} must not be empty or whitespace-only.")
    return value


def _require_owner_repo(value: str) -> str:
    """Reject blank repo strings and anything not shaped like 'owner/repo'."""
    value = _require_non_blank(value, "repo")
    parts = value.split("/")
    if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
        raise ValueError("repo must look like 'owner/repo'.")
    return value


def _require_positive_issue_number(value: int) -> int:
    """Reject non-positive issue numbers."""
    if value <= 0:
        raise ValueError("issue_number must be positive.")
    return value


class _Strict(BaseModel):
    """Base model that rejects unknown fields, so forged extras fail loudly."""

    model_config = ConfigDict(extra="forbid")


class DiffEditApproval(_Strict):
    """A human's explicit approval of one diff proposal, for file editing.

    Every field is required and none has a default: there is no way to construct
    an approval by omission. ``source`` is a closed enum whose only permitted
    value is ``"manual"``, so ``"model"``, ``"automatic"``, ``"github"`` and
    ``"issue"`` are all rejected rather than tolerated, and a future automated
    source would have to be added deliberately.

    ``approval_text`` is validated for **exact** equality with
    :data:`REQUIRED_DIFF_EDIT_APPROVAL_TEXT` — following the Phase 5B
    :class:`~ai_dev_orchestrator.handoff.models.PlanApproval` precedent, the
    check is a validator rather than a ``Literal`` so the failure message can
    name the field without echoing what was supplied. A lowercase variant, a
    trailing period, padded whitespace, a paraphrase, the Phase 5B plan-approval
    sentence, and ``"Automation Authorization: approved"`` are all **not**
    approval.

    An endpoint host, a base URL, an API key, a prompt, a completion, a message
    list, a raw response, and a workspace path all have **no field here**, so a
    payload carrying one is rejected as an extra rather than being stored.

    A model may never populate any field here. The orchestrator does not write
    this block either — writing it *is* the approval act, and it is a human's.
    """

    approved_by: str
    approved_at: datetime
    approval_text: str
    source: Literal["manual"]

    @field_validator("approved_by")
    @classmethod
    def _approved_by_not_blank(cls, value: str) -> str:
        return _require_non_blank(value, "approved_by")

    @field_validator("approval_text")
    @classmethod
    def _approval_text_exact(cls, value: str) -> str:
        if value != REQUIRED_DIFF_EDIT_APPROVAL_TEXT:
            raise ValueError(
                "approval_text must match the required file-edit approval phrase "
                "exactly; a paraphrase, a case variant, padded whitespace, "
                "trailing punctuation, or the L1 plan approval phrase is not "
                "approval to edit files."
            )
        return value


class ApprovedDiffProposalArtifact(_Strict):
    """A human's file-edit approval of one specific diff proposal snapshot.

    The ``diff_proposal`` field is a **snapshot**, not a reference: it carries
    the diffs exactly as they stood when the human read them, so there is no
    second lookup that could return different text. It is re-validated by
    :class:`DiffProposalArtifact` on every parse, which in turn re-validates the
    :class:`~ai_dev_orchestrator.handoff.models.ApprovedL1PlanArtifact` nested
    inside it. An artifact therefore cannot assert its own authorization: it can
    only carry approvals humans already gave, for one project, repo, issue, and
    title.

    Beyond the per-model checks, the wrapper enforces:

    - **Exact identity matching** in both directions — against
      ``diff_proposal.provenance`` and against ``diff_proposal.approved_plan``
      (whose title lives on ``.plan.title``). String equality only, no
      normalization and no case folding. The failure this prevents is an
      approval given for one issue being carried into another.
    - **Re-checked proposal invariants.** ``approved_plan.plan`` must still be
      ``automation_level == "L1"`` with ``requires_human_approval is True``; the
      proposal must still have ``requires_human_review is True``,
      ``diffs_generated is True``, and ``files_edited`` / ``commands_run`` /
      ``applies_cleanly_checked`` all ``False``. :class:`DiffProposalArtifact`
      already guarantees each of these, and each is checked again here anyway:
      a write gate must not inherit its safety from a model it does not own,
      and an instance handed in directly rather than parsed is not re-validated
      by pydantic.
    - **Re-checked path discipline.** No duplicate ``changes[].path``, every
      path present **exactly** in
      ``approved_plan.plan.files_likely_to_change``, and no path present in
      ``files_forbidden_or_out_of_scope``. Same reasoning: already true
      upstream, re-established here.
    - **Re-checked image identity** (Phase 5F2C). Every ``modify`` carries a
      ``pre_image_sha256``; every ``create`` carries ``null`` for it. This is
      the invariant that makes the approval mean *"this human approved turning
      these exact bytes into those exact bytes"* rather than the much weaker
      *"this human approved a diff for this path"*, so it is re-established
      here rather than inherited.
    - **An optional wrapped patch proposal is left to
      :class:`DiffProposalArtifact`.** Its consistency rules are not relaxed,
      duplicated, or overridden here.

    ``diff_proposal.changes`` may be **empty** — a human may legitimately
    approve a proposal that proposes nothing, in which case a future apply phase
    would simply have nothing to edit. That is a well-formed statement, not a
    defect, and not a loophole: an empty change list authorizes no write.

    What this model deliberately has **no field for**: raw artifact text, source
    contents outside a diff, ``before_content`` / ``after_content``, a prompt, a
    completion, an API key, a base URL, a workspace path, a command or its
    output, an apply result, ``auto_apply``, a branch name, a commit id, and a
    PR URL. Every one of those is rejected as an extra.

    This model does **not** prove a diff applies, does **not** authorize command
    execution, and does **not** authorize commits, pushes, or PRs. It records a
    human approval that a future, separately authorized file-editing phase may
    consider — and no such phase exists.
    """

    schema_version: Literal[APPROVED_DIFF_PROPOSAL_SCHEMA_VERSION]
    mode: Literal[APPROVED_DIFF_PROPOSAL_MODE]
    approval: DiffEditApproval
    diff_proposal: DiffProposalArtifact
    project_id: str
    repo: str
    issue_number: int
    title: str
    next_authorization_required: str

    @field_validator("project_id", "title", "next_authorization_required")
    @classmethod
    def _not_blank(cls, value: str, info) -> str:
        return _require_non_blank(value, info.field_name)

    @field_validator("repo")
    @classmethod
    def _repo_valid(cls, value: str) -> str:
        return _require_owner_repo(value)

    @field_validator("issue_number")
    @classmethod
    def _issue_number_positive(cls, value: int) -> int:
        return _require_positive_issue_number(value)

    @model_validator(mode="after")
    def _identity_and_proposal_invariants(self) -> ApprovedDiffProposalArtifact:
        proposal = self.diff_proposal
        approved_plan = proposal.approved_plan
        plan = approved_plan.plan

        # Identity, against the proposal's own provenance.
        if self.project_id != proposal.provenance.project_id:
            raise ValueError(
                "project_id does not match diff_proposal.provenance.project_id "
                "exactly."
            )
        if self.repo != proposal.provenance.repo:
            raise ValueError(
                "repo does not match diff_proposal.provenance.repo exactly."
            )
        if self.issue_number != proposal.provenance.issue_number:
            raise ValueError(
                "issue_number does not match diff_proposal.provenance.issue_number "
                "exactly."
            )
        if self.title != proposal.provenance.title:
            raise ValueError(
                "title does not match diff_proposal.provenance.title exactly."
            )

        # Identity, against the approved plan nested inside the proposal.
        if self.project_id != approved_plan.project_id:
            raise ValueError(
                "project_id does not match diff_proposal.approved_plan.project_id "
                "exactly."
            )
        if self.repo != approved_plan.repo:
            raise ValueError(
                "repo does not match diff_proposal.approved_plan.repo exactly."
            )
        if self.issue_number != approved_plan.issue_number:
            raise ValueError(
                "issue_number does not match "
                "diff_proposal.approved_plan.issue_number exactly."
            )
        if self.title != plan.title:
            raise ValueError(
                "title does not match diff_proposal.approved_plan.plan.title "
                "exactly."
            )

        # The wrapped plan is still an unescalated, human-approval-requiring L1
        # plan. DiffProposalArtifact checks this too; a write gate re-checks.
        if plan.automation_level != "L1":
            raise ValueError(
                "diff_proposal.approved_plan.plan.automation_level must be exactly "
                "'L1'; a plan claiming a higher level is corrupt or forged, not "
                "more authorized."
            )
        if plan.requires_human_approval is not True:
            raise ValueError(
                "diff_proposal.approved_plan.plan.requires_human_approval must be "
                "True."
            )

        # The wrapped proposal still describes a thing that has not happened.
        # Approving a diff does not retroactively make any of these true, and an
        # artifact claiming one is describing work this repository cannot do.
        if proposal.requires_human_review is not True:
            raise ValueError(
                "diff_proposal.requires_human_review must be True; a proposal "
                "cannot waive the review this approval exists to record."
            )
        if proposal.diffs_generated is not True:
            raise ValueError(
                "diff_proposal.diffs_generated must be True; there is nothing to "
                "approve for editing otherwise."
            )
        if proposal.files_edited is not False:
            raise ValueError(
                "diff_proposal.files_edited must be False; approval is granted "
                "before any edit, never after one, and no phase edits files."
            )
        if proposal.commands_run is not False:
            raise ValueError(
                "diff_proposal.commands_run must be False; no phase runs commands."
            )
        if proposal.applies_cleanly_checked is not False:
            raise ValueError(
                "diff_proposal.applies_cleanly_checked must be False; whether the "
                "diff applies is never checked, and approving it does not check it."
            )

        # Path discipline **and image identity**, re-established rather than
        # inherited. The digest rule is checked here for the same reason every
        # other invariant is: pydantic does not re-validate an instance it is
        # handed, so a mutated or hand-built proposal reaches this wrapper with
        # a missing pre-image digest intact — and a missing pre-image digest is
        # precisely the thing that would let a writer transform bytes nobody
        # approved.
        allowed = plan.files_likely_to_change
        forbidden = plan.files_forbidden_or_out_of_scope
        seen: set[str] = set()
        for change in proposal.changes:
            _require_image_digests_match_change_type(
                change_type=change.change_type,
                pre_image_sha256=change.pre_image_sha256,
            )
            if change.path in forbidden:
                raise ValueError(
                    "diff_proposal.changes.path is listed in "
                    "approved_plan.plan.files_forbidden_or_out_of_scope and may "
                    "never be approved for editing."
                )
            if change.path not in allowed:
                raise ValueError(
                    "diff_proposal.changes.path is not listed in "
                    "approved_plan.plan.files_likely_to_change; an approval may "
                    "narrow the approved scope, never widen it."
                )
            if change.path in seen:
                raise ValueError(
                    "diff_proposal.changes contains more than one entry for the "
                    "same path; duplicates are rejected, not merged."
                )
            seen.add(change.path)

        return self


def _summarize_validation_error(exc: ValidationError) -> str:
    """Render a ``ValidationError`` as field locations and messages only.

    Following the Phase 4L/5B/5E0/5E2 precedent, failures are loud about
    *category* and quiet about *content*: the supplied values are never echoed.
    That matters here because a rejected artifact can carry a diff full of
    source lines and an approval phrase somebody typed.
    """
    parts = []
    for error in exc.errors():
        location = ".".join(str(item) for item in error["loc"]) or "(root)"
        parts.append(f"{location}: {error['msg']}")
    return "; ".join(parts)


def parse_approved_diff_proposal_artifact(text: str) -> ApprovedDiffProposalArtifact:
    """Parse strict-JSON approved-diff-proposal text into a validated wrapper.

    Pure function. It loads no file, reads no environment variable, touches no
    workspace, calls no model, opens no socket, runs no command, generates no
    diff, modifies no diff, applies no patch, checks no apply-cleanliness, edits
    nothing, creates no branch, commits nothing, pushes nothing, opens no PR,
    stamps no approval, and logs or prints nothing. It is handed the text;
    obtaining that text is the caller's problem and is not implemented in this
    phase.

    Strict in the Phase 4F sense — it **rejects rather than repairs**. The text
    must be exactly one JSON object: surrounding whitespace is tolerated, but
    markdown fences, prose before or after the object, arrays, strings, numbers,
    booleans, and ``null`` all fail. Unknown fields are never stripped, missing
    fields are never inferred, and nothing inside a diff is normalized.

    A successful parse means a human wrote an explicit, exactly-worded file-edit
    approval for one well-formed diff proposal that is itself bound to a valid
    L1 plan approval and stays inside that plan's declared scope. It does **not**
    mean the diffs apply — that is never checked — and it authorizes nothing:
    nothing in this repository consumes the result, no file editor exists, and
    L2 is not built.

    Raises:
        FileEditingApprovalParseError: ``text`` is not exactly one strict JSON
            object.
        FileEditingApprovalValidationError: the object failed
            :class:`ApprovedDiffProposalArtifact` validation — a missing,
            paraphrased, or non-manual approval, an extra field, an identity
            mismatch, a duplicate or out-of-scope path, a claim that files were
            edited / commands were run / apply-cleanliness was checked, or a
            missing or malformed diff proposal.
    """
    if not isinstance(text, str):
        raise FileEditingApprovalParseError(
            "approved diff proposal artifact text must be a string."
        )

    stripped = text.strip()
    if not stripped:
        raise FileEditingApprovalParseError(
            "approved diff proposal artifact text was empty."
        )
    if not (stripped.startswith("{") and stripped.endswith("}")):
        raise FileEditingApprovalParseError(
            "approved diff proposal artifact text must be exactly one JSON object "
            "with no markdown fences, prose, or other content around it."
        )

    try:
        decoded = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise FileEditingApprovalParseError(
            f"approved diff proposal artifact text is not valid JSON: {exc}"
        ) from exc

    if not isinstance(decoded, dict):
        raise FileEditingApprovalParseError(
            "approved diff proposal artifact text must be a JSON object, not an "
            "array, string, number, boolean, or null."
        )

    try:
        return ApprovedDiffProposalArtifact.model_validate(decoded)
    except ValidationError as exc:
        raise FileEditingApprovalValidationError(
            "approved diff proposal artifact failed validation: "
            + _summarize_validation_error(exc)
        ) from exc
