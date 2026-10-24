"""DL-4B S1 — the human attestation verifier (offline).

Every signature here is made by a **test-only software Ed25519 key** that
emulates the OpenSSH ``sk-ssh-ed25519@openssh.com`` format: the test plays the
FIDO authenticator, building ``SHA256(application) || flags || counter ||
SHA256(sshsig_data)`` with its own code (not the module under test) and
signing it. Those keys are fixtures. They never leave this file and are never
production signing authority: the verifier cannot tell them from an
authenticator, which is exactly why only an admin-written registry decides
which keys are approvers.

The registry and identity boundary live in S0's synthetic world (synthetic
SIDs and descriptors, built in memory). No test creates or modifies an
account, ACL or system directory; none runs a subprocess, opens a socket,
invokes ``ssh-keygen`` or touches a real authenticator.

Sections: statement and models; known-answer vectors; SSHSIG/sk structure;
signature, identity and flags; challenge and timestamps; registry content;
revocation and rotation; registry protection (S0 facts); caller bypass and
malformed objects; production entry point; static boundaries.
"""

from __future__ import annotations

import ast
import base64
import copy
import hashlib
import inspect
import json
import ntpath
import pickle
import random
import sys
from dataclasses import dataclass, fields
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

import ai_dev_orchestrator.integration as integration
from ai_dev_orchestrator.control_plane import attestation_v2 as av2
from ai_dev_orchestrator.control_plane.attestation_v2 import (
    APPROVAL_TEXT_V2,
    ApprovalChallengeV2,
    ApprovalSubjectKindV2 as K,
    AttestationStatementV1,
    HumanAttestationV2,
    attestation_statement,
)
from ai_dev_orchestrator.control_plane.authority import (
    APPROVAL_CHALLENGE_TTL,
    ApprovalChallenge,
    ApprovalSubjectKind,
    AuthorityRefusedError,
    HumanAttestation,
)
from ai_dev_orchestrator.control_plane.transitions import RefusalCode
from ai_dev_orchestrator.integration import approver_registry as reg_module
from ai_dev_orchestrator.integration import attestation_verifier as verifier_module
from ai_dev_orchestrator.integration import sshsig
from ai_dev_orchestrator.integration.approver_registry import (
    RegistryError,
    parse_approver_registry,
    read_approver_registry,
)
from ai_dev_orchestrator.integration.attestation_verifier import (
    AttestationRefusal as R,
    HumanAttestationRefusedError,
    RegistryHumanAttestationVerifier,
    VerifiedHumanAttestation,
)
from ai_dev_orchestrator.integration.boundary_facts import PrincipalFacts, TokenFacts
from ai_dev_orchestrator.integration.identity_boundary import IsolationCategory as C
from ai_dev_orchestrator.integration.security_descriptor import (
    ADMINISTRATORS,
    DELETE,
    FILE_ALL_ACCESS,
    FILE_APPEND_DATA,
    FILE_DELETE_CHILD,
    FILE_WRITE_DATA,
    LOCAL_SYSTEM,
    WRITE_DAC,
    WRITE_OWNER,
    parse_security_descriptor,
    upper_bound_rights,
)
from test_dl4b_s0_identity_boundary import (
    A,
    ADMIN_FULL,
    ANCHOR_DIR,
    O,
    OICI,
    RX,
    USERS,
    X,
    World,
    allow,
    good_world,
)

WINDOWS = sys.platform == "win32"
windows_only = pytest.mark.skipif(not WINDOWS, reason="reads real Windows security facts")

REGISTRY = ANCHOR_DIR + "\\approver-registry.v1.json"
APP = "ssh:aido-approval"
NS = "aido-approval@v1"
SK = "sk-ssh-ed25519@openssh.com"
STATE_ROOT_ID = "0123456789abcdef0123456789abcdef"
OTHER_ROOT_ID = "fedcba9876543210fedcba9876543210"
CHALLENGE_ID = "aa" * 16
SUBJECT = "5e" * 32
ISSUED = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)
NOW = ISSUED + timedelta(minutes=10)
ATTESTED = ISSUED + timedelta(minutes=5)

# -- the test-only authenticator ---------------------------------------------------------


def s(value: bytes) -> bytes:
    return len(value).to_bytes(4, "big") + value


def key(seed: int) -> Ed25519PrivateKey:
    """A deterministic TEST-ONLY software key. Never production authority."""
    return Ed25519PrivateKey.from_private_bytes(hashlib.sha256(b"aido-s1-test-key-%d" % seed).digest())


def raw_public(private: Ed25519PrivateKey) -> bytes:
    return private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)


def sk_blob(private: Ed25519PrivateKey, application: str = APP, key_type: str = SK) -> bytes:
    return s(key_type.encode()) + s(raw_public(private)) + s(application.encode())


def key_line(private: Ed25519PrivateKey, application: str = APP) -> str:
    return SK + " " + base64.b64encode(sk_blob(private, application)).decode()


def fingerprint(blob: bytes) -> str:
    return "SHA256:" + base64.b64encode(hashlib.sha256(blob).digest()).decode().rstrip("=")


def armor(blob: bytes, newline: str = "\n", width: int = 70) -> str:
    text = base64.b64encode(blob).decode()
    lines = [text[i:i + width] for i in range(0, len(text), width)]
    return newline.join(["-----BEGIN SSH SIGNATURE-----", *lines, "-----END SSH SIGNATURE-----"]) + newline


def sign(
    private: Ed25519PrivateKey,
    message: bytes,
    *,
    flags: int = 0x01,
    counter: int = 7,
    application: str = APP,
    namespace: str = NS,
    hash_alg: str = "sha512",
    reserved: bytes = b"",
    version: int = 1,
    signed_flags: int | None = None,
    signed_counter: int | None = None,
    signed_application: str | None = None,
    pub_blob: bytes | None = None,
    sig_type: str = SK,
    sig_trailing: bytes = b"",
    envelope_trailing: bytes = b"",
    magic: bytes = b"SSHSIG",
) -> bytes:
    """Emulate ``ssh-keygen -Y sign`` with an sk-ed25519 authenticator. Returns the SSHSIG blob."""
    digest = hashlib.sha512(message).digest() if hash_alg == "sha512" else hashlib.sha256(message).digest()
    to_sign = b"SSHSIG" + s(namespace.encode()) + s(reserved) + s(hash_alg.encode()) + s(digest)
    authenticator_data = (
        hashlib.sha256((signed_application or application).encode()).digest()
        + bytes([flags if signed_flags is None else signed_flags])
        + (counter if signed_counter is None else signed_counter).to_bytes(4, "big")
    )
    ed_sig = private.sign(authenticator_data + hashlib.sha256(to_sign).digest())
    signature = s(sig_type.encode()) + s(ed_sig) + bytes([flags]) + counter.to_bytes(4, "big") + sig_trailing
    return (
        magic + version.to_bytes(4, "big") + s(pub_blob if pub_blob is not None else sk_blob(private, application))
        + s(namespace.encode()) + s(reserved) + s(hash_alg.encode()) + s(signature) + envelope_trailing
    )


# -- challenge, attestation, statement ------------------------------------------------------


def challenge(kind: K = K.PLAN_ACTIVATION, **changes) -> ApprovalChallengeV2:
    values = dict(
        schema_version="approval-challenge.v2", challenge_id=CHALLENGE_ID, subject_kind=kind,
        subject_sha256=SUBJECT, issued_at=ISSUED, expires_at=ISSUED + APPROVAL_CHALLENGE_TTL,
        required_approval_text=APPROVAL_TEXT_V2[kind],
    )
    values.update(changes)
    return ApprovalChallengeV2(**values)


