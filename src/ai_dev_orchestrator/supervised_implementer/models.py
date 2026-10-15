"""Typed models for the supervised implementer (ALPHA-P1A).

Four things live here:

- the **errors**, which say whether a request was ever handed to the transport
  (``transmission_attempted``), so a failure report never overstates or
  understates what left AIDO;
- :class:`SupervisedImplementerOutput` and its strict parser, the only shape a
  model reply may take — exactly ``{"content_text": "<final file text>"}``. The
  model cannot name a path, a change type, a review flag, a rationale or
  anything else;
- :class:`SourceTransmissionNotice`, announced to the operator **before** the
  request is handed to the transport;
- :class:`SupervisedImplementerProvenance` and
  :class:`SupervisedImplementerResult`, the record that the proposed content was
  model-authored (DEC-SUP item 6), bound by digest to the diff proposal it
  produced.

Every model is ``frozen`` and ``extra="forbid"``. Booleans and fixed facts are
``Literal`` types, so neither Python truthiness nor a forged field can flip a
fact.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, model_validator

from ai_dev_orchestrator.diff_proposal.generator import MAX_PROPOSED_CONTENT_CHARS
from ai_dev_orchestrator.diff_proposal.models import (
    DiffProposalArtifact,
    _summarize_validation_error,
)

PROVENANCE_SCHEMA_VERSION = "supervised-implementer-provenance.v1"

#: The one place a supervised-implementer model may be named.
MODEL_SOURCE = "project_config.supervised_implementer.model"

#: What the human must do next. AIDO never creates the approval itself.
NEXT_STEP = "human_exact_diff_approval_required"


class SupervisedImplementerError(Exception):
    """The supervised implementer produced nothing usable, and nothing was written.

    ``category`` is a short stable token. ``transmission_attempted`` is ``True``
    exactly when the request was handed to the transport. It does not say
    whether bytes reached a server; that is outside AIDO's observation.
    Messages name a category and field names. They never echo source text,
    proposed content, the reply, a base URL, or a credential.
    """

    transmission_attempted: bool = False

    def __init__(self, category: str, message: str) -> None:
        super().__init__(f"{category}: {message}")
        self.category = category


class SupervisedImplementerRefused(SupervisedImplementerError):
    """A gate refused before any request was handed to the transport."""

    transmission_attempted = False


class SupervisedImplementerTransportFailed(SupervisedImplementerError):
    """The single request failed at the transport or the HTTP layer.

    Terminal: there is no retry and no fallback.
    """

    transmission_attempted = True


class SupervisedImplementerOutputRejected(SupervisedImplementerError):
    """A reply was received and rejected. It is never repaired, and never retried."""

    transmission_attempted = True


class SupervisedImplementerOutput(BaseModel):
    """The entire reply contract: the complete final text of the one target file.

    Strict mode means a number, ``null`` or a list is not coerced into a
    string. ``extra="forbid"`` means a reply that also names a ``path``,
    ``change_type``, ``rationale``, ``approved`` flag or anything else is
    rejected whole.
    """

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    content_text: str

    @field_validator("content_text")
    @classmethod
    def _bounded_text(cls, value: str) -> str:
        if len(value) > MAX_PROPOSED_CONTENT_CHARS:
            raise ValueError(
                "content_text exceeds the maximum of "
                f"{MAX_PROPOSED_CONTENT_CHARS} characters."
            )
        if "\x00" in value:
            raise ValueError("content_text must not contain a NUL character.")
        try:
            value.encode("utf-8")
        except UnicodeEncodeError:
            # A lone surrogate escape (e.g. "\\ud800") decodes from JSON but is
            # not text any real UTF-8 file can hold.
            raise ValueError("content_text is not encodable as UTF-8.") from None
        return value


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    keys = [key for key, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate key")
    return dict(pairs)


def parse_supervised_implementer_output(text: str) -> SupervisedImplementerOutput:
    """Parse a reply as exactly one strict JSON object. Rejects, never repairs.

    Surrounding whitespace is tolerated. Anything else is refused: a markdown
    fence, prose before or after the object, an array, a scalar, a duplicate
    key, an extra key, or a non-string ``content_text``.

    Raises:
        SupervisedImplementerOutputRejected: the reply is not acceptable. The
            reply text is never echoed.
    """
    if not isinstance(text, str):
        raise SupervisedImplementerOutputRejected(
            "output_not_text", "the reply content was not a string."
        )
    stripped = text.strip()
    if not stripped:
        raise SupervisedImplementerOutputRejected(
            "output_empty", "the reply content was empty."
        )
    if not (stripped.startswith("{") and stripped.endswith("}")):
        raise SupervisedImplementerOutputRejected(
            "output_not_bare_json_object",
            "the reply must be exactly one JSON object with no markdown fence, "
            "prose, or other content around it. It was rejected, not repaired.",
        )
    try:
        decoded = json.loads(stripped, object_pairs_hook=_reject_duplicate_keys)
    except (ValueError, RecursionError):
        raise SupervisedImplementerOutputRejected(
            "output_invalid_json",
            "the reply is not valid JSON, or repeats a key. It was rejected, not "
            "repaired.",
        ) from None
    if not isinstance(decoded, dict):
        raise SupervisedImplementerOutputRejected(
            "output_not_json_object", "the reply must be a JSON object."
        )
    try:
        return SupervisedImplementerOutput.model_validate(decoded)
    except ValidationError as exc:
        raise SupervisedImplementerOutputRejected(
            "output_schema_violation",
            "the reply failed the output contract: "
            + _summarize_validation_error(exc),
        ) from None


@dataclass(frozen=True)
class SourceTransmissionNotice:
    """What is about to be sent, and where. Announced before the request is handed over.

    Names the one file and its size and digest, the candidate, the model, the
    provider, and the endpoint **host and scheme only**. It never carries the
    file text, the base URL, a path or query, or a credential.
    """

    target_path: str
    source_bytes: int
    source_sha256: str
    candidate: str
    model: str
    provider: str
    endpoint_scheme: str
    endpoint_host: str
    transport_tls: bool
    transport_kind: str

    def render(self) -> str:
        transport = (
            "TLS (https)"
            if self.transport_tls
            else "PLAINTEXT HTTP — NOT TLS-ENCRYPTED (project acknowledged)"
        )
        return (
            "SUPERVISED IMPLEMENTER SOURCE TRANSMISSION: 1 approved file "
            f"{self.target_path!r} ({self.source_bytes} bytes, sha256 "
            f"{self.source_sha256}) is about to be sent to candidate "
            f"{self.candidate} / model {self.model} via provider {self.provider} "
            f"at host {self.endpoint_host!r} over {transport}. Transport: "
            f"{self.transport_kind}. The reply is untrusted proposed content; "
            "nothing is written without a separate exact human diff approval."
        )


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ReportedUsage(_Frozen):
    """Token usage exactly as the provider reported it (absent means unknown, never zero)."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class SupervisedImplementerProvenance(_Frozen):
    """The record that a model, not a human, authored the proposed content.

    It sits beside the diff proposal (DEC-SUP item 6). The Phase 5E2 artifact's
    own ``provenance`` truthfully describes the *diff generator*
    (``engine="deterministic"``, ``model=None``). This record describes where
    the *content* came from.

    It states what AIDO requested and observed. It is **not** evidence that the
    content is correct, that it was verified, or that the server honoured
    ``response_format``, and it confers no qualification of any kind.
    """

    schema_version: Literal["supervised-implementer-provenance.v1"]
    role: Literal["supervised_implementer"]
    candidate: Literal["SUP-D"]
    model: Literal["qwen3.8-27b"]
    model_source: Literal["project_config.supervised_implementer.model"]
    #: The ``model`` field of the normalized reply. The shipped client falls
    #: back to the requested name when a server omits it, so equality here does
    #: not prove the server named the model.
    response_model_field: str
    provider: Literal["litellm", "vllm"]
    endpoint_scheme: Literal["http", "https"]
    endpoint_host: str
    transport_tls: bool
    transport_kind: Literal["offline_mock"]
    qualification_credit: Literal["none"]
    autonomous_implementer_qualified: Literal[False]
    model_output_is_evidence: Literal[False]

    project_id: str
    repo: str
    issue_number: int
    target_path: str
    change_type: Literal["modify"]
    outcome: Literal["diff_proposed", "no_change_proposed"]

    transmitted_file_count: Literal[1]
    transmitted_source_bytes: int
    transmitted_source_sha256: str
    request_messages_sha256: str
    response_content_sha256: str
    proposed_content_sha256: str

    semantic_requests_issued: Literal[1]
    transport_max_retries: Literal[0]
    requested_max_output_tokens: int | None
    structured_output_mode: Literal["json_schema", "none"]
    finish_reason: Literal["stop"]
    usage_reported: ReportedUsage | None

    orchestrator_approval_created: Literal[False]
    orchestrator_workspace_written: Literal[False]
    next_step: Literal["human_exact_diff_approval_required"]


