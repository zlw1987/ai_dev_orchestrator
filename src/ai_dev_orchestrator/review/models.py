"""Typed reviewer output models and a strict parser (Phase 5F2E).

This module owns the **model-controlled** half of the controlled reviewer slice:
the exact shape a reviewer reply must have, and the parser that either produces a
validated :class:`ModelReviewResult` or rejects the reply outright.

Two properties matter more than the schema itself.

**It rejects rather than repairs.** There is no second prompt, no "please fix
your JSON" retry, no fence stripping, no key renaming, no field coercion, and no
semantic merging of findings. A reply that is not exactly one strict JSON object
matching this schema is a reviewer failure, and a reviewer failure is reported to
a human rather than negotiated with the model. The existing
:class:`~ai_dev_orchestrator.llm.client.LLMClient` keeps its already-shipped
bounded *transport*-level retries; that is a property of the transport, not a
re-review, and this module adds nothing on top of it.

**No trusted field is ever read from model output.** The project id, repo, issue
number, title, target path, reviewer model, endpoint, verification outcome,
approval identity, branch, commit, PR, command, executable, patch and file
contents are either orchestrator-owned or absent entirely. ``extra="forbid"``
would already reject them as unknown keys; :data:`_TRUSTED_FIELDS` is checked
first anyway so that an injection attempt surfaces as *"the model tried to supply
a caller-controlled field"* rather than as a generic extra-key error.

The reviewer's verdict is **advisory**. Nothing here — and nothing downstream in
this phase — converts a finding into an edit, a patch, a command, a branch, a
commit, a push, or a PR. All three verdicts end at a human.
"""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, model_validator

# The closed enums. A severity or category outside them is a reviewer failure,
# never mapped onto a nearest neighbour.
ReviewVerdict = Literal["approve", "changes_requested", "needs_human_review"]
ReviewSeverity = Literal["blocker", "major", "minor", "nit"]
ReviewCategory = Literal[
    "correctness", "security", "testing", "scope", "maintainability", "other"
]

# The severities that make a change-request coherent. `changes_requested` must
# carry at least one of them, and `approve` must carry none.
BLOCKING_SEVERITIES: tuple[str, ...] = ("blocker", "major")

# Bounds, in the style of the existing artifact models: a single reply may not
# carry an unbounded amount of text through this parser. These are string-length
# and list-length checks — nothing is truncated, streamed, or summarized.
MAX_REVIEW_FINDINGS = 20
MAX_REVIEW_SUMMARY_CHARS = 4_000
MAX_REVIEW_MESSAGE_CHARS = 4_000
MAX_REVIEW_SUGGESTED_ACTION_CHARS = 2_000
MAX_REVIEW_NOTE_CHARS = 2_000
MAX_REVIEW_NOTES = 20

# Fields the orchestrator owns, or that have no place in a review at all. Their
# presence in a reply is treated as an injection attempt (Phase 4F precedent).
_TRUSTED_FIELDS = (
    "project_id",
    "repo",
    "issue_number",
    "title",
    "target_path",
    "path",
    "change_type",
    "model",
    "provider",
    "endpoint",
    "endpoint_host",
    "verification",
    "verification_outcome",
    "verification_passed",
    "approved_by",
    "approved_at",
    "approval",
    "approval_text",
    "branch",
    "commit",
    "push",
    "pr",
    "pull_request",
    "command",
    "executable",
    "args",
    "patch",
    "diff",
    "unified_diff",
    "file_contents",
    "new_file_contents",
    "replacement",
    "schema_version",
    "mode",
)

_REQUIRED_FIELDS = (
    "verdict",
    "summary",
    "findings",
    "residual_risks",
    "human_notes",
)


class ReviewError(Exception):
    """Base class for reviewer-stage failures.

    Messages name the failure **category** and the field that failed. They never
    echo the raw model response, the approved diff, the review prompt, an API
    key, a base URL, or an absolute path.
    """


class ReviewRefusedError(ReviewError):
    """Refused **before** the reviewer stage was reached.

    Raised by the project-config review gate. No environment value was read, no
    client was built, and no model was contacted.
    """


class ReviewerStageError(ReviewError):
    """The reviewer stage failed **after** verification had already passed.

    Scoped to AIDO's review stage: it repairs nothing, restores nothing, retries
    nothing, re-prompts nothing, writes no file into the target workspace,
    performs no Git mutation, and creates no branch, commit, push or PR. An
    operator may correct the reviewer configuration and run the same command
    again.

    That is deliberately **not** a claim about the whole invocation. The
    unsandboxed Phase 5F2D verification child has already run by this point. What
    is established about the workspace is what that passed verification
    established — the approved target's exact bytes, an unchanged HEAD object id,
    and a Git-visible dirty state of exactly that one unstaged path — and nothing
    outside Phase 5F2D's documented detection boundary is claimed.
    """


