"""The human-facing review packet (``review-packet.v4``) — 5F2E / RS1 / V1 / V2.

One structured artifact per successful controlled review, assembled from five
sources that are kept strictly separate:

- **orchestrator-owned identity**, taken from the validated Phase 5F2D
  verification report (which was itself built from the project config and an
  approval matched against it exactly);
- **the embedded verification result**, preserved as the accepted typed
  :class:`~ai_dev_orchestrator.verification.VerificationResultReport` rather than
  summarized into something weaker;
- **reviewer provenance**, built from the project config and the validated
  connection settings — the configured provider (``litellm`` or ``vllm``), the
  exact configured model, the endpoint **host only**, the transport scheme and
  whether it was TLS, whether generation was constrained by the
  ``ModelReviewResult`` JSON Schema and which class that schema was generated
  from, and token usage if the endpoint reported any;
- **reviewer supervision** (Phase 5F2E-RS1) — how many semantic requests AIDO
  issued, of a hard maximum of two; that each was exactly one HTTP/model request
  because reviewer transport retries are forced to zero; whether the one compact
  retry was enabled and whether it was used; that a stalled attempt is terminal;
  that each attempt's wait was bounded by AIDO's **own** monotonic deadline
  rather than by httpx timeout semantics; that the abandoned worker's and the
  backend's lifetimes are unobserved; the configured attempt timeout and
  requested output cap; and each attempt's outcome, stall source,
  ``finish_reason`` and reported usage;
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

Why this is ``v2`` and not a redefined ``v1``
---------------------------------------------

``review-packet.v1`` shipped with Phase 5F2E and meant something specific: **one**
semantic reviewer request, with the generic client's transport retries still in
play and unreported. Phase 5F2E-RS1 changed both halves of that — up to two
supervised semantic attempts, with reviewer transport retries forced to zero —
and added the attempt accounting that makes the change auditable.

Silently redefining ``v1`` would have made every archived packet ambiguous about
which policy produced it. So the version was bumped instead, ``v1``'s meaning is
preserved as history in
:data:`REVIEW_PACKET_SCHEMA_VERSION_V1_SEMANTICS`, and one field was **removed**
rather than left in place lying: ``orchestrator_review_retry_or_reprompt_attempted``
was a hard-coded ``false``, and under RS1 it would have been false only when the
compact retry did not run. Its replacements are truthful about what actually
happened — see :class:`ReviewCapabilityBoundaries`.

Why this is now ``v3`` and not a redefined ``v2`` (Phase 5F2E-V1)
-----------------------------------------------------------------

``review-packet.v2`` carried a **LiteLLM-specific** reviewer provenance contract:
``provider`` could only ever be ``"litellm"``, because that was the only reviewer
provider that existed, and the packet said nothing at all about the transport's
scheme. Phase 5F2E-V1 added a second explicitly supported reviewer backend — a
direct OpenAI-compatible vLLM endpoint — and, with it, a fact a reader now needs:
**whether the source-derived diff went over TLS.**

Redefining ``v2`` in place would have made every archived ``v2`` packet ambiguous
about which backend produced it, and would have retroactively implied a
transport claim those packets never made. So the version was bumped again.
``v2``'s meaning is preserved verbatim in
:data:`REVIEW_PACKET_SCHEMA_VERSION_V2_SEMANTICS`, and the whole history is
stated in :data:`REVIEW_PACKET_SCHEMA_VERSION_HISTORY`.

**The supervision semantics did not change.** ``v3`` records exactly the accepted
Phase 5F2E-RS1 policy that ``v2`` did — transport retries forced to zero, at most
two semantic requests, an AIDO-owned monotonic wait deadline per attempt, a
terminal stall, and per-attempt accounting — applied identically to both
providers. The only additions are provenance: ``provider`` now admits ``"vllm"``,
and ``endpoint_scheme`` / ``transport_tls`` report what was actually used.

``transport_tls`` is a statement about the URL scheme the client was configured
with, and nothing more. It does not certify a certificate, a cipher, a peer
identity, or a network. A ``false`` here means the material was sent
unencrypted — and, for the vLLM provider, that the project had to explicitly opt
in for that to be possible at all.

Why this is now ``v4`` and not a redefined ``v3`` (Phase 5F2E-V2)
------------------------------------------------------------------

Phase 5F2E-V2 changed **how the reviewer response was generated**: a direct-vLLM
review may now carry the ``ModelReviewResult`` JSON Schema in the
OpenAI-compatible ``response_format``/``json_schema`` field, so the server
constrains generation. That is provenance a reader materially needs — a reply
produced under a schema constraint and one produced freely are not the same
evidence — and no ``v1``, ``v2`` or ``v3`` packet records it.

Redefining ``v3`` in place would have made every archived ``v3`` packet ambiguous
about whether a constraint was used. So the version was bumped again. ``v3``'s
meaning is preserved verbatim in
:data:`REVIEW_PACKET_SCHEMA_VERSION_V3_SEMANTICS`, and the whole history stays in
:data:`REVIEW_PACKET_SCHEMA_VERSION_HISTORY`.

**Nothing else changed.** ``v4`` records exactly the accepted RS1 supervision
policy and exactly the accepted V1 provider/transport provenance. The strict
reviewer parser is unchanged and remains the final authority: a JSON Schema
cannot express AIDO's Pydantic model validators, and
:data:`~ai_dev_orchestrator.review.request.STRUCTURED_OUTPUT_PARSER_AUTHORITY_NOTE`
— carried in the packet as ``reviewer.structured_output_note`` — says so in the
artifact itself.

Deliberately still absent: the JSON Schema document, the ``response_format``
request JSON, the prompt, the raw model response, and the provider's separate
``message.reasoning`` field, which this phase does not read, log, transmit,
parse, store, or expose.
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
from ai_dev_orchestrator.review.request import (
    REDACTION_NOTE,
    REVIEW_RESPONSE_SCHEMA_SOURCE,
    STRUCTURED_OUTPUT_MODE_JSON_SCHEMA,
    STRUCTURED_OUTPUT_MODE_NONE,
    STRUCTURED_OUTPUT_MODES,
    STRUCTURED_OUTPUT_PARSER_AUTHORITY_NOTE,
    ReviewContext,
)
from ai_dev_orchestrator.review.supervision import (
    MAX_SEMANTIC_REVIEW_ATTEMPTS,
    REVIEWER_TRANSPORT_MAX_RETRIES,
    ReviewSupervisionBlock,
)
from ai_dev_orchestrator.verification import VerificationResultReport

REVIEW_PACKET_SCHEMA_VERSION = "review-packet.v4"
REVIEW_PACKET_MODE = "controlled-review"

# The superseded versions, kept so an archived packet's meaning stays legible.
# Neither is reinterpreted under a later version's rules.
REVIEW_PACKET_SCHEMA_VERSION_V1 = "review-packet.v1"
REVIEW_PACKET_SCHEMA_VERSION_V1_SEMANTICS = (
    "review-packet.v1 (Phase 5F2E) recorded exactly ONE semantic reviewer "
    "request, made with the generic LLM client's shipped transport-retry "
    "behavior still in effect and unreported, and it carried no attempt "
    "accounting. Its reviewer provenance was LiteLLM-specific: the only "
    "supported provider was the internal OpenAI-compatible LiteLLM path, and "
    "the packet reported no endpoint scheme and no transport-TLS fact. "
    "review-packet.v2 (Phase 5F2E-RS1) supersedes it: the reviewer client "
    "forces transport max_retries=0, so one semantic attempt is exactly one "
    "HTTP/model request, and a project may authorize at most one bounded "
    "compact second semantic attempt. A v1 packet keeps its original meaning and "
    "is not reinterpreted under v2, v3, or v4 rules — in particular it makes no "
    "claim about the transport scheme and none about structured generation."
)

REVIEW_PACKET_SCHEMA_VERSION_V2 = "review-packet.v2"
REVIEW_PACKET_SCHEMA_VERSION_V2_SEMANTICS = (
    "review-packet.v2 (Phase 5F2E-RS1, with FU1 and FU2) recorded the bounded "
    "reviewer supervision that is still in force: reviewer transport retries "
    "forced to zero, at most two semantic requests, an AIDO-owned monotonic "
    "wait deadline per attempt, a terminal stall, and per-attempt accounting. "
    "Its reviewer provenance was still LiteLLM-SPECIFIC: 'litellm' was the only "
    "provider a v2 packet could have been produced by, and v2 carried no "
    "endpoint_scheme and no transport_tls field. A v2 packet must NOT be read "
    "as though it may have come from a direct vLLM endpoint, and it must not be "
    "read as making any claim about transport encryption. A v2 packet also "
    "carried NO structured-generation provenance and must not be read as "
    "proving whether a response_format/json_schema constraint was used; V2 did "
    "not exist, so no v2 run ever sent one. review-packet.v3 (Phase 5F2E-V1) "
    "superseded it, and review-packet.v4 (Phase 5F2E-V2) supersedes v3 for new "
    "runs, with identical supervision semantics throughout."
)

REVIEW_PACKET_SCHEMA_VERSION_V3 = "review-packet.v3"
REVIEW_PACKET_SCHEMA_VERSION_V3_SEMANTICS = (
    "review-packet.v3 (Phase 5F2E-V1, with FU1) recorded the same accepted "
    "Phase 5F2E-RS1 supervision as v2, plus explicit LiteLLM/vLLM reviewer "
    "provenance and truthful transport-scheme reporting (endpoint_scheme and "
    "transport_tls). It carried NO structured-generation provenance: it has no "
    "structured_output_mode and no structured_output_schema_source field, and "
    "an archived v3 packet must NOT be read as proving whether a "
    "response_format/json_schema generation constraint was used. Phase "
    "5F2E-V2 did not exist when v3 shipped, so no v3 run ever sent one — but "
    "the packet itself does not record that, which is exactly why the version "
    "was bumped rather than v3 redefined. review-packet.v4 (Phase 5F2E-V2) "
    "supersedes it for new runs, retaining every accepted v3 and RS1 semantic "
    "unchanged."
)

REVIEW_PACKET_SCHEMA_VERSION_HISTORY = (
    "review-packet.v1 = original Phase 5F2E semantics: exactly one semantic "
    "reviewer attempt, unreported generic transport retries, no attempt "
    "accounting, LiteLLM-only reviewer provenance, no transport-scheme "
    "reporting. "
    "review-packet.v2 = Phase 5F2E-RS1 supervision semantics (transport retries "
    "forced to zero, at most two semantic requests, AIDO-owned per-attempt wait "
    "deadline, terminal stall, per-attempt accounting), with LiteLLM-only "
    "reviewer provenance and still no transport-scheme reporting. "
    "review-packet.v3 = the SAME accepted RS1 supervision semantics as v2, now "
    "with explicit LiteLLM/vLLM reviewer provenance and truthful "
    "transport-scheme reporting (endpoint_scheme and transport_tls), and NO "
    "structured-generation provenance. The version was bumped rather than v2 "
    "redefined, so no archived v2 packet becomes ambiguous about which provider "
    "produced it. "
    "review-packet.v4 = the SAME accepted RS1 supervision semantics and the "
    "SAME v3 provider/transport provenance, plus structured-generation "
    "provenance (structured_output_mode and structured_output_schema_source). "
    "The version was bumped rather than v3 redefined, so no archived v1, v2 or "
    "v3 packet may be read as recording whether a response_format/json_schema "
    "constraint was used — none of them carried that fact."
)

# What the reviewer request policy actually is, stated exactly.
REVIEWER_REQUEST_POLICY = (
    f"AIDO may ISSUE at most {MAX_SEMANTIC_REVIEW_ATTEMPTS} semantic reviewer "
    f"requests, and the reviewer client is built with "
    f"max_retries={REVIEWER_TRANSPORT_MAX_RETRIES}, so each semantic attempt is "
    "exactly one HTTP/model request. The second request exists only when the "
    "project enabled controlled_review.compact_retry_on_unusable_output AND the "
    "first response was COMPLETED but unusable — it exhausted its output budget "
    "or was rejected by the strict parser. A TIMEOUT IS TERMINAL: AIDO stops "
    "waiting but does not observe whether the backend released its inference "
    "slot, so it never issues a second request that could run concurrently with "
    "the first. The compact request is a separate, smaller review using the SAME "
    "configured model — never a repair of the first reply, never a merge of the "
    "two, and never a fallback model. There is no third request, no 'fix your "
    "JSON' round trip, and no second reviewer. The generic LLM client keeps its "
    "own bounded transport retries for other callers; they are disabled for the "
    "reviewer. Each attempt's wait is bounded by AIDO's OWN monotonic deadline in "
    "the supervisor — not by the client's network-inactivity timeout — so this "
    "bounds AIDO's request issuance and wait budget only. It does NOT bound the "
    "abandoned worker's lifetime, the HTTP request's lifetime after AIDO stops "
    "waiting, or backend inference lifetime. See reviewer_supervision for what "
    "actually happened on this run."
)

# The whole point of the phase, in the artifact itself.
REVIEW_HUMAN_DECISION = (
    "A reviewer verdict is ADVISORY and is not executable authority. All three "
    "verdicts — approve, changes_requested, needs_human_review — end here, with a "
    "human. AIDO did not and cannot act on the findings: there is no fixer, no "
    "second reviewer, no re-review of a completed verdict, no retry after "
    "findings, no patch generation from findings, no file edit, no revert or "
    "restore, no branch, no commit, no push, and no PR. (The Phase 5F2E-RS1 "
    "compact retry is not a counter-example: it exists only when a COMPLETED "
    "response carried NO usable review at all, never to revisit a verdict that "
    "was produced. See reviewer_supervision.) The approved single-file modification "
    "is left uncommitted in the working tree exactly as the writer and the "
    "verifier left it. The human decides what happens next."
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

    ``provider`` is ``"litellm"`` or ``"vllm"``, taken from
    ``project_config.controlled_review.provider`` after the review gate accepted
    it. **It cannot be forged by model output**: the strict reviewer parser has
    no such field, and this block is assembled from orchestrator-owned values
    only.

    ``endpoint_scheme`` and ``transport_tls`` were added by Phase 5F2E-V1 and are
    derived from the base URL the client was configured with — the scheme is the
    one URL component that carries neither credential nor payload.
    ``transport_tls`` is exactly ``endpoint_scheme == "https"``; it is a statement
    about the configured scheme and **not** a certificate, cipher, peer-identity,
    or network-privacy claim. It is reported truthfully for both providers,
    including the synthetic ``http`` URLs the offline test suite uses.

    ``usage`` is the usage block of the attempt that produced this review, or
    ``None`` when the provider reported none — recorded as **unknown**, never
    invented as zero. Per-attempt usage for every attempt, including one that
    failed, lives in ``reviewer_supervision.attempts``.

    ``fallback_model_configured`` and ``fallback_model_used`` are both fixed
    ``False`` because there is no fallback model *anywhere*: no config field, no
    CLI option, and no code path. Automatic model failover would send the
    approved source-derived diff to a second model, which is a separate authority
    decision and is deliberately not taken here.

    ``structured_output_mode`` and ``structured_output_schema_source`` were
    added by Phase 5F2E-V2 and are the whole reason this is ``v4``. They record
    whether the reviewer requests carried the ``ModelReviewResult`` JSON Schema
    in the OpenAI-compatible ``response_format``/``json_schema`` field, and — when
    they did — the dotted path of the class the schema was **generated** from.
    ``"json_schema"`` appears only for a direct-vLLM review whose project set
    ``controlled_review.vllm_structured_output``; a LiteLLM review and a vLLM
    review without that opt-in both report ``"none"`` with a ``None`` source.

    Both are **orchestrator-owned and cannot be forged by model output**: they
    come from the review gate's reading of trusted project config, the strict
    reviewer schema has no such field, and this block is assembled entirely from
    orchestrator-owned values. The schema **document** is deliberately absent —
    there is no field for it, for the ``response_format`` request JSON, for the
    prompt, for the raw model response, or for the provider's ``reasoning``
    field, which Phase 5F2E-V2 does not capture at all.

    Recording ``"json_schema"`` is a statement about what AIDO **requested**, not
    a claim that generation was in fact constrained, that the server honored the
    schema, or that the reply was therefore valid. The strict parser remains the
    final authority and is unchanged.
    """

    provider: Literal["litellm", "vllm"]
    model: str
    model_source: Literal["project_config.controlled_review.model"]
    endpoint_host: str
    endpoint_scheme: Literal["http", "https"]
    transport_tls: bool
    structured_output_mode: Literal[
        STRUCTURED_OUTPUT_MODE_NONE, STRUCTURED_OUTPUT_MODE_JSON_SCHEMA  # type: ignore[valid-type]
    ]
    structured_output_schema_source: (
        Literal[REVIEW_RESPONSE_SCHEMA_SOURCE] | None  # type: ignore[valid-type]
    )
    structured_output_note: str
    operation: Literal["code-review"]
    real_call: Literal[True]
    # RS1: no longer pinned to 1 — one or two, and the exact number is a fact
    # about this run rather than a promise from the schema. The per-attempt
    # detail lives in ``reviewer_supervision``.
    semantic_requests: int
    max_semantic_requests: Literal[MAX_SEMANTIC_REVIEW_ATTEMPTS]  # type: ignore[valid-type]
    transport_retries_per_semantic_request: Literal[REVIEWER_TRANSPORT_MAX_RETRIES]  # type: ignore[valid-type]
    request_policy: str
    environment_default_model_used: Literal[False]
    cli_model_override_available: Literal[False]
    fallback_model_configured: Literal[False]
    fallback_model_used: Literal[False]
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

    **RS1 replaced one field rather than letting it lie.** ``v1`` carried a
    hard-coded ``orchestrator_review_retry_or_reprompt_attempted: false``. Under
    RS1 a project may authorize one bounded compact second semantic attempt, so
    that field would have been false only sometimes. It is gone. In its place:

    - ``orchestrator_bounded_compact_retry_used`` — a **real** boolean, true when
      the second attempt actually ran;
    - ``orchestrator_third_semantic_attempt_made`` — fixed ``False``, because two
      is a hard ceiling with no configuration and no code path past it;
    - ``orchestrator_parser_repair_attempted`` and
      ``orchestrator_partial_findings_merged_across_attempts`` — fixed ``False``,
      because a rejected reply is discarded whole rather than patched or mined;
    - ``orchestrator_fallback_reviewer_model_used`` — fixed ``False``, because
      there is no second model to fall back to.
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
    orchestrator_bounded_compact_retry_used: bool
    orchestrator_third_semantic_attempt_made: Literal[False]
    orchestrator_parser_repair_attempted: Literal[False]
    orchestrator_partial_findings_merged_across_attempts: Literal[False]
    orchestrator_fallback_reviewer_model_used: Literal[False]
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
    reviewer_supervision: ReviewSupervisionBlock
    review: ModelReviewResult
    transmission_boundary: ReviewTransmissionBoundary
    capability_boundaries: ReviewCapabilityBoundaries
    human_decision_required: Literal[True]
    next_step: str
    superseded_schema_version_note: str


