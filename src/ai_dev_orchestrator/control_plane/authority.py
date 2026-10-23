"""DL-4A — authority records that a real integration must present.

DL-1 typed every authoritative input, but a type is not a provenance: any
in-process caller can construct a valid ``ProjectContractApproval``,
``HumanStepAcceptance``, ``VerificationObservation`` or Step Contract. This
module holds the records that DL-4A's **authority store** (a
:class:`~ai_dev_orchestrator.control_plane.store.ControlPlaneStore` opened
through an :class:`~ai_dev_orchestrator.control_plane.containment.AidoStateRoot`)
requires *in addition* to those types, and refuses without:

```text
ExecutionPolicy        the execution-affecting policy (review, human acceptance,
                       attempt budget); taken from a human-approved plan
                       activation, never from the caller who issues a contract
ApprovalChallenge      AIDO-issued, persisted, single-use, expiring, bound to one
                       subject digest
HumanAttestation       the human's answer to one challenge; accepted only when
                       an injected HumanAttestationVerifier (the EXTERNAL trust
                       source) says so, and consumed atomically
DispatchTicket         AIDO-issued, persisted, single-use permission to dispatch
                       ONE role for ONE persisted step version
BoundRoleOutput        a role output enveloped with the ticket it answers: the
                       Project Run, Step Run, contract, attempt and role
```

Nothing here is authority by construction either: every record is checked
against the store's persisted issuance at the consumption boundary. The frozen
DL-1 models are unchanged and still required; these are versioned additions.

The ``verification-result.v1`` reader below mirrors the shipped 5F2D report
shape without importing the verifier (this package must stay free of executing
modules). A test pins the mirror to the shipped model.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from enum import Enum
from typing import Annotated, Literal, Protocol

from pydantic import Field, StrictBool, StrictInt, field_validator, model_validator

from ai_dev_orchestrator.control_plane.models import (
    MAX_REF_CHARS,
    MAX_STEP_ATTEMPTS,
    REQUIRED_PROJECT_CONTRACT_APPROVAL_TEXT,
    REQUIRED_STEP_ACCEPTANCE_APPROVAL_TEXT,
    ImplementationReport,
    PlannerDecision,
    ReviewProposal,
    Sha256,
    StepState,
    VerificationObservation,
    VerificationOutcome,
    _aware,
    _hex64,
    _Strict,
    _text,
    canonical_json_bytes,
    is_hex32,
    model_sha256,
)
from ai_dev_orchestrator.control_plane.transitions import RefusalCode, TransitionRefused

EXECUTION_POLICY_SCHEMA_VERSION = "execution-policy.v1"
APPROVAL_CHALLENGE_SCHEMA_VERSION = "approval-challenge.v1"
HUMAN_ATTESTATION_SCHEMA_VERSION = "human-attestation.v1"
DISPATCH_TICKET_SCHEMA_VERSION = "dispatch-ticket.v1"
BOUND_ROLE_OUTPUT_SCHEMA_VERSION = "bound-role-output.v1"

REQUIRED_PLAN_ACTIVATION_APPROVAL_TEXT = (
    "I approve this execution plan, policy and target workspace for AIDO execution"
)

#: How long an approval challenge may be answered. Fixed, like P1B's window.
APPROVAL_CHALLENGE_TTL = timedelta(minutes=60)
MAX_ATTESTATION_PROOF_CHARS = 8_192
#: A transport-style bound on evidence bytes AIDO will read; never a token cap.
MAX_VERIFICATION_EVIDENCE_BYTES = 16 * 1024 * 1024


class AuthorityRefusedError(TransitionRefused):
    """DL-4A authority was not proven. Nothing was recorded or consumed."""

    def __init__(self, message: str) -> None:
        super().__init__(RefusalCode.AUTHORITY_UNPROVEN, message)


class EvidenceRefusedError(ValueError):
    """Bytes are not a well-formed, self-consistent ``verification-result.v1``."""


# --- execution policy -----------------------------------------------------------


class ExecutionPolicy(_Strict):
    """The execution-affecting policy every Step Contract of one plan carries.

    It is approved by a human together with the plan and the target workspace
    (a ``plan_activation`` subject), and the authority store copies it into
    each issued Step Contract. A caller issuing a contract has no way to name
    any of these values.
    """

    schema_version: Literal["execution-policy.v1"]
    review_required: StrictBool
    human_acceptance_required: StrictBool
    max_attempts: Annotated[StrictInt, Field(ge=1, le=MAX_STEP_ATTEMPTS)]

    @property
    def sha256(self) -> str:
        return model_sha256(self)


# --- human approval -------------------------------------------------------------


class ApprovalSubjectKind(str, Enum):
    PROJECT_CONTRACT = "project_contract"
    PLAN_ACTIVATION = "plan_activation"
    STEP_ACCEPTANCE = "step_acceptance"


#: The exact sentence a human must write for each subject. Compared with ``==``.
APPROVAL_TEXT: dict[ApprovalSubjectKind, str] = {
    ApprovalSubjectKind.PROJECT_CONTRACT: REQUIRED_PROJECT_CONTRACT_APPROVAL_TEXT,
    ApprovalSubjectKind.PLAN_ACTIVATION: REQUIRED_PLAN_ACTIVATION_APPROVAL_TEXT,
    ApprovalSubjectKind.STEP_ACCEPTANCE: REQUIRED_STEP_ACCEPTANCE_APPROVAL_TEXT,
}


def _hex32(value: str, field_name: str) -> str:
    if not is_hex32(value):
        raise ValueError(f"{field_name} must be 32 lowercase hexadecimal characters.")
    return value


class ApprovalChallenge(_Strict):
    """An AIDO-issued request for one human approval of one subject digest."""

    schema_version: Literal["approval-challenge.v1"]
    challenge_id: str
    subject_kind: ApprovalSubjectKind
    subject_sha256: Sha256
    issued_at: datetime
    expires_at: datetime
    required_approval_text: str

    @field_validator("challenge_id")
    @classmethod
    def _id(cls, value: str) -> str:
        return _hex32(value, "challenge_id")

    @field_validator("subject_sha256")
    @classmethod
    def _subject(cls, value: str) -> str:
        return _hex64(value, "subject_sha256")

    @field_validator("issued_at", "expires_at")
    @classmethod
    def _times(cls, value: datetime, info) -> datetime:
        return _aware(value, info.field_name)

    @model_validator(mode="after")
    def _shape(self) -> ApprovalChallenge:
        if self.required_approval_text != APPROVAL_TEXT[self.subject_kind]:
            raise ValueError("required_approval_text is not this subject kind's phrase.")
        if self.expires_at <= self.issued_at:
            raise ValueError("expires_at must be after issued_at.")
        return self


class HumanAttestation(_Strict):
    """A human's answer to one :class:`ApprovalChallenge`.

    ``proof`` is opaque to AIDO. Only the injected
    :class:`HumanAttestationVerifier` interprets it, and that verifier is the
    external trust source: AIDO cannot itself tell a human from code that can
    run in its process.
    """

    schema_version: Literal["human-attestation.v1"]
    challenge_id: str
    subject_kind: ApprovalSubjectKind
    subject_sha256: Sha256
    approver_id: str
    attested_at: datetime
    approval_text: str
    proof: str

    @field_validator("challenge_id")
    @classmethod
    def _id(cls, value: str) -> str:
        return _hex32(value, "challenge_id")

    @field_validator("subject_sha256")
    @classmethod
    def _subject(cls, value: str) -> str:
        return _hex64(value, "subject_sha256")

    @field_validator("approver_id")
    @classmethod
    def _approver(cls, value: str) -> str:
        return _text(value, "approver_id", MAX_REF_CHARS)

    @field_validator("attested_at")
    @classmethod
    def _attested_at(cls, value: datetime) -> datetime:
        return _aware(value, "attested_at")

    @field_validator("proof")
    @classmethod
    def _proof(cls, value: str) -> str:
        return _text(value, "proof", MAX_ATTESTATION_PROOF_CHARS)

    @model_validator(mode="after")
    def _phrase(self) -> HumanAttestation:
        if self.approval_text != APPROVAL_TEXT[self.subject_kind]:
            raise ValueError(
                "approval_text must match the required approval phrase exactly; "
                "a paraphrase is not approval."
            )
        return self

    @property
    def sha256(self) -> str:
        return model_sha256(self)


class HumanAttestationVerifier(Protocol):
    """The external trust source for human approval.

    Return exactly ``True`` only when ``attestation`` provably came from an
    authorized human for exactly ``challenge``. Any other return value, and any
    exception, is a refusal. A real implementation must rest on something the
    AIDO process itself cannot produce (see ``docs/DL4A_REAL_INTEGRATION_AUTHORITY.md``).
    """

    def verify(self, *, challenge: ApprovalChallenge, attestation: HumanAttestation) -> bool: ...


class UnavailableHumanAttestationVerifier:
    """The default. There is no human attestation source, so nothing is approved."""

    def verify(self, *, challenge: ApprovalChallenge, attestation: HumanAttestation) -> bool:
        return False


def plan_activation_subject_sha256(
    *,
    project_contract_sha256: str,
    execution_plan_sha256: str,
    execution_policy_sha256: str,
    target_workspace_sha256: str,
) -> str:
    """The digest a human approves to activate one plan, policy and workspace."""
    return hashlib.sha256(canonical_json_bytes({
        "kind": ApprovalSubjectKind.PLAN_ACTIVATION.value,
        "project_contract_sha256": project_contract_sha256,
        "execution_plan_sha256": execution_plan_sha256,
        "execution_policy_sha256": execution_policy_sha256,
        "target_workspace_sha256": target_workspace_sha256,
    })).hexdigest()


def step_acceptance_subject_sha256(
    *,
    project_run_id: str,
    step_run_id: str,
    step_contract_sha256: str,
    attempt: int,
    state_version: int,
    verification_evidence_sha256: str,
) -> str:
    """The digest a human approves to accept one step attempt at one version."""
    return hashlib.sha256(canonical_json_bytes({
        "kind": ApprovalSubjectKind.STEP_ACCEPTANCE.value,
        "project_run_id": project_run_id,
        "step_run_id": step_run_id,
        "step_contract_sha256": step_contract_sha256,
        "attempt": attempt,
        "state_version": state_version,
        "verification_evidence_sha256": verification_evidence_sha256,
    })).hexdigest()


# --- role-output identity binding -----------------------------------------------

Role = Literal["implementer", "verifier", "reviewer", "planner"]

#: The one step state each role may be dispatched from.
ROLE_STATE: dict[str, StepState] = {
    "implementer": StepState.EXECUTING,
    "verifier": StepState.VERIFYING,
    "reviewer": StepState.REVIEWING,
    "planner": StepState.ACCEPTANCE,
}

ROLE_OUTPUT_TYPES: dict[str, type] = {
    "implementer": ImplementationReport,
    "verifier": VerificationObservation,
    "reviewer": ReviewProposal,
    "planner": PlannerDecision,
}


class DispatchTicket(_Strict):
    """AIDO's single-use permission to dispatch one role for one step version.

    Issued and persisted by the authority store before the role is called, at
    most once per ``(step_run_id, state_version, role)``, and consumed in the
    same transaction that records the role's output.
    """

    schema_version: Literal["dispatch-ticket.v1"]
    ticket_id: str
    project_run_id: str
    step_run_id: str
    step_contract_sha256: Sha256
    attempt: Annotated[StrictInt, Field(ge=1, le=MAX_STEP_ATTEMPTS)]
    role: Role
    step_state: StepState
    state_version: Annotated[StrictInt, Field(ge=0)]
    issued_at: datetime

    @field_validator("ticket_id", "project_run_id", "step_run_id")
    @classmethod
    def _ids(cls, value: str, info) -> str:
        return _hex32(value, info.field_name)

    @field_validator("step_contract_sha256")
    @classmethod
    def _contract(cls, value: str) -> str:
        return _hex64(value, "step_contract_sha256")

    @field_validator("issued_at")
    @classmethod
    def _issued_at(cls, value: datetime) -> datetime:
        return _aware(value, "issued_at")

    @model_validator(mode="after")
    def _role_state(self) -> DispatchTicket:
        if ROLE_STATE[self.role] is not self.step_state:
            raise ValueError(f"a {self.role} is dispatched only from {ROLE_STATE[self.role].value}.")
        return self


RoleOutput = ImplementationReport | VerificationObservation | ReviewProposal | PlannerDecision


class BoundRoleOutput(_Strict):
    """A role output bound to the exact dispatch it answers.

    The frozen DL-1 outputs name only ``(step_contract_sha256, attempt)``, which
    two runs of one contract share. This envelope adds the Project Run, the Step
    Run, the role and the unpredictable ``ticket_id`` AIDO issued for this
    dispatch, so a structurally valid output from another run, another step,
    another version or another dispatch cannot be consumed.
    """

    schema_version: Literal["bound-role-output.v1"]
    ticket_id: str
    project_run_id: str
    step_run_id: str
    step_contract_sha256: Sha256
    attempt: Annotated[StrictInt, Field(ge=1, le=MAX_STEP_ATTEMPTS)]
    role: Role
    output: RoleOutput

    @field_validator("ticket_id", "project_run_id", "step_run_id")
    @classmethod
    def _ids(cls, value: str, info) -> str:
        return _hex32(value, info.field_name)

    @field_validator("step_contract_sha256")
    @classmethod
    def _contract(cls, value: str) -> str:
        return _hex64(value, "step_contract_sha256")

    @model_validator(mode="after")
    def _output_matches(self) -> BoundRoleOutput:
        if type(self.output) is not ROLE_OUTPUT_TYPES[self.role]:
            raise ValueError(f"a {self.role} output must be a {ROLE_OUTPUT_TYPES[self.role].__name__}.")
        if (
            self.output.step_contract_sha256 != self.step_contract_sha256
            or self.output.attempt != self.attempt
        ):
            raise ValueError("the output's own binding differs from the envelope's.")
        return self


def bind_role_output(ticket: DispatchTicket, output: RoleOutput) -> BoundRoleOutput:
    """Envelope ``output`` for ``ticket``. A convenience, never a check: the
    authority store re-proves every field against its persisted ticket."""
    return BoundRoleOutput(
        schema_version=BOUND_ROLE_OUTPUT_SCHEMA_VERSION,
        ticket_id=ticket.ticket_id,
        project_run_id=ticket.project_run_id,
        step_run_id=ticket.step_run_id,
        step_contract_sha256=ticket.step_contract_sha256,
        attempt=ticket.attempt,
        role=ticket.role,
        output=output,
    )


# --- verification-result.v1 (mirror of the shipped 5F2D report) -----------------

VERIFICATION_RESULT_SCHEMA_VERSION = "verification-result.v1"
VERIFICATION_RESULT_MODE = "controlled-verification"
#: The shipped ``VerificationResultReport`` fields, restated. Pinned by a test.
VERIFICATION_RESULT_FIELDS = frozenset({
    "schema_version", "mode", "outcome", "project_id", "repo", "issue_number", "title",
    "approved_by", "approved_at", "target", "command", "execution", "output",
    "workspace_precondition", "workspace_postcondition", "capability_boundaries",
    "single_actor_contract", "next_step",
})
#: The postcondition facts 5F2D's ``_build_report`` derives ``workspace_trusted`` from.
VERIFICATION_TRUST_FIELDS = (
    "exact_approved_target_still_present",
    "exact_post_image_still_matches",
    "head_unchanged",
    "only_approved_target_git_dirty",
    "git_state_reestablished",
)


class VerificationEvidenceReceipt(_Strict):
    """What the authority store recorded for one verifier dispatch: the digest
    of the exact ``verification-result.v1`` bytes and the outcome they prove."""

    evidence_sha256: Sha256
    outcome: VerificationOutcome


def _no_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise EvidenceRefusedError("verification evidence repeats a JSON key.")
        result[key] = value
    return result


def _no_constant(name: str) -> object:
    raise EvidenceRefusedError(f"verification evidence contains the non-JSON constant {name}.")


def verification_outcome_from_evidence(data: bytes) -> VerificationOutcome:
    """The outcome a ``verification-result.v1`` document proves, or a refusal.

    The outcome is not read on trust: it is re-derived from the document's own
    facts exactly as 5F2D derives it (an untrusted workspace outranks a failed
    run), and a document whose stated outcome disagrees is refused. The bytes
    are never repaired or normalized.
    """
    if type(data) is not bytes:
        raise EvidenceRefusedError("verification evidence must be bytes.")
    if len(data) > MAX_VERIFICATION_EVIDENCE_BYTES:
        raise EvidenceRefusedError("verification evidence exceeds the evidence size bound.")
    try:
        document = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_no_duplicate_keys,
            parse_constant=_no_constant,
        )
    except (UnicodeDecodeError, ValueError) as exc:
        raise EvidenceRefusedError("verification evidence is not UTF-8 JSON.") from exc
    if not isinstance(document, dict) or set(document) != VERIFICATION_RESULT_FIELDS:
        raise EvidenceRefusedError("verification evidence is not a verification-result.v1 object.")
    if (
        document["schema_version"] != VERIFICATION_RESULT_SCHEMA_VERSION
        or document["mode"] != VERIFICATION_RESULT_MODE
    ):
        raise EvidenceRefusedError("verification evidence has the wrong schema or mode.")
    outcome = document["outcome"]
    if outcome not in ("verified", "verification-failed", "workspace-state-untrusted"):
        raise EvidenceRefusedError("verification evidence has an unknown outcome.")
    execution = document["execution"]
    post = document["workspace_postcondition"]
    if not isinstance(execution, dict) or type(execution.get("passed")) is not bool:
        raise EvidenceRefusedError("verification evidence has no boolean execution.passed.")
    if not isinstance(post, dict) or any(type(post.get(f)) is not bool for f in VERIFICATION_TRUST_FIELDS):
        raise EvidenceRefusedError("verification evidence has no boolean postcondition facts.")
    if not all(post[f] for f in VERIFICATION_TRUST_FIELDS):
        derived = "workspace-state-untrusted"
    elif execution["passed"]:
        derived = "verified"
    else:
        derived = "verification-failed"
    if derived != outcome:
        raise EvidenceRefusedError(
            "verification evidence states an outcome its own facts do not support."
        )
    return outcome