class ReviewerEnvironmentError(ReviewerStageError):
    """The LiteLLM environment configuration was missing or invalid."""


class ReviewerTransportError(ReviewerStageError):
    """The reviewer call failed under the existing LLM client's own policy."""


class ReviewParseError(ReviewerStageError):
    """The reply was not exactly one strict JSON object."""


class ReviewValidationError(ReviewerStageError):
    """The decoded object had wrong keys, wrong types, or an incoherent verdict."""


class _Strict(BaseModel):
    """Base model for **model-controlled** data: no extras, and no coercion.

    ``extra="forbid"`` alone was not strict enough. Pydantic's default lax mode
    still *converts* scalars, so a reply carrying ``"line": "12"`` was silently
    normalized to the integer ``12``, and ``12.0`` and ``true`` were likewise
    accepted as ``12`` and ``1``. That is exactly the "repair rather than reject"
    behavior this phase's contract forbids — quietly fixing up model output is
    how a schema stops being evidence of anything.

    ``strict=True`` makes the JSON types themselves part of the contract:
    validation happens through :meth:`model_validate_json`, where a JSON string
    is not an int, a JSON float is not an int, and a JSON boolean is not an int.
    Objects are still accepted for the nested finding model, and ``null`` is
    still accepted for the optional ``line``, so every intended valid reply
    continues to parse unchanged.

    This applies **only** to the model-controlled models here. The review packet
    is orchestrator-built from already-typed Python objects and keeps ordinary
    validation.
    """

    model_config = ConfigDict(extra="forbid", strict=True)


def _require_non_blank(value: str, field_name: str) -> str:
    if value is None or not value.strip():
        raise ValueError(f"{field_name} must not be empty or whitespace-only.")
    return value


def _require_max_chars(value: str, field_name: str, limit: int) -> str:
    if len(value) > limit:
        raise ValueError(f"{field_name} must be at most {limit} characters.")
    return value