class SupervisedImplementerResult(_Frozen):
    """A diff proposal plus the provenance of its content, cross-checked by digest.

    Construction validates that the two agree. They must name the same project,
    repo, issue and path. A proposed diff must carry exactly one ``modify``
    whose pre-image and post-image digests are the transmitted source and the
    proposed content. A no-change outcome carries no diff and names the path in
    ``omitted_paths``. Two individually valid records that disagree cannot form
    a result.

    It holds no approval and grants none. The human approves the diff through
    the unchanged Phase 5F0 artifact.
    """

    diff_proposal: DiffProposalArtifact
    provenance: SupervisedImplementerProvenance

    @model_validator(mode="after")
    def _records_agree(self) -> SupervisedImplementerResult:
        diff = self.diff_proposal
        prov = self.provenance
        identity = diff.provenance
        if (
            identity.project_id != prov.project_id
            or identity.repo != prov.repo
            or identity.issue_number != prov.issue_number
        ):
            raise ValueError("diff proposal and provenance name different targets.")
        if identity.engine != "deterministic" or identity.real_call is not False:
            raise ValueError("the diff proposal was not produced by the deterministic generator.")

        if prov.outcome == "diff_proposed":
            if len(diff.changes) != 1 or diff.omitted_paths:
                raise ValueError("a proposed diff must carry exactly one change.")
            change = diff.changes[0]
            if (
                change.path != prov.target_path
                or change.change_type != "modify"
                or change.pre_image_sha256 != prov.transmitted_source_sha256
                or change.post_image_sha256 != prov.proposed_content_sha256
            ):
                raise ValueError("diff change and provenance disagree on path, type or digests.")
            if prov.proposed_content_sha256 == prov.transmitted_source_sha256:
                raise ValueError("a proposed diff cannot have identical pre- and post-images.")
        else:
            if diff.changes or list(diff.omitted_paths) != [prov.target_path]:
                raise ValueError("a no-change outcome must carry no diff and omit exactly the target.")
            if prov.proposed_content_sha256 != prov.transmitted_source_sha256:
                raise ValueError("a no-change outcome must propose the transmitted content unchanged.")
        return self


def revalidate_supervised_implementer_result(
    result: SupervisedImplementerResult,
) -> SupervisedImplementerResult:
    """Re-validate a result from its serialized form, at a consumption boundary.

    A JSON round trip discards anything a caller assembled with
    ``model_construct`` or changed after construction (a mutable nested list,
    for example), and runs every validator again, including the
    diff-to-provenance cross-check.

    Raises:
        SupervisedImplementerOutputRejected: the result does not re-validate.
    """
    if not isinstance(result, SupervisedImplementerResult):
        raise SupervisedImplementerOutputRejected(
            "result_wrong_type", "not a SupervisedImplementerResult."
        )
    try:
        return SupervisedImplementerResult.model_validate_json(result.model_dump_json())
    except (ValidationError, ValueError) as exc:
        detail = (
            _summarize_validation_error(exc)
            if isinstance(exc, ValidationError)
            else "serialization failed"
        )
        raise SupervisedImplementerOutputRejected(
            "result_revalidation_failed", detail
        ) from None
