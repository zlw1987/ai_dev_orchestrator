"""DL-4B S1 — the human attestation verifier (FD-1 to FD-5).

``RegistryHumanAttestationVerifier`` decides whether one
:class:`~ai_dev_orchestrator.control_plane.attestation_v2.HumanAttestationV2`
is a human's approval of exactly one AIDO challenge. It is pure and read-only:
it parses, reads security facts and files, and checks one Ed25519 signature.
It never signs, holds no private key, runs no subprocess, opens no network
connection, reads no environment variable and caches nothing.

```text
inputs (re-validated copies)  challenge  attestation  state_root_id
        │                         │           │            │
        ▼                         ▼           ▼            ▼
  statement fields agree ─► timestamps inside the challenge (and, to consume, now)
        │
  armored SSHSIG parsed strictly (sk-ssh-ed25519, sha512, version 1, no trailing bytes)
        │
  approver-registry.v1 read and PROVEN protected (S0 facts, A/X/O cannot alter it)
        │
  approver_id → registered key, exact public-key blob and application
  not revoked; validity window covers the whole challenge
        │
  attestation-statement.v1 rebuilt by AIDO → Ed25519 over the nested FIDO signed data
        │
  user presence set; user verification if the entry requires it; no other flag
        ▼
  VerifiedHumanAttestation (a record of one run, not a capability)
```

Two entry points with different time rules:

- :meth:`~RegistryHumanAttestationVerifier.verify_for_consumption` is for a
  challenge the store is about to consume: AIDO's clock must lie inside the
  challenge (60 minutes, FD-3). The store then re-checks, inside its write
  transaction, that the challenge is still unconsumed and unexpired and that
  the attestation it consumes has the digest verified here (FD-5).
- :meth:`~RegistryHumanAttestationVerifier.reprove` is for an attestation the
  store already consumed (FD-4): the challenge has long expired, so the clock
  is not compared with it, but everything else, the registry read included, is
  repeated. Revocation is total, so a revoked key fails every re-proof.

The verifier does not know whether a challenge was consumed; the store does.
It is not a second source of truth for consumption.

Production construction takes no argument: ``RegistryHumanAttestationVerifier()``
reads live Windows facts and the code-constant registry, and its records are
``is_production``. :meth:`~RegistryHumanAttestationVerifier.from_facts` runs
the identical checks over a caller's facts source and clock for offline tests;
its records are always ``facts_origin="injected"``.

A software Ed25519 key formatted as an ``sk`` key produces signatures this
verifier cannot tell from an authenticator's (SSHSIG carries no FIDO
attestation certificate). What makes a key a human's is that the registry,
which only an administrator can write, names it.
"""

from __future__ import annotations

import hashlib
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from ai_dev_orchestrator.control_plane.attestation_v2 import (
    ATTESTATION_NAMESPACE,
    ApprovalChallengeV2,
    ApprovalSubjectKindV2,
    HumanAttestationV2,
    attestation_statement,
)
from ai_dev_orchestrator.control_plane.authority import AuthorityRefusedError
from ai_dev_orchestrator.control_plane.models import is_hex32
from ai_dev_orchestrator.integration.approver_registry import (
    REGISTERED_APPLICATION,
    RegistryError,
    RegistrySnapshot,
    read_approver_registry,
)
from ai_dev_orchestrator.integration.boundary_facts import SecurityFacts
from ai_dev_orchestrator.integration.sshsig import (
    ALLOWED_FLAGS,
    FLAG_USER_PRESENT,
    FLAG_USER_VERIFIED,
    SshSigError,
    parse_armored_sshsig,
    verify_sk_sshsig,
)


