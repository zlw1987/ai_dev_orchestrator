"""Typed **unified diff proposal** artifact models and a strict parser (Phase 5E2).

This module lets a diff-shaped artifact exist as **data**. It is a schema plus a
pure parser, in the Phase 4B/4F/5B/5E0 style, wired into no command.

Phase 5E0 typed a proposal that deliberately carried **no diff at all** — prose
only — because carrying one meant reading file contents, which was unauthorized
at the time. Phase 5D2 has since shipped bounded, redacted content reads as its
own separately gated command. Phase 5E2 is the next, still-inert step: it types
what a real unified diff would look like *inside* an artifact, and validates its
**shape**, so that a future producer has a schema to be checked against.

**Phase 5E2 is not diff generation.** There is no generator here, deterministic
or otherwise. Nothing in this module produces a diff, and a parsed diff was
written by something outside this repository.

What this module deliberately cannot do:

- **No diff generation.** Nothing here creates, computes, derives, or modifies a
  diff. :func:`parse_diff_proposal_artifact` is handed text and validates it.
- **No diff application.** Nothing here applies, stages, or writes a patch, and
  no patch tooling is invoked. ``applies_cleanly_checked`` is
  ``Literal[False]``: whether a diff would apply is a question this phase does
  not ask, because asking it means touching a workspace.
- **No file content read.** The ``unified_diff`` string may contain source lines
  as diff context — that is what a diff *is*, and it is allowed as **data** in
  this artifact. It arrived in the text handed to the parser. Nothing here
  opened a file to obtain it, and nothing here sends it anywhere. There is
  deliberately **no** separate ``before_content``/``after_content``/
  ``file_contents`` field: source text lives inside the diff or nowhere.
- **No file loading.** The parser is handed a string. It never opens a path,
  never resolves one, and there is no loader function here.
- **No workspace access.** No target project workspace is read, listed, stat'd,
  globbed, walked, or resolved. Paths are validated as **strings**, lexically,
  and are never joined to a workspace root or canonicalized — that is the Phase
  5D0 guard's job, and nothing here calls it.
- **No file editing, no command execution.** Nothing is applied, run, or
  written. ``required_verification`` is not run.
- **No model call, no network call, no environment read.** ``httpx``,
  ``requests``, ``LLMClient``, ``LLMClientConfig``,
  ``load_llm_client_config_from_env`` and ``GitHubClient`` are not imported, so
  no code path here can construct one. ``engine == "model"`` is a *claim
  recorded in an artifact*, not an instruction to call anything.
- **No clock.** ``generated_at`` is *parsed* when supplied and is never produced
  here.
- **No approval.** Nothing here stamps, writes, or infers an approval. The
  approval already inside the wrapped :class:`ApprovedL1PlanArtifact` is
  re-validated, never created.
- **No CLI behavior.** Importing this package adds no command and no option.

Like Phase 5E0, the artifact wraps an **untouched** ``ApprovedL1PlanArtifact``
snapshot, matches identity **exactly** against it, and contains every proposed
path within the approved plan's ``files_likely_to_change`` while excluding
everything in ``files_forbidden_or_out_of_scope``. It may additionally wrap the
Phase 5E0 ``PatchProposalArtifact`` the diffs were drafted from, in which case
the two must agree — same approval, same identity, and no diff for a path the
prose proposal did not name.

The diff itself is validated for **shape only** (see
:func:`_require_single_file_unified_diff`): one file, real headers naming
exactly the declared path, at least one hunk, no binary payload, and no
rename/mode/delete metadata. Whether it would *apply* is not checked, line
endings are not normalized, and nothing is repaired.

Every model is ``extra="forbid"``, and validation **rejects rather than
repairs**.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from ai_dev_orchestrator.handoff.models import ApprovedL1PlanArtifact
from ai_dev_orchestrator.patch_proposal.models import PatchProposalArtifact


class DiffProposalError(Exception):
    """Base class for diff proposal parsing and validation errors.

    Messages name the *category* of failure and the field that failed. They
    never echo the artifact text, the diff, plan prose, rationales, or any other
    supplied value.

    There is deliberately **no apply error, no edit error, and no command
    error** in this hierarchy: this phase applies nothing, edits nothing, and
    runs nothing, so there is no failure of that kind to report.
    """


class DiffProposalParseError(DiffProposalError):
    """The text was not exactly one strict JSON object."""


class DiffProposalValidationError(DiffProposalError):
    """The decoded object failed :class:`DiffProposalArtifact` validation."""


# The artifact's schema identity. Compared with ``==`` through a ``Literal``: a
# different version is a different artifact and is rejected, not upgraded.
DIFF_PROPOSAL_SCHEMA_VERSION = "diff-proposal.v1"

# What this artifact *is*. There is one mode and it is the harmless one: a
# proposal a human reads. There is no "apply" mode, and adding one would be a
# separately authorized phase, not a new enum member.
DIFF_PROPOSAL_MODE = "proposal-only"

# A diff big enough to be worth capping. The bound exists so a single artifact
# cannot carry an unbounded amount of text through a parser, mirroring the
# candidate/byte caps the workspace phases use. It is a *string length* check —
# nothing is read, truncated, or streamed.
MAX_UNIFIED_DIFF_CHARS = 200_000

# Substrings whose presence means the payload is not the one narrow thing this
# artifact accepts: a single-file textual unified diff of a modification or an
# addition.
#
# - ``GIT binary patch`` / ``Binary files `` — a binary payload. Not reviewable
#   by the human this artifact exists for, and not text.
# - ``rename from `` / ``rename to `` / ``similarity index `` — a rename, which
#   moves a path. ``change_type`` has no rename member, and a rename touches a
#   path the approved plan may never have listed.
# - ``delete file mode`` — a deletion. ``change_type`` has no delete member.
# - ``old mode `` / ``new mode `` — a permission change, which is not a content
#   change and is invisible in a reviewed diff body.
# - ``diff --git`` — a git patch *envelope*. It is the shape that carries all of
#   the above and the shape multi-file patches are built from, so Phase 5E2
#   refuses it outright and accepts only the bare ``---``/``+++``/``@@`` form.
_FORBIDDEN_DIFF_MARKERS = (
    "GIT binary patch",
    "Binary files ",
    "rename from ",
    "rename to ",
    "delete file mode",
    "old mode ",
    "new mode ",
    "similarity index ",
    "diff --git",
)

# An 8.3-style short name — ``PROGRA~1``, ``LONGFI~1.TXT``. Such a component
# names the same file as its long form with a different string, so a proposal
# using one cannot be compared reliably against the approved plan's path list.
# Refused rather than expanded (expanding would require touching disk).
_SHORT_NAME_RE = re.compile(r"^[^/\\.]{1,8}~[0-9]{1,3}(\.[^/\\.]{1,3})?$")

_SEPARATOR_CHARS = "\\/"


def _require_non_blank(value: str, field_name: str) -> str:
    """Reject empty or whitespace-only strings."""
    if value is None or not value.strip():
        raise ValueError(f"{field_name} must not be empty or whitespace-only.")
    return value


def _require_non_blank_items(values: list[str], field_name: str) -> list[str]:
    """Reject lists containing empty or whitespace-only string items."""
    for item in values:
        if item is None or not item.strip():
            raise ValueError(
                f"{field_name} items must not be empty or whitespace-only."
            )
    return values


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


def _split_components(raw: str) -> list[str]:
    """Split on either separator, keeping empties. Purely lexical."""
    return raw.replace("\\", "/").split("/")


def _require_safe_relative_repo_path(value: str, field_name: str) -> str:
    """Reject anything but a plain, relative, unambiguous repo path string.

    Identical in intent and conservatism to the Phase 5E0 check, and deliberately
    duplicated rather than shared: nothing here touches disk, joins a workspace
    root, canonicalizes, or normalizes. A path is either obviously safe to reason
    about as a string or it is refused, because the only things this artifact
    does with a path are compare it against the approved plan's list and require
    the diff headers to name it exactly — and a form that can denote the same
    file as some other string makes both meaningless.

    Refused: absolute paths (leading separator or drive letter), UNC,
    extended-length ``\\\\?\\`` and device ``\\\\.\\`` prefixes, any ``:``
    (drive-relative forms and NTFS alternate data streams), ``.`` and ``..``
    components (so all parent traversal, and the bare ``"."``), empty components
    from doubled separators, components ending in a dot or a space, and
    8.3-short-name-looking components.
    """
    value = _require_non_blank(value, field_name)

    head = value[:4]
    if len(head) >= 4 and head[0] in _SEPARATOR_CHARS and head[1] in _SEPARATOR_CHARS:
        if head[2] == "?" and head[3] in _SEPARATOR_CHARS:
            raise ValueError(
                f"{field_name} must not use an extended-length path prefix."
            )
        if head[2] == "." and head[3] in _SEPARATOR_CHARS:
            raise ValueError(f"{field_name} must not use a device path prefix.")
    if len(value) >= 2 and value[0] in _SEPARATOR_CHARS and value[1] in _SEPARATOR_CHARS:
        raise ValueError(f"{field_name} must not be a UNC path.")
    if value[0] in _SEPARATOR_CHARS:
        raise ValueError(
            f"{field_name} must be a relative repo path, not an absolute path."
        )
    if ":" in value:
        raise ValueError(
            f"{field_name} must not contain ':' (drive letters and alternate "
            "data streams are refused)."
        )

    components = _split_components(value)
    for component in components:
        if component == "":
            raise ValueError(f"{field_name} must not contain an empty path component.")
        if component == "..":
            raise ValueError(f"{field_name} must not contain parent traversal ('..').")
        if component == ".":
            raise ValueError(
                f"{field_name} must not contain a '.' path component, and must "
                "not be '.' itself."
            )
        if component.endswith(" "):
            raise ValueError(
                f"{field_name} must not have a path component ending in a space."
            )
        if component.endswith("."):
            raise ValueError(
                f"{field_name} must not have a path component ending in a dot."
            )
        if _SHORT_NAME_RE.match(component):
            raise ValueError(
                f"{field_name} must not have a path component that looks like an "
                "8.3 short name."
            )

    return value


def _require_textual_diff_payload(value: str) -> str:
    """Reject blank, oversized, NUL-bearing, and non-content diff payloads.

    These are the checks that need only the diff string itself. Nothing here
    parses hunks arithmetically, normalizes line endings, or decides whether the
    diff would apply — the last of those would require a workspace.
    """
    value = _require_non_blank(value, "unified_diff")

    if len(value) > MAX_UNIFIED_DIFF_CHARS:
        raise ValueError(
            "unified_diff exceeds the maximum of "
            f"{MAX_UNIFIED_DIFF_CHARS} characters."
        )
    if "\x00" in value:
        raise ValueError("unified_diff must not contain a NUL byte.")

    for marker in _FORBIDDEN_DIFF_MARKERS:
        if marker in value:
            raise ValueError(
                f"unified_diff must not contain {marker!r}: this artifact accepts "
                "only a single-file textual diff of a modification or an "
                "addition, never a binary payload, a rename, a deletion, a mode "
                "change, or a git patch envelope."
            )

    return value


def _require_single_file_unified_diff(
    value: str, change_type: str, path: str
) -> str:
    """Reject anything but one single-file unified diff naming exactly ``path``.

    The accepted shape is deliberately the narrowest one that is still a real
    diff::

        --- a/<path>        (or '--- /dev/null' when change_type is 'create')
        +++ b/<path>
        @@ ... @@
        ...

    Exactly one ``---`` line and exactly one ``+++`` line may appear, the second
    immediately after the first, and both must equal the expected header
    **exactly** — no timestamp suffix, no ``a/``-less form, no substituted path.
    At least one ``@@`` hunk header must follow. A multi-file patch therefore
    fails on the header count, and so, conservatively, does a diff whose body
    happens to contain a line starting with ``--- `` or ``+++ ``; refusing such a
    payload is the safe direction, since this phase's job is to be sure what it
    is looking at.

    What is **not** checked, on purpose: whether the hunk line counts are
    arithmetically consistent, whether the context matches any real file, and
    whether the diff would apply. The last two require reading a workspace, and
    no patch tooling is invoked here.
    """
    lines = value.split("\n")

    old_headers = [index for index, line in enumerate(lines) if line.startswith("--- ")]
    new_headers = [index for index, line in enumerate(lines) if line.startswith("+++ ")]

    if not old_headers:
        raise ValueError("unified_diff must contain a '---' file header line.")
    if not new_headers:
        raise ValueError("unified_diff must contain a '+++' file header line.")
    if len(old_headers) > 1 or len(new_headers) > 1:
        raise ValueError(
            "unified_diff must be exactly one single-file diff; multi-file "
            "patches are rejected, not split."
        )

    old_index = old_headers[0]
    new_index = new_headers[0]
    if new_index != old_index + 1:
        raise ValueError(
            "unified_diff must have its '+++' header on the line immediately "
            "after its '---' header."
        )

    expected_old = "--- /dev/null" if change_type == "create" else f"--- a/{path}"
    expected_new = f"+++ b/{path}"

    if lines[old_index] != expected_old:
        if change_type == "create":
            raise ValueError(
                "unified_diff for change_type 'create' must have exactly "
                "'--- /dev/null' as its '---' header."
            )
        raise ValueError(
            "unified_diff for change_type 'modify' must have exactly "
            "'--- a/<path>' as its '---' header, naming the change's own path."
        )
    if lines[new_index] != expected_new:
        raise ValueError(
            "unified_diff must have exactly '+++ b/<path>' as its '+++' header, "
            "naming the change's own path."
        )

    if not any(line.startswith("@@") for line in lines[new_index + 1 :]):
        raise ValueError(
            "unified_diff must contain at least one '@@' hunk header after its "
            "file headers."
        )

    return value


class _Strict(BaseModel):
    """Base model that rejects unknown fields, so forged extras fail loudly."""

    model_config = ConfigDict(extra="forbid")


class DiffProposalFileChange(_Strict):
    """One file a proposal suggests a **human** change, carrying a real diff.

    This is where Phase 5E2 differs from Phase 5E0: there **is** a
    ``unified_diff`` here, and it may contain source lines as diff context. That
    text is **data in an artifact somebody else produced**. Nothing in this
    module created it, read a file to obtain it, or sends it anywhere — and
    there is still no ``before_content``, ``after_content``, ``command``,
    ``command_output``, ``apply``, or ``workspace_path`` field, so a payload
    carrying one is rejected as an extra.

    ``change_type`` is ``"modify"`` or ``"create"`` only. Deletes and renames
    have no member here and are additionally refused inside the diff body: both
    move or destroy a path, and a path the approved plan listed as changeable is
    not thereby a path it authorized removing.

    ``requires_human_review`` is ``Literal[True]`` with no default: a proposal
    cannot mark its own change as not needing review, and cannot get the flag by
    omitting it.

    ``path`` is validated as a **string** — relative, unambiguous, no traversal.
    It is never joined to a workspace root, canonicalized, stat'd, or read. The
    diff headers must then name that same string exactly, so the diff cannot
    claim one file while the artifact declares another.
    """

    path: str
    change_type: Literal["modify", "create"]
    unified_diff: str
    rationale: str
    risks: list[str] = Field(default_factory=list)
    requires_human_review: Literal[True]

    @field_validator("path")
    @classmethod
    def _path_is_safe_relative(cls, value: str) -> str:
        return _require_safe_relative_repo_path(value, "path")

    @field_validator("unified_diff")
    @classmethod
    def _diff_payload_is_textual(cls, value: str) -> str:
        return _require_textual_diff_payload(value)

    @field_validator("rationale")
    @classmethod
    def _rationale_not_blank(cls, value: str) -> str:
        return _require_non_blank(value, "rationale")

    @field_validator("risks")
    @classmethod
    def _list_items_not_blank(cls, value: list[str], info) -> list[str]:
        return _require_non_blank_items(value, info.field_name)

    @model_validator(mode="after")
    def _diff_headers_name_this_path(self) -> DiffProposalFileChange:
        _require_single_file_unified_diff(
            self.unified_diff, self.change_type, self.path
        )
        return self


class DiffProposalProvenance(_Strict):
    """How a diff proposal was produced, and what it was produced for.

    ``engine`` is a closed enum. ``"deterministic"`` and ``"manual"`` must carry
    ``real_call is False`` and ``model is None`` — an engine that does not call a
    model has no model name and made no call, and claiming otherwise is a
    contradiction rather than extra detail. ``"model"`` must name a model, but
    that is still only a **record of a claim**: this module calls nothing, and a
    ``"model"`` provenance parses exactly as inertly as the other two.

    An endpoint host, a base URL, an API key, a prompt, a completion, a message
    list, a raw response, and a workspace path all have **no field here**, so a
    payload carrying one is rejected as an extra rather than being stored.

    ``generated_at`` is optional and is only ever *parsed*: nothing in this
    module produces a timestamp.
    """

    engine: Literal["manual", "deterministic", "model"]
    operation: Literal["diff-proposal"]
    real_call: bool
    model: str | None = None
    generated_at: datetime | None = None
    project_id: str
    repo: str
    issue_number: int
    title: str

    @field_validator("project_id", "title")
    @classmethod
    def _not_blank(cls, value: str, info) -> str:
        return _require_non_blank(value, info.field_name)

    @field_validator("model")
    @classmethod
    def _optional_not_blank(cls, value: str | None, info) -> str | None:
        if value is None:
            return None
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
    def _engine_claims_are_consistent(self) -> DiffProposalProvenance:
        if self.engine == "model":
            if self.model is None:
                raise ValueError("model must be named when engine is 'model'.")
        else:
            if self.model is not None:
                raise ValueError("model must be null when engine is not 'model'.")
            if self.real_call is not False:
                raise ValueError(
                    "real_call must be false when engine is not 'model'."
                )
        return self


class DiffProposalArtifact(_Strict):
    """A set of proposed unified diffs, bound to one approved plan.

    The ``approved_plan`` field is a **snapshot** carrying the human approval as
    it stood, re-validated by :class:`ApprovedL1PlanArtifact` on every parse. A
    proposal therefore cannot assert its own authorization: it can only carry one
    a human already gave, for one specific project, repo, issue, and title.

    ``patch_proposal`` is an optional snapshot of the Phase 5E0 prose proposal
    these diffs were drafted from. When present it must agree with this artifact
    exactly — the same approved plan by ``model_dump``, the same identity, and no
    diff for a path the prose proposal did not name (unless it named none at
    all, which means "no paths chosen yet" rather than "no paths permitted").

    Beyond the per-model checks, the wrapper enforces:

    - **Exact identity matching** between ``provenance`` and ``approved_plan``.
      String equality only — the failure this prevents is a proposal for one
      issue being carried into another.
    - **Scope containment.** Every ``changes[].path`` must appear **exactly** in
      ``approved_plan.plan.files_likely_to_change`` and must **not** appear in
      its ``files_forbidden_or_out_of_scope``. A proposal may cover fewer files
      than the plan allowed; it may never introduce one.
    - **No duplicate paths.** Two diffs for the same file are rejected, not
      merged or concatenated: there is no defined precedence, and dropping one
      would hide a change from the human reading this.
    - **``automation_level == "L1"`` and ``requires_human_approval is True``,
      re-checked explicitly** even though ``ApprovedL1PlanArtifact`` already
      guarantees both. A downstream guard must not depend on an upstream
      invariant staying true forever.
    - **The flags describing what did and did not happen.**
      ``diffs_generated`` is ``Literal[True]`` — this artifact exists because
      diffs were produced somewhere. ``files_edited``, ``commands_run`` and
      ``applies_cleanly_checked`` are ``Literal[False]`` with no defaults: in
      Phase 5E2 these are not observations but the *shape* of a legal artifact,
      and a payload claiming one is describing something this phase does not do.
      ``source_contents_read`` is a plain ``bool``, because a producer plausibly
      did read contents (via Phase 5D2 or otherwise) to draft a diff — this
      parser records that **claim** and never reads anything itself.

    ``changes`` may be **empty**, which means "no diff proposed yet" — a
    well-formed statement about an approved plan, not a defect.

    Constructing this model never means anything may be *done*. Phase 5E2 ships
    no producer, no applier, and no consumer, and L2 remains unbuilt.
    """

    schema_version: Literal[DIFF_PROPOSAL_SCHEMA_VERSION]
    mode: Literal[DIFF_PROPOSAL_MODE]
    provenance: DiffProposalProvenance
    approved_plan: ApprovedL1PlanArtifact
    patch_proposal: PatchProposalArtifact | None = None
    changes: list[DiffProposalFileChange]
    omitted_paths: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    source_contents_read: bool
    diffs_generated: Literal[True]
    files_edited: Literal[False]
    commands_run: Literal[False]
    applies_cleanly_checked: Literal[False]
    requires_human_review: Literal[True]
    next_authorization_required: str

    @field_validator("omitted_paths")
    @classmethod
    def _omitted_paths_are_safe(cls, value: list[str]) -> list[str]:
        for item in value:
            _require_safe_relative_repo_path(item, "omitted_paths")
        return value

    @field_validator("assumptions", "risks", "open_questions")
    @classmethod
    def _list_items_not_blank(cls, value: list[str], info) -> list[str]:
        return _require_non_blank_items(value, info.field_name)

    @field_validator("next_authorization_required")
    @classmethod
    def _next_authorization_not_blank(cls, value: str) -> str:
        return _require_non_blank(value, "next_authorization_required")

    @model_validator(mode="after")
    def _identity_and_scope_match(self) -> DiffProposalArtifact:
        plan = self.approved_plan.plan

        if self.provenance.project_id != self.approved_plan.project_id:
            raise ValueError(
                "provenance.project_id does not match approved_plan.project_id "
                "exactly."
            )
        if self.provenance.repo != self.approved_plan.repo:
            raise ValueError(
                "provenance.repo does not match approved_plan.repo exactly."
            )
        if self.provenance.issue_number != self.approved_plan.issue_number:
            raise ValueError(
                "provenance.issue_number does not match "
                "approved_plan.issue_number exactly."
            )
        if self.provenance.title != plan.title:
            raise ValueError(
                "provenance.title does not match approved_plan.plan.title exactly."
            )

        if plan.automation_level != "L1":
            raise ValueError(
                "approved_plan.plan.automation_level must be exactly 'L1'; a plan "
                "claiming a higher level is corrupt or forged, not more authorized."
            )
        if plan.requires_human_approval is not True:
            raise ValueError(
                "approved_plan.plan.requires_human_approval must be True."
            )

        allowed = plan.files_likely_to_change
        forbidden = plan.files_forbidden_or_out_of_scope
        seen: set[str] = set()
        for change in self.changes:
            if change.path in forbidden:
                raise ValueError(
                    "changes.path is listed in "
                    "approved_plan.plan.files_forbidden_or_out_of_scope and may "
                    "never be proposed."
                )
            if change.path not in allowed:
                raise ValueError(
                    "changes.path is not listed in "
                    "approved_plan.plan.files_likely_to_change; a proposal may "
                    "narrow the approved scope, never widen it."
                )
            if change.path in seen:
                raise ValueError(
                    "changes contains more than one entry for the same path; "
                    "duplicates are rejected, not merged."
                )
            seen.add(change.path)

        self._patch_proposal_agrees(seen)
        return self

    def _patch_proposal_agrees(self, change_paths: set[str]) -> None:
        """Require the optional prose-proposal snapshot to agree with this one."""
        proposal = self.patch_proposal
        if proposal is None:
            return

        if proposal.approved_plan.model_dump() != self.approved_plan.model_dump():
            raise ValueError(
                "patch_proposal.approved_plan does not match approved_plan "
                "exactly; a diff proposal may not re-approve itself against a "
                "different plan snapshot."
            )
        if proposal.provenance.project_id != self.provenance.project_id:
            raise ValueError(
                "patch_proposal.provenance.project_id does not match "
                "provenance.project_id exactly."
            )
        if proposal.provenance.repo != self.provenance.repo:
            raise ValueError(
                "patch_proposal.provenance.repo does not match provenance.repo "
                "exactly."
            )
        if proposal.provenance.issue_number != self.provenance.issue_number:
            raise ValueError(
                "patch_proposal.provenance.issue_number does not match "
                "provenance.issue_number exactly."
            )
        if proposal.provenance.title != self.provenance.title:
            raise ValueError(
                "patch_proposal.provenance.title does not match provenance.title "
                "exactly."
            )

        proposed_paths = {change.path for change in proposal.changes}
        if proposed_paths and not change_paths <= proposed_paths:
            raise ValueError(
                "changes.path is not present in patch_proposal.changes; a diff "
                "may only be proposed for a path the wrapped patch proposal "
                "already named."
            )


def _summarize_validation_error(exc: ValidationError) -> str:
    """Render a ``ValidationError`` as field locations and messages only.

    Following the Phase 4L/5B/5E0 precedent, failures are loud about *category*
    and quiet about *content*: the supplied values are never echoed. That matters
    more here than anywhere before it, because a rejected artifact can carry a
    diff full of source lines.
    """
    parts = []
    for error in exc.errors():
        location = ".".join(str(item) for item in error["loc"]) or "(root)"
        parts.append(f"{location}: {error['msg']}")
    return "; ".join(parts)


def parse_diff_proposal_artifact(text: str) -> DiffProposalArtifact:
    """Parse strict-JSON diff proposal text into a validated artifact.

    Pure function. It loads no file, reads no environment variable, touches no
    workspace, calls no model, opens no socket, runs no command, generates no
    diff, modifies no diff, applies no patch, edits nothing, and logs or prints
    nothing. It is handed the text; obtaining that text is the caller's problem
    and is not implemented in this phase.

    Strict in the Phase 4F sense — it **rejects rather than repairs**. The text
    must be exactly one JSON object: surrounding whitespace is tolerated, but
    markdown fences, prose before or after the object, arrays, strings, numbers,
    booleans, and ``null`` all fail. Unknown fields are never stripped, missing
    fields are never inferred, and line endings inside a diff are never
    normalized.

    A successful parse means the proposal is **well-formed, bound to a valid
    approval, within that approval's declared scope, and carrying diffs of the
    one narrow shape this artifact accepts**. It does not mean the diffs apply —
    that is never checked — and it authorizes nothing: nothing in this repository
    consumes the result, no patch applier exists, and L2 is not built.

    Raises:
        DiffProposalParseError: ``text`` is not exactly one strict JSON object.
        DiffProposalValidationError: the object failed
            :class:`DiffProposalArtifact` validation — an extra field, an unsafe
            or out-of-scope path, an identity mismatch, a duplicate path, a diff
            that is not one single-file textual unified diff naming its own path,
            a claim that files were edited / commands were run / apply-cleanliness
            was checked, or a missing or malformed approved plan.
    """
    if not isinstance(text, str):
        raise DiffProposalParseError("diff proposal artifact text must be a string.")

    stripped = text.strip()
    if not stripped:
        raise DiffProposalParseError("diff proposal artifact text was empty.")
    if not (stripped.startswith("{") and stripped.endswith("}")):
        raise DiffProposalParseError(
            "diff proposal artifact text must be exactly one JSON object with no "
            "markdown fences, prose, or other content around it."
        )

    try:
        decoded = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise DiffProposalParseError(
            f"diff proposal artifact text is not valid JSON: {exc}"
        ) from exc

    if not isinstance(decoded, dict):
        raise DiffProposalParseError(
            "diff proposal artifact text must be a JSON object, not an array, "
            "string, number, boolean, or null."
        )

    try:
        return DiffProposalArtifact.model_validate(decoded)
    except ValidationError as exc:
        raise DiffProposalValidationError(
            "diff proposal artifact failed validation: "
            + _summarize_validation_error(exc)
        ) from exc