def build_review_packet(
    *,
    verification: VerificationResultReport,
    context: ReviewContext,
    review: ModelReviewResult,
    provider: str,
    model: str,
    endpoint_host: str,
    endpoint_scheme: str,
    structured_output_mode: str,
    usage: LLMUsage | None,
    supervision: ReviewSupervisionBlock,
) -> ReviewPacket:
    """Assemble the packet. Identity from the orchestrator, review from the model.

    Pure and deterministic apart from the values handed in: no clock, no
    environment read, no file IO, no network, and no workspace access.

    ``supervision`` is the Phase 5F2E-RS1 attempt accounting, produced by
    :func:`~ai_dev_orchestrator.review.supervision.run_supervised_review`. It is
    a required argument rather than an optional extra so that no code path can
    emit a ``v3`` packet whose attempt history is missing.

    ``provider`` and ``endpoint_scheme`` are required for the same reason: a
    ``v3`` packet's whole added value over ``v2`` is that it names the backend
    and states truthfully whether the transport was TLS, so neither may default.
    Both come from trusted project config and the validated connection settings;
    ``transport_tls`` is derived here rather than passed, so it can never
    disagree with the scheme beside it.

    ``structured_output_mode`` is required for exactly the same reason at ``v4``:
    the version exists to record whether generation was constrained by the
    ``ModelReviewResult`` JSON Schema, so it may not default to the quieter
    answer. ``structured_output_schema_source`` is **derived** here from it
    rather than passed, so the two can never disagree — a ``"json_schema"``
    packet always names the one generating class, and a ``"none"`` packet always
    reports ``None``.

    Raises:
        ReviewerStageError: The assembled packet failed its own validation. That
            is defensive — reaching it would mean this function built something
            its own schema forbids.
    """
    if structured_output_mode not in STRUCTURED_OUTPUT_MODES:  # pragma: no cover
        # Defensive: the review gate produces one of exactly two tokens. Failing
        # closed here keeps an unrecognized value out of a packet rather than
        # letting pydantic's message be the only record of it.
        raise ReviewerStageError(
            "packet error: unknown structured output mode; the packet records "
            "only orchestrator-owned provenance and refuses to invent one."
        )

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
            # Orchestrator-owned, from the accepted review gate — never from the
            # model, which has no field capable of naming a provider.
            "provider": provider,
            "model": model,
            "model_source": "project_config.controlled_review.model",
            "endpoint_host": endpoint_host,
            "endpoint_scheme": endpoint_scheme,
            "transport_tls": endpoint_scheme == "https",
            # Phase 5F2E-V2 provenance. Orchestrator-owned: it comes from the
            # review gate's reading of trusted project config, and the strict
            # reviewer schema has no field a model could forge it with. The
            # schema source is derived from the mode, never passed, so the two
            # cannot disagree. The schema DOCUMENT is deliberately not carried.
            "structured_output_mode": structured_output_mode,
            "structured_output_schema_source": (
                REVIEW_RESPONSE_SCHEMA_SOURCE
                if structured_output_mode == STRUCTURED_OUTPUT_MODE_JSON_SCHEMA
                else None
            ),
            "structured_output_note": STRUCTURED_OUTPUT_PARSER_AUTHORITY_NOTE,
            "operation": "code-review",
            "real_call": True,
            "semantic_requests": supervision.semantic_attempts_used,
            "max_semantic_requests": MAX_SEMANTIC_REVIEW_ATTEMPTS,
            "transport_retries_per_semantic_request": REVIEWER_TRANSPORT_MAX_RETRIES,
            "request_policy": REVIEWER_REQUEST_POLICY,
            "environment_default_model_used": False,
            "cli_model_override_available": False,
            "fallback_model_configured": False,
            "fallback_model_used": False,
            "usage": usage,
        },
        "reviewer_supervision": supervision,
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
            # A real fact, not a fixed claim: true when the one bounded compact
            # second semantic attempt actually ran.
            "orchestrator_bounded_compact_retry_used": supervision.compact_retry_used,
            "orchestrator_third_semantic_attempt_made": False,
            "orchestrator_parser_repair_attempted": False,
            "orchestrator_partial_findings_merged_across_attempts": False,
            "orchestrator_fallback_reviewer_model_used": False,
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
        "superseded_schema_version_note": REVIEW_PACKET_SCHEMA_VERSION_HISTORY,
    }

    try:
        return ReviewPacket.model_validate(payload)
    except ValidationError as exc:  # pragma: no cover - defensive
        raise ReviewerStageError(
            "packet error: the generated review packet failed its own "
            "validation: " + _summarize_validation_error(exc)
        ) from exc
