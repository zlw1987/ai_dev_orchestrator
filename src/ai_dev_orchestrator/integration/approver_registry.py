"""DL-4B S1 — ``approver-registry.v1``: which security keys are human approvers.

The registry is the trust root of every human approval (FD-2). It is written
once, with elevation, by the human, at the code-constant location
``%ProgramData%\\AIDO\\approver-registry.v1.json`` (``%ProgramData%`` resolved
through the Windows known-folder API, not the environment). AIDO only reads it,
and refuses it unless it can prove from the OS's own security facts that
neither the authority identity A nor the execution identity X nor the operator
O can write, append to, delete, rename, re-permission, take ownership of or
replace it, its directory or any ancestor, and that this process is A and not
elevated (FD-2 (a)-(e)).

That proof is not a second access-control evaluator. It is S0's: the same
facts source, the same token and identity checks, the same ``identity-boundary.v1``
anchor checks (from which X's and O's SIDs come), and the same upper-bound
rights evaluation (with AuthZ in production), applied to one more file in the
same anchor directory. :mod:`.identity_boundary` is reused unchanged.

Nothing is cached. Every call re-reads the boundary, the registry and every
security fact, so a revocation, a rotation or a re-permissioning takes effect
at the next verification.
"""

from __future__ import annotations

import hashlib
import json
import ntpath
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, model_validator

from ai_dev_orchestrator.control_plane.attestation_v2 import is_key_fingerprint
from ai_dev_orchestrator.integration import identity_boundary as _ib
from ai_dev_orchestrator.integration.boundary_facts import SecurityFacts
from ai_dev_orchestrator.integration.identity_boundary import IdentityBoundaryError, IsolationCategory
from ai_dev_orchestrator.integration.security_descriptor import READ_ONLY
from ai_dev_orchestrator.integration.sshsig import (
    SkEd25519PublicKey,
    SshSigError,
    parse_sk_public_key_line,
)

APPROVER_REGISTRY_SCHEMA_VERSION = "approver-registry.v1"
#: ``%ProgramData%\AIDO\approver-registry.v1.json``, beside the identity
#: boundary. A code constant: not configuration, not a CLI option, not an
#: environment variable.
REGISTRY_DIRECTORY_NAME = _ib.BOUNDARY_DIRECTORY_NAME
REGISTRY_FILE_NAME = "approver-registry.v1.json"
MAX_REGISTRY_BYTES = 64 * 1024
MAX_APPROVER_ENTRIES = 64
#: The FIDO application every approval key is created with
#: (``-O application=ssh:aido-approval``). A key made for SSH login
#: (``ssh:``) or for anything else is not an approval key.
REGISTERED_APPLICATION = "ssh:aido-approval"
MAX_APPROVER_ID_CHARS = 200

_ALL_ROLES = ("authority", "execution", "operator")
_INSTANT = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?(Z|[+-]\d{2}:\d{2})"
)


class RegistryError(Exception):
    """The registry is unreadable, unprotected or malformed: no key is an approver.

    ``category`` is ``registry_unreadable``, ``registry_unprotected`` or
    ``registry_malformed``. For ``registry_unprotected`` caused by the S0 proof,
    ``isolation_category`` names the S0 check that failed.
    """

    def __init__(self, category: str, detail: str, *, isolation_category: IsolationCategory | None = None) -> None:
        self.category = category
        self.detail = detail
        self.isolation_category = isolation_category
        super().__init__(f"{category}: {detail}")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


def _instant(value: object, field_name: str) -> datetime:
    if type(value) is datetime:
        parsed = value
    elif type(value) is str and _INSTANT.fullmatch(value):
        parsed = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    else:
        raise ValueError(f"{field_name} must be an RFC 3339 instant with an offset.")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field_name} must carry a UTC offset.")
    return parsed


