"""The supervised implementer, offline and library-only (ALPHA-P1A, DEC-SUP).

The flow, end to end:

    approved plan + project config                       (re-validated private copies)
      → gates: consent, offline transport, config, endpoint, target path
      → Phase 5D2 bounded read, in-process (the shipped reader, not a saved packet)
      → refuse unless the target was read, is a file, and was NOT redacted
      → announce the transmission, then ONE request through an in-process mock
      → strict parse of {"content_text": ...}            (rejected, never repaired)
      → AIDO assembles proposed-content.v1               (the model names no path)
      → existing build_deterministic_diff_proposal       (unchanged 5E3 rules)
      → STOP: a result for a human to approve as an exact diff

The model's output is **untrusted proposed content**, and nothing here can
write it. This module opens no file for writing, creates no approval, applies
no diff, runs no command and touches no Git. The only workspace access is the
shipped Phase 5D2 bounded read, behind that phase's own project opt-in.

**ALPHA-P1A is offline-only.** The runner accepts exactly an
``httpx.MockTransport``. Any other supplied transport type, including a
subclass, a real transport or a pre-built client, is refused before the
workspace is read. That is a guard against **accidental** live use, not a
sandbox: a ``MockTransport`` handler is arbitrary trusted Python supplied by
the caller, and it could itself perform network operations. Nothing here
inspects or confines it, so the gate is no guarantee against a malicious or
network-capable injected handler. P1A stays offline because it has no
authorized live invocation entry point: no CLI command reaches this module.
Lifting the restriction is the first live pilot's separate authorization, not
a configuration change.

There is **one** semantic request and **zero** transport retries. Any failure
is terminal: no retry, no fallback model, no unstructured fallback after a
structured-output rejection, and no repair.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx
from pydantic import ValidationError

from ai_dev_orchestrator.diff_proposal.generator import (
    WORKSPACE_CONTENT_CANDIDATE_SOURCE,
    WORKSPACE_CONTENT_MODE,
    DiffProposalGenerationError,
    ProposedContentInput,
    WorkspaceContentPacket,
    build_deterministic_diff_proposal,
)
from ai_dev_orchestrator.diff_proposal.models import (
    _require_safe_relative_repo_path,
    _summarize_validation_error,
)
from ai_dev_orchestrator.handoff.models import ApprovedL1PlanArtifact
from ai_dev_orchestrator.llm.client import LLMClient, LLMClientError
from ai_dev_orchestrator.llm.models import LLMClientConfig, LLMResponse
from ai_dev_orchestrator.models import ProjectConfig, SupervisedImplementerConfig
from ai_dev_orchestrator.supervised_implementer.identity import (
    QUALIFICATION_CREDIT,
    SUPERVISED_CANDIDATE_MODEL_IDS,
    SUPERVISED_IMPLEMENTER_ROLE,
)
from ai_dev_orchestrator.supervised_implementer.models import (
    MODEL_SOURCE,
    NEXT_STEP,
    PROVENANCE_SCHEMA_VERSION,
    ReportedUsage,
    SourceTransmissionNotice,
    SupervisedImplementerOutputRejected,
    SupervisedImplementerProvenance,
    SupervisedImplementerRefused,
    SupervisedImplementerResult,
    SupervisedImplementerTransportFailed,
    parse_supervised_implementer_output,
)
from ai_dev_orchestrator.supervised_implementer.request import (
    build_supervised_implementer_request,
    request_messages_sha256,
)
from ai_dev_orchestrator.workspace.content_read import (
    WorkspaceContentReadRefused,
    read_approved_plan_workspace_contents,
)

SUPPORTED_PROVIDERS = ("litellm", "vllm")

#: ALPHA-P1A's transport restriction, by exact type.
OFFLINE_TRANSPORT_TYPE = httpx.MockTransport
TRANSPORT_KIND = "offline_mock"

#: Forced on the client for this role: one semantic attempt is one request.
TRANSPORT_MAX_RETRIES = 0

# Fixed AIDO prose for the proposed-content input. It is built only from
# registry values, never from model text (DEC-SUP item 6), so a model cannot
# put persuasion into the artifact a human approves.
_RATIONALE_TEMPLATE = (
    "Model-authored proposed content from supervised implementer candidate "
    "{candidate} (model {model}). AIDO did not author it and does not attest "
    "that it is correct, complete, minimal, or safe."
)
_ASSUMPTION_TEMPLATE = (
    "The proposed content was authored by supervised implementer candidate "
    "{candidate} (model {model}) through an offline mock transport, from one "
    "approved file read in-process by the Phase 5D2 reader. A separate "
    "supervised-implementer provenance record binds it by SHA-256. That record "
    "is not evidence of correctness and confers no qualification."
)
_RISK_TEXT = (
    "Model-authored content can be wrong, incomplete, out of scope or subtly "
    "harmful while still being well-formed. Review the exact diff line by line "
    "before approving it."
)
_NEXT_AUTHORIZATION = (
    "A human must approve this exact diff (Phase 5F0) before any write. "
    "Applying it, verifying it, reviewing it, committing, pushing and opening "
    "PRs each remain separately authorized."
)


@dataclass(frozen=True)
class SupervisedImplementerSettings:
    """The gate's resolved, type-checked view of the project config block."""

    candidate: str
    model: str
    provider: str
    allow_insecure_http: bool
    structured_output: bool
    max_output_tokens: int | None


