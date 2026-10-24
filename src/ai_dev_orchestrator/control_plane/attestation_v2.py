"""DL-4B S1 — versioned approval records for the integration store (store.v4).

DL-4A's ``approval-challenge.v1`` and ``human-attestation.v1`` close the subject
kinds over three values, and leave ``proof`` opaque. DL-4B needs a fourth kind
(``exact_diff_approval``) and a defined proof (an OpenSSH ``SSHSIG`` signature
from a FIDO2 security key, FD-1), so it versions both records rather than
widening the frozen ones (C-7). The v1 models are unchanged and still used by
every v2/v3 store; these are used by store.v4 only.

```text
ApprovalChallengeV2       AIDO-issued, single-use, exactly APPROVAL_CHALLENGE_TTL long
HumanAttestationV2        the human's answer; ``proof`` is an armored SSHSIG
AttestationStatementV1    the exact bytes the human's security key signs
```

The statement is never supplied by a caller. The verifier rebuilds it from the
store's own challenge, the store's state root id, the attestation and the
registry's key fingerprint, and checks the signature over those bytes. A
signature over any other bytes, a typed phrase, or a matching digest therefore
proves nothing.

This module is pure: it imports no executing, network or environment surface,
and it holds no verifier. The verifier is ``RegistryHumanAttestationVerifier``
in the A-side integration package, which this package never imports.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from ai_dev_orchestrator.control_plane.authority import (
    APPROVAL_CHALLENGE_TTL,
    MAX_ATTESTATION_PROOF_CHARS,
    REQUIRED_PLAN_ACTIVATION_APPROVAL_TEXT,
)
from ai_dev_orchestrator.control_plane.models import (
    MAX_REF_CHARS,
    REQUIRED_PROJECT_CONTRACT_APPROVAL_TEXT,
    REQUIRED_STEP_ACCEPTANCE_APPROVAL_TEXT,
    canonical_json_bytes,
    is_hex32,
)

APPROVAL_CHALLENGE_V2_SCHEMA_VERSION = "approval-challenge.v2"
HUMAN_ATTESTATION_V2_SCHEMA_VERSION = "human-attestation.v2"
ATTESTATION_STATEMENT_SCHEMA_VERSION = "attestation-statement.v1"

#: The SSHSIG namespace of every AIDO approval (FD-1). It keeps a git, login
#: or file signature made with the same key from counting as an approval.
ATTESTATION_NAMESPACE = "aido-approval@v1"

#: 5F2C's ``REQUIRED_DIFF_EDIT_APPROVAL_TEXT``, mirrored so that this package
#: imports no writer module. A test pins the mirror to the shipped constant.
REQUIRED_EXACT_DIFF_APPROVAL_TEXT = "I approve this diff proposal for workspace file editing"

#: ``SHA256:`` and the unpadded base64 of a SHA-256, as OpenSSH prints a key
#: fingerprint. The last character carries two zero bits, so only these 16
#: letters can end a canonical encoding.
_FINGERPRINT = re.compile(r"SHA256:[A-Za-z0-9+/]{42}[AEIMQUYcgkosw048]")
_HEX64 = re.compile(r"[0-9a-f]{64}")


class ApprovalSubjectKindV2(str, Enum):
    PROJECT_CONTRACT = "project_contract"
    PLAN_ACTIVATION = "plan_activation"
    STEP_ACCEPTANCE = "step_acceptance"
    EXACT_DIFF_APPROVAL = "exact_diff_approval"


#: The exact sentence a human must approve for each subject. Compared with ``==``.
APPROVAL_TEXT_V2: dict[ApprovalSubjectKindV2, str] = {
    ApprovalSubjectKindV2.PROJECT_CONTRACT: REQUIRED_PROJECT_CONTRACT_APPROVAL_TEXT,
    ApprovalSubjectKindV2.PLAN_ACTIVATION: REQUIRED_PLAN_ACTIVATION_APPROVAL_TEXT,
    ApprovalSubjectKindV2.STEP_ACCEPTANCE: REQUIRED_STEP_ACCEPTANCE_APPROVAL_TEXT,
    ApprovalSubjectKindV2.EXACT_DIFF_APPROVAL: REQUIRED_EXACT_DIFF_APPROVAL_TEXT,
}


def is_key_fingerprint(value: object) -> bool:
    """``value`` is an OpenSSH ``SHA256:`` fingerprint in its one canonical spelling."""
    return type(value) is str and _FINGERPRINT.fullmatch(value) is not None


def utc_text(value: datetime) -> str:
    """The one spelling of an instant inside signed bytes: UTC, microseconds, ``Z``."""
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _aware(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must carry a UTC offset.")
    return value


def _hex32(value: str, field_name: str) -> str:
    if not is_hex32(value):
        raise ValueError(f"{field_name} must be 32 lowercase hexadecimal characters.")
    return value


def _hex64(value: str, field_name: str) -> str:
    if _HEX64.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be 64 lowercase hexadecimal characters.")
    return value


def _ref(value: str, field_name: str) -> str:
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty or whitespace-only.")
    if len(value) > MAX_REF_CHARS:
        raise ValueError(f"{field_name} must be at most {MAX_REF_CHARS} characters.")
    return value


class _StrictV2(BaseModel):
    """Frozen, strict types, unknown fields refused."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ApprovalChallengeV2(_StrictV2):
    """An AIDO-issued request for one human approval of one subject digest.

    Unlike v1, its lifetime is fixed: ``expires_at`` is exactly
    ``issued_at + APPROVAL_CHALLENGE_TTL`` (60 minutes, R-8).
    """

    schema_version: Literal["approval-challenge.v2"]
    challenge_id: str
    subject_kind: ApprovalSubjectKindV2
    subject_sha256: str
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
    def _shape(self) -> ApprovalChallengeV2:
        if self.required_approval_text != APPROVAL_TEXT_V2[self.subject_kind]:
            raise ValueError("required_approval_text is not this subject kind's phrase.")
        if self.expires_at - self.issued_at != APPROVAL_CHALLENGE_TTL:
            raise ValueError("a challenge lives exactly APPROVAL_CHALLENGE_TTL.")
        return self