class ApproverEntry(_Strict):
    """One registered approval key. ``revoked`` is total (FD-3): a revoked
    key approves nothing, including re-proofs of what it signed earlier."""

    approver_id: str
    public_key: str
    application: str
    fingerprint_sha256: str
    require_user_verification: bool
    not_before: datetime
    not_after: datetime
    revoked: bool

    @field_validator("approver_id")
    @classmethod
    def _approver(cls, value: str) -> str:
        if not value.strip() or len(value) > MAX_APPROVER_ID_CHARS:
            raise ValueError(f"approver_id must be non-blank and at most {MAX_APPROVER_ID_CHARS} characters.")
        return value

    @field_validator("not_before", "not_after", mode="before")
    @classmethod
    def _instants(cls, value: object, info) -> datetime:
        return _instant(value, info.field_name)

    @field_validator("fingerprint_sha256")
    @classmethod
    def _fingerprint(cls, value: str) -> str:
        if not is_key_fingerprint(value):
            raise ValueError("fingerprint_sha256 must be an OpenSSH SHA256: fingerprint.")
        return value

    @model_validator(mode="after")
    def _key(self) -> ApproverEntry:
        try:
            key = parse_sk_public_key_line(self.public_key)
        except SshSigError as exc:
            raise ValueError(f"public_key: {exc.category}") from None
        if self.application != REGISTERED_APPLICATION:
            raise ValueError(f"application must be exactly {REGISTERED_APPLICATION}.")
        if key.application != self.application:
            raise ValueError("the public key was not created for the registered application.")
        if key.fingerprint != self.fingerprint_sha256:
            raise ValueError("fingerprint_sha256 is not the fingerprint of public_key.")
        if not self.not_before < self.not_after:
            raise ValueError("not_before must be before not_after.")
        return self

    @property
    def key(self) -> SkEd25519PublicKey:
        return parse_sk_public_key_line(self.public_key)