class ReviewFinding(_Strict):
    """One reviewer finding about the one approved change.

    ``line`` is optional because a real review often has something to say that no
    single line owns — a missing test, a scope concern, an interaction between
    two hunks. When it *is* supplied it must be a positive line number; ``0`` and
    negatives are rejected rather than normalized.

    There is deliberately no field for a replacement, a patch, a suggested diff,
    a command, or a file path: ``suggested_action`` is **plain-language
    recommendation prose** for a human or a later, separately authorized fixer,
    and nothing in this repository executes or applies it.
    """

    severity: ReviewSeverity
    category: ReviewCategory
    line: int | None = None
    message: str
    suggested_action: str

    @field_validator("message")
    @classmethod
    def _message_ok(cls, value: str) -> str:
        return _require_max_chars(
            _require_non_blank(value, "message"), "message", MAX_REVIEW_MESSAGE_CHARS
        )

    @field_validator("suggested_action")
    @classmethod
    def _suggested_action_ok(cls, value: str) -> str:
        return _require_max_chars(
            _require_non_blank(value, "suggested_action"),
            "suggested_action",
            MAX_REVIEW_SUGGESTED_ACTION_CHARS,
        )

    @field_validator("line")
    @classmethod
    def _line_positive(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            raise ValueError("line must be a positive line number when supplied.")
        return value


class ModelReviewResult(_Strict):
    """The strict, validated reviewer reply.

    Beyond the per-field rules, two consistency rules make the verdict mean
    something rather than being an unrelated label stapled to a finding list:

    - ``changes_requested`` requires at least one ``blocker`` or ``major``
      finding — otherwise the reviewer is asking for changes it did not name;
    - ``approve`` must carry no ``blocker`` or ``major`` finding — otherwise the
      reviewer is approving something it called blocking.

    ``needs_human_review`` is unconstrained: it may carry findings or none, and
    it is the correct answer when the reviewer cannot decide. It is a **success**
    for this command, exactly like the other two verdicts.

    Duplicate findings are preserved as written. There is no semantic merging and
    no dedupe: collapsing two findings that happen to share a line is a judgement
    this phase does not make on a human's behalf.
    """

    verdict: ReviewVerdict
    summary: str
    findings: list[ReviewFinding]
    residual_risks: list[str]
    human_notes: list[str]

    @field_validator("summary")
    @classmethod
    def _summary_ok(cls, value: str) -> str:
        return _require_max_chars(
            _require_non_blank(value, "summary"), "summary", MAX_REVIEW_SUMMARY_CHARS
        )

    @field_validator("findings")
    @classmethod
    def _findings_bounded(cls, value: list[ReviewFinding]) -> list[ReviewFinding]:
        if len(value) > MAX_REVIEW_FINDINGS:
            raise ValueError(
                f"findings must contain at most {MAX_REVIEW_FINDINGS} entries; a "
                "longer list is rejected, never truncated."
            )
        return value

    @field_validator("residual_risks", "human_notes")
    @classmethod
    def _notes_ok(cls, value: list[str], info) -> list[str]:
        name = info.field_name
        if len(value) > MAX_REVIEW_NOTES:
            raise ValueError(f"{name} must contain at most {MAX_REVIEW_NOTES} entries.")
        for item in value:
            _require_max_chars(
                _require_non_blank(item, f"{name} entries"),
                f"{name} entries",
                MAX_REVIEW_NOTE_CHARS,
            )
        return value

    @model_validator(mode="after")
    def _verdict_matches_findings(self) -> ModelReviewResult:
        blocking = [
            finding
            for finding in self.findings
            if finding.severity in BLOCKING_SEVERITIES
        ]
        if self.verdict == "changes_requested" and not blocking:
            raise ValueError(
                "verdict 'changes_requested' requires at least one 'blocker' or "
                "'major' finding; a change request must name what blocks it."
            )
        if self.verdict == "approve" and blocking:
            raise ValueError(
                "verdict 'approve' must not carry a 'blocker' or 'major' finding; "
                "approving something the reviewer called blocking is incoherent "
                "and is rejected rather than downgraded."
            )
        return self


def _summarize_validation_error(exc: ValidationError) -> str:
    """Render a ``ValidationError`` as field locations and messages only.

    Following the Phase 4L/5B/5F0 precedent, failures are loud about *category*
    and quiet about *content*: the supplied values are never echoed. That matters
    especially here, where the rejected object is model output that may quote the
    reviewed source back at us.
    """
    parts = []
    for error in exc.errors():
        location = ".".join(str(item) for item in error["loc"]) or "(root)"
        parts.append(f"{location}: {error['msg']}")
    return "; ".join(parts)


def parse_model_review_response(text: str) -> ModelReviewResult:
    """Parse a strict-JSON reviewer completion into a validated result.

    Pure function: no file IO, no environment read, no network, no client, and no
    workspace access. It is handed the completion text and either returns a
    validated :class:`ModelReviewResult` or raises.

    Strict in the Phase 4F sense — it **rejects rather than repairs**. The text
    must be exactly one JSON object: surrounding whitespace is tolerated, but a
    markdown fence, prose before or after the object, an array, a scalar, a
    missing key, an extra key, or a caller-controlled key all fail. There is no
    second prompt and no parser repair.

    Raises:
        ReviewParseError: ``text`` was not exactly one strict JSON object.
        ReviewValidationError: the object supplied a caller-controlled field, had
            unexpected or missing keys, failed a field rule, exceeded a bound, or
            carried a verdict its findings contradict.
    """
    if not isinstance(text, str):
        raise ReviewParseError("reviewer output must be a string.")

    stripped = text.strip()
    if not stripped:
        raise ReviewParseError("reviewer output was empty.")
    if not (stripped.startswith("{") and stripped.endswith("}")):
        raise ReviewParseError(
            "reviewer output must be exactly one JSON object with no markdown "
            "fences, prose, or other content around it."
        )

    try:
        decoded = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ReviewParseError(f"reviewer output is not valid JSON: {exc}") from exc

    if not isinstance(decoded, dict):
        raise ReviewParseError(
            "reviewer output must be a JSON object, not an array, string, number, "
            "boolean, or null."
        )

    keys = set(decoded)

    trusted_present = [name for name in _TRUSTED_FIELDS if name in keys]
    if trusted_present:
        raise ReviewValidationError(
            "reviewer output must not supply orchestrator-controlled field(s): "
            + ", ".join(trusted_present)
            + ". Identity, verification facts, and any branch/commit/push/PR or "
            "command/patch field are owned by the orchestrator or absent entirely."
        )

    unexpected = sorted(keys - set(_REQUIRED_FIELDS))
    if unexpected:
        raise ReviewValidationError(
            "reviewer output has unexpected top-level key(s): "
            + ", ".join(unexpected)
            + "."
        )

    missing = [name for name in _REQUIRED_FIELDS if name not in keys]
    if missing:
        raise ReviewValidationError(
            "reviewer output is missing required field(s): " + ", ".join(missing) + "."
        )

    # Validated from the JSON text, not from the decoded dict, so that
    # ``strict=True`` compares against the **JSON** types the model actually
    # emitted: a quoted "12" stays a string and is rejected, rather than being
    # coerced into the integer the reply failed to send. The decoded dict above
    # is used only for the key checks, which need no type information.
    try:
        return ModelReviewResult.model_validate_json(stripped)
    except ValidationError as exc:
        raise ReviewValidationError(
            "reviewer output failed validation: " + _summarize_validation_error(exc)
        ) from exc
