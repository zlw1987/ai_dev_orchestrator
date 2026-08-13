"""Deterministic **unified diff proposal** generator (Phase 5E3).

Phase 5E2 typed the diff proposal artifact and shipped no producer. This module
is the producer, and it is deliberately the dullest one that could exist: a pure
function over four already-loaded objects that runs ``difflib`` over text it was
handed and returns a validated :class:`DiffProposalArtifact`.

The four inputs are the whole story, and none of them is a workspace:

1. an :class:`ApprovedL1PlanArtifact` — the human approval and the path scope;
2. a :class:`ProjectConfig` — the identity the approval must match;
3. a **Phase 5D2 workspace-content packet** — the JSON a human previously
   printed with ``l2-read-workspace-files``, carrying bounded, redacted original
   file text as *data*;
4. a **proposed-content input** — the final text a human or an external tool
   wants each file to have.

**This module generates diff text. It does nothing with it.** The diff is a
string placed inside an artifact and returned. Nothing here applies it, stages
it, writes it, or asks whether it would apply.

What this module deliberately cannot do:

- **No file IO.** It is handed objects. It opens nothing, reads nothing, and
  writes nothing — not the workspace, not the config, not the packet, not the
  proposed content, and not an output file. Loading those files is the caller's
  problem, and the Phase 5E3 CLI command prints to stdout instead.
- **No workspace access.** No target project workspace is read, listed, stat'd,
  globbed, walked, or resolved. In particular the paths the approved plan names
  are **never opened**: their original text arrives inside the Phase 5D2 packet
  or the generation for that path fails. Paths stay **strings**, are never
  joined to a workspace root, and are never canonicalized.
- **No diff application, and no apply-cleanliness check.** No patch tooling is
  invoked, nothing is staged, and ``applies_cleanly_checked`` is ``False``
  because the question was never asked. Whether a generated diff applies is for
  a later, separately authorized phase and for the human reading it.
- **No file editing, no command execution.** Nothing is applied, run, or
  written. ``required_verification`` is plan prose that this module never reads
  as a command and never executes.
- **No model call, no network call, no environment read.** ``httpx``,
  ``requests``, ``LLMClient``, ``LLMClientConfig``,
  ``load_llm_client_config_from_env`` and ``GitHubClient`` are not imported, so
  no code path here can construct one. The produced provenance says
  ``engine="deterministic"``, ``real_call=False``, ``model=None`` — facts about
  this function, not claims copied from an input.
- **No clock.** ``generated_at`` is ``None``. A deterministic generator that
  stamped a timestamp would return a different artifact on every call for the
  same inputs, which would make the output impossible to diff or re-verify.
- **No GitHub fetch or write.** Issue number and title come from the approved
  plan snapshot; nothing is confirmed against GitHub.
- **No approval.** Nothing here stamps, writes, or infers an approval. The
  approval inside the wrapped :class:`ApprovedL1PlanArtifact` is carried through
  **unchanged** and re-validated, never created.

The generator **fails closed**, and the interesting failures are the ones about
*source text*:

- A path whose Phase 5D2 item was **redacted** is refused outright. Redaction
  replaces secret-like values with a placeholder, so a diff built from redacted
  text would describe a file that does not exist — a misleading patch is worse
  than no patch.
- A ``modify`` whose item is anything but a successfully read regular file —
  missing, a directory, too large, skipped by the total cap, binary — is
  refused rather than guessed at.
- A ``create`` whose item was actually **read** is refused: this phase does not
  overwrite an existing file under the name "create".
- A generated diff that contains an obvious secret-like pattern is refused, and
  the refusal names the category and the path and **never echoes the value**.
  The diff is deliberately *not* redacted: redacting it would produce text that
  reads like a patch but could never apply.

Producing a diff never means anything may be *done*. Applying a diff, editing a
file, running a command, committing, pushing, and opening PRs all remain
proposed and not authorized.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from ai_dev_orchestrator.diff_proposal.models import (
    DIFF_PROPOSAL_MODE,
    DIFF_PROPOSAL_SCHEMA_VERSION,
    DiffProposalArtifact,
    _require_non_blank,
    _require_non_blank_items,
    _require_owner_repo,
    _require_positive_issue_number,
    _require_safe_relative_repo_path,
    _summarize_validation_error,
)
from ai_dev_orchestrator.handoff.models import ApprovedL1PlanArtifact
from ai_dev_orchestrator.models import ProjectConfig


class DiffProposalGenerationError(Exception):
    """A diff proposal could not be generated, and none was.

    Raised for an identity mismatch between the approved plan, the project
    config and the workspace-content packet; a proposed path outside the
    approved scope; a proposed path whose original content is unavailable,
    redacted, or of the wrong kind; a generated diff that looks like it carries
    a secret; and any failure of the Phase 5E2 artifact validation.

    Messages name the *category* of failure and the field or path that failed.
    They never echo the artifact text, the plan prose, the proposed content, the
    original file content, the generated diff, or any secret-like value.

    There is deliberately **no apply error, no edit error, and no command
    error** in this hierarchy: this phase applies nothing, edits nothing, and
    runs nothing, so there is no failure of that kind to report.
    """


class DiffProposalInputParseError(DiffProposalGenerationError):
    """An input text was not exactly one strict JSON object."""


class DiffProposalInputValidationError(DiffProposalGenerationError):
    """A decoded input object failed validation."""


# The proposed-content input's schema identity, compared with ``==`` through a
# ``Literal``: a different version is a different input and is rejected, not
# upgraded.
PROPOSED_CONTENT_SCHEMA_VERSION = "proposed-content.v1"

# What the input *is*. There is one mode and it is the harmless one: content a
# human proposes and a human then reviews. There is no "apply" mode.
PROPOSED_CONTENT_MODE = "proposal-only"

# A single proposed file body big enough to be worth capping. The bound exists
# so one input cannot carry an unbounded amount of text through this generator,
# mirroring the byte caps the Phase 5D2 read enforces. It is a *string length*
# check — nothing is read, truncated, or streamed.
MAX_PROPOSED_CONTENT_CHARS = 1_000_000

# The Phase 5D2 packet's own identifying strings. Matched exactly: a packet
# printed by some other command is not this input.
WORKSPACE_CONTENT_MODE = "l2-read-workspace-files"
WORKSPACE_CONTENT_CANDIDATE_SOURCE = "approved_plan.files_likely_to_change"

# Every per-item status Phase 5D2 can report. Only ``"read"`` can supply
# original content; the rest are recorded so a proposal naming one of those
# paths fails with a specific reason instead of a generic "not found".
WORKSPACE_CONTENT_STATUSES = (
    "read",
    "missing",
    "directory_no_content",
    "other_no_content",
    "too_large",
    "skipped_total_limit",
    "binary_or_non_utf8",
)

# Detection-only copies of the Phase 5D2 redaction patterns. Phase 5D2 uses them
# to *replace* secret-like text before printing; here they only ever answer
# "does this look like a secret?", because replacing anything inside a generated
# diff would produce text that reads like a patch and could never apply.
#
# Word boundaries are hand-rolled as `(?<![A-Za-z0-9])` / `(?![A-Za-z0-9])`
# instead of `\b` so that an underscore-prefixed name like `MY_API_KEY` still
# matches — `_` is a word character, so `\b` would not fire there.
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?<![A-Za-z0-9])(api[_-]?key|token|secret|password|passwd|pwd)"
    r"(?![A-Za-z0-9])(\s*[:=]\s*)"
    r"(\"[^\"\n]*\"|'[^'\n]*'|[^\s,;]+)",
    re.IGNORECASE,
)

_BEARER_TOKEN_RE = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]+=*", re.IGNORECASE)

_OPENAI_STYLE_KEY_RE = re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{8,}")

_SECRET_LIKE_PATTERNS = (
    ("secret_assignment", _SECRET_ASSIGNMENT_RE),
    ("bearer_token", _BEARER_TOKEN_RE),
    ("openai_style_key", _OPENAI_STYLE_KEY_RE),
)


class _Strict(BaseModel):
    """Base model that rejects unknown fields, so forged extras fail loudly."""

    model_config = ConfigDict(extra="forbid")


class _Packet(BaseModel):
    """Base model for the Phase 5D2 packet's *container* objects.

    Unknown keys are **ignored** rather than rejected, and only here. The real
    ``l2-read-workspace-files`` output carries a ``notice``, the project's
    workspace and content policies, and approval metadata that this generator
    has no use for; forbidding them would mean re-declaring Phase 5D2's whole
    report shape and re-breaking on every future field it adds.

    Ignoring is not trusting. Nothing outside the fields declared below is read,
    copied into the artifact, or acted on in any way — an ignored key cannot
    make this generator do something, because there is no code that looks at it.
    The one place a forged extra *would* matter, the per-item row that carries
    file text, is ``extra="forbid"`` instead.
    """

    model_config = ConfigDict(extra="ignore")


class ProposedContentChange(_Strict):
    """The final text a human or an external tool proposes one file should have.

    This is **proposed content, not a diff**: there is no ``diff`` field, no
    ``patch``, no ``hunks``, no ``command``, no ``apply``, no ``workspace_path``,
    and deliberately no ``before_content``/``after_content`` pair — the "before"
    is whatever the Phase 5D2 packet recorded, and pairing it here would let an
    input assert a starting state that was never read.

    ``change_type`` is ``"modify"`` or ``"create"`` only, matching Phase 5E2.
    ``content_text`` may be empty for a ``modify`` (emptying a file is a real
    change); a ``create`` with empty content is accepted here and refused at
    generation time, where it becomes clear that no diff hunk can express it.

    ``requires_human_review`` is ``Literal[True]`` with no default: an input
    cannot mark its own change as not needing review, and cannot get the flag by
    omitting it.
    """

    path: str
    change_type: Literal["modify", "create"]
    content_text: str
    rationale: str
    risks: list[str] = Field(default_factory=list)
    requires_human_review: Literal[True]

    @field_validator("path")
    @classmethod
    def _path_is_safe_relative(cls, value: str) -> str:
        return _require_safe_relative_repo_path(value, "path")

    @field_validator("content_text")
    @classmethod
    def _content_is_bounded_text(cls, value: str) -> str:
        if len(value) > MAX_PROPOSED_CONTENT_CHARS:
            raise ValueError(
                "content_text exceeds the maximum of "
                f"{MAX_PROPOSED_CONTENT_CHARS} characters."
            )
        if "\x00" in value:
            raise ValueError("content_text must not contain a NUL byte.")
        return value

    @field_validator("rationale")
    @classmethod
    def _rationale_not_blank(cls, value: str) -> str:
        return _require_non_blank(value, "rationale")

    @field_validator("risks")
    @classmethod
    def _list_items_not_blank(cls, value: list[str], info) -> list[str]:
        return _require_non_blank_items(value, info.field_name)


class ProposedContentInput(_Strict):
    """A set of proposed file bodies, supplied as one strict JSON object.

    It carries no approval, no prompt, no completion, no API key, no base URL,
    no command output, and no apply flag — none of those has a field here, so a
    payload carrying one is **rejected**, not stored. Authorization lives in the
    approved plan artifact and nowhere else; an input cannot authorize itself.

    ``changes`` may be **empty**, which means "nothing proposed yet" — a
    well-formed statement, not a defect.
    """

    schema_version: Literal[PROPOSED_CONTENT_SCHEMA_VERSION]
    mode: Literal[PROPOSED_CONTENT_MODE]
    changes: list[ProposedContentChange]
    assumptions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    requires_human_review: Literal[True]
    next_authorization_required: str

    @field_validator("assumptions", "risks", "open_questions")
    @classmethod
    def _list_items_not_blank(cls, value: list[str], info) -> list[str]:
        return _require_non_blank_items(value, info.field_name)

    @field_validator("next_authorization_required")
    @classmethod
    def _next_authorization_not_blank(cls, value: str) -> str:
        return _require_non_blank(value, "next_authorization_required")

    @model_validator(mode="after")
    def _paths_are_unique(self) -> ProposedContentInput:
        seen: set[str] = set()
        for change in self.changes:
            if change.path in seen:
                raise ValueError(
                    "changes contains more than one entry for the same path; "
                    "duplicates are rejected, not merged."
                )
            seen.add(change.path)
        return self


class WorkspaceContentItem(_Strict):
    """One row of the Phase 5D2 report: what happened to one candidate path.

    ``extra="forbid"`` here and nowhere else in the packet. This is the row that
    carries file text, so it is the one place an unexpected key could smuggle a
    second content field, an apply instruction, or a workspace path past a
    reader's eye — it is rejected instead.

    ``content_text`` is Phase 5D2's already-redacted text, present only when
    ``status`` is ``"read"``. It is **data**: this generator diffs it locally and
    sends it nowhere.
    """

    original_plan_path: str
    canonical_relative_path: str | None = None
    status: Literal[WORKSPACE_CONTENT_STATUSES]  # type: ignore[valid-type]
    kind: Literal["file", "directory", "other"] | None = None
    size_bytes: int | None = None
    bytes_read: int
    encoding: Literal["utf-8"] | None = None
    redacted: bool
    redaction_count: int
    redaction_kinds: list[str] = Field(default_factory=list)
    content_text: str | None = None

    @field_validator("original_plan_path")
    @classmethod
    def _original_path_is_safe_relative(cls, value: str) -> str:
        return _require_safe_relative_repo_path(value, "original_plan_path")

    @field_validator("canonical_relative_path")
    @classmethod
    def _canonical_path_is_safe_relative(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _require_safe_relative_repo_path(value, "canonical_relative_path")

    @field_validator("size_bytes")
    @classmethod
    def _size_not_negative(cls, value: int | None) -> int | None:
        if value is not None and value < 0:
            raise ValueError("size_bytes must not be negative.")
        return value

    @field_validator("bytes_read", "redaction_count")
    @classmethod
    def _count_not_negative(cls, value: int, info) -> int:
        if value < 0:
            raise ValueError(f"{info.field_name} must not be negative.")
        return value


class WorkspaceContentProject(_Packet):
    """The project the Phase 5D2 packet was produced for."""

    project_id: str
    repo: str

    @field_validator("project_id")
    @classmethod
    def _not_blank(cls, value: str, info) -> str:
        return _require_non_blank(value, info.field_name)

    @field_validator("repo")
    @classmethod
    def _repo_valid(cls, value: str) -> str:
        return _require_owner_repo(value)


class WorkspaceContentApprovedPlan(_Packet):
    """The approved plan the Phase 5D2 packet was produced against.

    Only the two fields that pin the packet to one issue are declared. The
    approval metadata Phase 5D2 also prints is **not** read here: an approval is
    honoured from the ``ApprovedL1PlanArtifact`` alone, never from a report.
    """

    issue_number: int
    title: str

    @field_validator("issue_number")
    @classmethod
    def _issue_number_positive(cls, value: int) -> int:
        return _require_positive_issue_number(value)

    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, value: str) -> str:
        return _require_non_blank(value, "title")


class WorkspaceContentBlock(_Packet):
    """Phase 5D2's account of what it did — and, mostly, of what it did not do.

    The five ``Literal[False]`` flags are the point. A packet claiming that
    directories were listed, commands were run, a model was called, diffs were
    generated, or files were edited is not a Phase 5D2 read report, whatever it
    says its mode is, and it is refused rather than used as a diff source.
    """

    candidate_source: Literal[WORKSPACE_CONTENT_CANDIDATE_SOURCE]  # type: ignore[valid-type]
    file_contents_read: Literal[True]
    directories_listed: Literal[False]
    commands_run: Literal[False]
    model_called: Literal[False]
    diffs_generated: Literal[False]
    files_edited: Literal[False]
    items: list[WorkspaceContentItem]

    @model_validator(mode="after")
    def _paths_are_unique(self) -> WorkspaceContentBlock:
        seen: set[str] = set()
        for item in self.items:
            if item.original_plan_path in seen:
                raise ValueError(
                    "items contains more than one entry for the same "
                    "original_plan_path; duplicates are rejected, not merged."
                )
            seen.add(item.original_plan_path)
        return self


class WorkspaceContentPacket(_Packet):
    """A Phase 5D2 ``l2-read-workspace-files`` report, supplied as a local file.

    This is the only channel through which original file text reaches this
    generator. It is **not** a workspace: nothing here is opened, stat'd, or
    resolved, and a path the packet does not mention is a path whose diff cannot
    be generated — never a path to go and read.
    """

    mode: Literal[WORKSPACE_CONTENT_MODE]  # type: ignore[valid-type]
    project: WorkspaceContentProject
    approved_plan: WorkspaceContentApprovedPlan
    workspace_content: WorkspaceContentBlock


# What each generated proposal says about how it was built. Fixed prose: the
# same inputs must always produce the same artifact, so nothing here is
# templated with a value that could vary between runs.
_ASSUMPTIONS = (
    "Diffs were generated from a Phase 5D2 workspace-content packet and a "
    "proposed-content input, both supplied as local files. This generator read "
    "no target workspace file directly.",
    "Original content is whatever that packet recorded. It was bounded by Phase "
    "5D2's byte caps and may be older than the workspace's current state.",
    "Whether these diffs apply cleanly was not checked: no patch tool was run, "
    "no workspace was touched, and no verification was executed.",
    "Line structure was derived with str.splitlines(), so a difference that "
    "exists only in a file's trailing newline is not represented.",
    "pre_image_sha256 and post_image_sha256 are SHA-256 over the exact UTF-8 "
    "bytes of the recorded original and the proposed final text, with no "
    "normalization. They bind the transformation the human approves; the diff "
    "describes it. A proposal whose diff and whose digests disagree is refused "
    "by a writer rather than reconciled.",
)

_NO_CHANGES_ASSUMPTION = (
    "The proposed-content input named no changes, or every change it named "
    "matched the recorded original exactly, so this proposal carries no diff."
)

_RISKS = (
    "These diffs were not applied, not verified, and not checked for "
    "apply-cleanliness. A human must review them and decide.",
    "The proposed content was supplied as an input. This generator did not "
    "author it and cannot attest that it is correct, complete, or safe.",
)

# What a human must authorize before anything beyond a printed diff happens.
# Carried in the artifact itself so the boundary travels with it.
NEXT_AUTHORIZATION_REQUIRED = (
    "Phase 5F or later must be explicitly authorized before applying diffs, "
    "editing files, running commands, committing, pushing, or opening PRs."
)


def _check_identity(
    approved_plan: ApprovedL1PlanArtifact, project: ProjectConfig
) -> None:
    """Refuse an approved plan that is not this project's, exactly (design §3.5).

    String equality only. A plan approved for one project/repo grants nothing
    for another, and the mismatch is reported by *field name* — the differing
    values are never echoed.
    """
    repo = project.repo.github_repo
    mismatched = [
        label
        for label, left, right in (
            ("project_id", approved_plan.project_id, project.project_id),
            ("repo", approved_plan.repo, repo),
            ("plan.repo", approved_plan.plan.repo, repo),
            ("plan_provenance.repo", approved_plan.plan_provenance.repo, repo),
        )
        if left != right
    ]
    if mismatched:
        raise DiffProposalGenerationError(
            "the approved plan does not match this project config exactly; "
            "mismatched fields: " + ", ".join(mismatched) + ". A plan approved "
            "for one project or repo grants nothing for another."
        )


def _check_plan_level(approved_plan: ApprovedL1PlanArtifact) -> None:
    """Re-check the L1 invariants rather than trusting an upstream guarantee.

    ``ApprovedL1PlanArtifact`` already enforces both, exactly as the Phase 5E2
    artifact re-checks them: a downstream guard must not depend on an upstream
    invariant staying true forever, and a plan claiming L2 is corrupt or forged
    — not more authorized.
    """
    plan = approved_plan.plan
    if plan.automation_level != "L1":
        raise DiffProposalGenerationError(
            "approved_plan.plan.automation_level must be exactly 'L1'; a plan "
            "claiming a higher level is corrupt or forged, not more authorized."
        )
    if plan.requires_human_approval is not True:
        raise DiffProposalGenerationError(
            "approved_plan.plan.requires_human_approval must be True."
        )


def _check_packet_identity(
    workspace_content: WorkspaceContentPacket,
    approved_plan: ApprovedL1PlanArtifact,
    project: ProjectConfig,
) -> None:
    """Refuse a content packet read for some other project, repo, or issue.

    The packet is the only source of original file text, so a packet from
    elsewhere would silently produce diffs against the wrong files. Matched with
    exact string equality, by field name, echoing no value.
    """
    mismatched = [
        label
        for label, left, right in (
            (
                "project.project_id",
                workspace_content.project.project_id,
                project.project_id,
            ),
            ("project.repo", workspace_content.project.repo, project.repo.github_repo),
            (
                "approved_plan.issue_number",
                workspace_content.approved_plan.issue_number,
                approved_plan.issue_number,
            ),
            (
                "approved_plan.title",
                workspace_content.approved_plan.title,
                approved_plan.plan.title,
            ),
        )
        if left != right
    ]
    if mismatched:
        raise DiffProposalGenerationError(
            "the workspace-content packet does not match this project config "
            "and approved plan exactly; mismatched fields: "
            + ", ".join(mismatched)
            + ". A packet read for one project, repo, or issue supplies no "
            "original content for another."
        )


def _check_scope(change_path: str, approved_plan: ApprovedL1PlanArtifact) -> None:
    """Refuse a proposed path the approved plan did not put in scope.

    ``files_forbidden_or_out_of_scope`` is checked **first**, so a plan that
    contradicts itself by listing a path in both places resolves in the
    restrictive direction. Neither ``proposed_steps`` nor
    ``required_verification`` nor ``risks`` nor ``open_questions`` is ever read
    as a path: those are prose.
    """
    plan = approved_plan.plan
    if change_path in plan.files_forbidden_or_out_of_scope:
        raise DiffProposalGenerationError(
            f"proposed path {change_path!r} is listed in "
            "approved_plan.plan.files_forbidden_or_out_of_scope and may never "
            "be proposed."
        )
    if change_path not in plan.files_likely_to_change:
        raise DiffProposalGenerationError(
            f"proposed path {change_path!r} is not listed in "
            "approved_plan.plan.files_likely_to_change; a proposal may narrow "
            "the approved scope, never widen it."
        )


def _original_content_for(
    change: ProposedContentChange, item: WorkspaceContentItem
) -> str | None:
    """Return the original text for one change, or refuse to generate its diff.

    ``None`` means "there is deliberately no original" — the ``create`` case.
    Every other outcome is either a string that came out of the Phase 5D2 packet
    or an exception, because a diff invented against an unknown starting state
    would look exactly as authoritative as a real one.
    """
    path = change.path

    if change.change_type == "create":
        if item.status == "read":
            raise DiffProposalGenerationError(
                f"proposed path {path!r} is a 'create', but the workspace-content "
                "packet recorded it as read, so the file already exists. This "
                "phase does not overwrite an existing file under the name "
                "'create'; propose a 'modify' instead."
            )
        if item.status != "missing":
            raise DiffProposalGenerationError(
                f"proposed path {path!r} is a 'create', but the workspace-content "
                f"packet recorded status {item.status!r} rather than 'missing'. "
                "Only a path Phase 5D2 could not find may be created."
            )
        return None

    if item.status != "read":
        raise DiffProposalGenerationError(
            f"proposed path {path!r} is a 'modify', but the workspace-content "
            f"packet recorded status {item.status!r} rather than 'read', so no "
            "original content is available. No diff was generated for it."
        )
    if item.kind != "file":
        raise DiffProposalGenerationError(
            f"proposed path {path!r} was read as kind {item.kind!r} rather than "
            "'file'. Only a regular file's contents may be diffed."
        )
    if item.content_text is None:
        raise DiffProposalGenerationError(
            f"proposed path {path!r} was recorded as read but carries no "
            "content_text. No diff was generated for it."
        )
    if item.redacted:
        raise DiffProposalGenerationError(
            f"proposed path {path!r} was redacted by the Phase 5D2 read, so its "
            "recorded content is not the file's real content. A diff built from "
            "redacted source would be misleading and is refused."
        )
    return item.content_text


def _unified_diff_text(
    *, original: str | None, proposed: str, path: str, change_type: str
) -> str:
    """Run ``difflib`` over two in-memory strings. Returns ``""`` for no change.

    The headers are written to satisfy the Phase 5E2 parser exactly:
    ``--- a/<path>`` / ``+++ b/<path>`` for a modify, ``--- /dev/null`` /
    ``+++ b/<path>`` for a create. ``lineterm=""`` keeps every emitted line
    unterminated so joining on ``"\\n"`` produces a plain textual diff with no
    doubled blank lines.

    ``splitlines()`` is the only normalization, and it is the one the diff needs:
    it drops the line terminators that the ``-``/``+``/`` `` prefixes replace. A
    consequence worth stating plainly is that a difference existing *only* in a
    file's trailing newline produces no diff here, and the artifact records that
    as an assumption rather than hiding it.

    Nothing is applied, staged, or checked for applicability, and no file is
    opened: both operands are strings this function was handed.
    """
    from_lines = [] if original is None else original.splitlines()
    to_lines = proposed.splitlines()
    fromfile = "/dev/null" if change_type == "create" else f"a/{path}"

    return "\n".join(
        difflib.unified_diff(
            from_lines,
            to_lines,
            fromfile=fromfile,
            tofile=f"b/{path}",
            lineterm="",
        )
    )


def _sha256_of_utf8(text: str) -> str:
    """Return the lowercase hex SHA-256 of ``text``'s exact UTF-8 bytes.

    Phase 5F2C. The digest is taken over the bytes the string *is*, with **no
    normalization of any kind** first: no line-ending translation, no trailing
    newline added or removed, no Unicode normalization, no stripping. The whole
    point of the value is that a writer can recompute it from real file bytes
    and compare with ``==``; anything this function tidied up would be a
    difference the comparison could no longer see.

    ``errors`` is deliberately left at its strict default. A string that cannot
    be encoded is a surrogate-bearing string that never came from a real UTF-8
    file, and it fails here rather than being encoded lossily.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _check_no_secret_like_text(unified_diff: str, path: str) -> None:
    """Refuse a generated diff that looks like it carries a credential.

    **Detection only.** The diff is never redacted, because a redacted diff
    reads like a patch and could never apply — it would be a misleading artifact
    rather than a safe one. So the whole generation fails instead, and the human
    decides what to do about the file.

    The message names the *category* and the *path*. The matched text, the
    surrounding line, and the diff itself are never echoed: reporting a leak by
    reprinting it is not a report.
    """
    for category, pattern in _SECRET_LIKE_PATTERNS:
        if pattern.search(unified_diff):
            raise DiffProposalGenerationError(
                f"the diff generated for {path!r} matches the {category!r} "
                "secret-like pattern. It was discarded rather than redacted: a "
                "redacted diff could never apply and would mislead a reviewer. "
                "The matched value is not echoed."
            )