class AttestationRefusal(str, Enum):
    """Why an attestation approves nothing. The first nine are §5.1's; the
    rest refine them so that each test and audit line names one check."""

    REGISTRY_UNPROTECTED = "registry_unprotected"
    KEY_UNKNOWN = "key_unknown"
    KEY_REVOKED = "key_revoked"
    SIGNATURE_INVALID = "signature_invalid"
    PRESENCE_MISSING = "presence_missing"
    NAMESPACE_MISMATCH = "namespace_mismatch"
    STATEMENT_MISMATCH = "statement_mismatch"
    #: Reserved for the store (S2): only it knows whether a challenge was consumed.
    CHALLENGE_SPENT = "challenge_spent"
    CHALLENGE_EXPIRED = "challenge_expired"
    REGISTRY_UNREADABLE = "registry_unreadable"
    REGISTRY_MALFORMED = "registry_malformed"
    INPUT_INVALID = "input_invalid"
    TIMESTAMP_INVALID = "timestamp_invalid"
    PROOF_MALFORMED = "proof_malformed"
    ALGORITHM_UNSUPPORTED = "algorithm_unsupported"
    APPLICATION_MISMATCH = "application_mismatch"
    KEY_NOT_VALID = "key_not_valid"
    USER_VERIFICATION_MISSING = "user_verification_missing"
    FLAGS_UNSUPPORTED = "flags_unsupported"


class HumanAttestationRefusedError(AuthorityRefusedError):
    """The attestation is not proven. Nothing was recorded or consumed.

    The message names the category and the failed check; it never contains
    the proof, a key blob, file bytes or environment contents.
    """

    def __init__(self, category: AttestationRefusal, detail: str) -> None:
        self.category = category
        self.detail = detail
        super().__init__(f"{category.value}: {detail}")


_R = AttestationRefusal

# -- the result record -------------------------------------------------------------

_RECORD_TOKEN = object()
_RECORD_FIELDS = (
    "purpose",
    "state_root_id",
    "challenge_id",
    "subject_kind",
    "subject_sha256",
    "approver_id",
    "attested_at",
    "attestation_sha256",
    "statement_sha256",
    "signature_sha256",
    "key_fingerprint_sha256",
    "authenticator_flags",
    "authenticator_counter",
    "user_verified",
    "registry_sha256",
    "identity_boundary_sha256",
    "facts_origin",
    "independent_evaluation",
    "verified_at",
)


class VerifiedHumanAttestation:
    """A record that one verification run passed. Minted only by the verifier;
    immutable, not subclassable, not copyable or picklable.

    It is **not** a capability and never authorizes anything by being held.
    The store compares ``attestation_sha256`` with the attestation it consumes
    (FD-5), and re-verifies on every later proof (FD-4).
    ``authenticator_counter`` is recorded for audit only: some authenticators
    do not increment it, so it is not a replay defence (FD-3).
    """

    __slots__ = _RECORD_FIELDS
    purpose: Literal["consumption", "reproof"]
    state_root_id: str
    challenge_id: str
    subject_kind: ApprovalSubjectKindV2
    subject_sha256: str
    approver_id: str
    attested_at: datetime
    attestation_sha256: str
    statement_sha256: str
    signature_sha256: str
    key_fingerprint_sha256: str
    authenticator_flags: int
    authenticator_counter: int
    user_verified: bool
    registry_sha256: str
    identity_boundary_sha256: str
    facts_origin: Literal["windows", "injected"]
    independent_evaluation: bool
    verified_at: datetime

    def __init__(self, *, _token: object = None, **fields: Any) -> None:
        if _token is not _RECORD_TOKEN or set(fields) != set(_RECORD_FIELDS):
            raise TypeError("a verified attestation record is produced only by the attestation verifier.")
        for name in _RECORD_FIELDS:
            object.__setattr__(self, name, fields[name])

    def __init_subclass__(cls, **kwargs: Any) -> None:
        raise TypeError("VerifiedHumanAttestation cannot be subclassed.")

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("a verified attestation record is immutable.")

    def __delattr__(self, name: str) -> None:
        raise AttributeError("a verified attestation record is immutable.")

    def __reduce__(self) -> Any:
        raise TypeError("a verified attestation record cannot be copied or pickled.")

    def __copy__(self) -> Any:
        raise TypeError("a verified attestation record cannot be copied or pickled.")

    def __deepcopy__(self, memo: Any) -> Any:
        raise TypeError("a verified attestation record cannot be copied or pickled.")

    @property
    def is_production(self) -> bool:
        """Verified by the production verifier against live Windows facts,
        with every rights result confirmed by AuthZ."""
        return self.facts_origin == "windows" and self.independent_evaluation