class HumanAttestationV2(_StrictV2):
    """A human's answer to one :class:`ApprovalChallengeV2`.

    ``proof`` is the armored OpenSSH ``SSHSIG`` signature over the
    :class:`AttestationStatementV1` bytes. Nothing in this record is authority
    by itself: the phrase and the digest are what the challenge already says,
    and only the verifier's check of ``proof`` against the approver registry
    connects them to a human.
    """

    schema_version: Literal["human-attestation.v2"]
    challenge_id: str
    subject_kind: ApprovalSubjectKindV2
    subject_sha256: str
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
        return _ref(value, "approver_id")

    @field_validator("attested_at")
    @classmethod
    def _attested_at(cls, value: datetime) -> datetime:
        return _aware(value, "attested_at")

    @field_validator("proof")
    @classmethod
    def _proof(cls, value: str) -> str:
        if not value.strip() or len(value) > MAX_ATTESTATION_PROOF_CHARS:
            raise ValueError(f"proof must be non-blank and at most {MAX_ATTESTATION_PROOF_CHARS} characters.")
        return value

    @model_validator(mode="after")
    def _phrase(self) -> HumanAttestationV2:
        if self.approval_text != APPROVAL_TEXT_V2[self.subject_kind]:
            raise ValueError(
                "approval_text must match the required approval phrase exactly; "
                "a paraphrase is not approval."
            )
        return self

    @property
    def sha256(self) -> str:
        """SHA-256 over this record's canonical JSON, ``proof`` included."""
        return hashlib.sha256(canonical_json_bytes(self.model_dump(mode="json"))).hexdigest()


class AttestationStatementV1(_StrictV2):
    """``attestation-statement.v1``: what the human's security key signs.

    Its bytes (:meth:`canonical_bytes`) are canonical JSON with every instant
    spelled by :func:`utc_text`, so exactly one byte string exists per
    statement. It binds the state root, the challenge, the subject, the
    approver, the registered key, both timestamps and the phrase (FD-1, §8).
    """

    schema_version: Literal["attestation-statement.v1"]
    namespace: Literal["aido-approval@v1"]
    state_root_id: str
    challenge_id: str
    subject_kind: ApprovalSubjectKindV2
    subject_sha256: str
    approver_id: str
    key_fingerprint_sha256: str
    attested_at: datetime
    expires_at: datetime
    approval_text: str

    @field_validator("state_root_id", "challenge_id")
    @classmethod
    def _ids(cls, value: str, info) -> str:
        return _hex32(value, info.field_name)

    @field_validator("subject_sha256")
    @classmethod
    def _subject(cls, value: str) -> str:
        return _hex64(value, "subject_sha256")

    @field_validator("approver_id")
    @classmethod
    def _approver(cls, value: str) -> str:
        return _ref(value, "approver_id")

    @field_validator("key_fingerprint_sha256")
    @classmethod
    def _fingerprint(cls, value: str) -> str:
        if not is_key_fingerprint(value):
            raise ValueError("key_fingerprint_sha256 must be an OpenSSH SHA256: fingerprint.")
        return value

    @field_validator("attested_at", "expires_at")
    @classmethod
    def _times(cls, value: datetime, info) -> datetime:
        return _aware(value, info.field_name)

    @model_validator(mode="after")
    def _phrase(self) -> AttestationStatementV1:
        if self.approval_text != APPROVAL_TEXT_V2[self.subject_kind]:
            raise ValueError("approval_text is not this subject kind's phrase.")
        return self

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes({
            "schema_version": self.schema_version,
            "namespace": self.namespace,
            "state_root_id": self.state_root_id,
            "challenge_id": self.challenge_id,
            "subject_kind": self.subject_kind.value,
            "subject_sha256": self.subject_sha256,
            "approver_id": self.approver_id,
            "key_fingerprint_sha256": self.key_fingerprint_sha256,
            "attested_at": utc_text(self.attested_at),
            "expires_at": utc_text(self.expires_at),
            "approval_text": self.approval_text,
        })


def attestation_statement(
    *,
    state_root_id: str,
    challenge: ApprovalChallengeV2,
    attestation: HumanAttestationV2,
    key_fingerprint_sha256: str,
) -> AttestationStatementV1:
    """The statement ``attestation`` must carry a signature over.

    Every field comes from AIDO's own records (the state root id, the
    challenge) or from the attestation's claims that the verifier has already
    compared with the challenge; ``expires_at`` is the challenge's.
    """
    return AttestationStatementV1(
        schema_version="attestation-statement.v1",
        namespace="aido-approval@v1",
        state_root_id=state_root_id,
        challenge_id=challenge.challenge_id,
        subject_kind=challenge.subject_kind,
        subject_sha256=challenge.subject_sha256,
        approver_id=attestation.approver_id,
        key_fingerprint_sha256=key_fingerprint_sha256,
        attested_at=attestation.attested_at,
        expires_at=challenge.expires_at,
        approval_text=challenge.required_approval_text,
    )
