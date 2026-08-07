"""Typed approved-plan handoff models and a strict parser (Phase 5B).

This module implements §3 of
[PHASE_5_L2_IMPLEMENTER_BOUNDARY_DESIGN.md](../../../docs/PHASE_5_L2_IMPLEMENTER_BOUNDARY_DESIGN.md)
— the L1-to-L2 handoff **artifact shape** — and nothing else. It is a schema
plus a pure parser, in the Phase 4B/4F style, wired into no command.

What this module deliberately cannot do:

- **No L2 action.** Nothing here inspects, edits, proposes, applies, or executes
  anything. A parsed artifact is *data describing an approval*, never a
  permission slip that this module acts on.
- **No file loading.** The parser is handed a string. It never opens a path,
  never resolves one, and there is no loader function here — reading an artifact
  from disk is a later, separately authorized phase.
- **No workspace access.** No target project workspace is read, listed, stat'd,
  or resolved. ``repo`` and ``project_id`` are compared as plain strings.
- **No model call, no network call, no environment read.** ``httpx``,
  ``requests``, ``LLMClient``, ``LLMClientConfig``,
  ``load_llm_client_config_from_env`` and ``GitHubClient`` are not imported, so
  no code path here can construct one.
- **No clock.** ``generated_at`` and ``approved_at`` are *parsed* when supplied
  and are never produced here. There is no "now", no default timestamp, and no
  staleness comparison.
- **No CLI behavior.** Importing this package adds no command and no option.

The approval sits in a **wrapper around an untouched ``L1Plan`` snapshot**
(design §3.2). ``L1Plan`` is the shape a *planner* produces, and one of the two
planners is a model; every field on it is a field an adversarial model could try
to fill in. So approval, provenance, and identity live here, outside the plan,
and :class:`ApprovedL1PlanArtifact` additionally rejects any field inside
``plan`` that ``L1Plan`` does not declare — a payload carrying ``plan.approval``
is an attempted forgery and is **rejected**, never stripped and accepted
(design §3.6). ``L1Plan`` itself is neither modified nor extended by this module.

Approval is never inferred (design §3.6/§4.2). Not from an artifact existing,
not from it parsing, not from an ``approval`` key merely being present, and not
from ``Automation Authorization`` text in an issue or in plan prose — that
section is a heading anyone who can edit an issue can write, and it grants
nothing. Approval requires a non-blank ``approved_by``, a parseable
``approved_at``, an ``approval_text`` equal to :data:`REQUIRED_APPROVAL_TEXT`
**exactly**, and ``source`` from a closed enum whose only permitted value is
``"manual"``.

Every model is ``extra="forbid"``, and the identity fields are compared with
**exact** string equality — no normalization, no case folding, no prefix
matching (design §3.5).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, model_validator

from ai_dev_orchestrator.plan.models import L1Plan


class ApprovedPlanError(Exception):
    """Base class for approved-plan handoff parsing and validation errors.

    Messages name the *category* of failure and the field that failed. They
    never echo the artifact text, plan prose, or any supplied value.
    """


class ApprovedPlanParseError(ApprovedPlanError):
    """The text was not exactly one strict JSON object."""


class ApprovedPlanValidationError(ApprovedPlanError):
    """The decoded object failed :class:`ApprovedL1PlanArtifact` validation."""


# The exact sentence a human must write to approve a plan for L2. Compared with
# ``==`` — a paraphrase, a different case, or extra whitespace is not approval.
REQUIRED_APPROVAL_TEXT = "I approve this L1 plan for L2 implementation"

# Characters that must never appear in a bare endpoint host. Their presence
# means the value is a URL, a path, or carries userinfo (which can be a
# credential) rather than the host-only value Phase 4J produces.
_UNSAFE_HOST_CHARS = ("/", "?", "#", "@")


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


class PlanApproval(_Strict):
    """A human's explicit approval of one specific plan snapshot (design §3.6).

    Every field is required and none has a default: there is no way to construct
    an approval by omission. ``source`` is a closed enum whose only permitted
    value today is ``"manual"``, so a future automated source has to be added
    deliberately rather than slipping in as an unrecognized string.

    A model may never populate any field here. The orchestrator does not write
    this block either — writing it is the approval act, and it is a human's.
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
        if value != REQUIRED_APPROVAL_TEXT:
            raise ValueError(
                "approval_text must match the required approval phrase exactly; "
                "a paraphrase is not approval."
            )
        return value


