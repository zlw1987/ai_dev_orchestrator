"""DL-4B S3 — mirror readers for the bytes the authority identity handles.

The authority identity A never imports a frozen harness: importing
``ai_dev_orchestrator.file_editing`` or ``ai_dev_orchestrator.diff_proposal``
loads the Git adapter, ``subprocess``, the LLM client and ``httpx``. So A reads
the three documents it must bind with **mirror readers** that restate exactly
the fields it needs, and a test pins each restatement to the shipped model
(the DL-4A pattern for ``verification-result.v1``):

```text
approved-diff-proposal.v2   the human-approved artifact (5F2C input). What A binds:
                            the one change (path, modify, pre/post image digests),
                            the DiffEditApproval block and the identity tuple
workspace-write-result.v1   the 5F2C report, received as an EXECUTION CLAIM (FD-15).
                            What A binds: target path, change type, sizes,
                            approved_by / approved_at and the identity tuple
project config (YAML)       the config bytes X receives. What A checks: the write,
                            verification and review opt-ins, the workspace root and
                            the project identity
review-command stdout       (S4) what `l2-review-approved-file-edit` prints, received
                            as an EXECUTION CLAIM: a `review-packet.v5` embedding the
                            `verification-result.v1` (exit 0), or the bare report with
                            outcome `verification-failed` (exit 2) or
                            `workspace-state-untrusted` (exit 3). What A binds: the
                            shape, the outcome the report's own facts support, the
                            target path and size, approved_by / approved_at and the
                            identity tuple
```

Every reader is strict and **rejects, never repairs**: UTF-8 without a BOM,
exactly one JSON object, no duplicate key, no non-standard constant, exact
field sets where the shipped model has no default. A reader proves only that
the bytes *say* something. That an approved artifact is fully valid is 5F2C's
own check when X runs it; that a write happened is decided by A's
observations (FD-18), never by a claim. Messages name a category and a field,
never a value.

Pure: no file, environment, network, subprocess or harness access.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime

import yaml
from pydantic import ValidationError

from ai_dev_orchestrator.control_plane.attestation_v2 import REQUIRED_EXACT_DIFF_APPROVAL_TEXT
from ai_dev_orchestrator.control_plane.authority import (
    VERIFICATION_RESULT_FIELDS,
    VERIFICATION_RESULT_MODE,
    VERIFICATION_RESULT_SCHEMA_VERSION,
    VERIFICATION_TRUST_FIELDS,
)
from ai_dev_orchestrator.control_plane.integration_records import REVIEW_CLAIM_OUTCOMES
from ai_dev_orchestrator.models import ProjectConfig

#: Fixed bounds on what A reads. Code constants, never configuration.
MAX_APPROVED_DIFF_BYTES = 2 * 1024 * 1024
MAX_PROJECT_CONFIG_BYTES = 256 * 1024
MAX_WRITE_CLAIM_BYTES = 4 * 1024 * 1024
#: S4: the review command's stdout. A packet embeds the bounded, redacted
#: verification output and the review; DL-4A's evidence bound applies.
MAX_REVIEW_CLAIM_BYTES = 16 * 1024 * 1024

APPROVED_DIFF_SCHEMA_VERSION = "approved-diff-proposal.v2"
APPROVED_DIFF_MODE = "file-edit-approval-only"
DIFF_PROPOSAL_SCHEMA_VERSION = "diff-proposal.v2"
WRITE_RESULT_SCHEMA_VERSION = "workspace-write-result.v1"
WRITE_RESULT_MODE = "controlled-single-file-modify"
WRITE_RESULT_OUTCOME = "written-and-verified"

#: The shipped models' field sets, restated. Each is pinned by a test.
APPROVED_DIFF_FIELDS = frozenset({
    "schema_version", "mode", "approval", "diff_proposal", "project_id", "repo",
    "issue_number", "title", "next_authorization_required",
})
DIFF_EDIT_APPROVAL_FIELDS = frozenset({"approved_by", "approved_at", "approval_text", "source"})
DIFF_PROPOSAL_FIELDS = frozenset({
    "schema_version", "mode", "provenance", "approved_plan", "patch_proposal", "changes",
    "omitted_paths", "assumptions", "risks", "open_questions", "source_contents_read",
    "diffs_generated", "files_edited", "commands_run", "applies_cleanly_checked",
    "requires_human_review", "next_authorization_required",
})
DIFF_PROPOSAL_REQUIRED = frozenset({
    "schema_version", "mode", "provenance", "approved_plan", "changes", "source_contents_read",
    "diffs_generated", "files_edited", "commands_run", "applies_cleanly_checked",
    "requires_human_review", "next_authorization_required",
})
DIFF_CHANGE_FIELDS = frozenset({
    "path", "change_type", "unified_diff", "pre_image_sha256", "post_image_sha256", "rationale",
    "risks", "requires_human_review",
})
DIFF_CHANGE_REQUIRED = DIFF_CHANGE_FIELDS - {"risks"}
APPROVED_PLAN_FIELDS = frozenset({"approval", "plan_provenance", "plan", "project_id", "repo", "issue_number"})
WRITE_RESULT_FIELDS = frozenset({
    "schema_version", "mode", "outcome", "project_id", "repo", "issue_number", "title",
    "approved_by", "approved_at", "target", "files_edited", "checks", "exclusions",
    "operational_files", "git", "single_writer_contract", "next_step",
})
WRITE_TARGET_FIELDS = frozenset({"path", "change_type", "line_ending", "pre_image_bytes", "post_image_bytes"})
#: S4: the shipped 5F2D target block and the 5F2E packet, restated (pinned by test).
VERIFICATION_TARGET_FIELDS = frozenset({
    "path", "change_type", "post_image_verified_before_execution", "post_image_bytes",
})
REVIEW_PACKET_SCHEMA_VERSION = "review-packet.v5"
REVIEW_PACKET_MODE = "controlled-review"
REVIEW_PACKET_FIELDS = frozenset({
    "schema_version", "mode", "project_id", "repo", "issue_number", "title", "approved_by",
    "approved_at", "target", "verification", "reviewer", "reviewer_supervision", "review",
    "transmission_boundary", "capability_boundaries", "human_decision_required", "next_step",
    "superseded_schema_version_note",
})
REVIEW_TARGET_FIELDS = frozenset({"path", "change_type"})
MODEL_REVIEW_FIELDS = frozenset({"verdict", "summary", "findings", "residual_risks", "human_notes"})
REVIEW_VERDICTS = ("approve", "changes_requested", "needs_human_review")

_HEX64 = re.compile(r"[0-9a-f]{64}")


class ClaimReadError(ValueError):
    """The bytes are not the document A requires. ``category`` names why."""

    def __init__(self, category: str, detail: str) -> None:
        self.category = category
        self.detail = detail
        super().__init__(f"{category}: {detail}")


@dataclass(frozen=True)
class Identity:
    """The identity tuple 5F2C binds a project config, an artifact and its report to."""

    project_id: str
    repo: str
    issue_number: int
    title: str


@dataclass(frozen=True)
class ApprovedDiffFacts:
    """What A binds from one ``approved-diff-proposal.v2``."""

    path: str
    pre_image_sha256: str
    post_image_sha256: str
    approved_by: str
    approved_at: datetime
    identity: Identity


@dataclass(frozen=True)
class WriteClaimFacts:
    """What a ``workspace-write-result.v1`` execution claim *says*. Not a fact."""

    path: str
    pre_image_bytes: int
    post_image_bytes: int
    approved_by: str
    approved_at: datetime
    identity: Identity


@dataclass(frozen=True)
class ReviewClaimFacts:
    """What the review command's stdout *says* (S4). Not a fact.

    ``shape`` is ``review-packet`` (exit 0), ``verification-failed`` (exit 2)
    or ``workspace-untrusted`` (exit 3). ``outcome`` is the outcome the
    verification report's own facts support, which must also be the one it
    states and the one its shape permits. ``verdict`` is the packet's claimed
    review verdict (``None`` for a bare report); S5 re-derives it.
    """

    shape: str
    outcome: str
    path: str
    post_image_bytes: int
    approved_by: str
    approved_at: datetime
    identity: Identity
    verdict: str | None


@dataclass(frozen=True)
class ProjectConfigFacts:
    """What A checks in the config bytes the execution identity receives."""

    project_id: str
    github_repo: str
    workspace_path: str
    workspace_write_enabled: bool
    controlled_verification_enabled: bool
    controlled_review_enabled: bool


def _no_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ClaimReadError("malformed", "the document repeats a JSON key.")
        result[key] = value
    return result


def _no_constant(name: str) -> object:
    raise ClaimReadError("malformed", "the document contains a non-standard JSON constant.")


def strict_json_object(data: object, limit: int, what: str) -> dict:
    """Exactly one JSON object in UTF-8 without a BOM, or a refusal."""
    if type(data) is not bytes:
        raise ClaimReadError("malformed", f"the {what} must be bytes.")
    if not data:
        raise ClaimReadError("empty", f"the {what} is empty.")
    if len(data) > limit:
        raise ClaimReadError("oversize", f"the {what} exceeds its size bound.")
    if data.startswith(b"\xef\xbb\xbf") or data.startswith((b"\xff\xfe", b"\xfe\xff")):
        raise ClaimReadError("malformed", f"the {what} starts with a byte-order mark.")
    try:
        document = json.loads(data.decode("utf-8"), object_pairs_hook=_no_duplicates,
                              parse_constant=_no_constant)
    except ClaimReadError:
        raise
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise ClaimReadError("malformed", f"the {what} is not one strict UTF-8 JSON document.") from None
    if not isinstance(document, dict):
        raise ClaimReadError("malformed", f"the {what} is not a JSON object.")
    return document


def _object(value: object, fields: frozenset[str], what: str, *, required: frozenset[str] | None = None) -> dict:
    if not isinstance(value, dict):
        raise ClaimReadError("malformed", f"{what} is not an object.")
    keys = set(value)
    if required is None:
        if keys != fields:
            raise ClaimReadError("malformed", f"{what} does not have exactly the shipped fields.")
    elif not required <= keys <= fields:
        raise ClaimReadError("malformed", f"{what} has a missing or unknown field.")
    return value


def _text(value: object, what: str) -> str:
    if type(value) is not str or not value.strip():
        raise ClaimReadError("malformed", f"{what} is not a non-blank string.")
    return value


def _positive(value: object, what: str) -> int:
    if type(value) is not int or value <= 0:
        raise ClaimReadError("malformed", f"{what} is not a positive integer.")
    return value


def _size(value: object, what: str) -> int:
    if type(value) is not int or value < 0:
        raise ClaimReadError("malformed", f"{what} is not a non-negative integer.")
    return value


def _digest(value: object, what: str) -> str:
    if type(value) is not str or _HEX64.fullmatch(value) is None:
        raise ClaimReadError("malformed", f"{what} is not a lowercase SHA-256 digest.")
    return value


def _instant(value: object, what: str) -> datetime:
    if type(value) is not str:
        raise ClaimReadError("malformed", f"{what} is not a timestamp.")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise ClaimReadError("malformed", f"{what} is not an ISO 8601 timestamp.") from None
    if parsed.tzinfo is None:
        raise ClaimReadError("malformed", f"{what} has no timezone.")
    return parsed


def _exactly(value: object, expected: object, what: str) -> None:
    if type(value) is not type(expected) or value != expected:
        raise ClaimReadError("malformed", f"{what} is not the shipped value.")


def _identity(document: dict, what: str) -> Identity:
    return Identity(
        project_id=_text(document.get("project_id"), f"{what}.project_id"),
        repo=_text(document.get("repo"), f"{what}.repo"),
        issue_number=_positive(document.get("issue_number"), f"{what}.issue_number"),
        title=_text(document.get("title"), f"{what}.title"),
    )


def read_approved_diff(data: bytes) -> ApprovedDiffFacts:
    """Bind one ``approved-diff-proposal.v2`` for A, or refuse.

    Required here, mirroring the 5F0/5F2C model: the schema and mode; a
    manual ``DiffEditApproval`` with the exact phrase; the identity tuple equal
    in the wrapper, the proposal's provenance and the approved plan; the
    proposal's ``diffs_generated``/``files_edited``/``commands_run``/
    ``applies_cleanly_checked``/``requires_human_review`` flags; and **exactly
    one** change, a ``modify`` with both image digests, whose path the approved
    plan lists as likely to change and does not forbid.
    """
    document = _object(strict_json_object(data, MAX_APPROVED_DIFF_BYTES, "approved diff artifact"),
                       APPROVED_DIFF_FIELDS, "the approved diff artifact")
    _exactly(document["schema_version"], APPROVED_DIFF_SCHEMA_VERSION, "schema_version")
    _exactly(document["mode"], APPROVED_DIFF_MODE, "mode")
    approval = _object(document["approval"], DIFF_EDIT_APPROVAL_FIELDS, "approval")
    _exactly(approval["approval_text"], REQUIRED_EXACT_DIFF_APPROVAL_TEXT, "approval.approval_text")
    _exactly(approval["source"], "manual", "approval.source")
    approved_by = _text(approval["approved_by"], "approval.approved_by")
    approved_at = _instant(approval["approved_at"], "approval.approved_at")
    _text(document["next_authorization_required"], "next_authorization_required")
    identity = _identity(document, "the artifact")

    proposal = _object(document["diff_proposal"], DIFF_PROPOSAL_FIELDS, "diff_proposal",
                       required=DIFF_PROPOSAL_REQUIRED)
    _exactly(proposal["schema_version"], DIFF_PROPOSAL_SCHEMA_VERSION, "diff_proposal.schema_version")
    for flag, expected in (("diffs_generated", True), ("files_edited", False), ("commands_run", False),
                           ("applies_cleanly_checked", False), ("requires_human_review", True)):
        _exactly(proposal[flag], expected, f"diff_proposal.{flag}")
    provenance = proposal["provenance"]
    if not isinstance(provenance, dict) or _identity(provenance, "diff_proposal.provenance") != identity:
        raise ClaimReadError("identity_mismatch", "the proposal's provenance is not the artifact's identity.")
    plan_wrapper = _object(proposal["approved_plan"], APPROVED_PLAN_FIELDS, "diff_proposal.approved_plan")
    plan = plan_wrapper["plan"]
    if not isinstance(plan, dict):
        raise ClaimReadError("malformed", "diff_proposal.approved_plan.plan is not an object.")
    if (
        plan_wrapper["project_id"], plan_wrapper["repo"], plan_wrapper["issue_number"], plan.get("title"),
    ) != (identity.project_id, identity.repo, identity.issue_number, identity.title) or (
        type(plan_wrapper["issue_number"]) is not int
    ):
        raise ClaimReadError("identity_mismatch", "the approved plan is not the artifact's identity.")
    if plan.get("automation_level", "L1") != "L1" or plan.get("requires_human_approval", True) is not True:
        raise ClaimReadError("malformed", "the approved plan is not an L1 plan requiring human approval.")

    changes = proposal["changes"]
    if not isinstance(changes, list) or len(changes) != 1:
        raise ClaimReadError("not_one_change", "the artifact does not approve exactly one change.")
    change = _object(changes[0], DIFF_CHANGE_FIELDS, "the change", required=DIFF_CHANGE_REQUIRED)
    _exactly(change["change_type"], "modify", "the change's change_type")
    _exactly(change["requires_human_review"], True, "the change's requires_human_review")
    path = _text(change["path"], "the change's path")
    _text(change["unified_diff"], "the change's unified_diff")
    likely = plan.get("files_likely_to_change", [])
    forbidden = plan.get("files_forbidden_or_out_of_scope", [])
    if not isinstance(likely, list) or not isinstance(forbidden, list) or path not in likely or path in forbidden:
        raise ClaimReadError("out_of_plan_scope", "the change's path is outside the approved plan's scope.")
    return ApprovedDiffFacts(
        path=path,
        pre_image_sha256=_digest(change["pre_image_sha256"], "the change's pre_image_sha256"),
        post_image_sha256=_digest(change["post_image_sha256"], "the change's post_image_sha256"),
        approved_by=approved_by,
        approved_at=approved_at,
        identity=identity,
    )


def read_write_claim(data: bytes) -> WriteClaimFacts:
    """Classify stdout bytes as the ``workspace-write-result.v1`` shape, or
    refuse. What it returns is what the execution identity **claims**."""
    document = _object(strict_json_object(data, MAX_WRITE_CLAIM_BYTES, "write claim"),
                       WRITE_RESULT_FIELDS, "the write claim")
    _exactly(document["schema_version"], WRITE_RESULT_SCHEMA_VERSION, "schema_version")
    _exactly(document["mode"], WRITE_RESULT_MODE, "mode")
    _exactly(document["outcome"], WRITE_RESULT_OUTCOME, "outcome")
    _exactly(document["files_edited"], 1, "files_edited")
    for block, expected in (("checks", True), ("exclusions", False)):
        values = document[block]
        if not isinstance(values, dict) or not values or any(v is not expected for v in values.values()):
            raise ClaimReadError("malformed", f"{block} is not the shipped all-{str(expected).lower()} block.")
    for block in ("operational_files", "git"):
        if not isinstance(document[block], dict):
            raise ClaimReadError("malformed", f"{block} is not an object.")
    target = _object(document["target"], WRITE_TARGET_FIELDS, "target")
    _exactly(target["change_type"], "modify", "target.change_type")
    if target["line_ending"] not in ("lf", "crlf"):
        raise ClaimReadError("malformed", "target.line_ending is not a shipped value.")
    return WriteClaimFacts(
        path=_text(target["path"], "target.path"),
        pre_image_bytes=_size(target["pre_image_bytes"], "target.pre_image_bytes"),
        post_image_bytes=_size(target["post_image_bytes"], "target.post_image_bytes"),
        approved_by=_text(document["approved_by"], "approved_by"),
        approved_at=_instant(document["approved_at"], "approved_at"),
        identity=_identity(document, "the write claim"),
    )


def _verification_report(value: object, what: str) -> tuple[str, str, int, str, datetime, Identity]:
    """One ``verification-result.v1`` object: its supported outcome, target
    path and size, approval and identity. The outcome is re-derived from the
    report's own facts exactly as 5F2D derives it (DL-4A's rule: an untrusted
    workspace outranks a failed run) and must equal the stated one."""
    document = _object(value, VERIFICATION_RESULT_FIELDS, what)
    _exactly(document["schema_version"], VERIFICATION_RESULT_SCHEMA_VERSION, f"{what}.schema_version")
    _exactly(document["mode"], VERIFICATION_RESULT_MODE, f"{what}.mode")
    outcome = document["outcome"]
    if type(outcome) is not str or outcome not in REVIEW_CLAIM_OUTCOMES.values():
        raise ClaimReadError("malformed", f"{what}.outcome is not a shipped outcome.")
    execution = document["execution"]
    post = document["workspace_postcondition"]
    if not isinstance(execution, dict) or type(execution.get("passed")) is not bool:
        raise ClaimReadError("malformed", f"{what}.execution has no boolean passed.")
    if not isinstance(post, dict) or any(type(post.get(f)) is not bool for f in VERIFICATION_TRUST_FIELDS):
        raise ClaimReadError("malformed", f"{what}.workspace_postcondition has no boolean trust facts.")
    if not all(post[f] for f in VERIFICATION_TRUST_FIELDS):
        derived = "workspace-state-untrusted"
    elif execution["passed"]:
        derived = "verified"
    else:
        derived = "verification-failed"
    if derived != outcome:
        raise ClaimReadError("outcome_unsupported", f"{what} states an outcome its own facts do not support.")
    target = _object(document["target"], VERIFICATION_TARGET_FIELDS, f"{what}.target")
    _exactly(target["change_type"], "modify", f"{what}.target.change_type")
    _exactly(target["post_image_verified_before_execution"], True,
             f"{what}.target.post_image_verified_before_execution")
    for block in ("command", "output", "workspace_precondition", "capability_boundaries"):
        if not isinstance(document[block], dict):
            raise ClaimReadError("malformed", f"{what}.{block} is not an object.")
    for text in ("single_actor_contract", "next_step"):
        _text(document[text], f"{what}.{text}")
    return (
        outcome,
        _text(target["path"], f"{what}.target.path"),
        _size(target["post_image_bytes"], f"{what}.target.post_image_bytes"),
        _text(document["approved_by"], f"{what}.approved_by"),
        _instant(document["approved_at"], f"{what}.approved_at"),
        _identity(document, what),
    )


def read_review_claim(data: bytes) -> ReviewClaimFacts:
    """Classify the review command's stdout bytes by their shape, or refuse.

    The exit code is not an input: the bytes alone decide. Accepted shapes,
    each exactly what the frozen command prints:

    - ``review-packet.v5`` (exit 0). Its embedded verification must support
      ``verified``; its own identity, approval and target must be the embedded
      report's; its ``review`` must carry a shipped verdict;
    - a bare ``verification-result.v1`` supporting ``verification-failed``
      (exit 2) or ``workspace-state-untrusted`` (exit 3).

    Anything else is refused: a bare ``verified`` report (the command never
    prints one), a contradiction inside a packet, an unsupported outcome, a
    second document, or empty stdout (exits 1 and 4 print nothing on stdout).
    What it returns is what the execution identity **claims**.
    """
    document = strict_json_object(data, MAX_REVIEW_CLAIM_BYTES, "review claim")
    schema = document.get("schema_version")
    if schema == VERIFICATION_RESULT_SCHEMA_VERSION:
        outcome, path, size, approved_by, approved_at, identity = _verification_report(
            document, "the verification report")
        if outcome == "verified":
            raise ClaimReadError(
                "unexpected_shape", "a bare verified report is not a shape the review command prints."
            )
        shape = next(name for name, value in REVIEW_CLAIM_OUTCOMES.items() if value == outcome)
        return ReviewClaimFacts(shape, outcome, path, size, approved_by, approved_at, identity, None)
    if schema != REVIEW_PACKET_SCHEMA_VERSION:
        raise ClaimReadError("unexpected_shape", "the review claim is neither a review packet nor a report.")
    packet = _object(document, REVIEW_PACKET_FIELDS, "the review packet")
    _exactly(packet["mode"], REVIEW_PACKET_MODE, "mode")
    _exactly(packet["human_decision_required"], True, "human_decision_required")
    identity = _identity(packet, "the review packet")
    approved_by = _text(packet["approved_by"], "approved_by")
    approved_at = _instant(packet["approved_at"], "approved_at")
    target = _object(packet["target"], REVIEW_TARGET_FIELDS, "target")
    _exactly(target["change_type"], "modify", "target.change_type")
    path = _text(target["path"], "target.path")
    outcome, v_path, size, v_by, v_at, v_identity = _verification_report(
        packet["verification"], "verification")
    if outcome != "verified":
        raise ClaimReadError("contradictory", "a review packet embeds a verification that did not pass.")
    if (v_path, v_by, v_at, v_identity) != (path, approved_by, approved_at, identity):
        raise ClaimReadError(
            "contradictory", "the packet's target, approval or identity is not its verification's."
        )
    review = _object(packet["review"], MODEL_REVIEW_FIELDS, "review")
    verdict = review["verdict"]
    if type(verdict) is not str or verdict not in REVIEW_VERDICTS:
        raise ClaimReadError("malformed", "review.verdict is not a shipped verdict.")
    for block in ("reviewer", "reviewer_supervision", "transmission_boundary", "capability_boundaries"):
        if not isinstance(packet[block], dict):
            raise ClaimReadError("malformed", f"{block} is not an object.")
    _text(packet["next_step"], "next_step")
    if type(packet["superseded_schema_version_note"]) is not str:
        raise ClaimReadError("malformed", "superseded_schema_version_note is not a string.")
    return ReviewClaimFacts("review-packet", outcome, path, size, approved_by, approved_at, identity, verdict)


def read_project_config(data: bytes) -> ProjectConfigFacts:
    """Parse config bytes exactly as ``load_project_config`` parses a file's
    text (UTF-8, ``yaml.safe_load``, one mapping, ``ProjectConfig``)."""
    if type(data) is not bytes or not data:
        raise ClaimReadError("empty", "the project config is empty.")
    if len(data) > MAX_PROJECT_CONFIG_BYTES:
        raise ClaimReadError("oversize", "the project config exceeds its size bound.")
    try:
        loaded = yaml.safe_load(data.decode("utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError):
        raise ClaimReadError("malformed", "the project config is not UTF-8 YAML.") from None
    if not isinstance(loaded, dict):
        raise ClaimReadError("malformed", "the project config is not a YAML mapping.")
    try:
        config = ProjectConfig.model_validate(loaded)
    except ValidationError:
        raise ClaimReadError("malformed", "the project config does not validate.") from None
    return ProjectConfigFacts(
        project_id=config.project_id,
        github_repo=config.repo.github_repo,
        workspace_path=config.repo.workspace_path,
        workspace_write_enabled=config.workspace_write.enabled,
        controlled_verification_enabled=config.controlled_verification.enabled,
        controlled_review_enabled=config.controlled_review.enabled,
    )
