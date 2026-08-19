"""Controlled reviewer integration (Phase 5F2E).

The first capability in this repository that deliberately sends **source-derived
code** to a model. Phase 5F2C writes one approved file; Phase 5F2D asks the
project's own verification process whether that change holds up; this phase takes
the freshly verified change and asks a project-configured reviewer model what it
thinks — and then stops, at a human.

Five modules, and the split is the design:

- :mod:`~ai_dev_orchestrator.review.models` owns the **model-controlled** shape:
  the strict reviewer output schema and a parser that rejects rather than
  repairs. No trusted field is ever read from model output.
- :mod:`~ai_dev_orchestrator.review.request` owns the **transmission boundary**:
  what the reviewer receives (one approved unified diff, selected approved-plan
  prose, verification facts), what it never receives (whole files, unrelated
  source, listings, git history, absolute paths, credentials), the redaction
  applied before transmission, and the untrusted-data delimiters that keep
  project text from reading as instructions.
- :mod:`~ai_dev_orchestrator.review.supervision` owns the **bounded attempt
  policy** added by Phase 5F2E-RS1: at most two supervised semantic attempts,
  exactly one HTTP/model request each (reviewer transport retries are forced to
  zero), one optional compact retry for three narrow non-actionable outcomes, and
  the honest accounting of what was and was not observable.
- :mod:`~ai_dev_orchestrator.review.packet` owns the **human-facing artifact**:
  orchestrator identity, the embedded Phase 5F2D result, safe reviewer
  provenance, the attempt accounting, the review, and capability claims scoped
  truthfully.
- :mod:`~ai_dev_orchestrator.review.reviewer` owns the **ordering** and the
  **reviewer authority**: verify with the accepted Phase 5F2D verifier first,
  and only after a ``verified`` outcome select the configured provider's
  environment names, load them, and contact the reviewer. Phase 5F2E-V1 made the
  provider an explicit two-way choice — the existing internal LiteLLM path, or a
  direct OpenAI-compatible vLLM endpoint — with the model still coming only from
  project config. Phase 5F2E-V2 added one **generation constraint** to the
  direct-vLLM path: the request may carry the ``ModelReviewResult`` JSON Schema
  in the OpenAI-compatible ``response_format``/``json_schema`` field. The strict
  parser is unchanged and remains the final authority, and there is no fallback
  to an unstructured request.

A reviewer verdict is advisory. ``approve``, ``changes_requested`` and
``needs_human_review`` all end with a human: there is no fixer, no re-review of a
completed verdict, no patch generation from findings, no branch, no commit, no
push, and no PR.

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
    ReviewerAttemptExhaustedError,
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
    REVIEW_PACKET_SCHEMA_VERSION_HISTORY,
    REVIEW_PACKET_SCHEMA_VERSION_V1,
    REVIEW_PACKET_SCHEMA_VERSION_V1_SEMANTICS,
    REVIEW_PACKET_SCHEMA_VERSION_V2,
    REVIEW_PACKET_SCHEMA_VERSION_V2_SEMANTICS,
    REVIEW_PACKET_SCHEMA_VERSION_V3,
    REVIEW_PACKET_SCHEMA_VERSION_V3_SEMANTICS,
    VERIFICATION_CHILD_PROCESS_NOTE,
    ReviewCapabilityBoundaries,
    ReviewPacket,
    ReviewTargetBlock,
    ReviewTransmissionBoundary,
    ReviewerProvenanceBlock,
    build_review_packet,
)
from ai_dev_orchestrator.review.request import (
    COMPACT_RETRY_MAX_FINDINGS,
    COMPACT_RETRY_OMITTED_CONTEXT,
    REDACTION_NOTE,
    REVIEW_RESPONSE_FORMAT_NAME,
    REVIEW_RESPONSE_SCHEMA_SOURCE,
    STRUCTURED_OUTPUT_MODE_JSON_SCHEMA,
    STRUCTURED_OUTPUT_MODE_NONE,
    STRUCTURED_OUTPUT_MODES,
    STRUCTURED_OUTPUT_PARSER_AUTHORITY_NOTE,
    UNTRUSTED_BEGIN,
    UNTRUSTED_END,
    UNTRUSTED_NEUTRALIZED,
    ReviewContext,
    build_compact_model_review_request,
    build_model_review_request,
    build_review_context,
    build_review_response_format,
)
from ai_dev_orchestrator.review.reviewer import (
    LITELLM_REVIEWER_ENV_NAMES,
    REVIEW_PROVIDER_LITELLM,
    REVIEW_PROVIDER_VLLM,
    REVIEWER_ENV_NAMES_BY_PROVIDER,
    SUPPORTED_ENDPOINT_SCHEMES,
    SUPPORTED_REVIEW_PROVIDERS,
    VLLM_COMPATIBILITY_PLACEHOLDER_API_KEY,
    VLLM_ENV_API_KEY,
    VLLM_ENV_BASE_URL,
    VLLM_INSECURE_HTTP_OPT_IN_MEANING,
    VLLM_REVIEWER_ENV_NAMES,
    ControlledReviewOutcome,
    ReviewerAuthority,
    ReviewerCallNotice,
    build_reviewer_client_config,
    check_controlled_review_gate,
    endpoint_scheme_from_base_url,
    request_model_review,
    run_controlled_review,
    reviewer_env_names_for_provider,
)
from ai_dev_orchestrator.review.supervision import (
    ABANDONED_WORKER_LIFETIME_IF_DEADLINE_EXPIRES,
    ATTEMPT_OUTCOME_LABELS,
    ATTEMPT_WAIT_BOUND,
    BACKEND_INFERENCE_LIFETIME_IF_STALLED,
    MAX_SEMANTIC_REVIEW_ATTEMPTS,
    OUTPUT_BUDGET_FINISH_REASONS,
    RETRY_ELIGIBLE_OUTCOMES,
    REVIEWER_ATTEMPT_THREAD_NAME,
    REVIEWER_TRANSPORT_MAX_RETRIES,
    SUPERVISION_COMPACT_RETRY_NOTE,
    SUPERVISION_OBSERVABILITY_NOTE,
    SUPERVISION_OUTPUT_CAP_NOTE,
    SUPERVISION_RETRY_OWNERSHIP_NOTE,
    SUPERVISION_SCOPE_NOTE,
    SUPERVISION_TIMEOUT_NOTE,
    SUPERVISION_WAIT_BOUND_NOTE,
    TRANSPORT_REQUESTS_PER_ATTEMPT,
    ReviewAttemptRecord,
    ReviewSupervisionBlock,
    ReviewSupervisionEvent,
    SupervisedReviewOutcome,
    run_one_review_attempt,
    run_supervised_review,
)

__all__ = [
    "ABANDONED_WORKER_LIFETIME_IF_DEADLINE_EXPIRES",
    "ATTEMPT_OUTCOME_LABELS",
    "ATTEMPT_WAIT_BOUND",
    "BACKEND_INFERENCE_LIFETIME_IF_STALLED",
    "BLOCKING_SEVERITIES",
    "COMPACT_RETRY_MAX_FINDINGS",
    "COMPACT_RETRY_OMITTED_CONTEXT",
    "ControlledReviewOutcome",
    "LITELLM_REVIEWER_ENV_NAMES",
    "MAX_REVIEW_FINDINGS",
    "MAX_REVIEW_MESSAGE_CHARS",
    "MAX_REVIEW_NOTES",
    "MAX_REVIEW_NOTE_CHARS",
    "MAX_REVIEW_SUGGESTED_ACTION_CHARS",
    "MAX_REVIEW_SUMMARY_CHARS",
    "MAX_SEMANTIC_REVIEW_ATTEMPTS",
    "ModelReviewResult",
    "OUTPUT_BUDGET_FINISH_REASONS",
    "REDACTION_NOTE",
    "RETRY_ELIGIBLE_OUTCOMES",
    "REVIEWER_ATTEMPT_THREAD_NAME",
    "REVIEWER_ENV_NAMES_BY_PROVIDER",
    "REVIEWER_REQUEST_POLICY",
    "REVIEWER_TRANSPORT_MAX_RETRIES",
    "REVIEW_HUMAN_DECISION",
    "REVIEW_PACKET_MODE",
    "REVIEW_PACKET_SCHEMA_VERSION",
    "REVIEW_PACKET_SCHEMA_VERSION_HISTORY",
    "REVIEW_PACKET_SCHEMA_VERSION_V1",
    "REVIEW_PACKET_SCHEMA_VERSION_V1_SEMANTICS",
    "REVIEW_PACKET_SCHEMA_VERSION_V2",
    "REVIEW_PACKET_SCHEMA_VERSION_V2_SEMANTICS",
    "REVIEW_PACKET_SCHEMA_VERSION_V3",
    "REVIEW_PACKET_SCHEMA_VERSION_V3_SEMANTICS",
    "REVIEW_PROVIDER_LITELLM",
    "REVIEW_PROVIDER_VLLM",
    "REVIEW_RESPONSE_FORMAT_NAME",
    "REVIEW_RESPONSE_SCHEMA_SOURCE",
    "ReviewAttemptRecord",
    "ReviewCapabilityBoundaries",
    "ReviewContext",
    "ReviewError",
    "ReviewFinding",
    "ReviewPacket",
    "ReviewParseError",
    "ReviewRefusedError",
    "ReviewSupervisionBlock",
    "ReviewSupervisionEvent",
    "ReviewTargetBlock",
    "ReviewTransmissionBoundary",
    "ReviewValidationError",
    "ReviewerAttemptExhaustedError",
    "ReviewerAuthority",
    "ReviewerCallNotice",
    "ReviewerEnvironmentError",
    "ReviewerProvenanceBlock",
    "ReviewerStageError",
    "ReviewerTransportError",
    "SUPERVISION_COMPACT_RETRY_NOTE",
    "SUPERVISION_OBSERVABILITY_NOTE",
    "SUPERVISION_OUTPUT_CAP_NOTE",
    "SUPERVISION_RETRY_OWNERSHIP_NOTE",
    "SUPERVISION_SCOPE_NOTE",
    "SUPERVISION_TIMEOUT_NOTE",
    "SUPERVISION_WAIT_BOUND_NOTE",
    "SUPPORTED_ENDPOINT_SCHEMES",
    "STRUCTURED_OUTPUT_MODES",
    "STRUCTURED_OUTPUT_MODE_JSON_SCHEMA",
    "STRUCTURED_OUTPUT_MODE_NONE",
    "STRUCTURED_OUTPUT_PARSER_AUTHORITY_NOTE",
    "SUPPORTED_REVIEW_PROVIDERS",
    "SupervisedReviewOutcome",
    "TRANSPORT_REQUESTS_PER_ATTEMPT",
    "UNTRUSTED_BEGIN",
    "UNTRUSTED_END",
    "UNTRUSTED_NEUTRALIZED",
    "VERIFICATION_CHILD_PROCESS_NOTE",
    "VLLM_COMPATIBILITY_PLACEHOLDER_API_KEY",
    "VLLM_ENV_API_KEY",
    "VLLM_ENV_BASE_URL",
    "VLLM_INSECURE_HTTP_OPT_IN_MEANING",
    "VLLM_REVIEWER_ENV_NAMES",
    "build_compact_model_review_request",
    "build_model_review_request",
    "build_review_context",
    "build_review_packet",
    "build_review_response_format",
    "build_reviewer_client_config",
    "check_controlled_review_gate",
    "endpoint_scheme_from_base_url",
    "parse_model_review_response",
    "request_model_review",
    "reviewer_env_names_for_provider",
    "run_controlled_review",
    "run_one_review_attempt",
    "run_supervised_review",
]
