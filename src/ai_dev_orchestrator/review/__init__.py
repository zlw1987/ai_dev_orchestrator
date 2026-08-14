"""Controlled reviewer integration (Phase 5F2E).

The first capability in this repository that deliberately sends **source-derived
code** to a model. Phase 5F2C writes one approved file; Phase 5F2D asks the
project's own verification process whether that change holds up; this phase takes
the freshly verified change and asks a project-configured reviewer model what it
thinks — and then stops, at a human.

Four modules, and the split is the design:

- :mod:`~ai_dev_orchestrator.review.models` owns the **model-controlled** shape:
  the strict reviewer output schema and a parser that rejects rather than
  repairs. No trusted field is ever read from model output.
- :mod:`~ai_dev_orchestrator.review.request` owns the **transmission boundary**:
  what the reviewer receives (one approved unified diff, selected approved-plan
  prose, verification facts), what it never receives (whole files, unrelated
  source, listings, git history, absolute paths, credentials), the redaction
  applied before transmission, and the untrusted-data delimiters that keep
  project text from reading as instructions.
- :mod:`~ai_dev_orchestrator.review.packet` owns the **human-facing artifact**:
  orchestrator identity, the embedded Phase 5F2D result, safe reviewer
  provenance, the review, and capability claims scoped truthfully.
- :mod:`~ai_dev_orchestrator.review.reviewer` owns the **ordering**: verify with
  the accepted Phase 5F2D verifier first, and only after a ``verified`` outcome
  load the LiteLLM environment and contact the reviewer.

A reviewer verdict is advisory. ``approve``, ``changes_requested`` and
``needs_human_review`` all end with a human: there is no fixer, no re-review, no
patch generation from findings, no branch, no commit, no push, and no PR.

Importing this package contacts nothing, reads no environment variable, builds no
client, and touches no workspace.
"""

from ai_dev_orchestrator.review.models import (
    BLOCKING_SEVERITIES,
    MAX_REVIEW_FINDINGS,
    MAX_REVIEW_MESSAGE_CHARS,
    MAX_REVIEW_NOTES,
    MAX_REVIEW_NOTE_CHARS,
    MAX_REVIEW_SUGGESTED_ACTION_CHARS,
    MAX_REVIEW_SUMMARY_CHARS,
    ModelReviewResult,
    ReviewError,
    ReviewFinding,
    ReviewParseError,
    ReviewRefusedError,
    ReviewValidationError,
    ReviewerEnvironmentError,
    ReviewerStageError,
    ReviewerTransportError,
    parse_model_review_response,
)
from ai_dev_orchestrator.review.packet import (
    REVIEWER_REQUEST_POLICY,
    REVIEW_HUMAN_DECISION,
    REVIEW_PACKET_MODE,
    REVIEW_PACKET_SCHEMA_VERSION,
    VERIFICATION_CHILD_PROCESS_NOTE,
    ReviewCapabilityBoundaries,
    ReviewPacket,
    ReviewTargetBlock,
    ReviewTransmissionBoundary,
    ReviewerProvenanceBlock,
    build_review_packet,
)
from ai_dev_orchestrator.review.request import (
    REDACTION_NOTE,
    UNTRUSTED_BEGIN,
    UNTRUSTED_END,
    UNTRUSTED_NEUTRALIZED,
    ReviewContext,
    build_model_review_request,
    build_review_context,
)
from ai_dev_orchestrator.review.reviewer import (
    REVIEWER_ENV_NAMES,
    SUPPORTED_REVIEW_PROVIDER,
    ControlledReviewOutcome,
    ReviewerCallNotice,
    build_reviewer_client_config,
    check_controlled_review_gate,
    request_model_review,
    run_controlled_review,
)

__all__ = [
    "BLOCKING_SEVERITIES",
    "ControlledReviewOutcome",
    "MAX_REVIEW_FINDINGS",
    "MAX_REVIEW_MESSAGE_CHARS",
    "MAX_REVIEW_NOTES",
    "MAX_REVIEW_NOTE_CHARS",
    "MAX_REVIEW_SUGGESTED_ACTION_CHARS",
    "MAX_REVIEW_SUMMARY_CHARS",
    "ModelReviewResult",
    "REDACTION_NOTE",
    "REVIEWER_ENV_NAMES",
    "REVIEWER_REQUEST_POLICY",
    "REVIEW_HUMAN_DECISION",
    "REVIEW_PACKET_MODE",
    "REVIEW_PACKET_SCHEMA_VERSION",
    "ReviewCapabilityBoundaries",
    "ReviewContext",
    "ReviewError",
    "ReviewFinding",
    "ReviewPacket",
    "ReviewParseError",
    "ReviewRefusedError",
    "ReviewTargetBlock",
    "ReviewTransmissionBoundary",
    "ReviewValidationError",
    "ReviewerCallNotice",
    "ReviewerEnvironmentError",
    "ReviewerProvenanceBlock",
    "ReviewerStageError",
    "ReviewerTransportError",
    "SUPPORTED_REVIEW_PROVIDER",
    "UNTRUSTED_BEGIN",
    "UNTRUSTED_END",
    "UNTRUSTED_NEUTRALIZED",
    "VERIFICATION_CHILD_PROCESS_NOTE",
    "build_model_review_request",
    "build_review_context",
    "build_review_packet",
    "build_reviewer_client_config",
    "check_controlled_review_gate",
    "parse_model_review_response",
    "request_model_review",
    "run_controlled_review",
]