class L1PlanProvenance(_Strict):
    """How the wrapped plan was produced, and what it was produced for.

    This is the Phase 4H §9.1 / Phase 4J ``build_real_model_provenance`` shape,
    typed. ``endpoint_host`` is host-only and is validated for **shape** alone —
    reachability is never checked, no DNS lookup or connection is made, and the
    value is never parsed as a URL here. ``generated_at`` is optional and is
    only ever *parsed*: nothing in this module produces a timestamp.

    An API key, a base URL, a prompt, or a completion has no field here, so a
    payload carrying one is rejected as an extra rather than being stored.
    """

    engine: str
    operation: str | None = None
    real_call: bool
    model: str | None = None
    endpoint_host: str | None = None
    generated_at: datetime | None = None
    project_id: str
    repo: str
    issue_number: int
    title: str

    @field_validator("engine", "project_id", "title")
    @classmethod
    def _not_blank(cls, value: str, info) -> str:
        return _require_non_blank(value, info.field_name)

    @field_validator("operation", "model")
    @classmethod
    def _optional_not_blank(cls, value: str | None, info) -> str | None:
        if value is None:
            return None
        return _require_non_blank(value, info.field_name)

    @field_validator("endpoint_host")
    @classmethod
    def _endpoint_host_is_bare(cls, value: str | None) -> str | None:
        if value is None:
            return None
        # Nothing is stripped, trimmed, or rewritten: an unsafe host is rejected
        # rather than sanitized, so a credential-bearing value surfaces instead
        # of being silently reduced to something that looks clean.
        value = _require_non_blank(value, "endpoint_host")
        present = [char for char in _UNSAFE_HOST_CHARS if char in value]
        if present:
            raise ValueError(
                "endpoint_host must be a bare host (optionally 'host:port') and "
                "must not contain: " + ", ".join(repr(char) for char in present) + "."
            )
        return value

    @field_validator("repo")
    @classmethod
    def _repo_valid(cls, value: str) -> str:
        return _require_owner_repo(value)

    @field_validator("issue_number")
    @classmethod
    def _issue_number_positive(cls, value: int) -> int:
        return _require_positive_issue_number(value)


class ApprovedL1PlanArtifact(_Strict):
    """An ``L1Plan`` snapshot, its provenance, and a human's approval of it.

    The ``plan`` field is a **snapshot**, not a reference (design §3.3): it
    carries the plan as it stood when the human read it, so there is no second
    lookup that could return different text.

    Beyond the per-model checks, the wrapper enforces the design's cross-field
    rules:

    - **No unknown field inside ``plan``.** ``L1Plan`` itself is unmodified and
      still tolerant of extras; the wrapper is not. A ``plan.approval`` key is a
      forgery attempt, and every other nested value ``L1Plan`` declares is a
      list of strings, so this check covers the whole plan shape.
    - **Exact identity matching** across the wrapper, the provenance, and the
      plan (design §3.5). String equality only — no normalization, no case
      folding, no prefix or glob matching. The failure this prevents is a plan
      approved for one project/issue being carried into another.
    - **``automation_level == "L1"`` and ``requires_human_approval is True``,
      checked explicitly** even though ``L1Plan`` already guarantees both
      (design §4.1). A downstream guard must not depend on an upstream invariant
      staying true forever, and a plan claiming L2 is corrupt or hostile — not
      more authorized.

    Constructing this model never means anything may be *done*. Phase 5B ships
    no consumer, and L2 remains unbuilt.
    """

    approval: PlanApproval
    plan_provenance: L1PlanProvenance
    plan: L1Plan
    project_id: str
    repo: str
    issue_number: int

    @model_validator(mode="before")
    @classmethod
    def _reject_unknown_plan_fields(cls, data: object) -> object:
        """Reject any key inside ``plan`` that ``L1Plan`` does not declare.

        ``L1Plan`` is left exactly as Phase 4B defined it; this is a wrapper-side
        strictness so that a forged ``plan.approval`` (or any other injected
        field) fails the artifact instead of being silently dropped.
        """
        if isinstance(data, Mapping):
            plan = data.get("plan")
            if isinstance(plan, Mapping):
                unexpected = sorted(set(plan) - set(L1Plan.model_fields))
                if unexpected:
                    raise ValueError(
                        "plan must contain only L1Plan fields; unexpected: "
                        + ", ".join(unexpected)
                        + ". Approval never lives inside the plan."
                    )
        return data

    @field_validator("project_id")
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
    def _identity_and_level_match(self) -> ApprovedL1PlanArtifact:
        if self.project_id != self.plan_provenance.project_id:
            raise ValueError(
                "project_id does not match plan_provenance.project_id exactly."
            )
        if self.repo != self.plan_provenance.repo:
            raise ValueError("repo does not match plan_provenance.repo exactly.")
        if self.issue_number != self.plan_provenance.issue_number:
            raise ValueError(
                "issue_number does not match plan_provenance.issue_number exactly."
            )
        if self.repo != self.plan.repo:
            raise ValueError("repo does not match plan.repo exactly.")
        if self.issue_number != self.plan.issue_number:
            raise ValueError("issue_number does not match plan.issue_number exactly.")
        if self.plan_provenance.title != self.plan.title:
            raise ValueError(
                "plan_provenance.title does not match plan.title exactly."
            )
        if self.plan.automation_level != "L1":
            raise ValueError(
                "plan.automation_level must be exactly 'L1'; a plan claiming a "
                "higher level is corrupt or forged, not more authorized."
            )
        if self.plan.requires_human_approval is not True:
            raise ValueError("plan.requires_human_approval must be True.")
        return self