def _decode_strict_json_object(text: str, label: str) -> dict:
    """Decode exactly one strict JSON object, or raise. Rejects, never repairs.

    Surrounding whitespace is tolerated; markdown fences, prose before or after
    the object, arrays, strings, numbers, booleans and ``null`` all fail. No
    file is opened, no environment variable is read, no socket is opened, and no
    process is started — the text is handed in.
    """
    if not isinstance(text, str):
        raise DiffProposalInputParseError(f"{label} text must be a string.")

    stripped = text.strip()
    if not stripped:
        raise DiffProposalInputParseError(f"{label} text was empty.")
    if not (stripped.startswith("{") and stripped.endswith("}")):
        raise DiffProposalInputParseError(
            f"{label} text must be exactly one JSON object with no markdown "
            "fences, prose, or other content around it."
        )

    try:
        decoded = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise DiffProposalInputParseError(
            f"{label} text is not valid JSON: {exc}"
        ) from exc

    if not isinstance(decoded, dict):
        raise DiffProposalInputParseError(
            f"{label} text must be a JSON object, not an array, string, number, "
            "boolean, or null."
        )
    return decoded


def parse_proposed_content_input(text: str) -> ProposedContentInput:
    """Parse strict-JSON proposed-content text into a validated input object.

    Pure function. It loads no file, reads no environment variable, touches no
    workspace, calls no model, opens no socket, runs no command, generates no
    diff, applies no patch, edits nothing, and prints nothing.

    A successful parse means the input is **well-formed**. It does not mean the
    proposed content is correct, that its paths are in scope, or that anything
    may be done with it — scope is checked against the approved plan by
    :func:`build_deterministic_diff_proposal`, and applying anything is a later,
    separately authorized phase.

    Raises:
        DiffProposalInputParseError: ``text`` is not exactly one strict JSON
            object.
        DiffProposalInputValidationError: the object failed
            :class:`ProposedContentInput` validation — an extra field, an unsafe
            path, a duplicate path, oversized or NUL-bearing content, a blank
            rationale, or a missing required flag.
    """
    decoded = _decode_strict_json_object(text, "proposed-content input")
    try:
        return ProposedContentInput.model_validate(decoded)
    except ValidationError as exc:
        raise DiffProposalInputValidationError(
            "proposed-content input failed validation: "
            + _summarize_validation_error(exc)
        ) from exc


