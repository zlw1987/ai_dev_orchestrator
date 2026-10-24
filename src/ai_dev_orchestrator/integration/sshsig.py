"""DL-4B S1 — the one OpenSSH signature format AIDO accepts as human approval.

FD-1 fixes the protocol: an ``SSHSIG`` signature (OpenSSH ``PROTOCOL.sshsig``)
made by a FIDO2 security key of type ``sk-ssh-ed25519@openssh.com``
(``PROTOCOL.u2f``), namespace ``aido-approval@v1``, hash ``sha512``, with the
authenticator's user-presence flag set. Everything else is refused.

The nesting, outermost first, and what the Ed25519 signature finally covers:

```text
armor      -----BEGIN SSH SIGNATURE----- / base64 / -----END SSH SIGNATURE-----
SSHSIG     "SSHSIG" uint32(1) string(publickey) string(namespace) string(reserved)
           string(hash_algorithm) string(signature)
publickey  string("sk-ssh-ed25519@openssh.com") string(ed25519 key, 32) string(application)
signature  string("sk-ssh-ed25519@openssh.com") string(ed25519 sig, 64) byte(flags) uint32(counter)

signed by the authenticator (Ed25519, no prehash):
           SHA256(application) || flags || uint32(counter) || SHA256(sshsig_data)
sshsig_data "SSHSIG" string(namespace) string(reserved) string("sha512") string(SHA512(message))
```

Every length is checked against what remains, every nested string must be
consumed exactly, and no structure may carry trailing bytes. The base64 must be
canonical. Nothing is repaired or normalized.

This module is pure. It verifies with the pinned ``cryptography`` package
(FD-1a) and never implements curve arithmetic. It holds no private key and has
no signing function: a signature can only be checked here, never made.
Refusals are :class:`SshSigError` with a category and a detail that names
fields, never proof bytes or key material.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

SK_ED25519_KEY_TYPE = "sk-ssh-ed25519@openssh.com"
SSHSIG_MAGIC = b"SSHSIG"
SSHSIG_VERSION = 1
SSHSIG_HASH_ALGORITHM = "sha512"
ARMOR_BEGIN = "-----BEGIN SSH SIGNATURE-----"
ARMOR_END = "-----END SSH SIGNATURE-----"

#: Authenticator data flags (CTAP2 / WebAuthn): user present, user verified.
FLAG_USER_PRESENT = 0x01
FLAG_USER_VERIFIED = 0x04
#: The only flags an SSH security-key signature may carry here. Attested
#: credential data or extensions (0x40, 0x80) never belong to an SSH assertion,
#: and backup flags (0x08, 0x10) mark a synced, not a hardware-bound, credential.
ALLOWED_FLAGS = FLAG_USER_PRESENT | FLAG_USER_VERIFIED

#: Bounds on what one armored signature may decode to. A real one is ~250 bytes.
MAX_SSHSIG_BYTES = 4096
MAX_ARMOR_LINE = 76
MAX_APPLICATION_BYTES = 256

ED25519_KEY_BYTES = 32
ED25519_SIGNATURE_BYTES = 64

#: Ed25519 points of small order (as libsodium refuses them). A signature
#: under such a key can be made to verify for messages its holder never saw.
#: A real authenticator never produces one; the registry refuses it anyway.
_SMALL_ORDER_KEYS = frozenset(bytes.fromhex(h) for h in (
    "0100000000000000000000000000000000000000000000000000000000000000",
    "0000000000000000000000000000000000000000000000000000000000000000",
    "0000000000000000000000000000000000000000000000000000000000000080",
    "ecffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff7f",
    "ecffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
    "c7176a703d4dd84fba3c0b760d10670f2a2053fa2c39ccc64ec7fd7792ac037a",
    "c7176a703d4dd84fba3c0b760d10670f2a2053fa2c39ccc64ec7fd7792ac03fa",
    "26e8958fc2b227b045c3f489f2ef98f0d5dfac05d3c63339b13802886d53fc05",
    "26e8958fc2b227b045c3f489f2ef98f0d5dfac05d3c63339b13802886d53fc85",
))


class SshSigError(ValueError):
    """The proof or key is not the accepted SSHSIG / ``sk-ssh-ed25519`` form,
    or its signature does not verify. ``category`` is one of
    ``proof_malformed``, ``algorithm_unsupported``, ``namespace_mismatch``,
    ``signature_invalid``."""

    def __init__(self, category: str, detail: str) -> None:
        self.category = category
        self.detail = detail
        super().__init__(f"{category}: {detail}")


def _malformed(detail: str) -> SshSigError:
    return SshSigError("proof_malformed", detail)


class _Reader:
    """SSH wire-format reader (RFC 4251 §5) that refuses every short read."""

    def __init__(self, data: bytes, what: str) -> None:
        self._data = data
        self._offset = 0
        self._what = what

    def raw(self, count: int) -> bytes:
        end = self._offset + count
        if count < 0 or end > len(self._data):
            raise _malformed(f"{self._what} ends inside a field.")
        value = self._data[self._offset:end]
        self._offset = end
        return value

    def u8(self) -> int:
        return self.raw(1)[0]

    def u32(self) -> int:
        return int.from_bytes(self.raw(4), "big")

    def string(self, *, max_bytes: int = MAX_SSHSIG_BYTES) -> bytes:
        length = self.u32()
        if length > max_bytes:
            raise _malformed(f"{self._what} declares a field longer than its bound.")
        return self.raw(length)

    def text(self, *, max_bytes: int = MAX_APPLICATION_BYTES) -> str:
        value = self.string(max_bytes=max_bytes)
        try:
            text = value.decode("ascii")
        except UnicodeDecodeError:
            raise _malformed(f"{self._what} holds a name that is not ASCII.") from None
        if any(not 0x20 < ord(c) < 0x7F for c in text):
            raise _malformed(f"{self._what} holds a name with a control or space character.")
        return text

    def end(self) -> None:
        if self._offset != len(self._data):
            raise _malformed(f"{self._what} has trailing bytes.")


def _string(value: bytes) -> bytes:
    return len(value).to_bytes(4, "big") + value


@dataclass(frozen=True)
class SkEd25519PublicKey:
    """A parsed ``sk-ssh-ed25519@openssh.com`` public key."""

    blob: bytes
    ed25519: bytes
    application: str

    @property
    def fingerprint(self) -> str:
        return openssh_fingerprint(self.blob)


def openssh_fingerprint(blob: bytes) -> str:
    """``SHA256:<unpadded base64>``, as ``ssh-keygen -l`` prints it."""
    return "SHA256:" + base64.b64encode(hashlib.sha256(blob).digest()).decode("ascii").rstrip("=")


def parse_sk_public_key_blob(blob: bytes) -> SkEd25519PublicKey:
    if type(blob) is not bytes:
        raise _malformed("a public key must be bytes.")
    reader = _Reader(blob, "the public key")
    key_type = reader.text()
    if key_type != SK_ED25519_KEY_TYPE:
        # An ordinary ssh-ed25519 key is a software key: it never proves a touch.
        raise SshSigError("algorithm_unsupported", "the key is not an sk-ssh-ed25519@openssh.com key.")
    ed25519 = reader.string()
    if len(ed25519) != ED25519_KEY_BYTES:
        raise _malformed("the Ed25519 public key is not 32 bytes.")
    application = reader.text()
    reader.end()
    if ed25519 in _SMALL_ORDER_KEYS:
        raise _malformed("the Ed25519 public key is a point of small order.")
    try:
        Ed25519PublicKey.from_public_bytes(ed25519)
    except ValueError:
        raise _malformed("the Ed25519 public key is not a valid encoding.") from None
    return SkEd25519PublicKey(blob=bytes(blob), ed25519=bytes(ed25519), application=application)


def parse_sk_public_key_line(line: object) -> SkEd25519PublicKey:
    """Exactly ``sk-ssh-ed25519@openssh.com <base64>``: one space, canonical
    base64, no comment, no options."""
    if type(line) is not str or len(line) > 1024:
        raise _malformed("a public key line must be text of at most 1024 characters.")
    key_type, sep, encoded = line.partition(" ")
    if not sep or key_type != SK_ED25519_KEY_TYPE:
        raise SshSigError("algorithm_unsupported", "the key line is not an sk-ssh-ed25519@openssh.com key.")
    return parse_sk_public_key_blob(_strict_base64(encoded, "the public key line"))


def _strict_base64(encoded: str, what: str) -> bytes:
    if not encoded or len(encoded) % 4 or not encoded.isascii():
        raise _malformed(f"{what} is not canonical base64.")
    try:
        data = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        raise _malformed(f"{what} is not canonical base64.") from None
    if base64.b64encode(data).decode("ascii") != encoded:
        raise _malformed(f"{what} is not canonical base64.")
    return data


@dataclass(frozen=True)
class SkSshSignature:
    """A structurally valid SSHSIG made by an ``sk-ssh-ed25519`` key.

    Being parsed proves nothing: :func:`verify_sk_sshsig` decides.
    """

    blob: bytes
    public_key: SkEd25519PublicKey
    namespace: str
    hash_algorithm: str
    ed25519_signature: bytes
    flags: int
    counter: int

    @property
    def sha256(self) -> str:
        """SHA-256 of the decoded SSHSIG blob: the signature's identity,
        independent of how the armor wraps it."""
        return hashlib.sha256(self.blob).hexdigest()


def dearmor_sshsig(text: object) -> bytes:
    """The SSHSIG blob inside one armored signature, or a refusal.

    Accepts exactly: the begin line, one or more base64 lines of at most
    ``MAX_ARMOR_LINE`` characters, the end line, and an optional final line
    break; lines end uniformly in ``\\n`` or ``\\r\\n``. The joined base64 must
    be canonical.
    """
    if type(text) is not str:
        raise _malformed("the proof must be text.")
    if len(text) > 2 * MAX_SSHSIG_BYTES:
        raise _malformed("the proof exceeds its size bound.")
    newline = "\r\n" if "\r\n" in text else "\n"
    body = text[:-len(newline)] if text.endswith(newline) else text
    lines = body.split(newline)
    if any("\r" in line or "\n" in line for line in lines):
        raise _malformed("the proof mixes line endings.")
    if len(lines) < 3 or lines[0] != ARMOR_BEGIN or lines[-1] != ARMOR_END:
        raise _malformed("the proof is not an armored SSH signature.")
    payload = lines[1:-1]
    if any(not line or len(line) > MAX_ARMOR_LINE for line in payload):
        raise _malformed("the proof's base64 lines are empty or too long.")
    blob = _strict_base64("".join(payload), "the proof")
    if len(blob) > MAX_SSHSIG_BYTES:
        raise _malformed("the proof exceeds its size bound.")
    return blob


def parse_sshsig_blob(blob: bytes) -> SkSshSignature:
    if type(blob) is not bytes:
        raise _malformed("the signature must be bytes.")
    reader = _Reader(blob, "the SSHSIG envelope")
    if reader.raw(len(SSHSIG_MAGIC)) != SSHSIG_MAGIC:
        raise _malformed("the SSHSIG envelope does not start with its magic preamble.")
    if reader.u32() != SSHSIG_VERSION:
        raise SshSigError("algorithm_unsupported", "the SSHSIG envelope is not version 1.")
    public_key = parse_sk_public_key_blob(reader.string())
    namespace_raw = reader.string(max_bytes=MAX_APPLICATION_BYTES)
    reserved = reader.string()
    hash_algorithm_raw = reader.string(max_bytes=MAX_APPLICATION_BYTES)
    signature = reader.string()
    reader.end()
    if reserved:
        raise _malformed("the SSHSIG reserved field is not empty.")
    if hash_algorithm_raw != SSHSIG_HASH_ALGORITHM.encode("ascii"):
        raise SshSigError("algorithm_unsupported", "the SSHSIG hash algorithm is not sha512.")
    try:
        namespace = namespace_raw.decode("ascii")
    except UnicodeDecodeError:
        raise SshSigError("namespace_mismatch", "the SSHSIG namespace is not the AIDO approval namespace.") from None

    sig = _Reader(signature, "the security-key signature")
    if sig.text() != SK_ED25519_KEY_TYPE:
        raise SshSigError("algorithm_unsupported", "the signature is not an sk-ssh-ed25519@openssh.com signature.")
    ed25519_signature = sig.string()
    if len(ed25519_signature) != ED25519_SIGNATURE_BYTES:
        raise _malformed("the Ed25519 signature is not 64 bytes.")
    flags = sig.u8()
    counter = sig.u32()
    sig.end()
    return SkSshSignature(
        blob=bytes(blob),
        public_key=public_key,
        namespace=namespace,
        hash_algorithm=SSHSIG_HASH_ALGORITHM,
        ed25519_signature=bytes(ed25519_signature),
        flags=flags,
        counter=counter,
    )


def parse_armored_sshsig(text: object) -> SkSshSignature:
    return parse_sshsig_blob(dearmor_sshsig(text))


def sshsig_signed_data(namespace: str, message: bytes) -> bytes:
    """The bytes an SSHSIG signer hands to the key (``PROTOCOL.sshsig``)."""
    return (
        SSHSIG_MAGIC
        + _string(namespace.encode("ascii"))
        + _string(b"")
        + _string(SSHSIG_HASH_ALGORITHM.encode("ascii"))
        + _string(hashlib.sha512(message).digest())
    )


def sk_signed_data(application: str, flags: int, counter: int, data: bytes) -> bytes:
    """What an ``sk-ssh-ed25519`` authenticator signs over ``data`` (``PROTOCOL.u2f``)."""
    return (
        hashlib.sha256(application.encode("ascii")).digest()
        + bytes([flags])
        + counter.to_bytes(4, "big")
        + hashlib.sha256(data).digest()
    )


def verify_sk_sshsig(signature: SkSshSignature, *, namespace: str, message: bytes) -> None:
    """Check ``signature`` over exactly ``message`` in ``namespace``, or refuse.

    The caller has already required the public key and application to equal a
    registered key; this function checks the namespace and the Ed25519
    signature over the reconstructed nested signed data. Flags are the
    caller's to judge once the signature has proven them.
    """
    if type(signature) is not SkSshSignature or type(message) is not bytes:
        raise _malformed("the signature or message has the wrong type.")
    if signature.namespace != namespace:
        raise SshSigError("namespace_mismatch", "the SSHSIG namespace is not the AIDO approval namespace.")
    signed = sk_signed_data(
        signature.public_key.application,
        signature.flags,
        signature.counter,
        sshsig_signed_data(namespace, message),
    )
    try:
        Ed25519PublicKey.from_public_bytes(signature.public_key.ed25519).verify(
            signature.ed25519_signature, signed
        )
    except (InvalidSignature, ValueError):
        raise SshSigError(
            "signature_invalid", "the security-key signature does not verify over this statement."
        ) from None