def _refuse(category: str, message: str) -> SupervisedImplementerRefused:
    return SupervisedImplementerRefused(category, message)


def check_supervised_implementer_gate(
    config: SupervisedImplementerConfig,
) -> SupervisedImplementerSettings:
    """Resolve the config block, or refuse. Exact types and exact strings only.

    Every check uses ``is True`` or an exact ``type``, never truthiness, so a
    value forged after loading (``"yes"``, ``1``, a ``str`` subclass) fails
    closed.
    """
    if not isinstance(config, SupervisedImplementerConfig):
        raise _refuse("config_wrong_type", "supervised_implementer block is malformed.")
    if config.enabled is not True:
        raise _refuse(
            "not_enabled",
            "this project does not enable the supervised implementer "
            "(supervised_implementer.enabled is not true). Nothing was read.",
        )
    candidate = config.candidate
    if type(candidate) is not str or candidate not in SUPERVISED_CANDIDATE_MODEL_IDS:
        raise _refuse(
            "unknown_candidate",
            "supervised_implementer.candidate is not an exact supervised "
            f"candidate id; the registry is exactly {sorted(SUPERVISED_CANDIDATE_MODEL_IDS)}.",
        )
    expected_model = SUPERVISED_CANDIDATE_MODEL_IDS[candidate]
    if type(config.model) is not str or config.model != expected_model:
        raise _refuse(
            "candidate_model_mismatch",
            f"supervised_implementer.model must be exactly the registry model for "
            f"{candidate}. A different model is a different candidate, not a "
            "substitute.",
        )
    if type(config.provider) is not str or config.provider not in SUPPORTED_PROVIDERS:
        raise _refuse(
            "unsupported_provider",
            "supervised_implementer.provider must be exactly 'litellm' or 'vllm'.",
        )
    for name in ("allow_insecure_http", "structured_output"):
        if type(getattr(config, name)) is not bool:
            raise _refuse("config_wrong_type", f"supervised_implementer.{name} must be a boolean.")
    cap = config.max_output_tokens
    if cap is not None and (type(cap) is not int or cap <= 0):
        raise _refuse(
            "config_wrong_type",
            "supervised_implementer.max_output_tokens must be null or a positive integer.",
        )
    return SupervisedImplementerSettings(
        candidate=candidate,
        model=expected_model,
        provider=config.provider,
        allow_insecure_http=config.allow_insecure_http,
        structured_output=config.structured_output,
        max_output_tokens=cap,
    )