# -- the verifier ---------------------------------------------------------------------


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _production_facts() -> SecurityFacts:
    if sys.platform != "win32":
        raise RegistryError(
            "registry_unprotected",
            "the approver registry is protected by Windows access control; no other platform "
            "can prove it.",
        )
    from ai_dev_orchestrator.integration.windows_security import WindowsSecurityFacts

    try:
        return WindowsSecurityFacts()
    except Exception as exc:
        raise RegistryError(
            "registry_unprotected", f"Windows security APIs are unavailable ({type(exc).__name__})."
        ) from None


_CONFIG_TOKEN = object()
_VERIFIER_FIELDS = ("_origin", "_facts", "_clock")


class RegistryHumanAttestationVerifier:
    """Verifies DL-4B human attestations against ``approver-registry.v1``.

    ``RegistryHumanAttestationVerifier()`` is the production verifier. It has
    no parameter for a registry, a key, a facts source or a clock. It has no
    ``verify`` method, so it cannot be mistaken for DL-4A's ``v1`` verifier.
    """

    __slots__ = _VERIFIER_FIELDS
    _origin: Literal["windows", "injected"]
    _facts: SecurityFacts | None
    _clock: Callable[[], datetime]

    def __init__(self) -> None:
        self._configure(_CONFIG_TOKEN, "windows", None, _utc_now)

    @classmethod
    def from_facts(
        cls, facts: SecurityFacts, *, clock: Callable[[], datetime]
    ) -> RegistryHumanAttestationVerifier:
        """The same verifier over a caller's facts source and clock. Every
        record it produces is ``facts_origin="injected"`` and never
        ``is_production``, whatever the source is or claims to be."""
        if not callable(clock):
            raise TypeError("clock must be callable.")
        instance = cls.__new__(cls)
        instance._configure(_CONFIG_TOKEN, "injected", facts, clock)
        return instance

    def _configure(self, token: object, origin: str, facts: SecurityFacts | None,
                   clock: Callable[[], datetime]) -> None:
        if token is not _CONFIG_TOKEN or hasattr(self, "_origin"):
            raise TypeError("a verifier is configured once, by its own constructors.")
        object.__setattr__(self, "_origin", origin)
        object.__setattr__(self, "_facts", facts)
        object.__setattr__(self, "_clock", clock)

    def __init_subclass__(cls, **kwargs: Any) -> None:
        raise TypeError("RegistryHumanAttestationVerifier cannot be subclassed.")

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("a verifier is immutable.")

    def __delattr__(self, name: str) -> None:
        raise AttributeError("a verifier is immutable.")

    def __reduce__(self) -> Any:
        raise TypeError("a verifier cannot be copied or pickled.")

    def __copy__(self) -> Any:
        raise TypeError("a verifier cannot be copied or pickled.")

    def __deepcopy__(self, memo: Any) -> Any:
        raise TypeError("a verifier cannot be copied or pickled.")

    @property
    def is_production(self) -> bool:
        return self._origin == "windows"

    # -- public entry points --------------------------------------------------------

    def verify_for_consumption(
        self, *, state_root_id: str, challenge: ApprovalChallengeV2, attestation: HumanAttestationV2
    ) -> VerifiedHumanAttestation:
        """Verify an answer to a challenge the store is about to consume.

        Raises :class:`HumanAttestationRefusedError`; returns only on success.
        """
        return self._verify("consumption", state_root_id, challenge, attestation)

    def reprove(
        self, *, state_root_id: str, challenge: ApprovalChallengeV2, attestation: HumanAttestationV2
    ) -> VerifiedHumanAttestation:
        """Re-verify an attestation the store already consumed, against the
        current registry (FD-4). The clock is not compared with the
        challenge; everything else is checked again."""
        return self._verify("reproof", state_root_id, challenge, attestation)

    # -- the checks -------------------------------------------------------------------

    def _now(self) -> datetime:
        try:
            now = self._clock()
        except Exception:  # noqa: BLE001 - an unreadable clock approves nothing
            now = None
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise HumanAttestationRefusedError(_R.TIMESTAMP_INVALID, "the clock is not a timezone-aware instant.")
        return now

    def _read_registry(self) -> RegistrySnapshot:
        try:
            facts = _production_facts() if self._origin == "windows" else self._facts
            return read_approver_registry(facts, require_independent=self._origin == "windows")
        except RegistryError as exc:
            raise HumanAttestationRefusedError(AttestationRefusal(exc.category), exc.detail) from None
        except Exception as exc:  # noqa: BLE001 - e.g. a facts source without a method
            raise HumanAttestationRefusedError(
                _R.REGISTRY_UNPROTECTED, f"the security facts could not be read ({type(exc).__name__})."
            ) from None

    def _verify(
        self,
        purpose: Literal["consumption", "reproof"],
        state_root_id: object,
        challenge: object,
        attestation: object,
    ) -> VerifiedHumanAttestation:
        challenge = _fresh(challenge, ApprovalChallengeV2, "challenge")
        attestation = _fresh(attestation, HumanAttestationV2, "attestation")
        if type(state_root_id) is not str or not is_hex32(state_root_id):
            raise HumanAttestationRefusedError(_R.INPUT_INVALID, "state_root_id is not a state root id.")

        _check_statement_fields(challenge, attestation)
        if not challenge.issued_at <= attestation.attested_at <= challenge.expires_at:
            raise HumanAttestationRefusedError(
                _R.TIMESTAMP_INVALID, "the attestation is dated outside its challenge's lifetime."
            )
        if purpose == "consumption":
            now = self._now()
            if now < challenge.issued_at:
                raise HumanAttestationRefusedError(
                    _R.TIMESTAMP_INVALID, "AIDO's clock is before the challenge was issued."
                )
            if now >= challenge.expires_at:
                raise HumanAttestationRefusedError(
                    _R.CHALLENGE_EXPIRED, "the challenge expired before it was answered."
                )
            if attestation.attested_at > now:
                raise HumanAttestationRefusedError(
                    _R.TIMESTAMP_INVALID, "the attestation is dated in the future."
                )

        try:
            signature = parse_armored_sshsig(attestation.proof)
        except SshSigError as exc:
            raise HumanAttestationRefusedError(AttestationRefusal(exc.category), exc.detail) from None
        if signature.namespace != ATTESTATION_NAMESPACE:
            raise HumanAttestationRefusedError(
                _R.NAMESPACE_MISMATCH, "the SSHSIG namespace is not the AIDO approval namespace."
            )

        snapshot = self._read_registry()
        entries = snapshot.registry.entries_for(attestation.approver_id)
        if not entries:
            raise HumanAttestationRefusedError(_R.KEY_UNKNOWN, "the approver has no registered key.")
        matches = [entry for entry in entries if entry.key.blob == signature.public_key.blob]
        if not matches:
            if any(entry.key.ed25519 == signature.public_key.ed25519 for entry in entries):
                raise HumanAttestationRefusedError(
                    _R.APPLICATION_MISMATCH,
                    "the signing key was created for a different FIDO application than the registered key.",
                )
            raise HumanAttestationRefusedError(
                _R.KEY_UNKNOWN,
                f"the signing key {signature.public_key.fingerprint} is not registered for this approver.",
            )
        (entry,) = matches
        if signature.public_key.application != REGISTERED_APPLICATION:  # implied by the exact blob
            raise HumanAttestationRefusedError(
                _R.APPLICATION_MISMATCH, "the signing key is not an AIDO approval key."
            )
        if entry.revoked:
            raise HumanAttestationRefusedError(
                _R.KEY_REVOKED, f"the key {entry.fingerprint_sha256} is revoked; it approves nothing."
            )
        if not (entry.not_before <= challenge.issued_at and challenge.expires_at <= entry.not_after):
            raise HumanAttestationRefusedError(
                _R.KEY_NOT_VALID,
                f"the key {entry.fingerprint_sha256} is not valid for the whole lifetime of the challenge.",
            )

        statement = attestation_statement(
            state_root_id=state_root_id,
            challenge=challenge,
            attestation=attestation,
            key_fingerprint_sha256=entry.fingerprint_sha256,
        )
        message = statement.canonical_bytes()
        try:
            verify_sk_sshsig(signature, namespace=ATTESTATION_NAMESPACE, message=message)
        except SshSigError as exc:
            raise HumanAttestationRefusedError(AttestationRefusal(exc.category), exc.detail) from None

        # The flags are now proven to be the authenticator's.
        if signature.flags & ~ALLOWED_FLAGS:
            raise HumanAttestationRefusedError(
                _R.FLAGS_UNSUPPORTED,
                f"the authenticator set flags 0x{signature.flags & ~ALLOWED_FLAGS:02x}, which an SSH "
                "approval signature may not carry.",
            )
        if not signature.flags & FLAG_USER_PRESENT:
            raise HumanAttestationRefusedError(
                _R.PRESENCE_MISSING, "the authenticator did not assert user presence (no touch)."
            )
        user_verified = bool(signature.flags & FLAG_USER_VERIFIED)
        if entry.require_user_verification and not user_verified:
            raise HumanAttestationRefusedError(
                _R.USER_VERIFICATION_MISSING,
                "the registry requires user verification (PIN) for this key and the authenticator did not assert it.",
            )

        verified_at = self._now()
        return VerifiedHumanAttestation(
            _token=_RECORD_TOKEN,
            purpose=purpose,
            state_root_id=state_root_id,
            challenge_id=challenge.challenge_id,
            subject_kind=challenge.subject_kind,
            subject_sha256=challenge.subject_sha256,
            approver_id=attestation.approver_id,
            attested_at=attestation.attested_at,
            attestation_sha256=attestation.sha256,
            statement_sha256=hashlib.sha256(message).hexdigest(),
            signature_sha256=signature.sha256,
            key_fingerprint_sha256=entry.fingerprint_sha256,
            authenticator_flags=signature.flags,
            authenticator_counter=signature.counter,
            user_verified=user_verified,
            registry_sha256=snapshot.registry_sha256,
            identity_boundary_sha256=snapshot.identity_boundary_sha256,
            facts_origin=self._origin,
            independent_evaluation=snapshot.independent_evaluation,
            verified_at=verified_at,
        )