def _summarize_validation_error(exc: ValidationError) -> str:
    """Render a ``ValidationError`` as field locations and messages only.

    Following the Phase 4L precedent, failures are loud about *category* and
    quiet about *content*: the supplied values are never echoed, because an
    artifact can carry plan prose and provenance an operator may not want
    surfaced.
    """
    parts = []
    for error in exc.errors():
        location = ".".join(str(item) for item in error["loc"]) or "(root)"
        parts.append(f"{location}: {error['msg']}")
    return "; ".join(parts)


def parse_approved_l1_plan_artifact(text: str) -> ApprovedL1PlanArtifact:
    """Parse strict-JSON artifact text into a validated wrapper.

    Pure function. It loads no file, reads no environment variable, touches no
    workspace, calls no model, opens no socket, runs no command, and logs or
    prints nothing. It is handed the text; obtaining that text is the caller's
    problem and is not implemented in this phase.

    Strict in the Phase 4F sense — it **rejects rather than repairs**. The text
    must be exactly one JSON object: surrounding whitespace is tolerated, but
    markdown fences, prose before or after the object, arrays, strings, numbers,
    booleans, and ``null`` all fail. Unknown fields are never stripped and
    missing fields are never inferred.

    A successful parse means the artifact is **well-formed and carries a valid
    approval**. It does not authorize anything: nothing in this repository
    consumes the result, and L2 is not built.

    Raises:
        ApprovedPlanParseError: ``text`` is not exactly one strict JSON object.
        ApprovedPlanValidationError: the object failed
            :class:`ApprovedL1PlanArtifact` validation — a missing or malformed
            approval block, an extra field, an identity mismatch, or a plan that
            is not an unescalated L1 plan.
    """
    if not isinstance(text, str):
        raise ApprovedPlanParseError("approved plan artifact text must be a string.")

    stripped = text.strip()
    if not stripped:
        raise ApprovedPlanParseError("approved plan artifact text was empty.")
    if not (stripped.startswith("{") and stripped.endswith("}")):
        raise ApprovedPlanParseError(
            "approved plan artifact text must be exactly one JSON object with no "
            "markdown fences, prose, or other content around it."
        )

    try:
        decoded = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ApprovedPlanParseError(
            f"approved plan artifact text is not valid JSON: {exc}"
        ) from exc

    if not isinstance(decoded, dict):
        raise ApprovedPlanParseError(
            "approved plan artifact text must be a JSON object, not an array, "
            "string, number, boolean, or null."
        )

    try:
        return ApprovedL1PlanArtifact.model_validate(decoded)
    except ValidationError as exc:
        raise ApprovedPlanValidationError(
            "approved plan artifact failed validation: "
            + _summarize_validation_error(exc)
        ) from exc