def check_supervised_implementer_endpoint(
    base_url: str, *, allow_insecure_http: bool
) -> tuple[str, str]:
    """Return ``(scheme, host)`` for a permitted endpoint, or refuse.

    ``https`` is permitted. ``http`` is permitted only with the project's
    explicit plaintext acknowledgement, for **every** provider. Any other
    scheme, a missing host, or credentials embedded in the URL are refused.
    The URL itself is never echoed.
    """
    if type(base_url) is not str:
        raise _refuse("endpoint_invalid", "the endpoint base URL is not a string.")
    try:
        parts = urlsplit(base_url.strip())
        host = parts.hostname
    except ValueError:
        raise _refuse("endpoint_invalid", "the endpoint base URL could not be parsed.") from None
    if parts.username is not None or parts.password is not None:
        raise _refuse(
            "endpoint_embeds_credentials",
            "the endpoint base URL embeds credentials; they belong in the "
            "environment, never in a URL. The URL is not echoed.",
        )
    if not host:
        raise _refuse("endpoint_invalid", "the endpoint base URL names no host.")
    if parts.scheme == "https":
        return "https", host
    if parts.scheme == "http":
        if allow_insecure_http is not True:
            raise _refuse(
                "insecure_http_refused",
                f"the endpoint at host {host!r} uses PLAINTEXT HTTP and this "
                "project has not set supervised_implementer.allow_insecure_http. "
                "No source was sent.",
            )
        return "http", host
    raise _refuse("endpoint_invalid", "the endpoint scheme must be exactly 'https' or 'http'.")


