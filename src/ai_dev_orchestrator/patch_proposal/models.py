"""Typed patch **proposal** artifact models and a strict parser (Phase 5E0).

This module types the shape of the artifact §13's "Phase 5E — patch proposal
artifact only" would eventually produce, and **nothing else**. It is a schema
plus a pure parser, in the Phase 4B/4F/5B style, wired into no command.

**Phase 5E0 is not patch generation.** There is no generator here, deterministic
or otherwise. Nothing in this module produces a proposal, and a parsed proposal
was written by something outside this repository. Producing one is Phase 5E1,
which is proposed and not authorized.

What this module deliberately cannot do:

- **No diff.** :class:`PatchProposalChange` carries a *rationale* and *prose
  steps*, and has no field for a unified diff, a hunk, a patch, an edit script,
  before/after content, or any other applyable payload. That is a deliberate
  shape decision, not an omission to be filled in later by adding a key: a
  payload carrying one is rejected as an extra field (design §5). Generating a
  real diff requires reading file contents, which is Phase 5D2, which is also
  not authorized.
- **No file content.** No source text, no excerpt, and no command output has a
  field here. The proposal names paths the *approved plan already named* and
  says what a human should do to them.
- **No file loading.** The parser is handed a string. It never opens a path,
  never resolves one, and there is no loader function here.
- **No workspace access.** No target project workspace is read, listed, stat'd,
  or resolved. Paths are validated as **strings**, lexically, and are never
  joined to a workspace root or canonicalized — that is the Phase 5D0 guard's
  job, and nothing here calls it.
- **No file editing, no command execution.** Nothing is applied, run, or
  written.
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

The proposal wraps an **untouched** ``ApprovedL1PlanArtifact`` snapshot, for the
same reason Phase 5B wrapped an untouched ``L1Plan``: the approval a human gave
must travel with the thing it approved, and a proposal must not be able to
restate its own authorization. Identity is then matched **exactly** across the
proposal's provenance and the approved plan — no normalization, no case folding,
no prefix matching (design §3.5).

Scope containment is the other half. Every proposed path must appear **exactly**
in the approved plan's ``files_likely_to_change`` and must **not** appear in its
``files_forbidden_or_out_of_scope``: a proposal may propose less than the plan
allowed, never more. Duplicate paths are **rejected** rather than merged, since
two proposals for one file have no defined precedence and silently keeping one
would discard a change a human was meant to read.

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


class PatchProposalError(Exception):
    """Base class for patch proposal parsing and validation errors.

    Messages name the *category* of failure and the field that failed. They
    never echo the artifact text, plan prose, rationales, or any supplied value.
    """


class PatchProposalParseError(PatchProposalError):
    """The text was not exactly one strict JSON object."""


class PatchProposalValidationError(PatchProposalError):
    """The decoded object failed :class:`PatchProposalArtifact` validation."""


# The artifact's schema identity. Compared with ``==`` through a ``Literal``: a
# different version is a different artifact and is rejected, not upgraded.
PATCH_PROPOSAL_SCHEMA_VERSION = "patch-proposal.v1"

# What this artifact *is*. There is one mode and it is the harmless one: a
# proposal a human reads. There is no "apply" mode, and adding one would be a
# separately authorized phase, not a new enum member.
PATCH_PROPOSAL_MODE = "proposal-only"

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

    This is a **lexical** check, deliberately mirroring the Phase 5D0 precheck's
    conservatism without importing any of its machinery: nothing here touches
    disk, joins a workspace root, canonicalizes, or normalizes. A path is either
    obviously safe to reason about as a string or it is refused, because the
    only thing this artifact does with a path is compare it against the approved
    plan's list — and a form that can denote the same file as some other string
    makes that comparison meaningless.

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


class _Strict(BaseModel):
    """Base model that rejects unknown fields, so forged extras fail loudly."""

    model_config = ConfigDict(extra="forbid")


class PatchProposalChange(_Strict):
    """One file a proposal suggests a **human** change, described in prose.

    This is the shape decision that makes Phase 5E0 safe to ship: a change is a
    ``path``, a ``change_type``, a ``rationale``, ``proposed_steps`` and
    ``risks`` — and there is **no diff, no patch, no edit script, no command,
    and no file content**. Nothing here can be applied, because there is nothing
    applyable to apply.

    ``requires_human_review`` is ``Literal[True]`` with no default: a proposal
    cannot mark its own change as not needing review, and cannot get the flag by
    omitting it.

    ``path`` is validated as a **string** — relative, unambiguous, no traversal.
    It is never joined to a workspace root, canonicalized, stat'd, or read.
    """

    path: str
    change_type: Literal["modify", "create"]
    rationale: str
    proposed_steps: list[str]
    risks: list[str] = Field(default_factory=list)
    requires_human_review: Literal[True]

    @field_validator("path")
    @classmethod
    def _path_is_safe_relative(cls, value: str) -> str:
        return _require_safe_relative_repo_path(value, "path")

    @field_validator("rationale")
    @classmethod
    def _rationale_not_blank(cls, value: str) -> str:
        return _require_non_blank(value, "rationale")

    @field_validator("proposed_steps", "risks")
    @classmethod
    def _list_items_not_blank(cls, value: list[str], info) -> list[str]:
        return _require_non_blank_items(value, info.field_name)

    @field_validator("proposed_steps")
    @classmethod
    def _proposed_steps_not_empty(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("proposed_steps must contain at least one item.")
        return value


class PatchProposalProvenance(_Strict):
    """How a proposal was produced, and what it was produced for.

    ``engine`` is a closed enum. ``"deterministic"`` and ``"manual"`` must carry
    ``real_call is False`` and ``model is None`` — an engine that does not call a
    model has no model name and made no call, and claiming otherwise is a
    contradiction rather than extra detail. ``"model"`` must name a model, but
    that is still only a **record of a claim**: this module calls nothing, and a
    ``"model"`` provenance parses exactly as inertly as the other two.

    An endpoint host, a base URL, an API key, a prompt, a completion, a message
    list, a raw response, and a workspace path all have **no field here**, so a
    payload carrying one is rejected as an extra rather than being stored. That
    is stricter than Phase 5B's provenance, which does carry ``endpoint_host``:
    a proposal artifact travels further and has less reason to name where a
    model lives.

    ``generated_at`` is optional and is only ever *parsed*: nothing in this
    module produces a timestamp.
    """

    engine: Literal["deterministic", "manual", "model"]
    operation: Literal["patch-proposal"]
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
    def _engine_claims_are_consistent(self) -> PatchProposalProvenance:
        if self.engine == "model":
            if self.model is None:
                raise ValueError(
                    "model must be named when engine is 'model'."
                )
        else:
            if self.model is not None:
                raise ValueError(
                    "model must be null when engine is not 'model'."
                )
            if self.real_call is not False:
                raise ValueError(
                    "real_call must be false when engine is not 'model'."
                )
        return self


class PatchProposalArtifact(_Strict):
    """A proposal-shaped description of work, bound to one approved plan.

    The ``approved_plan`` field is a **snapshot** carrying the human approval as
    it stood, re-validated by :class:`ApprovedL1PlanArtifact` on every parse. A
    proposal therefore cannot assert its own authorization: it can only carry
    one a human already gave, for one specific project, repo, issue, and title.

    Beyond the per-model checks, the wrapper enforces:

    - **Exact identity matching** between ``provenance`` and ``approved_plan``
      (``project_id``, ``repo``, ``issue_number``, and ``title`` against the
      plan's title). String equality only — the failure this prevents is a
      proposal for one issue being carried into another.
    - **Scope containment.** Every ``changes[].path`` must appear **exactly** in
      ``approved_plan.plan.files_likely_to_change`` and must **not** appear in
      ``approved_plan.plan.files_forbidden_or_out_of_scope``. A proposal may
      cover fewer files than the plan allowed; it may never introduce one.
    - **No duplicate paths.** Two changes for the same file are rejected, not
      merged: there is no defined precedence, and dropping one would hide work
      from the human reading this.
    - **``automation_level == "L1"`` and ``requires_human_approval is True``,
      re-checked explicitly** even though ``ApprovedL1PlanArtifact`` already
      guarantees both. A downstream guard must not depend on an upstream
      invariant staying true forever.
    - **The three "did not happen" flags**, each ``Literal[False]`` with no
      default: ``file_contents_read``, ``files_edited`` and ``commands_run``. In
      Phase 5E0 these are not observations — they are the *shape* of a legal
      artifact. Nothing in this repository can produce a proposal for which any
      of them would be true, so a payload claiming one is describing something
      this phase does not do, and it is rejected.

    ``changes`` may be **empty**, which means "no patch proposed yet" — a
    well-formed statement about an approved plan, not a defect.

    Constructing this model never means anything may be *done*. Phase 5E0 ships
    no producer and no consumer, and L2 remains unbuilt.
    """

    schema_version: Literal[PATCH_PROPOSAL_SCHEMA_VERSION]
    mode: Literal[PATCH_PROPOSAL_MODE]
    provenance: PatchProposalProvenance
    approved_plan: ApprovedL1PlanArtifact
    changes: list[PatchProposalChange]
    omitted_paths: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    file_contents_read: Literal[False]
    files_edited: Literal[False]
    commands_run: Literal[False]
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
    def _identity_and_scope_match(self) -> PatchProposalArtifact:
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

        return self


def _summarize_validation_error(exc: ValidationError) -> str:
    """Render a ``ValidationError`` as field locations and messages only.

    Following the Phase 4L/5B precedent, failures are loud about *category* and
    quiet about *content*: the supplied values are never echoed, because a
    proposal can carry plan prose, rationales, and provenance an operator may
    not want surfaced.
    """
    parts = []
    for error in exc.errors():
        location = ".".join(str(item) for item in error["loc"]) or "(root)"
        parts.append(f"{location}: {error['msg']}")
    return "; ".join(parts)


def parse_patch_proposal_artifact(text: str) -> PatchProposalArtifact:
    """Parse strict-JSON proposal text into a validated artifact.

    Pure function. It loads no file, reads no environment variable, touches no
    workspace, calls no model, opens no socket, runs no command, generates no
    patch, edits nothing, and logs or prints nothing. It is handed the text;
    obtaining that text is the caller's problem and is not implemented in this
    phase.

    Strict in the Phase 4F sense — it **rejects rather than repairs**. The text
    must be exactly one JSON object: surrounding whitespace is tolerated, but
    markdown fences, prose before or after the object, arrays, strings, numbers,
    booleans, and ``null`` all fail. Unknown fields are never stripped and
    missing fields are never inferred.

    A successful parse means the proposal is **well-formed, bound to a valid
    approval, and within that approval's declared scope**. It does not authorize
    anything: there is no diff to apply, nothing in this repository consumes the
    result, and L2 is not built.

    Raises:
        PatchProposalParseError: ``text`` is not exactly one strict JSON object.
        PatchProposalValidationError: the object failed
            :class:`PatchProposalArtifact` validation — an extra field, an
            unsafe or out-of-scope path, an identity mismatch, a duplicate path,
            a claim that contents were read / files edited / commands run, or a
            missing or malformed approved plan.
    """
    if not isinstance(text, str):
        raise PatchProposalParseError("patch proposal artifact text must be a string.")

    stripped = text.strip()
    if not stripped:
        raise PatchProposalParseError("patch proposal artifact text was empty.")
    if not (stripped.startswith("{") and stripped.endswith("}")):
        raise PatchProposalParseError(
            "patch proposal artifact text must be exactly one JSON object with no "
            "markdown fences, prose, or other content around it."
        )

    try:
        decoded = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise PatchProposalParseError(
            f"patch proposal artifact text is not valid JSON: {exc}"
        ) from exc

    if not isinstance(decoded, dict):
        raise PatchProposalParseError(
            "patch proposal artifact text must be a JSON object, not an array, "
            "string, number, boolean, or null."
        )

    try:
        return PatchProposalArtifact.model_validate(decoded)
    except ValidationError as exc:
        raise PatchProposalValidationError(
            "patch proposal artifact failed validation: "
            + _summarize_validation_error(exc)
        ) from exc