def _fresh(value: object, model: type, what: str) -> Any:
    """A re-validated copy of ``value``, which must be exactly ``model``.

    A subclass, a ``model_construct`` object or one mutated after validation
    is never trusted to hold what its type says.
    """
    if type(value) is not model:
        raise HumanAttestationRefusedError(_R.INPUT_INVALID, f"the {what} is not a {model.__name__}.")
    try:
        # Field by field, not through a serializer: a serializer warning would
        # print the unexpected value (possibly proof bytes) to stderr.
        return model.model_validate({name: getattr(value, name) for name in model.model_fields})
    except Exception:  # noqa: BLE001 - anything that does not validate again is refused
        raise HumanAttestationRefusedError(_R.INPUT_INVALID, f"the {what} does not validate.") from None


def _check_statement_fields(challenge: ApprovalChallengeV2, attestation: HumanAttestationV2) -> None:
    if attestation.challenge_id != challenge.challenge_id:
        raise HumanAttestationRefusedError(_R.STATEMENT_MISMATCH, "the attestation answers a different challenge.")
    if attestation.subject_kind is not challenge.subject_kind or attestation.subject_sha256 != challenge.subject_sha256:
        raise HumanAttestationRefusedError(_R.STATEMENT_MISMATCH, "the attestation names a different subject.")
    if attestation.approval_text != challenge.required_approval_text:
        raise HumanAttestationRefusedError(_R.STATEMENT_MISMATCH, "the attestation carries a different phrase.")