def _sha256_of_utf8(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _private_copies(
    project: object, approved_plan: object
) -> tuple[ProjectConfig, ApprovedL1PlanArtifact]:
    """Re-validate both inputs into private copies, so later mutation cannot reach them.

    This discards anything assembled with ``model_construct`` or changed after
    the caller validated it, and it means a caller cannot change the plan or
    the config while this function is running.
    """
    if not isinstance(project, ProjectConfig):
        raise _refuse("project_wrong_type", "project must be a ProjectConfig.")
    if not isinstance(approved_plan, ApprovedL1PlanArtifact):
        raise _refuse("approved_plan_wrong_type", "approved_plan must be an ApprovedL1PlanArtifact.")
    # ValueError also covers a serialization failure of a forged object.
    try:
        project_copy = ProjectConfig.model_validate_json(project.model_dump_json())
    except (ValidationError, ValueError) as exc:
        raise _refuse(
            "project_revalidation_failed",
            _summarize_validation_error(exc)
            if isinstance(exc, ValidationError)
            else "the project config could not be serialized.",
        ) from None
    try:
        plan_copy = ApprovedL1PlanArtifact.model_validate_json(
            approved_plan.model_dump_json()
        )
    except (ValidationError, ValueError) as exc:
        raise _refuse(
            "approved_plan_revalidation_failed",
            _summarize_validation_error(exc)
            if isinstance(exc, ValidationError)
            else "the approved plan could not be serialized.",
        ) from None
    return project_copy, plan_copy


def _check_target_path(
    target_path: object, approved_plan: ApprovedL1PlanArtifact, project: ProjectConfig
) -> str:
    """The caller names the one target; the model never does. Refuse anything not plainly in scope."""
    from ai_dev_orchestrator.workspace import PathClassification, PathPolicy

    if type(target_path) is not str:
        raise _refuse("target_path_invalid", "target_path must be a string.")
    try:
        _require_safe_relative_repo_path(target_path, "target_path")
    except ValueError as exc:
        raise _refuse("target_path_invalid", str(exc)) from None
    plan = approved_plan.plan
    if target_path in plan.files_forbidden_or_out_of_scope:
        raise _refuse(
            "target_out_of_scope",
            f"{target_path!r} is listed as forbidden or out of scope by the approved plan.",
        )
    if target_path not in plan.files_likely_to_change:
        raise _refuse(
            "target_out_of_scope",
            f"{target_path!r} is not in the approved plan's files_likely_to_change.",
        )
    decision = PathPolicy.from_project_config(project).check_write(target_path)
    if decision.classification is not PathClassification.ALLOWED or decision.permitted is not True:
        raise _refuse(
            "target_not_writable",
            f"{target_path!r} is classified {decision.classification.value} by the "
            "project's path policy. Only an ALLOWED, writable path's source may be "
            "sent; protected paths are never sent.",
        )
    if decision.path != target_path:
        raise _refuse(
            "target_path_not_normal",
            f"{target_path!r} is not in its normalized form; name the path exactly.",
        )
    return target_path


def _check_identity(approved_plan: ApprovedL1PlanArtifact, project: ProjectConfig) -> None:
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
        raise _refuse(
            "identity_mismatch",
            "the approved plan does not match this project config exactly; "
            "mismatched fields: " + ", ".join(mismatched) + ".",
        )


def _target_item(items: tuple[dict, ...], target_path: str) -> dict:
    matching = [item for item in items if item.get("original_plan_path") == target_path]
    if len(matching) != 1:
        raise _refuse("target_not_read", f"{target_path!r} has no unique read result.")
    item = matching[0]
    if item.get("status") != "read" or item.get("kind") != "file":
        raise _refuse(
            "target_not_read",
            f"{target_path!r} was not read as a regular file (status "
            f"{item.get('status')!r}). Only an existing file can be modified, and "
            "nothing was sent.",
        )
    if item.get("redacted") is not False or item.get("redaction_count") != 0:
        raise _refuse(
            "target_redacted",
            f"{target_path!r} contains secret-like text that the bounded read "
            "redacted. Its source is never sent to a model, and a diff from "
            "redacted text would be refused anyway. Nothing was sent.",
        )
    if item.get("canonical_relative_path") != target_path:
        raise _refuse(
            "target_canonical_mismatch",
            f"{target_path!r} resolved on disk to a different relative spelling. "
            "Name the path exactly as it exists. Nothing was sent.",
        )
    if type(item.get("content_text")) is not str:
        raise _refuse("target_not_read", f"{target_path!r} carries no text.")
    return item


def _writer_text_domain_lines(original_text: str, target_path: str) -> tuple[str, list[str]]:
    """Refuse, before anything is sent, a file the 5F2C writer could never modify.

    The writer accepts only uniform LF or uniform CRLF text that ends with a
    terminal newline, and it rejoins lines itself. Sending a file outside that
    domain would produce a proposal no approval could ever apply. These are the
    writer's own pure text helpers, imported here so the rule cannot drift.
    Nothing that writes is called.
    """
    from ai_dev_orchestrator.file_editing.writer import (
        WorkspaceWriteRefusedError,
        _detect_uniform_line_ending,
        _split_content_lines,
    )

    try:
        ending = _detect_uniform_line_ending(original_text)
        return ending, _split_content_lines(original_text, ending)
    except WorkspaceWriteRefusedError:
        raise _refuse(
            "target_outside_writer_domain",
            f"{target_path!r} is not uniform-LF or uniform-CRLF text ending in a "
            "newline, so the single-file writer could never apply a change to it. "
            "Nothing was sent.",
        ) from None


def _check_post_image_reachable(
    *,
    ending: str,
    original_lines: list[str],
    unified_diff: str,
    target_path: str,
    post_image_sha256: str,
) -> None:
    """Prove in memory that the writer's exact rules turn this diff into the proposed bytes.

    The same strict applier and the same rejoin the 5F2C writer uses, applied to
    the recorded pre-image. If the result does not hash to the proposed
    post-image, then the diff a human would approve cannot produce the content
    the model proposed. The usual cause is a dropped or added final newline, or
    a changed line ending, which a unified diff over lines cannot express. That
    is refused here, before approval, rather than discovered by the writer
    afterwards.
    """
    from ai_dev_orchestrator.file_editing.diff_apply import (
        StrictDiffApplyError,
        apply_strict_unified_diff,
    )
    from ai_dev_orchestrator.file_editing.writer import _join_content_lines

    try:
        post_lines = apply_strict_unified_diff(
            original_lines=original_lines, unified_diff=unified_diff, path=target_path
        )
    except StrictDiffApplyError:
        raise SupervisedImplementerOutputRejected(
            "post_image_unreachable",
            "the generated diff does not apply exactly to the recorded pre-image.",
        ) from None
    if _sha256_of_utf8(_join_content_lines(post_lines, ending)) != post_image_sha256:
        raise SupervisedImplementerOutputRejected(
            "post_image_unreachable",
            "applying the diff with the writer's exact rules does not reproduce the "
            "proposed content. Its final newline or line endings differ from the "
            "file's, which a unified diff cannot express. It was rejected, not "
            "normalized.",
        )


def _usage(response: LLMResponse) -> ReportedUsage | None:
    if response.usage is None:
        return None
    return ReportedUsage(
        prompt_tokens=response.usage.prompt_tokens,
        completion_tokens=response.usage.completion_tokens,
        total_tokens=response.usage.total_tokens,
    )


def run_supervised_implementer_offline(
    *,
    project: ProjectConfig,
    approved_plan: ApprovedL1PlanArtifact,
    target_path: str,
    client_config: LLMClientConfig,
    transport: httpx.MockTransport,
    transmit_source: bool,
    announce: Callable[[SourceTransmissionNotice], None],
) -> SupervisedImplementerResult:
    """Ask the supervised candidate for one file's final text, and stop at human approval.

    Args:
        project: The loaded project config. Re-validated into a private copy.
        approved_plan: The human-approved L1 plan. Re-validated into a private copy.
        target_path: The one repo-relative path to modify, chosen by the caller
            (a human), never by the model. It must be in
            ``files_likely_to_change``, not out of scope, and ALLOWED for write.
        client_config: Connection settings. Its ``max_retries`` is overridden
            to zero, and the model always comes from the project config.
        transport: Must be exactly an ``httpx.MockTransport`` in ALPHA-P1A.
            Its handler is trusted caller code; this gate does not confine it.
        transmit_source: Explicit consent to send the one approved file. Must be
            exactly ``True``.
        announce: Called with the transmission notice **before** the request is
            handed to the transport. If it raises, nothing is sent.

    Returns:
        A :class:`SupervisedImplementerResult`: a Phase 5E2 diff proposal (or a
        no-change outcome) plus its content provenance. It contains no approval,
        and nothing has been written.

    Raises:
        SupervisedImplementerRefused: a gate refused; no request was handed over.
        SupervisedImplementerTransportFailed: the one request failed. Terminal.
        SupervisedImplementerOutputRejected: a reply was received and rejected.
    """
    # 1. Explicit consent, and the offline restriction, before anything is read.
    if transmit_source is not True:
        raise _refuse(
            "consent_missing",
            "sending an approved file to a model requires transmit_source=True "
            "exactly. Nothing was read or sent.",
        )
    if type(transport) is not OFFLINE_TRANSPORT_TYPE:
        raise _refuse(
            "live_transport_refused",
            "ALPHA-P1A is offline-only: the transport must be exactly an "
            "httpx.MockTransport. A live request needs its own separate "
            "authorization. Nothing was read or sent.",
        )
    if not callable(announce):
        raise _refuse("announce_missing", "a transmission announcement callback is required.")
    if not isinstance(client_config, LLMClientConfig):
        raise _refuse("client_config_wrong_type", "client_config must be an LLMClientConfig.")

    # 2. Private, re-validated copies; then the config gate and the endpoint gate.
    #    The client config is copied too, and the client is built from the
    #    checked copy, so nothing the caller does later (including from inside
    #    `announce`) can redirect the request away from the host that passed.
    project, approved_plan = _private_copies(project, approved_plan)
    settings = check_supervised_implementer_gate(project.supervised_implementer)
    try:
        client_config = LLMClientConfig.model_validate(
            {
                **client_config.model_dump(),
                "max_retries": TRANSPORT_MAX_RETRIES,
                "default_model": settings.model,
            }
        )
    except ValidationError:
        raise _refuse(
            "client_config_invalid", "client_config failed validation; no value is echoed."
        ) from None
    scheme, host = check_supervised_implementer_endpoint(
        client_config.base_url, allow_insecure_http=settings.allow_insecure_http
    )
    client = LLMClient(client_config, transport=transport)

    # 3. Identity, then the target path, all before any disk access.
    _check_identity(approved_plan, project)
    target_path = _check_target_path(target_path, approved_plan, project)

    # 4. The shipped Phase 5D2 bounded read, in-process, behind its own opt-in.
    try:
        read = read_approved_plan_workspace_contents(project=project, artifact=approved_plan)
    except WorkspaceContentReadRefused as exc:
        raise _refuse("workspace_read_refused", exc.lines[0] if exc.lines else "refused") from None
    item = _target_item(read.items, target_path)
    original_text: str = item["content_text"]
    ending, original_lines = _writer_text_domain_lines(original_text, target_path)
    source_sha256 = _sha256_of_utf8(original_text)
    source_bytes = len(original_text.encode("utf-8"))

    # 5. Build the one request, then announce it before handing it over.
    request = build_supervised_implementer_request(
        approved_plan=approved_plan,
        target_path=target_path,
        current_text=original_text,
        model=settings.model,
        max_output_tokens=settings.max_output_tokens,
        structured_output=settings.structured_output,
    )
    messages_sha256 = request_messages_sha256(request)
    announce(
        SourceTransmissionNotice(
            target_path=target_path,
            source_bytes=source_bytes,
            source_sha256=source_sha256,
            candidate=settings.candidate,
            model=settings.model,
            provider=settings.provider,
            endpoint_scheme=scheme,
            endpoint_host=host,
            transport_tls=scheme == "https",
            transport_kind=TRANSPORT_KIND,
        )
    )

    # 6. Exactly one request, zero transport retries, no fallback.
    try:
        response = client.chat(request)
    except LLMClientError as exc:
        raise SupervisedImplementerTransportFailed(
            "transport_failed",
            f"the single request failed ({type(exc).__name__}). It is terminal: "
            "no retry and no fallback was attempted.",
        ) from None

    # 7. The reply is untrusted. Check what AIDO can observe, then parse strictly.
    if response.model != settings.model:
        raise SupervisedImplementerOutputRejected(
            "model_substitution",
            "the reply names a different model than the one requested. It was "
            "rejected; no substitute is ever accepted.",
        )
    if response.finish_reason != "stop":
        raise SupervisedImplementerOutputRejected(
            "incomplete_reply",
            f"the reply's finish_reason was {response.finish_reason!r}, not "
            "'stop', so it may be truncated. It was rejected, not retried.",
        )
    output = parse_supervised_implementer_output(response.content)
    proposed_text = output.content_text

    # 8. AIDO assembles proposed-content.v1 itself. The path, change type and
    #    prose come from AIDO; only content_text came from the model.
    fixed = {"candidate": settings.candidate, "model": settings.model}
    try:
        proposed_content = ProposedContentInput.model_validate(
            {
                "schema_version": "proposed-content.v1",
                "mode": "proposal-only",
                "changes": [
                    {
                        "path": target_path,
                        "change_type": "modify",
                        "content_text": proposed_text,
                        "rationale": _RATIONALE_TEMPLATE.format(**fixed),
                        "risks": [_RISK_TEXT],
                        "requires_human_review": True,
                    }
                ],
                "assumptions": [_ASSUMPTION_TEMPLATE.format(**fixed)],
                "risks": [],
                "open_questions": [],
                "requires_human_review": True,
                "next_authorization_required": _NEXT_AUTHORIZATION,
            }
        )
        packet = WorkspaceContentPacket.model_validate(
            {
                "mode": WORKSPACE_CONTENT_MODE,
                "project": {
                    "project_id": project.project_id,
                    "repo": project.repo.github_repo,
                },
                "approved_plan": {
                    "issue_number": approved_plan.issue_number,
                    "title": approved_plan.plan.title,
                },
                "workspace_content": {
                    "candidate_source": WORKSPACE_CONTENT_CANDIDATE_SOURCE,
                    "file_contents_read": True,
                    "directories_listed": False,
                    "commands_run": False,
                    "model_called": False,
                    "diffs_generated": False,
                    "files_edited": False,
                    "items": [dict(item)],
                },
            }
        )
    except ValidationError as exc:
        raise SupervisedImplementerOutputRejected(
            "proposed_content_invalid", _summarize_validation_error(exc)
        ) from None

    # 9. The existing deterministic diff generator, with every 5E3 rule.
    try:
        diff_proposal = build_deterministic_diff_proposal(
            approved_plan=approved_plan,
            project=project,
            workspace_content=packet,
            proposed_content=proposed_content,
        )
    except DiffProposalGenerationError as exc:
        raise SupervisedImplementerOutputRejected("diff_generation_refused", str(exc)) from None

    proposed_sha256 = _sha256_of_utf8(proposed_text)
    outcome = "diff_proposed" if diff_proposal.changes else "no_change_proposed"
    if outcome == "diff_proposed":
        _check_post_image_reachable(
            ending=ending,
            original_lines=original_lines,
            unified_diff=diff_proposal.changes[0].unified_diff,
            target_path=target_path,
            post_image_sha256=diff_proposal.changes[0].post_image_sha256,
        )
    elif proposed_sha256 != source_sha256:
        raise SupervisedImplementerOutputRejected(
            "post_image_unreachable",
            "the proposed content differs from the file only in its final newline "
            "or line endings, which a unified diff cannot express. It was "
            "rejected, not normalized.",
        )

    # 10. Provenance, cross-checked against the diff on construction. STOP here.
    try:
        return SupervisedImplementerResult(
            diff_proposal=diff_proposal,
            provenance=SupervisedImplementerProvenance(
                schema_version=PROVENANCE_SCHEMA_VERSION,
                role=SUPERVISED_IMPLEMENTER_ROLE,
                candidate=settings.candidate,
                model=settings.model,
                model_source=MODEL_SOURCE,
                response_model_field=response.model,
                provider=settings.provider,
                endpoint_scheme=scheme,
                endpoint_host=host,
                transport_tls=scheme == "https",
                transport_kind=TRANSPORT_KIND,
                qualification_credit=QUALIFICATION_CREDIT,
                autonomous_implementer_qualified=False,
                model_output_is_evidence=False,
                project_id=project.project_id,
                repo=project.repo.github_repo,
                issue_number=approved_plan.issue_number,
                target_path=target_path,
                change_type="modify",
                outcome=outcome,
                transmitted_file_count=1,
                transmitted_source_bytes=source_bytes,
                transmitted_source_sha256=source_sha256,
                request_messages_sha256=messages_sha256,
                response_content_sha256=_sha256_of_utf8(response.content),
                proposed_content_sha256=proposed_sha256,
                semantic_requests_issued=1,
                transport_max_retries=TRANSPORT_MAX_RETRIES,
                requested_max_output_tokens=settings.max_output_tokens,
                structured_output_mode=(
                    "json_schema" if settings.structured_output else "none"
                ),
                finish_reason="stop",
                usage_reported=_usage(response),
                orchestrator_approval_created=False,
                orchestrator_workspace_written=False,
                next_step=NEXT_STEP,
            ),
        )
    except ValidationError as exc:
        raise SupervisedImplementerOutputRejected(
            "result_inconsistent", _summarize_validation_error(exc)
        ) from None