class ApproverRegistry(_Strict):
    schema_version: Literal["approver-registry.v1"]
    approvers: tuple[ApproverEntry, ...]

    @model_validator(mode="after")
    def _entries(self) -> ApproverRegistry:
        if not 1 <= len(self.approvers) <= MAX_APPROVER_ENTRIES:
            raise ValueError(f"between 1 and {MAX_APPROVER_ENTRIES} approver entries are required.")
        fingerprints = [entry.fingerprint_sha256 for entry in self.approvers]
        if len(set(fingerprints)) != len(fingerprints):
            # One key, two entries: which entry's revocation or window applies
            # would be ambiguous.
            raise ValueError("a key is registered more than once.")
        return self

    def entries_for(self, approver_id: str) -> tuple[ApproverEntry, ...]:
        return tuple(entry for entry in self.approvers if entry.approver_id == approver_id)


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    keys = [key for key, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate key")
    return dict(pairs)


def _reject_constant(name: str) -> None:
    raise ValueError(f"non-standard JSON constant {name}")


def parse_approver_registry(data: object) -> ApproverRegistry:
    """Strictly parse ``approver-registry.v1`` bytes: UTF-8 without a BOM, one
    JSON object, no duplicate keys, no non-standard constants, no unknown
    fields, every key well-formed and bound to its fingerprint."""
    if type(data) is not bytes:
        raise RegistryError("registry_malformed", "the registry must be bytes.")
    if len(data) > MAX_REGISTRY_BYTES:
        raise RegistryError("registry_malformed", "the registry exceeds its size bound.")
    if data.startswith(b"\xef\xbb\xbf"):
        raise RegistryError("registry_malformed", "the registry must not start with a BOM.")
    try:
        json.loads(data.decode("utf-8"), object_pairs_hook=_reject_duplicates,
                   parse_constant=_reject_constant)
        return ApproverRegistry.model_validate_json(data, strict=True)
    except (UnicodeDecodeError, ValueError, ValidationError) as exc:
        reason = type(exc).__name__ if not isinstance(exc, ValidationError) else (
            "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()[:3])
        )
        raise RegistryError(
            "registry_malformed", f"the registry is not a valid approver-registry.v1 ({reason})."
        ) from None


@dataclass(frozen=True)
class RegistrySnapshot:
    """What one protected read returned. A snapshot is evidence of one read;
    it is never reused for a later verification."""

    registry: ApproverRegistry
    registry_sha256: str
    identity_boundary_sha256: str
    independent_evaluation: bool
    objects_examined: int


def read_approver_registry(facts: SecurityFacts, *, require_independent: bool) -> RegistrySnapshot:
    """Read the registry from its code-constant location, proving it protected.

    Order: platform; this process's token (not elevated, no administrative
    group or privilege, one logon SID); ``identity-boundary.v1`` and its
    anchor (which names A, X and O); the process user is A; then the registry
    file itself: one handle that denies write sharing, not a reparse point,
    one hard link, at its exact final path, owned by SYSTEM, Administrators or
    TrustedInstaller, at most readable by A, X and O, and not replaceable by
    any of them through any ancestor. Only then are its bytes parsed.
    """
    run = _ib._Run(facts, require_independent=require_independent)
    try:
        _ib._check_platform(run)
        token = _ib._check_token(run)
        boundary, boundary_sha256, boundary_path, directory = _ib._read_boundary(run, None)
        _ib._check_identities(run, boundary, token)
        _ib._check_anchor(run, boundary_path, directory)
        data = _read_registry_file(run, directory)
    except IdentityBoundaryError as exc:
        raise RegistryError(
            "registry_unprotected", str(exc), isolation_category=exc.category
        ) from None
    registry = parse_approver_registry(data)
    return RegistrySnapshot(
        registry=registry,
        registry_sha256=hashlib.sha256(data).hexdigest(),
        identity_boundary_sha256=boundary_sha256,
        independent_evaluation=run.independent_complete,
        objects_examined=run.examined,
    )


def _unprotected(detail: str) -> IdentityBoundaryError:
    return IdentityBoundaryError(IsolationCategory.BOUNDARY_UNPROTECTED, detail)


def _read_registry_file(run: _ib._Run, directory: str) -> bytes:
    path = ntpath.join(directory, REGISTRY_FILE_NAME)
    what = "the approver registry"
    result = run.call(what, run.facts.read_file, path, MAX_REGISTRY_BYTES)
    if result is None:
        raise RegistryError("registry_unreadable", "no approver registry exists at its code-constant location.")
    if type(result) is not tuple or len(result) != 2 or type(result[1]) is not bytes:
        raise run.malformed("the approver registry read")
    facts = run.checked_object_facts(result[0], what)
    if facts.is_directory:
        raise _unprotected("the approver registry is a directory.")
    if facts.is_reparse_point or facts.final_path is None or _ib._key(facts.final_path) != _ib._key(path):
        raise _unprotected("the approver registry is a reparse point or is redirected.")
    if facts.link_count != 1:
        raise _unprotected("the approver registry has more than one hard link.")
    descriptor = run.descriptor(facts.security_descriptor, what)
    if descriptor.owner not in _ib.ADMIN_OWNERS:
        raise _unprotected(
            f"the approver registry is owned by {descriptor.owner}, not SYSTEM, "
            "Administrators or TrustedInstaller."
        )
    obj = _ib._Object(path, facts, descriptor)
    run.objects[_ib._key(path)] = obj
    run.limit_object(obj, {role: READ_ONLY for role in _ALL_ROLES}, what, IsolationCategory.BOUNDARY_UNPROTECTED)
    run.not_replaceable(path, _ALL_ROLES, what, IsolationCategory.BOUNDARY_UNPROTECTED)
    data = result[1]
    if len(data) > MAX_REGISTRY_BYTES:
        raise RegistryError("registry_malformed", "the registry exceeds its size bound.")
    return bytes(data)