def statement_bytes(
    *, private: Ed25519PrivateKey, ch: ApprovalChallengeV2, approver: str = "alice",
    attested_at: datetime = ATTESTED, root: str = STATE_ROOT_ID, application: str = APP,
) -> bytes:
    """The statement, built independently of the module under test."""
    def t(value: datetime) -> str:
        return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    return json.dumps({
        "schema_version": "attestation-statement.v1",
        "namespace": NS,
        "state_root_id": root,
        "challenge_id": ch.challenge_id,
        "subject_kind": ch.subject_kind.value,
        "subject_sha256": ch.subject_sha256,
        "approver_id": approver,
        "key_fingerprint_sha256": fingerprint(sk_blob(private, application)),
        "attested_at": t(attested_at),
        "expires_at": t(ch.expires_at),
        "approval_text": ch.required_approval_text,
    }, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def attestation(
    ch: ApprovalChallengeV2, *, private: Ed25519PrivateKey | None = None, approver: str = "alice",
    attested_at: datetime = ATTESTED, proof: str | None = None, root: str = STATE_ROOT_ID,
    message: bytes | None = None, **sign_options,
) -> HumanAttestationV2:
    private = private or ALICE
    if proof is None:
        message = message if message is not None else statement_bytes(
            private=private, ch=ch, approver=approver, attested_at=attested_at, root=root,
            application=sign_options.get("application", APP),
        )
        proof = armor(sign(private, message, **sign_options))
    return HumanAttestationV2(
        schema_version="human-attestation.v2", challenge_id=ch.challenge_id, subject_kind=ch.subject_kind,
        subject_sha256=ch.subject_sha256, approver_id=approver, attested_at=attested_at,
        approval_text=ch.required_approval_text, proof=proof,
    )


ALICE = key(1)
BOB = key(2)
ALICE_NEW = key(3)


def entry(private: Ed25519PrivateKey, approver: str = "alice", **changes) -> dict:
    value = {
        "approver_id": approver,
        "public_key": key_line(private),
        "application": APP,
        "fingerprint_sha256": fingerprint(sk_blob(private)),
        "require_user_verification": False,
        "not_before": "2026-01-01T00:00:00Z",
        "not_after": "2027-01-01T00:00:00Z",
        "revoked": False,
    }
    value.update(changes)
    return value


# -- the synthetic world with a registry ----------------------------------------------------


@dataclass
class RegWorld(World):
    registry: dict | None = None
    registry_raw: bytes | None = None

    def registry_bytes(self) -> bytes:
        if self.registry_raw is not None:
            return self.registry_raw
        return json.dumps(self.registry).encode("utf-8")

    def read_file(self, path, limit):
        facts = self._facts(path)
        if facts is None:
            return None
        if ntpath.normcase(path) == ntpath.normcase(REGISTRY):
            return facts, self.registry_bytes()
        return facts, self.boundary_bytes()


def reg_world() -> RegWorld:
    base = good_world()
    w = RegWorld(**{f.name: getattr(base, f.name) for f in fields(World)})
    w.put_child(ANCHOR_DIR, "approver-registry.v1.json", is_dir=False)
    w.registry = {
        "schema_version": "approver-registry.v1",
        "approvers": [entry(ALICE), entry(BOB, "bob")],
    }
    return w


@pytest.fixture
def world() -> RegWorld:
    return reg_world()


class Clock:
    def __init__(self, now: datetime = NOW) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


def verifier(w: RegWorld, clock: Clock | None = None) -> RegistryHumanAttestationVerifier:
    return RegistryHumanAttestationVerifier.from_facts(w, clock=clock or Clock())


def consume(w: RegWorld, ch: ApprovalChallengeV2, att: HumanAttestationV2, *, root: str = STATE_ROOT_ID,
            clock: Clock | None = None) -> VerifiedHumanAttestation:
    return verifier(w, clock).verify_for_consumption(state_root_id=root, challenge=ch, attestation=att)


def reprove(w: RegWorld, ch: ApprovalChallengeV2, att: HumanAttestationV2, *, root: str = STATE_ROOT_ID,
            clock: Clock | None = None) -> VerifiedHumanAttestation:
    return verifier(w, clock).reprove(state_root_id=root, challenge=ch, attestation=att)


def refused(category: R, call, *args, match: str | None = None, **kwargs) -> HumanAttestationRefusedError:
    with pytest.raises(HumanAttestationRefusedError) as info:
        call(*args, **kwargs)
    assert info.value.category is category, str(info.value)
    assert str(info.value).startswith(f"authority_unproven: {category.value}: "), str(info.value)
    assert info.value.code is RefusalCode.AUTHORITY_UNPROVEN
    if match is not None:
        assert match in str(info.value), str(info.value)
    return info.value


# =============================================================================
# 1. statement and models
# =============================================================================


def test_the_statement_bytes_are_exactly_the_canonical_json() -> None:
    ch = challenge()
    att = attestation(ch)
    fp = fingerprint(sk_blob(ALICE))
    built = attestation_statement(state_root_id=STATE_ROOT_ID, challenge=ch, attestation=att,
                                  key_fingerprint_sha256=fp)
    assert built.canonical_bytes() == statement_bytes(private=ALICE, ch=ch)
    assert built.canonical_bytes() == (
        b'{"approval_text":"I approve this execution plan, policy and target workspace for AIDO execution",'
        b'"approver_id":"alice","attested_at":"2026-10-23T12:05:00.000000Z","challenge_id":"'
        + CHALLENGE_ID.encode() + b'","expires_at":"2026-10-23T13:00:00.000000Z","key_fingerprint_sha256":"'
        + fp.encode() + b'","namespace":"aido-approval@v1","schema_version":"attestation-statement.v1",'
        b'"state_root_id":"0123456789abcdef0123456789abcdef","subject_kind":"plan_activation",'
        b'"subject_sha256":"' + SUBJECT.encode() + b'"}'
    )


def test_one_instant_has_one_spelling_in_the_statement() -> None:
    ch = challenge()
    fp = fingerprint(sk_blob(ALICE))
    plus_two = ATTESTED.astimezone(timezone(timedelta(hours=2)))
    a = attestation_statement(state_root_id=STATE_ROOT_ID, challenge=ch, attestation=attestation(ch),
                              key_fingerprint_sha256=fp)
    b = attestation_statement(state_root_id=STATE_ROOT_ID, challenge=ch,
                              attestation=attestation(ch, attested_at=plus_two), key_fingerprint_sha256=fp)
    assert a.canonical_bytes() == b.canonical_bytes()


def test_the_exact_diff_phrase_mirrors_the_shipped_writer() -> None:
    from ai_dev_orchestrator.file_editing.models import REQUIRED_DIFF_EDIT_APPROVAL_TEXT

    assert av2.REQUIRED_EXACT_DIFF_APPROVAL_TEXT == REQUIRED_DIFF_EDIT_APPROVAL_TEXT
    assert APPROVAL_TEXT_V2[K.EXACT_DIFF_APPROVAL] == REQUIRED_DIFF_EDIT_APPROVAL_TEXT


def test_the_v2_kinds_extend_v1_without_changing_it() -> None:
    from ai_dev_orchestrator.control_plane.authority import APPROVAL_TEXT

    assert [k.value for k in ApprovalSubjectKind] == ["project_contract", "plan_activation", "step_acceptance"]
    for kind in ApprovalSubjectKind:
        assert APPROVAL_TEXT_V2[K(kind.value)] == APPROVAL_TEXT[kind]
    assert set(K) - {K(k.value) for k in ApprovalSubjectKind} == {K.EXACT_DIFF_APPROVAL}


@pytest.mark.parametrize("changes", [
    {"expires_at": ISSUED + timedelta(minutes=61)},
    {"expires_at": ISSUED + timedelta(minutes=59)},
    {"required_approval_text": "I approve"},
    {"challenge_id": "AA" * 16},
    {"subject_sha256": "5E" * 32},
    {"issued_at": datetime(2026, 10, 23, 12, 0)},
    {"schema_version": "approval-challenge.v1"},
    {"subject_kind": "plan_activation"},  # strict: a string is not the enum
])
def test_a_v2_challenge_rejects_every_other_shape(changes) -> None:
    with pytest.raises(Exception):
        challenge(**changes)


def test_a_v2_attestation_rejects_a_paraphrase_and_naive_times() -> None:
    ch = challenge()
    with pytest.raises(Exception):
        HumanAttestationV2(**{**attestation(ch).model_dump(), "approval_text": "I approve this"})
    with pytest.raises(Exception):
        HumanAttestationV2(**{**attestation(ch).model_dump(), "attested_at": datetime(2026, 10, 23, 12, 5)})
    with pytest.raises(Exception):
        HumanAttestationV2(**{**attestation(ch).model_dump(), "proof": "x" * 9000})


# =============================================================================
# 2. known-answer vectors
# =============================================================================

#: TEST-ONLY key 1 (``alice``): sha256(b"aido-s1-test-key-1") is the private seed.
KAT_PUBLIC_KEY = (
    "sk-ssh-ed25519@openssh.com AAAAGnNrLXNzaC1lZDI1NTE5QG9wZW5zc2guY29tAAAAIMyC7XGDGoXowdktzDuXu3otG1Rg6WO"
    "9gp674QrPVsBNAAAAEXNzaDphaWRvLWFwcHJvdmFs"
)
KAT_FINGERPRINT = "SHA256:AZJl4ebxCEJg9+Vo7cxvoi6nJYQCnw+Wkb2HccGNIk0"
#: The armored SSHSIG of the plan_activation statement of ``challenge()``,
#: attested at ATTESTED, flags 0x05 (presence + verification), counter 42.
KAT_PROOF = (
    "-----BEGIN SSH SIGNATURE-----\n"
    "U1NIU0lHAAAAAQAAAFcAAAAac2stc3NoLWVkMjU1MTlAb3BlbnNzaC5jb20AAAAgzILtcY\n"
    "MahejB2S3MO5e7ei0bVGDpY72CnrvhCs9WwE0AAAARc3NoOmFpZG8tYXBwcm92YWwAAAAQ\n"
    "YWlkby1hcHByb3ZhbEB2MQAAAAAAAAAGc2hhNTEyAAAAZwAAABpzay1zc2gtZWQyNTUxOU\n"
    "BvcGVuc3NoLmNvbQAAAEBKeNXRCcxVl3+r2lnBY8Yzez7JmIO2fykXqnW5EtuzeNj4PTBt\n"
    "82PrmSrJiO8qYAPJ9nlQe/6BFWceqi9vke0MBQAAACo=\n"
    "-----END SSH SIGNATURE-----\n"
)


def kat_attestation() -> tuple[ApprovalChallengeV2, HumanAttestationV2]:
    ch = challenge()
    return ch, attestation(ch, proof=KAT_PROOF)


def test_kat_public_key_and_fingerprint() -> None:
    assert key_line(ALICE) == KAT_PUBLIC_KEY
    parsed = sshsig.parse_sk_public_key_line(KAT_PUBLIC_KEY)
    assert parsed.application == APP and parsed.ed25519 == raw_public(ALICE)
    assert parsed.fingerprint == KAT_FINGERPRINT == fingerprint(sk_blob(ALICE))


def test_kat_signature_is_reproduced_and_verifies(world) -> None:
    ch, att = kat_attestation()
    assert armor(sign(ALICE, statement_bytes(private=ALICE, ch=ch), flags=0x05, counter=42)) == KAT_PROOF
    record = consume(world, ch, att)
    assert (record.authenticator_flags, record.authenticator_counter, record.user_verified) == (0x05, 42, True)
    assert record.key_fingerprint_sha256 == KAT_FINGERPRINT


def test_kat_signature_structure() -> None:
    parsed = sshsig.parse_armored_sshsig(KAT_PROOF)
    assert parsed.namespace == NS and parsed.hash_algorithm == "sha512"
    assert parsed.public_key.blob == sk_blob(ALICE) and (parsed.flags, parsed.counter) == (5, 42)
    assert len(parsed.ed25519_signature) == 64
    # what the authenticator signed, rebuilt by the module and by hand, agrees
    message = statement_bytes(private=ALICE, ch=challenge())
    by_hand = (hashlib.sha256(APP.encode()).digest() + b"\x05" + (42).to_bytes(4, "big")
               + hashlib.sha256(b"SSHSIG" + s(NS.encode()) + s(b"") + s(b"sha512")
                                + s(hashlib.sha512(message).digest())).digest())
    assert sshsig.sk_signed_data(APP, 5, 42, sshsig.sshsig_signed_data(NS, message)) == by_hand
    ALICE.public_key().verify(parsed.ed25519_signature, by_hand)


def test_a_valid_vector_verifies_for_consumption_and_reproof(world) -> None:
    ch = challenge()
    att = attestation(ch)
    first = consume(world, ch, att)
    later = reprove(world, ch, att, clock=Clock(ISSUED + timedelta(days=30)))
    for record in (first, later):
        assert record.state_root_id == STATE_ROOT_ID and record.challenge_id == CHALLENGE_ID
        assert record.subject_kind is K.PLAN_ACTIVATION and record.subject_sha256 == SUBJECT
        assert record.approver_id == "alice" and record.attested_at == ATTESTED
        assert record.attestation_sha256 == att.sha256
        assert record.statement_sha256 == hashlib.sha256(statement_bytes(private=ALICE, ch=ch)).hexdigest()
        assert record.registry_sha256 == hashlib.sha256(world.registry_bytes()).hexdigest()
        assert record.identity_boundary_sha256 == hashlib.sha256(world.boundary_bytes()).hexdigest()
        assert record.facts_origin == "injected" and record.is_production is False
        assert (record.authenticator_flags, record.authenticator_counter, record.user_verified) == (1, 7, False)
    assert (first.purpose, later.purpose) == ("consumption", "reproof")
    assert later.verified_at == ISSUED + timedelta(days=30)


@pytest.mark.parametrize("kind", list(K))
def test_every_subject_kind_verifies(world, kind) -> None:
    ch = challenge(kind)
    assert consume(world, ch, attestation(ch)).subject_kind is kind


def test_crlf_armor_and_other_line_widths_are_the_same_signature(world) -> None:
    ch = challenge()
    blob = sign(ALICE, statement_bytes(private=ALICE, ch=ch))
    digests = {consume(world, ch, attestation(ch, proof=armor(blob, newline, width))).signature_sha256
               for newline in ("\n", "\r\n") for width in (64, 70, 76)}
    assert digests == {hashlib.sha256(blob).hexdigest()}
    no_final_newline = armor(blob)[:-1]
    assert consume(world, ch, attestation(ch, proof=no_final_newline))


# =============================================================================
# 3. SSHSIG / sk structure
# =============================================================================


def good_blob(ch: ApprovalChallengeV2 | None = None, **options) -> bytes:
    ch = ch or challenge()
    return sign(ALICE, statement_bytes(private=ALICE, ch=ch), **options)


@pytest.mark.parametrize("proof", [
    "x",
    "-----BEGIN SSH SIGNATURE-----\n-----END SSH SIGNATURE-----\n",
    "-----BEGIN SSH SIGNATURE-----\nAAAA\n",
    "-----BEGIN PGP SIGNATURE-----\nAAAA\n-----END SSH SIGNATURE-----\n",
    "-----BEGIN SSH SIGNATURE-----\nAA==AA==\n-----END SSH SIGNATURE-----\n",
    "-----BEGIN SSH SIGNATURE-----\nAAA\n-----END SSH SIGNATURE-----\n",
    "-----BEGIN SSH SIGNATURE-----\nAAB=\n-----END SSH SIGNATURE-----\n",  # non-canonical padding bits
    "-----BEGIN SSH SIGNATURE-----\n\n-----END SSH SIGNATURE-----\n",
    "-----BEGIN SSH SIGNATURE-----\n" + "A" * 80 + "\n-----END SSH SIGNATURE-----\n",
    "-----BEGIN SSH SIGNATURE-----\nAA AA\n-----END SSH SIGNATURE-----\n",
    " -----BEGIN SSH SIGNATURE-----\nAAAA\n-----END SSH SIGNATURE-----\n",
    "-----BEGIN SSH SIGNATURE-----\r\nAAAA\n-----END SSH SIGNATURE-----\r\n",
    "-----BEGIN SSH SIGNATURE-----\nAAAA\n-----END SSH SIGNATURE-----\n\n",
    "-----BEGIN SSH SIGNATURE-----\nAAAA\r-----END SSH SIGNATURE-----\n",
    "-----BEGIN SSH SIGNATURE-----\nAAAA\n-----END SSH SIGNATURE-----\nAAAA\n",
])
def test_malformed_armor_is_refused(world, proof) -> None:
    ch = challenge()
    refused(R.PROOF_MALFORMED, consume, world, ch, attestation(ch, proof=proof))


def test_noncanonical_base64_of_a_valid_signature_is_refused(world) -> None:
    ch = challenge()
    text = base64.b64encode(good_blob(ch)).decode()
    assert text.endswith("=")
    # change the unused low bits of the last data character
    last = text.rstrip("=")
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
    bumped = last[:-1] + alphabet[alphabet.index(last[-1]) + 1] + text[len(last):]
    assert base64.b64decode(bumped) == base64.b64decode(text)
    proof = "-----BEGIN SSH SIGNATURE-----\n" + bumped + "\n-----END SSH SIGNATURE-----\n"
    refused(R.PROOF_MALFORMED, consume, world, ch, attestation(ch, proof=proof))


def test_every_truncation_of_a_valid_signature_is_refused(world) -> None:
    ch = challenge()
    blob = good_blob(ch)
    for length in range(len(blob)):
        with pytest.raises(HumanAttestationRefusedError) as info:
            consume(world, ch, attestation(ch, proof=armor(blob[:length])))
        assert info.value.category in (R.PROOF_MALFORMED, R.ALGORITHM_UNSUPPORTED), (length, info.value)


@pytest.mark.parametrize("options, category", [
    ({"envelope_trailing": b"\x00"}, R.PROOF_MALFORMED),
    ({"sig_trailing": b"\x00"}, R.PROOF_MALFORMED),
    ({"magic": b"SSHSIH"}, R.PROOF_MALFORMED),
    ({"version": 2}, R.ALGORITHM_UNSUPPORTED),
    ({"version": 0}, R.ALGORITHM_UNSUPPORTED),
    ({"reserved": b"x"}, R.PROOF_MALFORMED),
    ({"hash_alg": "sha256"}, R.ALGORITHM_UNSUPPORTED),
    ({"hash_alg": "SHA512"}, R.ALGORITHM_UNSUPPORTED),
    ({"namespace": "git"}, R.NAMESPACE_MISMATCH),
    ({"namespace": "file"}, R.NAMESPACE_MISMATCH),
    ({"namespace": "aido-approval@v2"}, R.NAMESPACE_MISMATCH),
    ({"namespace": "aido-approval@v1 "}, R.NAMESPACE_MISMATCH),
    ({"sig_type": "ssh-ed25519"}, R.ALGORITHM_UNSUPPORTED),
    ({"sig_type": "webauthn-sk-ecdsa-sha2-nistp256@openssh.com"}, R.ALGORITHM_UNSUPPORTED),
])
def test_envelope_and_signature_structure_refusals(world, options, category) -> None:
    ch = challenge()
    refused(category, consume, world, ch, attestation(ch, proof=armor(good_blob(ch, **options))))


def test_a_namespace_with_bytes_that_are_not_ascii_is_refused(world) -> None:
    ch = challenge()
    blob = good_blob(ch, namespace="aido-approval@v1")
    tampered = blob.replace(s(NS.encode()), s("aido-approval@v\u00b9".encode()), 1)
    with pytest.raises(HumanAttestationRefusedError) as info:
        consume(world, ch, attestation(ch, proof=armor(tampered)))
    assert info.value.category in (R.PROOF_MALFORMED, R.NAMESPACE_MISMATCH)


@pytest.mark.parametrize("pub_blob, category", [
    # an ordinary software ssh-ed25519 key never proves a touch
    (lambda: s(b"ssh-ed25519") + s(raw_public(ALICE)), R.ALGORITHM_UNSUPPORTED),
    (lambda: s(SK.encode()) + s(raw_public(ALICE)[:31]) + s(APP.encode()), R.PROOF_MALFORMED),
    (lambda: s(SK.encode()) + s(raw_public(ALICE) + b"\0") + s(APP.encode()), R.PROOF_MALFORMED),
    (lambda: s(SK.encode()) + s(raw_public(ALICE)), R.PROOF_MALFORMED),
    (lambda: sk_blob(ALICE) + b"\0", R.PROOF_MALFORMED),
    (lambda: s(SK.encode()) + s(raw_public(ALICE)) + s("ssh:\u00e9".encode()), R.PROOF_MALFORMED),
    (lambda: s(SK.encode()) + s(raw_public(ALICE)) + s(b"ssh: aido"), R.PROOF_MALFORMED),
    (lambda: s(SK.encode()) + s(b"\x01" + b"\0" * 31) + s(APP.encode()), R.PROOF_MALFORMED),  # small order
    (lambda: (0xFFFF_FFFF).to_bytes(4, "big") + SK.encode(), R.PROOF_MALFORMED),
])
def test_public_key_blob_refusals(world, pub_blob, category) -> None:
    ch = challenge()
    refused(category, consume, world, ch, attestation(ch, proof=armor(good_blob(ch, pub_blob=pub_blob()))))


def test_wrong_ed25519_signature_lengths_are_refused(world) -> None:
    ch = challenge()
    blob = good_blob(ch)
    parsed = sshsig.parse_sshsig_blob(blob)
    for bad in (parsed.ed25519_signature[:63], parsed.ed25519_signature + b"\0"):
        signature = s(SK.encode()) + s(bad) + b"\x01" + (7).to_bytes(4, "big")
        envelope = (b"SSHSIG" + (1).to_bytes(4, "big") + s(sk_blob(ALICE)) + s(NS.encode()) + s(b"")
                    + s(b"sha512") + s(signature))
        refused(R.PROOF_MALFORMED, consume, world, ch, attestation(ch, proof=armor(envelope)))


def test_oversized_declared_lengths_are_refused_without_reading_past_the_blob() -> None:
    huge = b"SSHSIG" + (1).to_bytes(4, "big") + (2**31).to_bytes(4, "big")
    with pytest.raises(sshsig.SshSigError) as info:
        sshsig.parse_sshsig_blob(huge)
    assert info.value.category == "proof_malformed"
    with pytest.raises(sshsig.SshSigError):
        sshsig.parse_sshsig_blob(b"SSHSIG" + (1).to_bytes(4, "big") + (5000).to_bytes(4, "big") + b"\0" * 5000)


def test_random_mutations_of_a_valid_signature_never_verify(world) -> None:
    ch = challenge()
    blob = good_blob(ch)
    rng = random.Random(4242)
    accepted = 0
    for _ in range(400):
        mutated = bytearray(blob)
        for _ in range(rng.randint(1, 3)):
            choice = rng.random()
            index = rng.randrange(len(mutated))
            if choice < 0.6:
                mutated[index] ^= 1 << rng.randrange(8)
            elif choice < 0.8:
                del mutated[index]
            else:
                mutated.insert(index, rng.randrange(256))
        if bytes(mutated) == blob:
            continue
        try:
            consume(world, ch, attestation(ch, proof=armor(bytes(mutated))))
            accepted += 1
        except HumanAttestationRefusedError:
            pass
    assert accepted == 0


# =============================================================================
# 4. signature, identity and flags
# =============================================================================


def test_a_flipped_signature_bit_is_signature_invalid(world) -> None:
    ch = challenge()
    blob = bytearray(good_blob(ch))
    parsed = sshsig.parse_sshsig_blob(bytes(blob))
    offset = bytes(blob).index(parsed.ed25519_signature)
    blob[offset + 10] ^= 0x01
    refused(R.SIGNATURE_INVALID, consume, world, ch, attestation(ch, proof=armor(bytes(blob))))


@pytest.mark.parametrize("options", [
    {"flags": 0x01, "signed_flags": 0x00},  # flags rewritten after signing
    {"flags": 0x05, "signed_flags": 0x01},  # UV claimed but not signed
    {"counter": 8, "signed_counter": 7},
    {"signed_application": "ssh:"},  # the authenticator was asked for another relying party
])
def test_unsigned_authenticator_data_is_signature_invalid(world, options) -> None:
    ch = challenge()
    refused(R.SIGNATURE_INVALID, consume, world, ch, attestation(ch, **options))


@pytest.mark.parametrize("field_change", [
    {"root": OTHER_ROOT_ID},  # an attestation for another state root
    {"approver": "bob"},  # signed as bob, presented as alice: handled below
])
def test_a_valid_signature_over_a_different_statement_refuses(world, field_change) -> None:
    ch = challenge()
    if "root" in field_change:
        att = attestation(ch, root=OTHER_ROOT_ID)
        refused(R.SIGNATURE_INVALID, consume, world, ch, att)
        assert consume(world, ch, att, root=OTHER_ROOT_ID)
    else:
        message = statement_bytes(private=ALICE, ch=ch, approver="bob")
        refused(R.SIGNATURE_INVALID, consume, world, ch, attestation(ch, message=message))


@pytest.mark.parametrize("message_change", [
    {"subject": "77" * 32},
    {"challenge_id": "bb" * 16},
    {"kind": K.STEP_ACCEPTANCE},
    {"attested_at": ATTESTED + timedelta(seconds=1)},
    {"fingerprint_of": "bob"},
    {"application": "ssh:"},
])
def test_signature_substitution_across_statement_fields_refuses(world, message_change) -> None:
    ch = challenge()
    other = ch
    if "subject" in message_change:
        other = challenge(subject_sha256=message_change["subject"])
    if "challenge_id" in message_change:
        other = challenge(challenge_id=message_change["challenge_id"])
    if "kind" in message_change:
        other = challenge(message_change["kind"])
    attested = message_change.get("attested_at", ATTESTED)
    private_for_fp = BOB if "fingerprint_of" in message_change else ALICE
    message = statement_bytes(private=private_for_fp, ch=other, attested_at=attested,
                              application=message_change.get("application", APP))
    refused(R.SIGNATURE_INVALID, consume, world, ch, attestation(ch, message=message))


def test_a_signature_by_another_registered_approver_is_key_unknown(world) -> None:
    ch = challenge()
    att = attestation(ch, private=BOB, approver="alice",
                      message=statement_bytes(private=BOB, ch=ch, approver="alice"))
    refused(R.KEY_UNKNOWN, consume, world, ch, att, match=fingerprint(sk_blob(BOB)))
    # and bob's own, correctly attributed, verifies
    assert consume(world, ch, attestation(ch, private=BOB, approver="bob")).approver_id == "bob"


def test_an_unregistered_key_and_an_unregistered_approver_are_key_unknown(world) -> None:
    ch = challenge()
    refused(R.KEY_UNKNOWN, consume, world, ch, attestation(ch, private=key(99)))
    refused(R.KEY_UNKNOWN, consume, world, ch, attestation(ch, approver="mallory"))


def test_the_registered_key_with_another_application_is_application_mismatch(world) -> None:
    ch = challenge()
    for application in ("ssh:", "ssh:aido-approval2", "ssh:AIDO-approval"):
        refused(R.APPLICATION_MISMATCH, consume, world, ch, attestation(ch, application=application))


def test_presence_and_user_verification(world) -> None:
    ch = challenge()
    refused(R.PRESENCE_MISSING, consume, world, ch, attestation(ch, flags=0x00))
    refused(R.PRESENCE_MISSING, consume, world, ch, attestation(ch, flags=0x04))
    assert consume(world, ch, attestation(ch, flags=0x01)).user_verified is False
    world.registry["approvers"][0]["require_user_verification"] = True
    refused(R.USER_VERIFICATION_MISSING, consume, world, ch, attestation(ch, flags=0x01))
    assert consume(world, ch, attestation(ch, flags=0x05)).user_verified is True


@pytest.mark.parametrize("flags", [0x03, 0x09, 0x11, 0x21, 0x41, 0x81, 0xFF, 0x45])
def test_unsupported_authenticator_flags_refuse(world, flags) -> None:
    ch = challenge()
    refused(R.FLAGS_UNSUPPORTED, consume, world, ch, attestation(ch, flags=flags))


def test_the_counter_is_recorded_not_enforced(world) -> None:
    ch = challenge()
    for counter in (0, 7, 2**32 - 1):
        assert consume(world, ch, attestation(ch, counter=counter)).authenticator_counter == counter


# =============================================================================
# 5. challenge and timestamps
# =============================================================================


def test_attestation_and_challenge_must_agree(world) -> None:
    ch = challenge()
    other = challenge(challenge_id="bb" * 16)
    refused(R.STATEMENT_MISMATCH, consume, world, ch, attestation(other))
    refused(R.STATEMENT_MISMATCH, consume, world, ch, attestation(challenge(subject_sha256="77" * 32)))
    refused(R.STATEMENT_MISMATCH, consume, world, ch, attestation(challenge(K.STEP_ACCEPTANCE)))


@pytest.mark.parametrize("attested_at", [
    ISSUED - timedelta(microseconds=1),
    ISSUED + APPROVAL_CHALLENGE_TTL + timedelta(microseconds=1),
    datetime(2020, 1, 1, tzinfo=timezone.utc),
])
def test_forged_attestation_times_refuse_in_both_modes(world, attested_at) -> None:
    ch = challenge()
    att = attestation(ch, attested_at=attested_at)
    refused(R.TIMESTAMP_INVALID, consume, world, ch, att, clock=Clock(ISSUED + timedelta(minutes=59)))
    refused(R.TIMESTAMP_INVALID, reprove, world, ch, att)


def test_the_attestation_may_not_be_dated_after_aidos_clock(world) -> None:
    ch = challenge()
    att = attestation(ch, attested_at=NOW + timedelta(seconds=1))
    refused(R.TIMESTAMP_INVALID, consume, world, ch, att)
    assert reprove(world, ch, att)  # the store's consumption time, not the clock, bounded it then


def test_the_sixty_minute_challenge_lifetime_is_enforced_at_consumption(world) -> None:
    ch = challenge()
    att = attestation(ch)
    assert consume(world, ch, att, clock=Clock(ISSUED + APPROVAL_CHALLENGE_TTL - timedelta(microseconds=1)))
    refused(R.CHALLENGE_EXPIRED, consume, world, ch, att, clock=Clock(ISSUED + APPROVAL_CHALLENGE_TTL))
    refused(R.TIMESTAMP_INVALID, consume, world, ch, att, clock=Clock(ISSUED - timedelta(seconds=1)))
    assert reprove(world, ch, att, clock=Clock(ISSUED + timedelta(days=365)))


@pytest.mark.parametrize("clock", [
    lambda: datetime(2026, 10, 23, 12, 10),
    lambda: "2026-10-23T12:10:00Z",
    lambda: None,
    lambda: 1_700_000_000,
])
def test_an_unusable_clock_refuses(world, clock) -> None:
    ch = challenge()
    with pytest.raises(HumanAttestationRefusedError) as info:
        RegistryHumanAttestationVerifier.from_facts(world, clock=clock).verify_for_consumption(
            state_root_id=STATE_ROOT_ID, challenge=ch, attestation=attestation(ch))
    assert info.value.category is R.TIMESTAMP_INVALID


def test_a_raising_clock_refuses(world) -> None:
    def clock():
        raise RuntimeError("secret-clock-detail")

    ch = challenge()
    with pytest.raises(HumanAttestationRefusedError) as info:
        RegistryHumanAttestationVerifier.from_facts(world, clock=clock).reprove(
            state_root_id=STATE_ROOT_ID, challenge=ch, attestation=attestation(ch))
    assert info.value.category is R.TIMESTAMP_INVALID and "secret-clock-detail" not in str(info.value)


def test_a_typed_phrase_without_a_signature_is_nothing(world) -> None:
    ch = challenge()
    for proof in ("I approve this execution plan, policy and target workspace for AIDO execution",
                  "approved", ch.subject_sha256, "True"):
        refused(R.PROOF_MALFORMED, consume, world, ch, attestation(ch, proof=proof))


# =============================================================================
# 6. registry content
# =============================================================================


def _with_entry(world: RegWorld, **changes) -> None:
    world.registry["approvers"][0].update(changes)


@pytest.mark.parametrize("raw", [
    b"\xef\xbb\xbf{}",
    b"not json",
    b'{"schema_version":"approver-registry.v1","approvers":[]}',
    b'{"schema_version":"approver-registry.v2","approvers":[]}',
    b'{"schema_version":"approver-registry.v1","approvers":[],"approvers":[]}',
    b'{"schema_version":"approver-registry.v1","approvers":[],"extra":1}',
    b'[]',
    b'{"schema_version":"approver-registry.v1","approvers":NaN}',
    b"\xff\xfe",
    b"{" + b" " * (64 * 1024) + b"}",
], ids=lambda raw: f"{len(raw)}-bytes-{raw[:12]!r}")
def test_malformed_registry_documents_refuse(world, raw) -> None:
    world.registry_raw = raw
    ch = challenge()
    refused(R.REGISTRY_MALFORMED, consume, world, ch, attestation(ch))


@pytest.mark.parametrize("changes", [
    {"fingerprint_sha256": fingerprint(sk_blob(BOB))},
    {"fingerprint_sha256": "SHA256:abc"},
    {"fingerprint_sha256": fingerprint(sk_blob(ALICE)).lower()},
    {"application": "ssh:"},
    {"public_key": key_line(ALICE, "ssh:")},
    {"public_key": key_line(ALICE) + " alice@laptop"},
    {"public_key": key_line(ALICE).replace(" ", "  ")},
    {"public_key": "ssh-ed25519 " + base64.b64encode(s(b"ssh-ed25519") + s(raw_public(ALICE))).decode()},
    {"public_key": SK + " " + base64.b64encode(sk_blob(ALICE) + b"\0").decode()},
    {"not_before": "2027-01-01T00:00:00Z"},
    {"not_after": "2026-01-01T00:00:00Z"},
    {"not_before": "2026-01-01T00:00:00"},
    {"not_before": "2026-01-01"},
    {"not_before": 1_700_000_000},
    {"revoked": 0},
    {"revoked": "false"},
    {"require_user_verification": None},
    {"approver_id": " "},
    {"approver_id": "a" * 201},
    {"extra": True},
])
def test_malformed_registry_entries_refuse(world, changes) -> None:
    _with_entry(world, **changes)
    ch = challenge()
    refused(R.REGISTRY_MALFORMED, consume, world, ch, attestation(ch))


def test_one_key_registered_twice_refuses(world) -> None:
    world.registry["approvers"].append(entry(ALICE, "alice-2"))
    ch = challenge()
    refused(R.REGISTRY_MALFORMED, consume, world, ch, attestation(ch))


def test_registry_parser_reports_no_registry_bytes() -> None:
    with pytest.raises(RegistryError) as info:
        parse_approver_registry(b'{"schema_version":"secret-registry-value"}')
    assert "secret-registry-value" not in str(info.value)


def test_a_missing_registry_refuses(world) -> None:
    world.remove(REGISTRY)
    ch = challenge()
    refused(R.REGISTRY_UNREADABLE, consume, world, ch, attestation(ch))


# =============================================================================
# 7. revocation, validity windows and rotation across repeated verification
# =============================================================================


def test_revocation_is_total_and_takes_effect_at_the_next_verification(world) -> None:
    ch = challenge()
    att = attestation(ch)
    v = verifier(world)
    assert v.verify_for_consumption(state_root_id=STATE_ROOT_ID, challenge=ch, attestation=att)
    world.registry["approvers"][0]["revoked"] = True
    refused(R.KEY_REVOKED, v.reprove, state_root_id=STATE_ROOT_ID, challenge=ch, attestation=att)
    refused(R.KEY_REVOKED, v.verify_for_consumption, state_root_id=STATE_ROOT_ID, challenge=ch, attestation=att)
    # nothing was cached: the same instance follows the registry back
    world.registry["approvers"][0]["revoked"] = False
    assert v.reprove(state_root_id=STATE_ROOT_ID, challenge=ch, attestation=att)


def test_revoking_one_key_leaves_another_approvers_key_valid(world) -> None:
    ch = challenge()
    world.registry["approvers"][0]["revoked"] = True
    assert consume(world, ch, attestation(ch, private=BOB, approver="bob"))


@pytest.mark.parametrize("changes", [
    {"not_before": "2026-10-23T12:00:00.000001Z"},
    {"not_after": "2026-10-23T12:59:59.999999Z"},
    {"not_before": "2026-10-23T12:30:00Z"},
    {"not_after": "2026-10-23T12:30:00Z"},
    {"not_before": "2027-06-01T00:00:00Z", "not_after": "2028-01-01T00:00:00Z"},
])
def test_the_validity_window_must_cover_the_whole_challenge(world, changes) -> None:
    _with_entry(world, **changes)
    ch = challenge()
    att = attestation(ch)
    refused(R.KEY_NOT_VALID, consume, world, ch, att)
    refused(R.KEY_NOT_VALID, reprove, world, ch, att)


def test_a_window_exactly_covering_the_challenge_and_offsets_are_compared_as_instants(world) -> None:
    _with_entry(world, not_before="2026-10-23T14:00:00+02:00", not_after="2026-10-23T08:00:00-05:00")
    ch = challenge()
    assert consume(world, ch, attestation(ch))


def test_key_rotation(world) -> None:
    old_ch = challenge()
    old_att = attestation(old_ch)
    assert consume(world, old_ch, old_att)
    # rotate: the old key's window closes after the old challenge; the new key opens
    world.registry["approvers"][0]["not_after"] = "2026-10-24T00:00:00Z"
    world.registry["approvers"].append(entry(ALICE_NEW, not_before="2026-10-24T00:00:00Z"))
    assert reprove(world, old_ch, old_att, clock=Clock(datetime(2026, 11, 1, tzinfo=timezone.utc)))

    new_issued = datetime(2026, 11, 1, 9, 0, tzinfo=timezone.utc)
    new_ch = challenge(challenge_id="cc" * 16, issued_at=new_issued, expires_at=new_issued + APPROVAL_CHALLENGE_TTL)
    clock = Clock(new_issued + timedelta(minutes=1))
    refused(R.KEY_NOT_VALID, consume, world, new_ch,
            attestation(new_ch, attested_at=new_issued, private=ALICE), clock=clock)
    record = consume(world, new_ch, attestation(new_ch, attested_at=new_issued, private=ALICE_NEW), clock=clock)
    assert record.key_fingerprint_sha256 == fingerprint(sk_blob(ALICE_NEW))

    # deleting, rather than closing, the old entry untrusts what it signed
    del world.registry["approvers"][0]
    refused(R.KEY_UNKNOWN, reprove, world, old_ch, old_att)


def test_a_key_moved_to_another_approver_no_longer_proves_the_old_attribution(world) -> None:
    ch = challenge()
    att = attestation(ch)
    assert reprove(world, ch, att)
    world.registry["approvers"][0]["approver_id"] = "carol"
    refused(R.KEY_UNKNOWN, reprove, world, ch, att)


# =============================================================================
# 8. registry protection, through S0's facts and evaluator
# =============================================================================


def _registry_unprotected(world: RegWorld, isolation: C | None = None, match: str | None = None) -> None:
    ch = challenge()
    error = refused(R.REGISTRY_UNPROTECTED, consume, world, ch, attestation(ch), match=match)
    if isolation is not None:
        assert error.detail.startswith(f"isolation_unproven:{isolation.value}:"), error.detail


@pytest.mark.parametrize("role_sid", [A, X, O, USERS])
@pytest.mark.parametrize("mask", [FILE_WRITE_DATA, FILE_APPEND_DATA, DELETE, WRITE_DAC, WRITE_OWNER])
def test_a_registry_file_any_identity_can_alter_refuses(world, role_sid, mask) -> None:
    world.node(REGISTRY).aces.append(allow(role_sid, mask))
    _registry_unprotected(world, C.BOUNDARY_UNPROTECTED, "the approver registry")


@pytest.mark.parametrize("role_sid", [A, X, O])
def test_a_registry_directory_that_lets_an_identity_delete_its_child_refuses(world, role_sid) -> None:
    world.node(ANCHOR_DIR).aces.append(allow(role_sid, FILE_DELETE_CHILD))
    _registry_unprotected(world, C.BOUNDARY_UNPROTECTED)


@pytest.mark.parametrize("ancestor", ["C:\\", "C:\\ProgramData"])
@pytest.mark.parametrize("mask", [WRITE_DAC, WRITE_OWNER])
def test_ancestor_takeover_by_x_refuses(world, ancestor, mask) -> None:
    world.node(ancestor).aces.insert(0, allow(X, mask))
    _registry_unprotected(world, C.BOUNDARY_UNPROTECTED, "an ancestor of")


def test_an_x_owned_ancestor_refuses(world) -> None:
    world.node("C:\\ProgramData").owner = X
    _registry_unprotected(world, C.BOUNDARY_UNPROTECTED)


@pytest.mark.parametrize("owner", [A, X, O, USERS])
def test_a_registry_not_owned_by_an_administrator_principal_refuses(world, owner) -> None:
    world.node(REGISTRY).owner = owner
    _registry_unprotected(world, C.BOUNDARY_UNPROTECTED, "owned by")


def test_registry_substitution_by_link_or_redirect_refuses(world) -> None:
    for mutate in (
        lambda n: setattr(n, "reparse", True),
        lambda n: setattr(n, "links", 2),
        lambda n: setattr(n, "final", "C:\\Users\\aido-x\\approver-registry.v1.json"),
        lambda n: setattr(n, "final", "C:\\PROGRA~1\\AIDO\\approver-registry.v1.json"),
        lambda n: setattr(n, "is_dir", True),
    ):
        w = reg_world()
        mutate(w.node(REGISTRY))
        _registry_unprotected(w, C.BOUNDARY_UNPROTECTED)


def test_a_new_file_x_could_plant_beside_the_registry_refuses(world) -> None:
    world.node(ANCHOR_DIR).aces.append(allow(X, 0x0002 | 0x0004))  # add file / subdirectory
    _registry_unprotected(world, C.BOUNDARY_UNPROTECTED)


def test_inheritance_that_would_make_new_anchor_files_x_writable_refuses(world) -> None:
    world.node(ANCHOR_DIR).aces.append(allow(X, FILE_ALL_ACCESS, 0x0001 | 0x0008))  # OI | IO
    _registry_unprotected(world, C.BOUNDARY_UNPROTECTED)


def test_a_registry_protected_only_by_its_own_dacl_is_not_enough(world) -> None:
    world.node(REGISTRY).aces = list(ADMIN_FULL)
    world.node(REGISTRY).protected = True
    world.node(ANCHOR_DIR).aces.append(allow(X, FILE_DELETE_CHILD))
    _registry_unprotected(world, C.BOUNDARY_UNPROTECTED)


@pytest.mark.parametrize("change, isolation", [
    ({"elevated": True}, C.TOKEN_ELEVATED),
    ({"elevation_type": 2}, C.TOKEN_ELEVATED),
    ({"elevation_type": 3}, C.TOKEN_ELEVATED),
    ({"integrity_rid": 0x3000}, C.TOKEN_ELEVATED),
    ({"privileges": ("SeChangeNotifyPrivilege", "SeBackupPrivilege")}, C.TOKEN_PRIVILEGED),
    ({"user_sid": X}, C.TOKEN_IDENTITY_MISMATCH),
    ({"user_sid": O}, C.TOKEN_IDENTITY_MISMATCH),
])
def test_an_elevated_privileged_or_foreign_process_refuses(world, change, isolation) -> None:
    from dataclasses import replace

    world.token = replace(world.token, **change)
    _registry_unprotected(world, isolation)


def test_an_administrators_member_token_refuses(world) -> None:
    from dataclasses import replace

    world.token = replace(world.token, groups=world.token.groups + ((ADMINISTRATORS, 0x10),))
    _registry_unprotected(world, C.ACCOUNT_PRIVILEGED)


def test_an_unprotected_identity_boundary_refuses_the_registry(world) -> None:
    world.node(ANCHOR_DIR + "\\identity-boundary.v1.json").aces.append(allow(X, FILE_WRITE_DATA))
    _registry_unprotected(world, C.BOUNDARY_UNPROTECTED, "identity boundary")


def test_a_missing_or_malformed_identity_boundary_refuses_the_registry(world) -> None:
    world.boundary_raw = b"{}"
    _registry_unprotected(world, C.BOUNDARY_MALFORMED)
    w = reg_world()
    w.remove(ANCHOR_DIR + "\\identity-boundary.v1.json")
    _registry_unprotected(w, C.BOUNDARY_UNREADABLE)


def test_an_execution_account_that_cannot_be_computed_refuses(world) -> None:
    del world.principals[X]
    _registry_unprotected(world, C.PRINCIPAL_UNVERIFIABLE)


def test_x_rights_are_evaluated_through_its_real_groups(world) -> None:
    group = "S-1-5-21-100-200-300-2001"
    world.principals[X] = PrincipalFacts(
        sid=X, account_name="HOST\\aido-x", sid_type=1, is_local_account=True,
        groups=world.principals[X].groups + ((group, 7),), privileges=world.principals[X].privileges,
    )
    world.node(REGISTRY).aces.append(allow(group, FILE_WRITE_DATA))
    _registry_unprotected(world, C.BOUNDARY_UNPROTECTED)


@pytest.mark.parametrize("method", ["read_file", "object_facts", "principal", "current_token",
                                    "program_data_directory", "is_windows"])
def test_any_unreadable_security_fact_refuses(world, monkeypatch, method) -> None:
    def broken(*args, **kwargs):
        raise OSError("secret-fact-detail")

    monkeypatch.setattr(world, method, broken)
    ch = challenge()
    error = refused(R.REGISTRY_UNPROTECTED, consume, world, ch, attestation(ch))
    assert "secret-fact-detail" not in str(error)


def test_facts_of_the_wrong_type_refuse(world, monkeypatch) -> None:
    monkeypatch.setattr(world, "read_file", lambda path, limit: ("facts", b"{}"))
    _registry_unprotected(world, C.SECURITY_FACT_UNAVAILABLE)


def test_non_windows_facts_refuse(world) -> None:
    world.windows = False
    _registry_unprotected(world, C.PLATFORM_UNSUPPORTED)


def test_every_verification_rereads_the_registry_and_boundary(world) -> None:
    ch = challenge()
    att = attestation(ch)
    v = verifier(world)
    for _ in range(3):
        before = len(world.calls)
        v.verify_for_consumption(state_root_id=STATE_ROOT_ID, challenge=ch, attestation=att)
        reads = world.calls[before:]
        assert reads.count(REGISTRY) >= 1
        assert reads.count(ANCHOR_DIR + "\\identity-boundary.v1.json") >= 1


def test_a_registry_replaced_between_two_proofs_is_read_afresh(world) -> None:
    ch = challenge()
    att = attestation(ch)
    v = verifier(world)
    first = v.reprove(state_root_id=STATE_ROOT_ID, challenge=ch, attestation=att)
    world.registry["approvers"].append(entry(ALICE_NEW, "alice"))
    second = v.reprove(state_root_id=STATE_ROOT_ID, challenge=ch, attestation=att)
    assert first.registry_sha256 != second.registry_sha256
    world.registry = {"schema_version": "approver-registry.v1", "approvers": [entry(BOB, "bob")]}
    refused(R.KEY_UNKNOWN, v.reprove, state_root_id=STATE_ROOT_ID, challenge=ch, attestation=att)


def test_independent_evaluation_is_recorded_and_unioned(world) -> None:
    world.independent = lambda d, p, k: upper_bound_rights(parse_security_descriptor(d), p, k)
    ch = challenge()
    record = consume(world, ch, attestation(ch))
    assert record.independent_evaluation is True and record.is_production is False
    world.independent = lambda d, p, k: FILE_WRITE_DATA if p.role == "execution" else 0
    _registry_unprotected(world, C.BOUNDARY_UNPROTECTED)


def test_the_registry_is_parsed_only_after_its_protection_is_proven(world) -> None:
    world.registry_raw = b"not json"
    world.node(REGISTRY).aces.append(allow(X, FILE_WRITE_DATA))
    _registry_unprotected(world, C.BOUNDARY_UNPROTECTED)


def test_read_approver_registry_returns_a_one_read_snapshot(world) -> None:
    snapshot = read_approver_registry(world, require_independent=False)
    assert snapshot.registry_sha256 == hashlib.sha256(world.registry_bytes()).hexdigest()
    assert snapshot.independent_evaluation is False
    with pytest.raises(RegistryError) as info:
        read_approver_registry(world, require_independent=True)
    assert info.value.category == "registry_unprotected"
    assert info.value.isolation_category is C.SECURITY_FACT_UNAVAILABLE


# =============================================================================
# 9. caller bypass and malformed objects
# =============================================================================


def test_a_verified_record_cannot_be_forged_mutated_subclassed_or_copied(world) -> None:
    ch = challenge()
    record = consume(world, ch, attestation(ch))
    with pytest.raises(TypeError):
        VerifiedHumanAttestation(purpose="consumption")
    with pytest.raises(TypeError):
        VerifiedHumanAttestation(_token=object(), **{name: None for name in verifier_module._RECORD_FIELDS})
    with pytest.raises(AttributeError):
        record.facts_origin = "windows"
    with pytest.raises(AttributeError):
        del record.approver_id
    with pytest.raises(TypeError):
        class Fake(VerifiedHumanAttestation):  # noqa: F841
            pass
    for duplicate in (copy.copy, copy.deepcopy, pickle.dumps):
        with pytest.raises(TypeError):
            duplicate(record)


def test_the_verifier_cannot_be_reconfigured_subclassed_or_copied(world) -> None:
    v = verifier(world)
    assert v.is_production is False
    with pytest.raises(AttributeError):
        v._origin = "windows"
    with pytest.raises(TypeError):
        v._configure(object(), "windows", None, lambda: NOW)
    with pytest.raises(TypeError):
        v._configure(verifier_module._CONFIG_TOKEN, "windows", None, lambda: NOW)  # configured once
    with pytest.raises(TypeError):
        class Fake(RegistryHumanAttestationVerifier):  # noqa: F841
            pass
    for duplicate in (copy.copy, copy.deepcopy, pickle.dumps):
        with pytest.raises(TypeError):
            duplicate(v)


def test_facts_claiming_windows_never_yield_a_production_record(world) -> None:
    world.independent = lambda d, p, k: upper_bound_rights(parse_security_descriptor(d), p, k)
    ch = challenge()
    record = consume(world, ch, attestation(ch))
    assert record.facts_origin == "injected" and record.is_production is False


def test_the_verifier_is_not_a_dl4a_v1_verifier(world, tmp_path) -> None:
    from ai_dev_orchestrator.control_plane.authority_session import open_authority_session
    from ai_dev_orchestrator.control_plane.containment import AidoStateRoot
    from ai_dev_orchestrator.control_plane.store import StoreError

    v = verifier(world)
    assert not hasattr(v, "verify")
    (tmp_path / "root").mkdir()
    root = AidoStateRoot.create(str(tmp_path / "root"))
    with pytest.raises(StoreError):
        open_authority_session(root, approval_verifier=v)


def test_v1_models_are_refused(world) -> None:
    ch1 = ApprovalChallenge(
        schema_version="approval-challenge.v1", challenge_id=CHALLENGE_ID,
        subject_kind=ApprovalSubjectKind.PLAN_ACTIVATION, subject_sha256=SUBJECT, issued_at=ISSUED,
        expires_at=ISSUED + APPROVAL_CHALLENGE_TTL, required_approval_text=APPROVAL_TEXT_V2[K.PLAN_ACTIVATION],
    )
    att2 = attestation(challenge())
    att1 = HumanAttestation(**{**att2.model_dump(), "schema_version": "human-attestation.v1",
                               "subject_kind": ApprovalSubjectKind.PLAN_ACTIVATION})
    refused(R.INPUT_INVALID, consume, world, ch1, att2)
    refused(R.INPUT_INVALID, consume, world, challenge(), att1)


def test_constructed_mutated_subclassed_and_foreign_inputs_are_refused(world) -> None:
    ch = challenge()
    att = attestation(ch)

    class SubChallenge(ApprovalChallengeV2):
        pass

    bad_inputs = [
        (ApprovalChallengeV2.model_construct(**{**ch.model_dump(), "expires_at": ISSUED + timedelta(days=9)}), att),
        (ch, HumanAttestationV2.model_construct(**{**att.model_dump(), "approval_text": "I approve"})),
        (ch, HumanAttestationV2.model_construct(**{**att.model_dump(), "proof": 123})),
        (SubChallenge(**ch.model_dump()), att),
        (ch.model_dump(), att),
        (ch, att.model_dump()),
        (ch, att.model_dump_json()),
        (None, att),
    ]
    mutated = attestation(ch)
    object.__setattr__(mutated, "subject_sha256", "not-hex")
    bad_inputs.append((ch, mutated))
    for bad_challenge, bad_attestation in bad_inputs:
        refused(R.INPUT_INVALID, consume, world, bad_challenge, bad_attestation)


@pytest.mark.parametrize("root", [None, 1, "0123", STATE_ROOT_ID.upper(), STATE_ROOT_ID + "0", b"0" * 32])
def test_a_malformed_state_root_id_is_refused(world, root) -> None:
    ch = challenge()
    refused(R.INPUT_INVALID, consume, world, ch, attestation(ch), root=root)


def test_a_mutated_but_valid_attestation_is_judged_on_its_real_contents(world) -> None:
    ch = challenge()
    att = attestation(ch)
    object.__setattr__(att, "approver_id", "bob")
    refused(R.KEY_UNKNOWN, consume, world, ch, att)


# -- found by the post-implementation review (§9 of the S1 document) ------------------


@pytest.mark.parametrize("facts", [None, object(), "C:\\ProgramData"])
def test_r1_a_facts_source_that_is_not_one_refuses_instead_of_raising(facts) -> None:
    ch = challenge()
    with pytest.raises(HumanAttestationRefusedError) as info:
        RegistryHumanAttestationVerifier.from_facts(facts, clock=Clock()).verify_for_consumption(
            state_root_id=STATE_ROOT_ID, challenge=ch, attestation=attestation(ch))
    assert info.value.category is R.REGISTRY_UNPROTECTED


def test_r1_a_facts_source_missing_one_method_refuses(world, monkeypatch) -> None:
    class Partial:
        def __getattr__(self, name):
            if name == "principal":
                raise AttributeError(name)
            return getattr(world, name)

    ch = challenge()
    with pytest.raises(HumanAttestationRefusedError) as info:
        RegistryHumanAttestationVerifier.from_facts(Partial(), clock=Clock()).verify_for_consumption(
            state_root_id=STATE_ROOT_ID, challenge=ch, attestation=attestation(ch))
    assert info.value.category is R.REGISTRY_UNPROTECTED


def test_r2_a_constructed_attestation_never_prints_its_proof_bytes(world, recwarn, capsys) -> None:
    ch = challenge()
    secret = b"raw-proof-secret-bytes"
    forged = HumanAttestationV2.model_construct(**{**attestation(ch).model_dump(), "proof": secret})
    refused(R.INPUT_INVALID, consume, world, ch, forged)
    assert not [w for w in recwarn if "raw-proof-secret" in str(w.message)]
    assert len(recwarn) == 0
    out = capsys.readouterr()
    assert "raw-proof-secret" not in out.out + out.err


def test_r3_a_str_subclass_state_root_id_is_refused(world) -> None:
    class Sneaky(str):
        def __eq__(self, other):
            return True

        __hash__ = str.__hash__

    ch = challenge()
    refused(R.INPUT_INVALID, consume, world, ch, attestation(ch), root=Sneaky(STATE_ROOT_ID))


def test_the_verify_methods_take_no_trust_argument() -> None:
    for name in ("verify_for_consumption", "reprove"):
        params = inspect.signature(getattr(RegistryHumanAttestationVerifier, name)).parameters
        assert list(params) == ["self", "state_root_id", "challenge", "attestation"]
        assert all(p.kind is inspect.Parameter.KEYWORD_ONLY for n, p in params.items() if n != "self")


def test_refusals_never_echo_the_proof_key_blob_or_registry(world) -> None:
    ch = challenge()
    blob = good_blob(ch)
    secrets = [base64.b64encode(blob).decode()[:60], base64.b64encode(sk_blob(ALICE)).decode()[:40]]
    attempts = [
        attestation(ch, proof=armor(blob[:-3])),
        attestation(ch, flags=0x00),
        attestation(ch, private=key(99)),
        attestation(ch, message=b"other"),
    ]
    messages = []
    for att in attempts:
        with pytest.raises(HumanAttestationRefusedError) as info:
            consume(world, ch, att)
        messages.append(str(info.value))
        assert info.value.__cause__ is None
        assert info.value.__context__ is None or info.value.__suppress_context__
    world.registry["approvers"][0]["approver_id"] = "secret-registry-approver"
    world.registry["approvers"][0]["revoked"] = 3
    with pytest.raises(HumanAttestationRefusedError) as info:
        consume(world, ch, attestation(ch))
    messages.append(str(info.value))
    for message in messages:
        for secret in secrets + ["secret-registry-approver"]:
            assert secret not in message, message


# =============================================================================
# 10. the production entry point
# =============================================================================


def test_the_production_constructor_takes_nothing() -> None:
    assert list(inspect.signature(RegistryHumanAttestationVerifier.__init__).parameters) == ["self"]
    assert RegistryHumanAttestationVerifier().is_production is True
    assert list(inspect.signature(RegistryHumanAttestationVerifier.from_facts).parameters) == ["facts", "clock"]


def test_production_refuses_off_windows_without_loading_win32(monkeypatch) -> None:
    monkeypatch.setattr(verifier_module.sys, "platform", "linux")
    monkeypatch.delitem(sys.modules, "ai_dev_orchestrator.integration.windows_security", raising=False)
    ch = challenge()
    with pytest.raises(HumanAttestationRefusedError) as info:
        RegistryHumanAttestationVerifier().reprove(
            state_root_id=STATE_ROOT_ID, challenge=ch, attestation=attestation(ch))
    assert info.value.category is R.REGISTRY_UNPROTECTED
    assert "ai_dev_orchestrator.integration.windows_security" not in sys.modules


@windows_only
def test_production_on_this_development_host_refuses_and_reads_only(monkeypatch) -> None:
    """There is no provisioned registry, boundary or authority account here:
    the live verifier must refuse. Only read-only fact methods may be used."""
    from ai_dev_orchestrator.integration import windows_security

    allowed = {"is_windows", "current_token", "program_data_directory", "read_file", "object_facts",
               "list_directory", "principal", "independent_rights"}
    used: list[str] = []
    for name in ("is_windows", "environment_names", "current_token", "program_data_directory", "read_file",
                 "object_facts", "list_directory", "principal", "session", "process", "code_load",
                 "independent_rights"):
        original = getattr(windows_security.WindowsSecurityFacts, name)
        monkeypatch.setattr(windows_security.WindowsSecurityFacts, name,
                            lambda self, *a, _o=original, _n=name: used.append(_n) or _o(self, *a))
    ch = challenge()
    with pytest.raises(HumanAttestationRefusedError) as info:
        RegistryHumanAttestationVerifier().reprove(
            state_root_id=STATE_ROOT_ID, challenge=ch, attestation=attestation(ch))
    assert info.value.category in (R.REGISTRY_UNPROTECTED, R.REGISTRY_UNREADABLE)
    assert used and set(used) <= allowed, used


def test_malformed_input_is_refused_before_any_fact_is_read(world) -> None:
    ch = challenge()
    refused(R.INPUT_INVALID, consume, world, ch, attestation(ch).model_dump())
    refused(R.PROOF_MALFORMED, consume, world, ch, attestation(ch, proof="nope"))
    assert world.calls == []


# =============================================================================
# 11. static boundaries
# =============================================================================

_PACKAGE = Path(integration.__file__).resolve().parent
_S1_MODULES = ("sshsig.py", "approver_registry.py", "attestation_verifier.py")
_CONTROL_PLANE = _PACKAGE.parent / "control_plane" / "attestation_v2.py"


def _tree(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"))


def _imports(tree: ast.AST) -> set[str]:
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            found.add(node.module or "")
    return found


def _names(tree: ast.AST) -> set[str]:
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    names |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    names |= {a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names}
    return names


def test_no_subprocess_network_signing_environment_or_harness_surface() -> None:
    forbidden_modules = {"subprocess", "socket", "httpx", "requests", "aiohttp", "urllib", "http", "asyncio",
                         "multiprocessing", "shutil", "tempfile", "winreg", "_winapi", "ssl", "ctypes", "os"}
    forbidden_names = {
        "Popen", "system", "popen", "startfile", "spawnv", "execv", "environ", "getenv", "environb",
        "putenv", "max_tokens", "remove", "unlink", "rename", "replace", "rmdir", "mkdir", "write_text",
        "write_bytes", "Ed25519PrivateKey", "generate", "sign", "private_bytes", "load_ssh_private_key",
        "load_pem_private_key", "from_private_bytes", "PrivateFormat", "serialization",
    }
    harness = ("ai_dev_orchestrator.llm", "ai_dev_orchestrator.github", "ai_dev_orchestrator.review",
               "ai_dev_orchestrator.verification", "ai_dev_orchestrator.file_editing",
               "ai_dev_orchestrator.supervised_implementer", "ai_dev_orchestrator.workspace",
               "ai_dev_orchestrator.cli")
    for path in [_PACKAGE / name for name in _S1_MODULES] + [_CONTROL_PLANE]:
        tree = _tree(path)
        imported = _imports(tree)
        assert not {m.split(".")[0] for m in imported} & forbidden_modules, (path.name, imported)
        assert not [m for m in imported if m.startswith(harness)], (path.name, imported)
        assert not _names(tree) & forbidden_names, (path.name, _names(tree) & forbidden_names)
        assert "open" not in {n.func.id for n in ast.walk(tree)
                              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}, path.name
        assert "ssh-keygen" not in path.read_text(encoding="utf-8").replace("``ssh-keygen", ""), path.name


def test_the_only_cryptography_use_is_ed25519_public_key_verification() -> None:
    crypto_imports = set()
    for path in [_PACKAGE / name for name in _S1_MODULES] + [_CONTROL_PLANE]:
        for node in ast.walk(_tree(path)):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("cryptography"):
                crypto_imports |= {(node.module, a.name) for a in node.names}
            if isinstance(node, ast.Import):
                assert not any(a.name.startswith("cryptography") for a in node.names)
    assert crypto_imports == {
        ("cryptography.exceptions", "InvalidSignature"),
        ("cryptography.hazmat.primitives.asymmetric.ed25519", "Ed25519PublicKey"),
    }
    calls = {n.func.attr for n in ast.walk(_tree(_PACKAGE / "sshsig.py"))
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert {"from_public_bytes", "verify"} <= calls


def test_the_dependency_is_pinned_exactly() -> None:
    pyproject = (_PACKAGE.parent.parent.parent / "pyproject.toml").read_text(encoding="utf-8")
    assert '"cryptography==50.0.2"' in pyproject
    import cryptography

    assert cryptography.__version__ == "50.0.2"


def test_registry_protection_reuses_s0_and_adds_no_rights_evaluator() -> None:
    tree = _tree(_PACKAGE / "approver_registry.py")
    names = _names(tree)
    assert not names & {"upper_bound_rights", "upper_bound_transform", "inherited_descriptor",
                        "AuthzAccessCheck", "independent_rights"}
    assert {"_check_token", "_read_boundary", "_check_identities", "_check_anchor",
            "limit_object", "not_replaceable"} <= names
    for name in ("sshsig.py", "attestation_verifier.py"):
        assert not _names(_tree(_PACKAGE / name)) & {"upper_bound_rights", "limit_object", "descriptor"}


def test_the_registry_location_is_a_code_constant() -> None:
    assert (reg_module.REGISTRY_DIRECTORY_NAME, reg_module.REGISTRY_FILE_NAME) == (
        "AIDO", "approver-registry.v1.json")
    assert reg_module.REGISTERED_APPLICATION == "ssh:aido-approval"
    signature = inspect.signature(read_approver_registry)
    assert list(signature.parameters) == ["facts", "require_independent"]


def test_only_the_production_constructor_can_mint_a_windows_origin() -> None:
    tree = _tree(_PACKAGE / "attestation_verifier.py")
    owners = set()
    for function in ast.walk(tree):
        if isinstance(function, ast.FunctionDef):
            for node in ast.walk(function):
                if isinstance(node, ast.Constant) and node.value == "windows":
                    owners.add(function.name)
    assert owners == {"__init__", "is_production", "_read_registry"}
    assert '"injected"' in inspect.getsource(RegistryHumanAttestationVerifier.from_facts)


def test_no_cli_command_and_no_control_plane_module_reaches_s1() -> None:
    root = _PACKAGE.parent
    cli = (root / "cli.py").read_text(encoding="utf-8")
    for term in ("attestation_verifier", "approver_registry", "sshsig", "attestation_v2",
                 "RegistryHumanAttestationVerifier"):
        assert term not in cli
    for module in (root / "control_plane").glob("*.py"):
        assert "ai_dev_orchestrator.integration" not in module.read_text(encoding="utf-8"), module.name
