"""The human-facing review packet (``review-packet.v1``) — Phase 5F2E.

One structured artifact per successful controlled review, assembled from four
sources that are kept strictly separate:

- **orchestrator-owned identity**, taken from the validated Phase 5F2D
  verification report (which was itself built from the project config and an
  approval matched against it exactly);
- **the embedded verification result**, preserved as the accepted typed
  :class:`~ai_dev_orchestrator.verification.VerificationResultReport` rather than
  summarized into something weaker;
- **reviewer provenance**, built from the project config and the validated
  connection settings — provider, exact configured model, endpoint **host only**,
  and token usage if the endpoint reported any;
- **the model's own review**, and nothing else the model said.

No field here is populated from model output except
:attr:`ReviewPacket.review`. The model cannot name the project, the repo, the
issue, the target path, the model, the endpoint, the verification outcome, or the
approver: those are orchestrator-owned, and the strict parser rejects a reply
that tries to supply them.

Deliberately absent, because there is no field for any of them: the configured
workspace path, any absolute path (the verification executable's and Git's
included), the endpoint base URL, the API key, any header, any environment value,
the approval text, the raw input artifact, the raw model response, and any
unrelated source file.

The approved unified diff is deliberately **not** re-echoed into the packet
either. It already exists in the artifact the operator approved and passed in;
copying it into the output would duplicate source text into another file for no
review benefit.

Truthful capability scoping
---------------------------

This command really does two consequential things, and the packet says both
plainly rather than hiding behind a blanket negative:

- the review stage **makes a real model/network call**;
- the verification stage earlier in the same invocation **executed
  repository-controlled code**, unsandboxed.

So there is no ``network_called: false`` and no ``commands_run: false`` here.
Every AIDO-owned negative claim carries an ``orchestrator_`` prefix and is scoped
to a *stage* where the stage matters, and the child-process facts stay where they
were honestly established — inside the embedded verification report.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from ai_dev_orchestrator.llm.models import LLMUsage
from ai_dev_orchestrator.review.models import (
    ModelReviewResult,
    ReviewerStageError,
    _summarize_validation_error,
)
from ai_dev_orchestrator.review.request import REDACTION_NOTE, ReviewContext
from ai_dev_orchestrator.verification import VerificationResultReport

REVIEW_PACKET_SCHEMA_VERSION = "review-packet.v1"
REVIEW_PACKET_MODE = "controlled-review"

# What the reviewer transport policy actually is, stated exactly. One *semantic*
# reviewer request is made. The existing LLM client keeps its already-shipped
# bounded transport-level retries for timeouts, connection failures and 429/5xx;
# that is a property of the transport and is not a re-review. No application-level
# retry, re-prompt, or second reviewer exists in this phase.
REVIEWER_REQUEST_POLICY = (
    "One semantic reviewer request was issued. The existing LLM client's "
    "already-shipped bounded transport-level retries (timeout, connection "
    "failure, HTTP 429/5xx) still apply and are a transport property, not a "
    "re-review. There is no application-level retry, no second prompt, no "
    "'fix your JSON' round trip, and no second reviewer."
)

# The whole point of the phase, in the artifact itself.
REVIEW_HUMAN_DECISION = (
    "A reviewer verdict is ADVISORY and is not executable authority. All three "
    "verdicts — approve, changes_requested, needs_human_review — end here, with a "
    "human. AIDO did not and cannot act on the findings: there is no fixer, no "
    "second reviewer, no re-review, no patch generation from findings, no file "
    "edit, no revert or restore, no branch, no commit, no push, and no PR. The "
    "approved single-file modification is left uncommitted in the working tree "
    "exactly as the writer and the verifier left it. The human decides what "
    "happens next."
)

# Pointer rather than restatement: the child-process facts are established in the
# verification report, and duplicating them here would invite drift.
VERIFICATION_CHILD_PROCESS_NOTE = (
    "The verification stage of this same invocation executed "
    "repository-controlled code that AIDO does not sandbox. What is and is not "
    "known about that child process — its filesystem, network, subprocess, Git "
    "and credential effects, and the fact that its descendants are not tracked "
    "and may still be running — is recorded in verification.capability_boundaries "
    "and verification.workspace_postcondition.detection_limits, and is not "
    "restated or weakened here."
)


class _Strict(BaseModel):
    """Base model that rejects unknown fields, so forged extras fail loudly."""

    model_config = ConfigDict(extra="forbid")


class ReviewTargetBlock(_Strict):
    """The one approved file this review was bound to.

    Repository-relative path only. There is no absolute path field and no content
    field, for the same reason the verification report has neither.
    """

    path: str
    change_type: Literal["modify"]


class ReviewerProvenanceBlock(_Strict):
    """Where the review came from. Safe fields only.

    ``endpoint_host`` is produced by the existing host-reduction helper, which
    drops the scheme, userinfo, path, query and fragment — showing *where* data
    went is a safety property, showing the credential is not. There is no
    ``base_url`` field, no ``api_key`` field, and no header field, so no code path
    can place one here.
    """

    provider: Literal["litellm"]
    model: str
    model_source: Literal["project_config.controlled_review.model"]
    endpoint_host: str
    operation: Literal["code-review"]
    real_call: Literal[True]
    semantic_requests: Literal[1]
    request_policy: str
    environment_default_model_used: Literal[False]
    cli_model_override_available: Literal[False]
    usage: LLMUsage | None


class ReviewTransmissionBoundary(_Strict):
    """Exactly what was and was not sent to the reviewer.

    The positive claims are ``Literal[True]`` because they are properties of the
    one prompt builder this phase has; the negative claims are ``Literal[False]``
    because that builder has no field, and no code path, capable of carrying
    them.

    ``review_context_redacted_before_transmission`` records that redaction ran.
    It does **not** claim the transmitted material is secret-free —
    ``redaction_note`` says so explicitly, and nothing here should be read as a
    guarantee.
    """

    approved_diff_sent_to_reviewer: Literal[True]
    approved_plan_context_sent_to_reviewer: Literal[True]
    verification_output_sent_redacted: Literal[True]
    review_context_redacted_before_transmission: Literal[True]

    full_target_file_sent_to_reviewer: Literal[False]
    unrelated_source_sent_to_reviewer: Literal[False]
    directory_listing_or_repository_tree_sent_to_reviewer: Literal[False]
    git_history_sent_to_reviewer: Literal[False]
    workspace_absolute_path_sent_to_reviewer: Literal[False]
    verification_executable_path_sent_to_reviewer: Literal[False]
    git_executable_path_sent_to_reviewer: Literal[False]
    api_key_sent_to_reviewer: Literal[False]
    endpoint_base_url_sent_to_reviewer: Literal[False]
    raw_environment_sent_to_reviewer: Literal[False]
    github_token_sent_to_reviewer: Literal[False]
    approval_text_sent_to_reviewer: Literal[False]
    raw_input_artifact_sent_to_reviewer: Literal[False]
    raw_unredacted_verification_bytes_sent_to_reviewer: Literal[False]

    redaction_count: int
    redaction_kinds: list[str]
    redaction_note: str


class ReviewCapabilityBoundaries(_Strict):
    """What AIDO did, and what it did not do — each scoped to AIDO.

    The two ``Literal[True]`` fields at the top are the honest admissions this
    phase owes a reader: it called a model over the network, and earlier in the
    same invocation it executed repository-controlled code. A blanket
    ``network_called: false`` or ``commands_run: false`` would be a lie about this
    command, so neither exists.

    Every negative claim is prefixed ``orchestrator_``, following the Phase
    5F2D-FU1 discipline, and several are scoped further to the review *stage* —
    ``orchestrator_files_written_by_review_stage`` is a claim about the reviewer,
    not about the verification child, which is not sandboxed and about which this
    block makes no claim at all.
    """

    orchestrator_model_called: Literal[True]
    orchestrator_network_called: Literal[True]
    orchestrator_repository_controlled_code_executed_by_verification_stage: Literal[
        True
    ]

    orchestrator_files_written_by_review_stage: Literal[False]
    orchestrator_workspace_read_by_review_stage: Literal[False]
    orchestrator_verification_rerun_after_review: Literal[False]
    orchestrator_fixer_invoked: Literal[False]
    orchestrator_second_reviewer_invoked: Literal[False]
    orchestrator_review_retry_or_reprompt_attempted: Literal[False]
    orchestrator_patch_generated_from_findings: Literal[False]
    orchestrator_file_edit_from_findings: Literal[False]
    orchestrator_automatic_repair_attempted: Literal[False]
    orchestrator_rollback_or_restore_performed: Literal[False]
    orchestrator_git_mutation_performed_by_review_stage: Literal[False]
    orchestrator_branch_created: Literal[False]
    orchestrator_committed: Literal[False]
    orchestrator_pushed: Literal[False]
    orchestrator_pr_created: Literal[False]
    orchestrator_github_accessed: Literal[False]
    orchestrator_shell_invoked: Literal[False]

    verification_child_process_note: str


class ReviewPacket(_Strict):
    """The structured, human-facing result of one controlled review.

    ``verification`` embeds the accepted typed verification result unchanged, so
    a reader gets the full, honest execution record — including its detection
    limits and child-process caveats — rather than a summary written by this
    phase.
    """

    schema_version: Literal[REVIEW_PACKET_SCHEMA_VERSION]  # type: ignore[valid-type]
    mode: Literal[REVIEW_PACKET_MODE]  # type: ignore[valid-type]
    project_id: str
    repo: str
    issue_number: int
    title: str
    approved_by: str
    approved_at: datetime
    target: ReviewTargetBlock
    verification: VerificationResultReport
    reviewer: ReviewerProvenanceBlock
    review: ModelReviewResult
    transmission_boundary: ReviewTransmissionBoundary
    capability_boundaries: ReviewCapabilityBoundaries
    human_decision_required: Literal[True]
    next_step: str


def build_review_packet(
    *,
    verification: VerificationResultReport,
    context: ReviewContext,
    review: ModelReviewResult,
    model: str,
    endpoint_host: str,
    usage: LLMUsage | None,
) -> ReviewPacket:
    """Assemble the packet. Identity from the orchestrator, review from the model.

    Pure and deterministic apart from the values handed in: no clock, no
    environment read, no file IO, no network, and no workspace access.

    Raises:
        ReviewerStageError: The assembled packet failed its own validation. That
            is defensive — reaching it would mean this function built something
            its own schema forbids.
    """
    payload = {
        "schema_version": REVIEW_PACKET_SCHEMA_VERSION,
        "mode": REVIEW_PACKET_MODE,
        # Identity, copied from the validated verification report — never from
        # the model, and never re-derived from the raw artifact here.
        "project_id": verification.project_id,
        "repo": verification.repo,
        "issue_number": verification.issue_number,
        "title": verification.title,
        "approved_by": verification.approved_by,
        "approved_at": verification.approved_at,
        "target": {
            "path": verification.target.path,
            "change_type": "modify",
        },
        "verification": verification,
        "reviewer": {
            "provider": "litellm",
            "model": model,
            "model_source": "project_config.controlled_review.model",
            "endpoint_host": endpoint_host,
            "operation": "code-review",
            "real_call": True,
            "semantic_requests": 1,
            "request_policy": REVIEWER_REQUEST_POLICY,
            "environment_default_model_used": False,
            "cli_model_override_available": False,
            "usage": usage,
        },
        "review": review,
        "transmission_boundary": {
            "approved_diff_sent_to_reviewer": True,
            "approved_plan_context_sent_to_reviewer": True,
            "verification_output_sent_redacted": True,
            "review_context_redacted_before_transmission": True,
            "full_target_file_sent_to_reviewer": False,
            "unrelated_source_sent_to_reviewer": False,
            "directory_listing_or_repository_tree_sent_to_reviewer": False,
            "git_history_sent_to_reviewer": False,
            "workspace_absolute_path_sent_to_reviewer": False,
            "verification_executable_path_sent_to_reviewer": False,
            "git_executable_path_sent_to_reviewer": False,
            "api_key_sent_to_reviewer": False,
            "endpoint_base_url_sent_to_reviewer": False,
            "raw_environment_sent_to_reviewer": False,
            "github_token_sent_to_reviewer": False,
            "approval_text_sent_to_reviewer": False,
            "raw_input_artifact_sent_to_reviewer": False,
            "raw_unredacted_verification_bytes_sent_to_reviewer": False,
            "redaction_count": context.redaction_count,
            "redaction_kinds": list(context.redaction_kinds),
            "redaction_note": REDACTION_NOTE,
        },
        "capability_boundaries": {
            # The honest positives. This command called a model over the network,
            # and its verification stage ran repository-controlled code.
            "orchestrator_model_called": True,
            "orchestrator_network_called": True,
            "orchestrator_repository_controlled_code_executed_by_verification_stage": (
                True
            ),
            # Everything AIDO did not do, scoped to AIDO and — where it matters —
            # to the review stage specifically.
            "orchestrator_files_written_by_review_stage": False,
            "orchestrator_workspace_read_by_review_stage": False,
            "orchestrator_verification_rerun_after_review": False,
            "orchestrator_fixer_invoked": False,
            "orchestrator_second_reviewer_invoked": False,
            "orchestrator_review_retry_or_reprompt_attempted": False,
            "orchestrator_patch_generated_from_findings": False,
            "orchestrator_file_edit_from_findings": False,
            "orchestrator_automatic_repair_attempted": False,
            "orchestrator_rollback_or_restore_performed": False,
            "orchestrator_git_mutation_performed_by_review_stage": False,
            "orchestrator_branch_created": False,
            "orchestrator_committed": False,
            "orchestrator_pushed": False,
            "orchestrator_pr_created": False,
            "orchestrator_github_accessed": False,
            "orchestrator_shell_invoked": False,
            "verification_child_process_note": VERIFICATION_CHILD_PROCESS_NOTE,
        },
        "human_decision_required": True,
        "next_step": REVIEW_HUMAN_DECISION,
    }

    try:
        return ReviewPacket.model_validate(payload)
    except ValidationError as exc:  # pragma: no cover - defensive
        raise ReviewerStageError(
            "packet error: the generated review packet failed its own "
            "validation: " + _summarize_validation_error(exc)
        ) from exc