def parse_workspace_content_packet(text: str) -> WorkspaceContentPacket:
    """Parse strict-JSON Phase 5D2 report text into a validated packet.

    Pure function, with the same guarantees as
    :func:`parse_proposed_content_input`. The packet may contain file text
    because Phase 5D2 produced it; nothing here sends that text anywhere, and a
    packet is never treated as a licence to go and read more.

    Raises:
        DiffProposalInputParseError: ``text`` is not exactly one strict JSON
            object.
        DiffProposalInputValidationError: the object failed
            :class:`WorkspaceContentPacket` validation — a wrong ``mode``, a
            wrong ``candidate_source``, a claim that directories were listed,
            commands were run, a model was called, diffs were generated or files
            were edited, a blank or malformed identity, an unknown item status,
            an unsafe item path, an unexpected item field, or a duplicate item.
    """
    decoded = _decode_strict_json_object(text, "workspace-content packet")
    try:
        return WorkspaceContentPacket.model_validate(decoded)
    except ValidationError as exc:
        raise DiffProposalInputValidationError(
            "workspace-content packet failed validation: "
            + _summarize_validation_error(exc)
        ) from exc


def build_deterministic_diff_proposal(
    *,
    approved_plan: ApprovedL1PlanArtifact,
    project: ProjectConfig,
    workspace_content: WorkspaceContentPacket,
    proposed_content: ProposedContentInput,
) -> DiffProposalArtifact:
    """Build a Phase 5E2 diff proposal artifact from four objects. Pure function.

    It is handed four already-loaded objects and returns a fifth. It performs no
    file IO, touches no workspace, reads no environment variable, calls no
    model, opens no socket, runs no command, contacts GitHub not at all, reads
    no clock, edits nothing, applies nothing, checks no apply-cleanliness, and
    writes no artifact file. It prints nothing.

    The result is **deterministic**: the same inputs always produce an identical
    artifact, down to the byte. That is why ``generated_at`` is ``None`` and why
    every assumption and risk below is fixed prose.

    Each proposed change is turned into one single-file unified diff between the
    original text the Phase 5D2 packet recorded and the final text the
    proposed-content input supplies, **in the input's order**. A change whose
    proposed text matches the recorded original exactly produces no diff: the
    path is reported in ``omitted_paths`` rather than emitted as an empty or
    invented one. The wrapped :class:`ApprovedL1PlanArtifact` travels through
    **unchanged**, so the approval a human gave stays attached to the thing they
    approved.

    Args:
        approved_plan: A validated, human-approved L1 plan snapshot.
        project: The project config the plan and the packet must match exactly.
        workspace_content: A validated Phase 5D2 report, the only source of
            original file text.
        proposed_content: A validated set of proposed final file bodies.

    Returns:
        A validated :class:`DiffProposalArtifact`. ``changes`` is **empty** when
        nothing was proposed or every proposal was a no-op — a well-formed
        statement, not a defect — and ``patch_proposal`` is always ``None``:
        this phase wraps no Phase 5E0 prose proposal.

    Raises:
        DiffProposalGenerationError: an identity mismatch against the project
            config or the packet, a plan that is not an unescalated L1 plan, a
            proposed path outside the approved scope or absent from the packet,
            a ``modify`` without usable original content, a ``modify`` whose
            source was redacted, a ``create`` over a file that exists, a
            ``create`` with no content to add, a generated diff that matches a
            secret-like pattern, or any Phase 5E2 artifact validation failure.
            Nothing partial is returned and nothing is written.
    """
    _check_identity(approved_plan, project)
    _check_plan_level(approved_plan)
    _check_packet_identity(workspace_content, approved_plan, project)

    items = {
        item.original_plan_path: item for item in workspace_content.workspace_content.items
    }

    changes: list[dict] = []
    omitted_paths: list[str] = []
    source_contents_read = False

    for change in proposed_content.changes:
        path = change.path
        _check_scope(path, approved_plan)

        item = items.get(path)
        if item is None:
            raise DiffProposalGenerationError(
                f"proposed path {path!r} does not appear in the workspace-content "
                "packet, so nothing is known about it. This generator does not "
                "read the workspace to find out; re-run l2-read-workspace-files "
                "and supply a packet that covers it."
            )

        original = _original_content_for(change, item)
        if original is not None:
            # The recorded original was consulted, whether or not it differed.
            source_contents_read = True

        unified_diff = _unified_diff_text(
            original=original,
            proposed=change.content_text,
            path=path,
            change_type=change.change_type,
        )

        if not unified_diff:
            if change.change_type == "create":
                # An empty file cannot be expressed as a hunk, and silently
                # dropping a requested creation would misreport the proposal.
                raise DiffProposalGenerationError(
                    f"proposed path {path!r} is a 'create' with empty "
                    "content_text, which no unified diff hunk can express. It "
                    "was refused rather than silently omitted."
                )
            # A modify whose proposed text already matches the original. Named
            # in omitted_paths so the human sees it was considered, never
            # emitted as a fabricated diff.
            omitted_paths.append(path)
            continue

        _check_no_secret_like_text(unified_diff, path)

        changes.append(
            {
                "path": path,
                "change_type": change.change_type,
                "unified_diff": unified_diff,
                # Phase 5F2C: both ends of the transformation, bound to the
                # artifact. Computed from the exact UTF-8 bytes of the two
                # strings this generator already holds — the packet's recorded
                # original and the input's proposed final text — and never from
                # a normalized copy of either. A ``create`` has no original, so
                # its pre-image digest is null rather than a digest of "".
                "pre_image_sha256": (
                    None if original is None else _sha256_of_utf8(original)
                ),
                "post_image_sha256": _sha256_of_utf8(change.content_text),
                "rationale": change.rationale,
                "risks": list(change.risks),
                "requires_human_review": True,
            }
        )

    assumptions = list(_ASSUMPTIONS)
    assumptions.extend(proposed_content.assumptions)
    if not changes:
        assumptions.append(_NO_CHANGES_ASSUMPTION)

    payload = {
        "schema_version": DIFF_PROPOSAL_SCHEMA_VERSION,
        "mode": DIFF_PROPOSAL_MODE,
        "provenance": {
            # Facts about *this function*, not values copied from an input: it
            # is deterministic, it called nothing, and it used no model.
            "engine": "deterministic",
            "operation": "diff-proposal",
            "real_call": False,
            "model": None,
            "generated_at": None,
            "project_id": approved_plan.project_id,
            "repo": approved_plan.repo,
            "issue_number": approved_plan.issue_number,
            "title": approved_plan.plan.title,
        },
        "approved_plan": approved_plan,
        # Phase 5E3 wraps no Phase 5E0 prose proposal. The diffs were drafted
        # from a content packet and a proposed-content input, not from one.
        "patch_proposal": None,
        "changes": changes,
        "omitted_paths": omitted_paths,
        "assumptions": assumptions,
        "risks": list(_RISKS) + list(proposed_content.risks),
        "open_questions": list(proposed_content.open_questions),
        "source_contents_read": source_contents_read,
        "diffs_generated": True,
        "files_edited": False,
        "commands_run": False,
        # Never checked, and never checkable here: asking whether a diff applies
        # means touching the workspace this generator refuses to touch.
        "applies_cleanly_checked": False,
        "requires_human_review": True,
        "next_authorization_required": NEXT_AUTHORIZATION_REQUIRED,
    }

    # Deliberately validated through the Phase 5E2 model rather than constructed
    # field by field: an unsafe path, an out-of-scope path, a duplicate, a
    # malformed diff, or an identity slip is caught by the same rules that guard
    # an artifact arriving from outside this repository. The generator gets no
    # privileged path around them — which is also what catches the awkward case
    # where a source line beginning ``--`` or ``++`` turns into something that
    # reads like a second file header.
    try:
        return DiffProposalArtifact.model_validate(payload)
    except ValidationError as exc:
        raise DiffProposalGenerationError(
            "the generated diff proposal failed Phase 5E2 artifact validation "
            "and was discarded: " + _summarize_validation_error(exc)
        ) from exc
