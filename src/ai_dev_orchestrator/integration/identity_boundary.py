"""DL-4B S0 — the Windows identity boundary proof (FD-13, FD-14, FD-16).

The DL-4B integration session runs as a dedicated **authority** account A. The
human runs every command that touches repository content as a separate
**execution** account X, and reads published bundles as their own **operator**
account O. The boundary that keeps repository-controlled code (which runs as X)
away from A's authority plane is ordinary Windows access control between those
accounts. This module does not create that boundary and cannot repair it. It
**proves** it, mechanically, from facts the OS reports, and refuses otherwise.

```text
facts source ──► environment ─► token ─► identity-boundary.v1 (anchor) ─► accounts
 (Win32, read-only)   │            │            │                            │
                      ▼            ▼            ▼                            ▼
                 no credential  not elevated  admin-owned, A/X/O cannot   distinct,
                 or Python     no bypass      write, replace or           standard,
                 load variable privilege      re-permission it            local A and X
                                   │
     session ◄─────────────────────┘  then every FD-14 object: owner, protection,
     process / thread / token DACL     X's and O's upper-bound rights, rights on
     code-load locations               every ancestor, inheritance to new children
```

What each check answers, and why it is shaped this way:

- **Rights are evaluated for X and O, not for A's own token.** The question is
  what the adversary can do. Their rights are an **upper bound** over every
  token they could hold (:mod:`.security_descriptor`), computed twice in
  production — by the pure evaluator and by AuthZ — and the union is used.
- **An object is only as safe as its ancestors.** X can delete or rename an
  object if it has ``DELETE`` on it *or* ``FILE_DELETE_CHILD`` on its parent,
  whatever the object's own DACL says, and can then recreate it if it can add
  to the parent. It can grant itself either right on any ancestor it can
  re-permission or take over (``WRITE_DAC``, ``WRITE_OWNER``, ownership). So
  every component from the volume root down is checked for all of these, and
  a protected child DACL alone is never accepted as protection.
- **Inherit-only ACEs are invisible on the object itself** but decide what its
  future children grant, so each authority directory's inheritance is simulated
  for a new file and a new directory.
- **Ownership is a right.** An owner may rewrite the DACL unless an effective
  ``OWNER RIGHTS`` ACE replaces that implicit grant. X owns the clone and its
  ``.git`` (Git's ownership check, C-10), so both must carry one.
- **Privileges bypass all of this.** Any principal holding a privilege outside a
  short standard-user allowlist, or in an administrative group, is refused
  before any DACL result is used.
- **Code is authority too.** Every location A's interpreter imports from must
  sit inside a declared, admin-owned install root that A, X and O can only read
  and execute, walked in full. ``PATH`` directories (where any reparse entry
  refuses: a link's own protection is not its target's), the working
  directory and A's profile directories are checked as well.
- **A session is isolated by who can use it.** The window station must be
  A's own (its logon SID, or the station named after A's logon LUID for an
  S4U launch), and X and O must neither own nor open the station or desktop.
- **Nothing is cached across proofs.** Each call re-reads every fact, including
  the boundary file. A consumer must call the prover again; a proof object is
  a record of one successful run, not a capability that stays valid.

Every refusal is an :class:`IdentityBoundaryError` whose message starts with
``isolation_unproven:<category>``. Messages name roles, SIDs and paths relative
to a declared root; never file contents.

Production entry point: :func:`prove_identity_boundary`. It takes no facts
source, no path and no boundary: the facts come from
:class:`~.windows_security.WindowsSecurityFacts` and the boundary from the
code-constant location under ``%ProgramData%`` (resolved through the Windows
known-folder API, not the environment). The library entry point
:func:`prove_identity_boundary_from_facts` exists for offline tests; its proofs
are always marked ``facts_origin="injected"`` and are never production proofs.

What this proof cannot establish, and leaves to the separately authorized E-12
live rehearsal: that the accounts were provisioned as declared on a real host,
that the OS enforces these DACLs as evaluated (it is the OS's job; the
rehearsal attacks it), and every residual listed in
``docs/DL4B_S0_WINDOWS_IDENTITY_BOUNDARY.md``.
"""

from __future__ import annotations

import hashlib
import json
import ntpath
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, model_validator

from ai_dev_orchestrator.integration.boundary_facts import (
    CodeLoadFacts,
    DirectoryEntry,
    ObjectFacts,
    PrincipalFacts,
    ProcessFacts,
    SecurityFacts,
    SessionFacts,
    TokenFacts,
)
from ai_dev_orchestrator.integration.security_descriptor import (
    ADMINISTRATORS,
    DELETE,
    EVERYONE,
    FILE_ADD_FILE,
    FILE_ADD_SUBDIRECTORY,
    FILE_ALL_ACCESS,
    FILE_DELETE_CHILD,
    FILE_WRITE_ATTRIBUTES,
    FILE_WRITE_EA,
    LOCAL_SYSTEM,
    NO_ACCESS,
    OWNER_RIGHTS,
    READ_ONLY,
    TRUSTED_INSTALLER,
    WRITE_DAC,
    WRITE_OWNER,
    CONTAINER_INHERIT_ACE,
    OBJECT_INHERIT_ACE,
    DescriptorError,
    ObjectKind,
    Principal,
    SecurityDescriptor,
    canonical_sid,
    describe_rights,
    inherited_descriptor,
    is_integrity_sid,
    is_logon_sid,
    parse_acl,
    parse_security_descriptor,
    serialize,
    upper_bound_rights,
    upper_bound_transform,
)

IDENTITY_BOUNDARY_SCHEMA_VERSION = "identity-boundary.v1"
#: ``%ProgramData%\AIDO\identity-boundary.v1.json``. A code constant: not
#: configuration, not a CLI option, not an environment variable.
BOUNDARY_DIRECTORY_NAME = "AIDO"
BOUNDARY_FILE_NAME = "identity-boundary.v1.json"
MAX_BOUNDARY_BYTES = 64 * 1024
#: The most file-system objects one proof examines. Over it, the proof refuses.
MAX_EXAMINED_OBJECTS = 400_000
MAX_INSTALL_ROOTS = 16


class IsolationCategory(str, Enum):
    PLATFORM_UNSUPPORTED = "platform_unsupported"
    SECURITY_FACT_UNAVAILABLE = "security_fact_unavailable"
    ENVIRONMENT_UNSAFE = "environment_unsafe"
    TOKEN_IDENTITY_MISMATCH = "token_identity_mismatch"
    TOKEN_ELEVATED = "token_elevated"
    TOKEN_PRIVILEGED = "token_privileged"
    BOUNDARY_UNREADABLE = "boundary_unreadable"
    BOUNDARY_MALFORMED = "boundary_malformed"
    BOUNDARY_UNPROTECTED = "boundary_unprotected"
    BOUNDARY_DIGEST_MISMATCH = "boundary_digest_mismatch"
    IDENTITY_INVALID = "identity_invalid"
    ACCOUNT_PRIVILEGED = "account_privileged"
    PRINCIPAL_UNVERIFIABLE = "principal_unverifiable"
    SESSION_FOREIGN = "session_foreign"
    PROCESS_ACCESS = "process_access"
    OBJECT_MISSING = "object_missing"
    OBJECT_KIND = "object_kind"
    OBJECT_NOT_CANONICAL = "object_not_canonical"
    OBJECT_REPARSE = "object_reparse"
    OBJECT_LINKED = "object_linked"
    OBJECT_OWNER = "object_owner"
    OBJECT_UNPROTECTED = "object_unprotected"
    OWNER_RIGHTS_MISSING = "owner_rights_missing"
    DESCRIPTOR_UNSUPPORTED = "descriptor_unsupported"
    OBJECT_RIGHTS = "object_rights"
    OBJECT_REPLACEABLE = "object_replaceable"
    OBJECT_INHERITANCE = "object_inheritance"
    CODE_PATH_UNTRUSTED = "code_path_untrusted"
    EXAMINATION_LIMIT = "examination_limit"


class IdentityBoundaryError(Exception):
    """The identity boundary is not proven. Nothing was opened or consumed."""

    def __init__(self, category: IsolationCategory, detail: str) -> None:
        self.category = category
        self.detail = detail
        super().__init__(f"isolation_unproven:{category.value}: {detail}")


_C = IsolationCategory

# -- fixed security vocabulary --------------------------------------------------

#: Owners an administrator-provisioned anchor or install location may have.
ADMIN_OWNERS = frozenset({LOCAL_SYSTEM, ADMINISTRATORS, TRUSTED_INSTALLER})

#: The privileges of an ordinary standard user. Anything else (backup, restore,
#: take ownership, debug, impersonate, load driver, ...) bypasses or subverts
#: the DACLs this proof evaluates, and is refused even when disabled, because a
#: process can enable its own disabled privileges.
STANDARD_USER_PRIVILEGES = frozenset({
    "SeChangeNotifyPrivilege",
    "SeShutdownPrivilege",
    "SeUndockPrivilege",
    "SeIncreaseWorkingSetPrivilege",
    "SeTimeZonePrivilege",
})

_PRIVILEGED_BUILTIN_GROUPS = frozenset({
    ADMINISTRATORS,
    "S-1-5-32-547",  # Power Users
    "S-1-5-32-548",  # Account Operators
    "S-1-5-32-549",  # Server Operators
    "S-1-5-32-550",  # Print Operators
    "S-1-5-32-551",  # Backup Operators
    "S-1-5-32-552",  # Replicator
    "S-1-5-32-578",  # Hyper-V Administrators
    "S-1-5-32-582",  # Storage Replica Administrators
    "S-1-5-32-583",  # Device Owners
    "S-1-5-114",  # Local account and member of Administrators
})
#: Domain-relative RIDs of administrative domain groups.
_PRIVILEGED_DOMAIN_RIDS = frozenset({498, 512, 516, 518, 519, 520, 521, 526, 527})

#: SIDs a token gains from *how* it logged on, not from who the account is.
#: AuthZ does not report them for a SID, so they are added as possibly held,
#: and never treated as certainly held (a deny ACE naming one does not bind
#: every token of the account).
_LOGON_DEPENDENT_SIDS = frozenset({
    "S-1-2-0",  # LOCAL
    "S-1-2-1",  # CONSOLE LOGON
    "S-1-5-1",  # DIALUP
    "S-1-5-2",  # NETWORK
    "S-1-5-3",  # BATCH
    "S-1-5-4",  # INTERACTIVE
    "S-1-5-6",  # SERVICE
    "S-1-5-7",  # ANONYMOUS LOGON (reachable by anyone over a null session)
    "S-1-5-8",  # PROXY
    "S-1-5-13",  # TERMINAL SERVER USER
    "S-1-5-14",  # REMOTE INTERACTIVE LOGON
    "S-1-5-15",  # This Organization
    "S-1-5-1000",  # Other Organization
    "S-1-5-32-546",  # Guests
    "S-1-5-64-10",  # NTLM Authentication
    "S-1-5-64-14",  # SChannel Authentication
    "S-1-5-64-21",  # Digest Authentication
    "S-1-5-65-1",  # This Organization Certificate
    "S-1-5-113",  # Local account
    "S-1-5-114",  # Local account and member of Administrators
    "S-1-18-1",  # Authentication authority asserted identity
    "S-1-18-2",  # Service asserted identity
    "S-1-18-3", "S-1-18-4", "S-1-18-5", "S-1-18-6",
})
_ALWAYS_POSSIBLE = _LOGON_DEPENDENT_SIDS | {EVERYONE, "S-1-5-11", "S-1-5-32-545"}

#: Groups every standard account shares by construction; sharing any other
#: group with A is refused (FD-13).
_BASELINE_SHARED_GROUPS = _ALWAYS_POSSIBLE

_FORBIDDEN_ENVIRONMENT_NAMES = frozenset({
    "GITHUB_TOKEN",
    "PYTHONPATH",
    "PYTHONHOME",
    "PYTHONSTARTUP",
    "PYTHONUSERBASE",
    "PYTHONBREAKPOINT",
    "PYTHONPLATLIBDIR",
    "PYTHONEXECUTABLE",
    "PYTHONINSPECT",
})
_FORBIDDEN_ENVIRONMENT_PREFIXES = ("AIDO_LITELLM_", "AIDO_VLLM_")

_SE_GROUP_ENABLED = 0x4
_SE_GROUP_LOGON_ID = 0xC000_0000
_SID_TYPE_USER = 1
_TOKEN_ELEVATION_TYPE_DEFAULT = 1
_MEDIUM_INTEGRITY_RID = 0x2000
_HIGH_INTEGRITY_RID = 0x3000

#: Everything X may do inside the clone root itself: read, list, add files and
#: subdirectories, write attributes — but never delete or rename the root,
#: delete a child through it (that would let X rename ``.git`` away), or
#: re-permission or take it.
_CLONE_ROOT_EXECUTION_RIGHTS = (
    READ_ONLY | FILE_ADD_FILE | FILE_ADD_SUBDIRECTORY | FILE_WRITE_EA | FILE_WRITE_ATTRIBUTES
)
#: What a file or directory X creates in its working tree may grant X: anything
#: except re-permissioning or taking it (an inheritable OWNER RIGHTS ACE).
_WORKING_TREE_CHILD_RIGHTS = FILE_ALL_ACCESS & ~(WRITE_DAC | WRITE_OWNER)
_INBOX_OPERATOR_RIGHTS = READ_ONLY | FILE_ADD_FILE
_UNRESTRICTED = 0xFFFF_FFFF

# -- the boundary document --------------------------------------------------------

_RESERVED_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
    | {f"{base}{n}" for base in ("COM", "LPT") for n in "123456789\u00b9\u00b2\u00b3"}
)
_FORBIDDEN_NAME_CHARACTERS = frozenset('<>:"/|?*') | {chr(c) for c in range(32)}


def validate_local_path(value: object) -> str:
    """An absolute path on a local drive, in one unambiguous spelling, or a refusal.

    Refuses relative, UNC and device (``\\\\?\\``, ``\\\\.\\``) paths, forward
    slashes, empty, ``.`` and ``..`` components, alternate-stream colons,
    components with a trailing dot or space (Windows silently strips them),
    reserved device names, and a bare volume root.
    """
    if not isinstance(value, str) or not value or len(value) > 1024:
        raise ValueError("a path must be non-empty text of at most 1024 characters.")
    if len(value) < 4 or not ("A" <= value[0].upper() <= "Z") or value[1:3] != ":\\":
        raise ValueError("a path must be an absolute local path such as C:\\name.")
    for part in value[3:].split("\\"):
        if not part or part in (".", ".."):
            raise ValueError("a path must not contain empty, '.' or '..' components.")
        if part[-1] in ". ":
            raise ValueError("a path component must not end with a dot or a space.")
        if any(char in _FORBIDDEN_NAME_CHARACTERS for char in part):
            raise ValueError("a path component contains a character Windows reserves.")
        if part.split(".")[0].rstrip(" ").upper() in _RESERVED_NAMES:
            raise ValueError("a path component is a reserved device name.")
    return value


_ASCII_LOWER = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")


def _key(path: str) -> str:
    """Identity of a spelling: ASCII letters folded, nothing else.

    Two spellings equal under this key are equal under NTFS's own case
    mapping. Full Unicode lowering is deliberately not used: it equates names
    NTFS keeps apart (the Kelvin sign and ``k``, for one), which could make a
    different directory look like a declared one. The cost is that a declared
    path must match the on-disk spelling of any non-ASCII letter exactly.
    """
    return path.translate(_ASCII_LOWER)


def _within(child: str, parent: str, *, key: Callable[[str], str] = _key) -> bool:
    child_key, parent_key = key(child), key(parent).rstrip("\\")
    return child_key == parent_key or child_key.startswith(parent_key + "\\")


def _within_exact(child: str, parent: str) -> bool:
    """Containment by exact spelling, for paths Windows itself reported, which
    stays correct inside a per-directory case-sensitive folder."""
    return _within(child, parent, key=lambda p: p)


def _components(path: str) -> list[str]:
    """``C:\\a\\b`` → ``["C:\\", "C:\\a", "C:\\a\\b"]``."""
    root = path[:3]
    parts = [root]
    current = root
    for part in path[3:].split("\\"):
        current = current + part if current.endswith("\\") else current + "\\" + part
        parts.append(current)
    return parts


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class BoundaryAccount(_Strict):
    sid: str
    account: str

    @field_validator("sid")
    @classmethod
    def _sid(cls, value: str) -> str:
        try:
            return canonical_sid(value)
        except DescriptorError as exc:
            raise ValueError(str(exc)) from None

    @field_validator("account")
    @classmethod
    def _account(cls, value: str) -> str:
        domain, sep, name = value.partition("\\")
        if not sep or not domain or not name or "\\" in name or len(value) > 256:
            raise ValueError("an account must be written DOMAIN\\name.")
        return value


class BoundaryPaths(_Strict):
    state_root: str
    published: str
    inbox: str
    exchange_root: str
    clone: str
    install_roots: tuple[str, ...]

    @field_validator("state_root", "published", "inbox", "exchange_root", "clone")
    @classmethod
    def _path(cls, value: str) -> str:
        return validate_local_path(value)

    @field_validator("install_roots")
    @classmethod
    def _roots(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not 1 <= len(value) <= MAX_INSTALL_ROOTS:
            raise ValueError(f"between 1 and {MAX_INSTALL_ROOTS} install roots are required.")
        return tuple(validate_local_path(root) for root in value)

    def named(self) -> list[tuple[str, str]]:
        named = [
            ("state_root", self.state_root),
            ("published", self.published),
            ("inbox", self.inbox),
            ("exchange_root", self.exchange_root),
            ("clone", self.clone),
        ]
        return named + [(f"install_root[{i}]", root) for i, root in enumerate(self.install_roots)]

    @model_validator(mode="after")
    def _disjoint(self) -> BoundaryPaths:
        named = self.named()
        overlap = str.casefold  # broader than NTFS equality: errs towards refusing
        for index, (left_name, left) in enumerate(named):
            for right_name, right in named[index + 1:]:
                if _within(left, right, key=overlap) or _within(right, left, key=overlap):
                    raise ValueError(f"{left_name} and {right_name} overlap; each must be outside the other.")
        return self


class IdentityBoundary(_Strict):
    """``identity-boundary.v1``: which accounts are A, X and O, how A is
    launched, and where the authority plane, the clone and A's code live."""

    schema_version: Literal["identity-boundary.v1"]
    authority: BoundaryAccount
    execution: BoundaryAccount
    operator: BoundaryAccount
    launch_mechanism: Literal["task_scheduler_s4u", "interactive_session"]
    paths: BoundaryPaths

    @model_validator(mode="after")
    def _distinct(self) -> IdentityBoundary:
        accounts = (self.authority, self.execution, self.operator)
        if len({a.sid for a in accounts}) != 3:
            raise ValueError("the authority, execution and operator SIDs must be distinct.")
        if len({a.account.casefold() for a in accounts}) != 3:
            raise ValueError("the authority, execution and operator accounts must be distinct.")
        return self


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    keys = [key for key, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate key")
    return dict(pairs)


def _reject_constant(name: str) -> None:
    raise ValueError(f"non-standard JSON constant {name}")


def parse_identity_boundary(data: object) -> IdentityBoundary:
    """Strictly parse ``identity-boundary.v1`` bytes: UTF-8 without a BOM, one
    JSON object, no duplicate keys, no unknown fields."""
    if type(data) is not bytes:
        raise IdentityBoundaryError(_C.BOUNDARY_MALFORMED, "the boundary must be bytes.")
    if len(data) > MAX_BOUNDARY_BYTES:
        raise IdentityBoundaryError(_C.BOUNDARY_MALFORMED, "the boundary exceeds its size bound.")
    if data.startswith(b"\xef\xbb\xbf"):
        raise IdentityBoundaryError(_C.BOUNDARY_MALFORMED, "the boundary must not start with a BOM.")
    try:
        json.loads(data.decode("utf-8"), object_pairs_hook=_reject_duplicates,
                   parse_constant=_reject_constant)
        return IdentityBoundary.model_validate_json(data, strict=True)
    except (UnicodeDecodeError, ValueError, ValidationError) as exc:
        reason = type(exc).__name__ if not isinstance(exc, ValidationError) else (
            "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()[:3])
        )
        raise IdentityBoundaryError(
            _C.BOUNDARY_MALFORMED, f"the boundary is not a valid identity-boundary.v1 ({reason})."
        ) from None


# -- the proof record -------------------------------------------------------------

_PROOF_TOKEN = object()
_PROOF_FIELDS = (
    "boundary",
    "boundary_sha256",
    "facts_origin",
    "independent_evaluation",
    "proven_at",
    "objects_examined",
)


class IdentityBoundaryProof:
    """A record that one run of the prover passed. Immutable, minted only by
    the prover, not subclassable, not copyable.

    It is **not** a capability: it proves nothing about any later moment. A
    consumer re-runs the prover at its own consumption boundary.
    """

    __slots__ = _PROOF_FIELDS
    boundary: IdentityBoundary
    boundary_sha256: str
    facts_origin: Literal["windows", "injected"]
    independent_evaluation: bool
    proven_at: datetime
    objects_examined: int

    def __init__(self, *, _token: object = None, **fields: Any) -> None:
        if _token is not _PROOF_TOKEN or set(fields) != set(_PROOF_FIELDS):
            raise TypeError("an identity boundary proof is produced only by the boundary prover.")
        for name in _PROOF_FIELDS:
            object.__setattr__(self, name, fields[name])

    def __init_subclass__(cls, **kwargs: Any) -> None:
        raise TypeError("IdentityBoundaryProof cannot be subclassed.")

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("an identity boundary proof is immutable.")

    def __delattr__(self, name: str) -> None:
        raise AttributeError("an identity boundary proof is immutable.")

    def __reduce__(self) -> Any:
        raise TypeError("an identity boundary proof cannot be copied or pickled.")

    def __copy__(self) -> Any:
        raise TypeError("an identity boundary proof cannot be copied or pickled.")

    def __deepcopy__(self, memo: Any) -> Any:
        raise TypeError("an identity boundary proof cannot be copied or pickled.")

    @property
    def is_production(self) -> bool:
        """Produced by :func:`prove_identity_boundary` from live Windows facts,
        with every rights result confirmed by AuthZ."""
        return self.facts_origin == "windows" and self.independent_evaluation


# -- the prover ------------------------------------------------------------------


@dataclass(frozen=True)
class _Object:
    path: str
    facts: ObjectFacts
    descriptor: SecurityDescriptor

    @property
    def kind(self) -> ObjectKind:
        return ObjectKind.DIRECTORY if self.facts.is_directory else ObjectKind.FILE


def _failure_reason(exc: BaseException) -> str:
    code = getattr(exc, "winerror", None) or getattr(exc, "errno", None)
    return f"{type(exc).__name__}" + (f" {code}" if code else "")


class _Run:
    """One proof run. Holds per-run caches only; nothing survives the run."""

    def __init__(self, facts: SecurityFacts, *, require_independent: bool) -> None:
        self.facts = facts
        self.require_independent = require_independent
        self.independent_complete = True
        self.examined = 0
        self.objects: dict[str, _Object | None] = {}
        self.rights_cache: dict[tuple[bytes, str, ObjectKind], int] = {}
        self.principals: dict[str, Principal] = {}
        self.token: TokenFacts | None = None
        self.authority_logon_sid: str | None = None

    # -- calling the facts source ------------------------------------------------

    def call(self, what: str, method: Callable[..., Any], *args: Any) -> Any:
        try:
            return method(*args)
        except IdentityBoundaryError:
            raise
        except Exception as exc:  # any failure to read a fact refuses the proof
            raise IdentityBoundaryError(
                _C.SECURITY_FACT_UNAVAILABLE, f"{what} could not be read ({_failure_reason(exc)})."
            ) from None

    @staticmethod
    def malformed(what: str) -> IdentityBoundaryError:
        return IdentityBoundaryError(_C.SECURITY_FACT_UNAVAILABLE, f"{what} is malformed.")

    def checked_object_facts(self, value: object, what: str) -> ObjectFacts:
        if (
            type(value) is not ObjectFacts
            or not (value.final_path is None or type(value.final_path) is str)
            or type(value.is_directory) is not bool
            or type(value.is_reparse_point) is not bool
            or type(value.link_count) is not int
            or value.link_count < 1
            or type(value.security_descriptor) is not bytes
        ):
            raise self.malformed(f"the facts of {what}")
        return ObjectFacts(
            final_path=value.final_path,
            is_directory=value.is_directory,
            is_reparse_point=value.is_reparse_point,
            link_count=value.link_count,
            security_descriptor=bytes(value.security_descriptor),
        )

    def descriptor(self, raw: bytes, what: str) -> SecurityDescriptor:
        try:
            return parse_security_descriptor(raw)
        except DescriptorError as exc:
            raise IdentityBoundaryError(_C.DESCRIPTOR_UNSUPPORTED, f"{what}: {exc}") from None

    def count(self) -> None:
        self.examined += 1
        if self.examined > MAX_EXAMINED_OBJECTS:
            raise IdentityBoundaryError(
                _C.EXAMINATION_LIMIT,
                f"more than {MAX_EXAMINED_OBJECTS} objects would have to be examined.",
            )

    def object(self, path: str, what: str) -> _Object | None:
        key = _key(path)
        if key in self.objects:
            return self.objects[key]
        self.count()
        value = self.call(f"the security of {what}", self.facts.object_facts, path)
        if value is None:
            self.objects[key] = None
            return None
        facts = self.checked_object_facts(value, what)
        result = _Object(path, facts, self.descriptor(facts.security_descriptor, what))
        self.objects[key] = result
        return result

    def listing(self, path: str, what: str) -> tuple[DirectoryEntry, ...]:
        entries = self.call(f"the listing of {what}", self.facts.list_directory, path)
        if type(entries) is not tuple:
            raise self.malformed(f"the listing of {what}")
        seen: set[str] = set()
        for entry in entries:
            if (
                type(entry) is not DirectoryEntry
                or type(entry.name) is not str
                or type(entry.is_directory) is not bool
                or type(entry.is_reparse_point) is not bool
                or entry.name in ("", ".", "..")
                or any(c in entry.name for c in "\\/:\x00")
                or entry.name.casefold() in seen
            ):
                raise self.malformed(f"the listing of {what}")
            seen.add(entry.name.casefold())
            try:
                validate_local_path("C:\\" + entry.name)
            except ValueError:
                # A trailing dot or space, a reserved device name or a reserved
                # character: Win32 path parsing would open a different object.
                raise IdentityBoundaryError(
                    _C.OBJECT_NOT_CANONICAL, f"{what} holds an entry Win32 cannot address exactly."
                ) from None
        return tuple(sorted(entries, key=lambda e: e.name))

    # -- rights ----------------------------------------------------------------

    def rights(self, obj_descriptor: SecurityDescriptor, raw: bytes, role: str, kind: ObjectKind) -> int:
        key = (raw, role, kind)
        if key in self.rights_cache:
            return self.rights_cache[key]
        principal = self.principals[role]
        bound = upper_bound_rights(obj_descriptor, principal, kind)
        transformed = serialize(upper_bound_transform(obj_descriptor, principal, kind))
        other = self.call(
            "an independent access evaluation", self.facts.independent_rights,
            transformed, principal, kind,
        )
        if other is None:
            if self.require_independent:
                raise IdentityBoundaryError(
                    _C.SECURITY_FACT_UNAVAILABLE, "the independent (AuthZ) evaluation is unavailable."
                )
            self.independent_complete = False
        elif type(other) is not int or not 0 <= other < 2**32:
            raise self.malformed("an independent access evaluation")
        else:
            bound |= other
        self.rights_cache[key] = bound
        return bound

    def rights_of(self, obj: _Object, role: str) -> int:
        return self.rights(obj.descriptor, obj.facts.security_descriptor, role, obj.kind)

    def limit(
        self,
        descriptor: SecurityDescriptor,
        kind: ObjectKind,
        limits: dict[str, int],
        what: str,
        category: IsolationCategory = _C.OBJECT_RIGHTS,
    ) -> None:
        raw = serialize(descriptor)
        for role, allowed in limits.items():
            excess = self.rights(descriptor, raw, role, kind) & ~allowed
            if excess:
                raise IdentityBoundaryError(
                    category,
                    f"the {role} identity could be granted {describe_rights(excess)} on {what}.",
                )

    def limit_object(self, obj: _Object, limits: dict[str, int], what: str,
                     category: IsolationCategory = _C.OBJECT_RIGHTS) -> None:
        for role, allowed in limits.items():
            excess = self.rights_of(obj, role) & ~allowed
            if excess:
                raise IdentityBoundaryError(
                    category,
                    f"the {role} identity could be granted {describe_rights(excess)} on {what}.",
                )

    def sid_of(self, role: str) -> str:
        return self.principals[role].sid

    def owner_is(self, obj: _Object, allowed: frozenset[str], what: str,
                 category: IsolationCategory = _C.OBJECT_OWNER) -> None:
        if obj.descriptor.owner not in allowed:
            raise IdentityBoundaryError(category, f"{what} is owned by {obj.descriptor.owner}.")

    def owner_not_held_by(self, obj: _Object, roles: tuple[str, ...], what: str) -> None:
        for role in roles:
            if self.principals[role].may_hold(obj.descriptor.owner):
                raise IdentityBoundaryError(
                    _C.OBJECT_OWNER, f"{what} is owned by a SID the {role} identity may hold."
                )

    def inheritance(
        self,
        obj: _Object,
        creator: str,
        limits: dict[str, int],
        what: str,
        *,
        kinds: tuple[ObjectKind, ...] = (ObjectKind.FILE, ObjectKind.DIRECTORY),
        category: IsolationCategory = _C.OBJECT_INHERITANCE,
    ) -> None:
        """Simulate a new child created by ``creator`` with no explicit DACL."""
        fallback = None
        if self.token is not None and creator == self.token.user_sid:
            fallback = parse_acl(self.token.default_dacl)
        for kind in kinds:
            child = inherited_descriptor(
                obj.descriptor, kind, creator=creator, creator_group=None, fallback_dacl=fallback
            )
            if child is None:
                raise IdentityBoundaryError(
                    category, f"what a new {kind.value} in {what} would grant cannot be stated."
                )
            self.limit(child, kind, limits, f"a new {kind.value} created in {what}", category)

    def require_owner_rights_ace(self, obj: _Object, what: str, *, inheritable: bool) -> None:
        effective = [a for a in obj.descriptor.effective_aces if a.sid == OWNER_RIGHTS]
        if not effective:
            raise IdentityBoundaryError(
                _C.OWNER_RIGHTS_MISSING,
                f"{what} has no effective OWNER RIGHTS ACE, so its owner may rewrite its DACL.",
            )
        if inheritable and not any(
            a.sid == OWNER_RIGHTS and a.flags & OBJECT_INHERIT_ACE and a.flags & CONTAINER_INHERIT_ACE
            for a in obj.descriptor.dacl
        ):
            raise IdentityBoundaryError(
                _C.OWNER_RIGHTS_MISSING,
                f"{what} has no OWNER RIGHTS ACE inherited by new files and directories.",
            )

    # -- paths and ancestors ------------------------------------------------------

    def declared(self, path: str, what: str, *, directory: bool = True) -> _Object:
        obj = self.object(path, what)
        if obj is None:
            raise IdentityBoundaryError(_C.OBJECT_MISSING, f"{what} does not exist.")
        if obj.facts.is_reparse_point:
            raise IdentityBoundaryError(_C.OBJECT_REPARSE, f"{what} is a reparse point.")
        if obj.facts.final_path is None or _key(obj.facts.final_path) != _key(path):
            raise IdentityBoundaryError(
                _C.OBJECT_NOT_CANONICAL, f"{what} is not at its declared canonical path."
            )
        if obj.facts.is_directory != directory:
            raise IdentityBoundaryError(
                _C.OBJECT_KIND, f"{what} is not a {'directory' if directory else 'file'}."
            )
        return obj

    def not_replaceable(self, path: str, roles: tuple[str, ...], what: str,
                        category: IsolationCategory = _C.OBJECT_REPLACEABLE) -> None:
        """No role can delete or rename ``path`` or any ancestor (``DELETE`` on
        the component, or ``FILE_DELETE_CHILD`` on its parent), none can obtain
        either right by re-permissioning or taking over any ancestor from the
        volume root down (``WRITE_DAC``, ``WRITE_OWNER``, or ownership without
        an effective ``OWNER RIGHTS`` ACE), and none is a reparse point.

        ``WRITE_DAC`` and ``WRITE_OWNER`` on ``path`` itself are each caller's
        own per-object limit, checked there with its precise category; every
        caller excludes both."""
        chain = _components(path)
        objects: list[_Object] = []
        for index, component in enumerate(chain):
            label = what if index == len(chain) - 1 else f"an ancestor of {what}"
            obj = self.object(component, label)
            if obj is None:
                raise IdentityBoundaryError(_C.OBJECT_MISSING, f"{label} does not exist.")
            if obj.facts.is_reparse_point:
                raise IdentityBoundaryError(_C.OBJECT_REPARSE, f"{label} is a reparse point.")
            if index < len(chain) - 1 and not obj.facts.is_directory:
                raise IdentityBoundaryError(_C.OBJECT_KIND, f"{label} is not a directory.")
            objects.append(obj)
        for index in range(len(objects)):
            leaf = index == len(objects) - 1
            label = what if leaf else f"an ancestor of {what}"
            for role in roles:
                # Ownership is evaluated inside the rights: an owner holds
                # WRITE_DAC implicitly unless OWNER RIGHTS replaces it.
                takeover = 0 if leaf else self.rights_of(objects[index], role) & (WRITE_DAC | WRITE_OWNER)
                if takeover:
                    raise IdentityBoundaryError(
                        category,
                        f"the {role} identity could be granted {describe_rights(takeover)} on {label}, "
                        "and so could grant itself the right to delete or rename what lies below it.",
                    )
                if index == 0:
                    continue  # the volume root has no parent and cannot be renamed
                if self.rights_of(objects[index], role) & DELETE:
                    raise IdentityBoundaryError(
                        category, f"the {role} identity could delete or rename {label}."
                    )
                if self.rights_of(objects[index - 1], role) & FILE_DELETE_CHILD:
                    raise IdentityBoundaryError(
                        category,
                        f"the {role} identity could delete or rename {label} through its parent "
                        "(DELETE_CHILD), whatever its own DACL says.",
                    )

    def nearest_existing(self, path: str, what: str) -> tuple[_Object, str]:
        """The deepest existing component of ``path`` and the missing remainder."""
        chain = _components(path)
        for component in reversed(chain):
            obj = self.object(component, f"an ancestor of {what}")
            if obj is not None:
                return obj, path[len(component):].lstrip("\\")
        raise IdentityBoundaryError(_C.OBJECT_MISSING, f"no component of {what} exists.")

    def walk(self, root: _Object, what: str, visit: Callable[[_Object, str], None]) -> None:
        """Visit every descendant of ``root``, refusing any reparse point."""
        stack = [(root.path, what)]
        while stack:
            path, label = stack.pop()
            for entry in self.listing(path, label):
                child_path = ntpath.join(path, entry.name)
                child_label = f"{label}\\{entry.name}"
                obj = self.object(child_path, child_label)
                if obj is None:
                    raise IdentityBoundaryError(
                        _C.SECURITY_FACT_UNAVAILABLE, f"{child_label} vanished while being examined."
                    )
                if obj.facts.is_reparse_point or entry.is_reparse_point:
                    raise IdentityBoundaryError(_C.OBJECT_REPARSE, f"{child_label} is a reparse point.")
                if obj.facts.is_directory != entry.is_directory:
                    raise self.malformed(f"the listing of {label}")
                visit(obj, child_label)
                if obj.facts.is_directory:
                    stack.append((child_path, child_label))


# -- the checks, in order ------------------------------------------------------------


def _check_platform(run: _Run) -> None:
    if run.call("the platform", run.facts.is_windows) is not True:
        raise IdentityBoundaryError(
            _C.PLATFORM_UNSUPPORTED,
            "the identity boundary is a Windows access-control boundary; no other platform "
            "can be proven isolated.",
        )


def _check_environment(run: _Run) -> None:
    names = run.call("the environment block", run.facts.environment_names)
    if type(names) is not tuple or any(type(n) is not str for n in names):
        raise run.malformed("the environment block")
    found = sorted({
        name for name in names
        if name.upper() in _FORBIDDEN_ENVIRONMENT_NAMES
        or name.upper().startswith(_FORBIDDEN_ENVIRONMENT_PREFIXES)
    })
    if found:
        raise IdentityBoundaryError(
            _C.ENVIRONMENT_UNSAFE,
            f"the authority process's environment holds {', '.join(found)}.",
        )


def _groups_ok(groups: object) -> bool:
    return type(groups) is tuple and all(
        type(g) is tuple and len(g) == 2 and type(g[0]) is str and type(g[1]) is int for g in groups
    )


def _canonical_groups(groups: tuple[tuple[str, int], ...], what: str, run: _Run) -> None:
    for sid, _attributes in groups:
        try:
            canonical_sid(sid)
        except DescriptorError:
            raise run.malformed(f"a group SID of {what}") from None


def _privileged_group(sid: str) -> bool:
    if sid in _PRIVILEGED_BUILTIN_GROUPS:
        return True
    parts = sid.split("-")
    if parts[:4] == ["S", "1", "5", "21"] and len(parts) == 8 and int(parts[7]) in _PRIVILEGED_DOMAIN_RIDS:
        return True
    return is_integrity_sid(sid) and int(parts[-1]) >= _HIGH_INTEGRITY_RID


def _check_token(run: _Run) -> TokenFacts:
    token = run.call("the process token", run.facts.current_token)
    if (
        type(token) is not TokenFacts
        or type(token.user_sid) is not str
        or not _groups_ok(token.groups)
        or type(token.privileges) is not tuple
        or any(type(p) is not str for p in token.privileges)
        or type(token.elevated) is not bool
        or type(token.elevation_type) is not int
        or type(token.integrity_rid) is not int
        or type(token.default_dacl) is not bytes
        or type(token.authentication_id) is not int
        or not 0 < token.authentication_id < 2**64
    ):
        raise run.malformed("the process token")
    try:
        canonical_sid(token.user_sid)
    except DescriptorError:
        raise run.malformed("the process token user") from None
    _canonical_groups(token.groups, "the process token", run)
    if token.elevated or token.elevation_type != _TOKEN_ELEVATION_TYPE_DEFAULT:
        raise IdentityBoundaryError(
            _C.TOKEN_ELEVATED,
            "the authority process token is elevated or belongs to an administrator "
            "(a full or filtered UAC token).",
        )
    if token.integrity_rid > _MEDIUM_INTEGRITY_RID:
        raise IdentityBoundaryError(
            _C.TOKEN_ELEVATED, "the authority process runs above medium integrity."
        )
    extra = sorted(set(token.privileges) - STANDARD_USER_PRIVILEGES)
    if extra:
        raise IdentityBoundaryError(
            _C.TOKEN_PRIVILEGED,
            f"the authority process token holds {', '.join(extra)} (enabled or not).",
        )
    for sid, _attributes in token.groups:
        if _privileged_group(sid):
            raise IdentityBoundaryError(
                _C.ACCOUNT_PRIVILEGED,
                f"the authority process token carries the administrative group {sid} "
                "(even deny-only membership means an administrator account).",
            )
    logon = [sid for sid, attrs in token.groups if attrs & _SE_GROUP_LOGON_ID == _SE_GROUP_LOGON_ID]
    if len(logon) != 1 or not is_logon_sid(logon[0]):
        raise IdentityBoundaryError(
            _C.SESSION_FOREIGN, "the authority process token does not carry exactly one logon SID."
        )
    try:
        parse_acl(token.default_dacl)
    except DescriptorError as exc:
        raise IdentityBoundaryError(
            _C.DESCRIPTOR_UNSUPPORTED, f"the token's default DACL: {exc}"
        ) from None
    run.token = token
    run.authority_logon_sid = logon[0]
    return token


def _read_boundary(run: _Run, expected_sha256: str | None) -> tuple[IdentityBoundary, str, str, str]:
    program_data = run.call("the ProgramData location", run.facts.program_data_directory)
    try:
        validate_local_path(program_data)
    except ValueError:
        raise IdentityBoundaryError(
            _C.BOUNDARY_UNREADABLE, "the ProgramData location is not an absolute local path."
        ) from None
    directory = ntpath.join(program_data, BOUNDARY_DIRECTORY_NAME)
    path = ntpath.join(directory, BOUNDARY_FILE_NAME)
    result = run.call("the identity boundary", run.facts.read_file, path, MAX_BOUNDARY_BYTES)
    if result is None:
        raise IdentityBoundaryError(
            _C.BOUNDARY_UNREADABLE, "no identity boundary exists at its code-constant location."
        )
    if type(result) is not tuple or len(result) != 2 or type(result[1]) is not bytes:
        raise run.malformed("the identity boundary read")
    facts = run.checked_object_facts(result[0], "the identity boundary")
    data = result[1]
    if facts.is_directory:
        raise IdentityBoundaryError(_C.BOUNDARY_UNREADABLE, "the identity boundary is a directory.")
    if facts.is_reparse_point or facts.final_path is None or _key(facts.final_path) != _key(path):
        raise IdentityBoundaryError(
            _C.BOUNDARY_UNPROTECTED, "the identity boundary is a reparse point or is redirected."
        )
    if facts.link_count != 1:
        raise IdentityBoundaryError(
            _C.BOUNDARY_UNPROTECTED, "the identity boundary has more than one hard link."
        )
    file_descriptor = run.descriptor(facts.security_descriptor, "the identity boundary")
    if file_descriptor.owner not in ADMIN_OWNERS:
        raise IdentityBoundaryError(
            _C.BOUNDARY_UNPROTECTED,
            f"the identity boundary is owned by {file_descriptor.owner}, not SYSTEM, "
            "Administrators or TrustedInstaller.",
        )
    run.objects[_key(path)] = _Object(path, facts, file_descriptor)
    anchor = run.object(directory, "the identity boundary directory")
    if anchor is None or not anchor.facts.is_directory:
        raise IdentityBoundaryError(
            _C.BOUNDARY_UNREADABLE, "the identity boundary directory does not exist."
        )
    if anchor.facts.is_reparse_point or anchor.facts.final_path is None or _key(anchor.facts.final_path) != _key(directory):
        raise IdentityBoundaryError(
            _C.BOUNDARY_UNPROTECTED, "the identity boundary directory is a reparse point or redirected."
        )
    if anchor.descriptor.owner not in ADMIN_OWNERS or not anchor.descriptor.protected:
        raise IdentityBoundaryError(
            _C.BOUNDARY_UNPROTECTED,
            "the identity boundary directory must be admin-owned with a protected DACL.",
        )
    if len(data) > MAX_BOUNDARY_BYTES:
        raise IdentityBoundaryError(_C.BOUNDARY_MALFORMED, "the boundary exceeds its size bound.")
    boundary = parse_identity_boundary(data)
    digest = hashlib.sha256(data).hexdigest()
    if expected_sha256 is not None and digest != expected_sha256:
        raise IdentityBoundaryError(
            _C.BOUNDARY_DIGEST_MISMATCH,
            "the identity boundary is not the one bound in the plan activation.",
        )
    return boundary, digest, path, directory


def _account_kind(sid: str) -> str | None:
    parts = sid.split("-")
    if len(parts) == 8 and parts[:4] == ["S", "1", "5", "21"] and int(parts[7]) >= 1000:
        return "machine_or_domain"
    if len(parts) == 8 and parts[:4] == ["S", "1", "12", "1"]:
        return "entra"
    return None


def _check_identities(run: _Run, boundary: IdentityBoundary, token: TokenFacts) -> None:
    declared = {
        "authority": boundary.authority,
        "execution": boundary.execution,
        "operator": boundary.operator,
    }
    for role, account in declared.items():
        kind = _account_kind(account.sid)
        if kind is None or (role != "operator" and kind != "machine_or_domain"):
            raise IdentityBoundaryError(
                _C.IDENTITY_INVALID,
                f"the {role} SID {account.sid} is not an ordinary user account SID.",
            )
    if boundary.authority.sid.rsplit("-", 1)[0] != boundary.execution.sid.rsplit("-", 1)[0]:
        raise IdentityBoundaryError(
            _C.IDENTITY_INVALID, "the authority and execution accounts are not in the same local domain."
        )
    if token.user_sid != boundary.authority.sid:
        raise IdentityBoundaryError(
            _C.TOKEN_IDENTITY_MISMATCH,
            f"the process runs as {token.user_sid}, not as the authority identity.",
        )

    facts: dict[str, PrincipalFacts] = {}
    for role, account in declared.items():
        try:
            value = run.call(f"the {role} account", run.facts.principal, account.sid)
        except IdentityBoundaryError as exc:
            raise IdentityBoundaryError(_C.PRINCIPAL_UNVERIFIABLE, exc.detail) from None
        if (
            type(value) is not PrincipalFacts
            or value.sid != account.sid
            or type(value.account_name) is not str
            or type(value.sid_type) is not int
            or type(value.is_local_account) is not bool
            or not _groups_ok(value.groups)
            or type(value.privileges) is not tuple
            or any(type(p) is not str for p in value.privileges)
        ):
            raise IdentityBoundaryError(
                _C.PRINCIPAL_UNVERIFIABLE, f"the {role} account's facts are malformed."
            )
        _canonical_groups(value.groups, f"the {role} account", run)
        if value.sid_type != _SID_TYPE_USER:
            raise IdentityBoundaryError(_C.IDENTITY_INVALID, f"the {role} SID is not a user account.")
        if value.account_name.casefold() != account.account.casefold():
            raise IdentityBoundaryError(
                _C.IDENTITY_INVALID,
                f"the {role} SID belongs to {value.account_name}, not the declared account.",
            )
        if role != "operator" and not value.is_local_account:
            raise IdentityBoundaryError(
                _C.IDENTITY_INVALID, f"the {role} account is not a local account of this computer."
            )
        for sid, _attributes in value.groups:
            if _privileged_group(sid):
                raise IdentityBoundaryError(
                    _C.ACCOUNT_PRIVILEGED, f"the {role} account is a member of {sid}."
                )
        extra = sorted(set(value.privileges) - STANDARD_USER_PRIVILEGES)
        if extra:
            raise IdentityBoundaryError(
                _C.ACCOUNT_PRIVILEGED, f"the {role} account holds {', '.join(extra)}."
            )
        facts[role] = value

    authority_groups = {sid for sid, _ in facts["authority"].groups} | {sid for sid, _ in token.groups}
    for role in ("execution", "operator"):
        shared = sorted(
            sid for sid in authority_groups & {s for s, _ in facts[role].groups}
            if sid not in _BASELINE_SHARED_GROUPS
            and not is_logon_sid(sid) and not is_integrity_sid(sid)
            and not (sid.startswith("S-1-5-21-") and sid.endswith("-513"))
        )
        if shared:
            raise IdentityBoundaryError(
                _C.IDENTITY_INVALID,
                f"the authority identity shares {', '.join(shared)} with the {role} identity.",
            )

    def principal(role: str, extra_groups: set[str], excluded: str | None) -> Principal:
        value = facts[role]
        groups = {sid for sid, _ in value.groups if not is_integrity_sid(sid)} | extra_groups
        certain = {value.sid, EVERYONE} | {
            sid for sid in groups if sid not in _LOGON_DEPENDENT_SIDS and not is_logon_sid(sid)
        }
        return Principal(
            role=role,
            sid=value.sid,
            allow_sids=frozenset(groups | certain | _ALWAYS_POSSIBLE),
            deny_sids=frozenset(certain),
            excluded_logon_sid=excluded,
        )

    token_groups = {sid for sid, _ in token.groups if not is_integrity_sid(sid)}
    run.principals = {
        "authority": principal("authority", token_groups, None),
        "execution": principal("execution", set(), run.authority_logon_sid),
        "operator": principal("operator", set(), run.authority_logon_sid),
    }


_ALL = ("authority", "execution", "operator")
_ADVERSARIES = ("execution", "operator")


def _check_anchor(run: _Run, path: str, directory: str) -> None:
    anchor_file = run.objects[_key(path)]
    anchor_dir = run.objects[_key(directory)]
    assert anchor_file is not None and anchor_dir is not None
    limits = {role: READ_ONLY for role in _ALL}
    run.limit_object(anchor_file, limits, "the identity boundary", _C.BOUNDARY_UNPROTECTED)
    run.limit_object(anchor_dir, limits, "the identity boundary directory", _C.BOUNDARY_UNPROTECTED)
    run.inheritance(anchor_dir, ADMINISTRATORS, limits, "the identity boundary directory",
                    category=_C.BOUNDARY_UNPROTECTED)
    run.not_replaceable(path, _ALL, "the identity boundary", _C.BOUNDARY_UNPROTECTED)


def _service_window_station(authentication_id: int) -> str:
    """``Service-0x<high>-<low>$``: the name Windows gives the non-interactive
    window station it creates for the logon session with this LUID."""
    return f"Service-0x{authentication_id >> 32:x}-{authentication_id & 0xFFFF_FFFF:x}$"


def _check_session(run: _Run, boundary: IdentityBoundary) -> None:
    session = run.call("the window station and desktop", run.facts.session)
    if (
        type(session) is not SessionFacts
        or type(session.window_station) is not str
        or type(session.window_station_visible) is not bool
        or type(session.desktop) is not str
        or not (session.window_station_sid is None or type(session.window_station_sid) is str)
        or not (session.desktop_sid is None or type(session.desktop_sid) is str)
        or type(session.window_station_descriptor) is not bytes
        or type(session.desktop_descriptor) is not bytes
    ):
        raise run.malformed("the window station and desktop")
    own = run.authority_logon_sid
    _check_session_identity(run, boundary, session, own)
    # Whatever the names and SIDs say, X and O must not be able to open or use
    # the station or the desktop (hooks, input, window messages, clipboard),
    # and must not own them. This also refuses a station someone else created
    # under the name Windows would give A's.
    for what, raw, kind in (
        ("the authority window station", session.window_station_descriptor, ObjectKind.WINDOW_STATION),
        ("the authority desktop", session.desktop_descriptor, ObjectKind.DESKTOP),
    ):
        descriptor = run.descriptor(bytes(raw), what)
        for role in _ADVERSARIES:
            if run.principals[role].may_hold(descriptor.owner):
                raise IdentityBoundaryError(
                    _C.SESSION_FOREIGN, f"{what} is owned by a SID the {role} identity may hold."
                )
        run.limit(descriptor, kind, {role: NO_ACCESS for role in _ADVERSARIES}, what, _C.SESSION_FOREIGN)


def _check_session_identity(
    run: _Run, boundary: IdentityBoundary, session: SessionFacts, own: str | None
) -> None:
    if boundary.launch_mechanism == "interactive_session":
        if not (
            session.window_station_visible
            and session.window_station.casefold() == "winsta0"
            and session.window_station_sid == own
            and session.desktop_sid == own
        ):
            raise IdentityBoundaryError(
                _C.SESSION_FOREIGN,
                "the authority process is not on the authority identity's own interactive "
                "window station and desktop.",
            )
    else:
        if session.window_station_visible or session.window_station.casefold() == "winsta0":
            raise IdentityBoundaryError(
                _C.SESSION_FOREIGN,
                "a Task Scheduler (S4U) launch must run on a non-interactive window station.",
            )
        # Not being WinSta0 proves nothing about whose station it is. A station
        # that reports a SID belongs to that logon session; one that reports
        # none (as service stations, SYSTEM's included, may) is A's only if it
        # is the station Windows names after A's own logon session LUID.
        if session.window_station_sid is not None and session.window_station_sid != own:
            raise IdentityBoundaryError(
                _C.SESSION_FOREIGN,
                "the authority process's window station belongs to another logon session.",
            )
        assert run.token is not None
        if _key(session.window_station) != _key(_service_window_station(run.token.authentication_id)):
            raise IdentityBoundaryError(
                _C.SESSION_FOREIGN,
                "the authority process's window station is not the one created for its own logon "
                "session (a shared or system window station does not isolate it).",
            )
        if session.desktop_sid is not None and session.desktop_sid != own:
            raise IdentityBoundaryError(
                _C.SESSION_FOREIGN, "the authority process's desktop belongs to another logon session."
            )


def _check_process(run: _Run) -> None:
    value = run.call("the process security", run.facts.process)
    if type(value) is not ProcessFacts or any(
        type(getattr(value, field)) is not bytes
        for field in ("process_descriptor", "thread_descriptor", "token_descriptor")
    ):
        raise run.malformed("the process security")
    assert run.token is not None
    default = SecurityDescriptor(
        owner=run.token.user_sid,
        dacl=parse_acl(run.token.default_dacl),
        control=0x8004,
    )
    targets = (
        ("the authority process", run.descriptor(value.process_descriptor, "the authority process"), ObjectKind.PROCESS),
        ("the authority thread", run.descriptor(value.thread_descriptor, "the authority thread"), ObjectKind.THREAD),
        ("the authority token", run.descriptor(value.token_descriptor, "the authority token"), ObjectKind.TOKEN),
        ("objects the authority token creates (default DACL)", default, ObjectKind.THREAD),
    )
    for what, descriptor, kind in targets:
        run.limit(descriptor, kind, {role: NO_ACCESS for role in _ADVERSARIES}, what, _C.PROCESS_ACCESS)


def _check_authority_directory(
    run: _Run, path: str, what: str, *, operator_rights: int, operator_child_rights: int,
    child_creator: str, descendant_owners: frozenset[str],
) -> None:
    authority = run.sid_of("authority")
    obj = run.declared(path, what)
    run.not_replaceable(path, _ADVERSARIES, what)
    run.owner_is(obj, frozenset({authority}), what)
    if not obj.descriptor.protected:
        raise IdentityBoundaryError(_C.OBJECT_UNPROTECTED, f"{what} does not have a protected DACL.")
    run.limit_object(obj, {"execution": NO_ACCESS, "operator": operator_rights}, what)
    run.inheritance(obj, child_creator, {"execution": NO_ACCESS, "operator": operator_child_rights}, what)

    def visit(child: _Object, label: str) -> None:
        run.owner_is(child, descendant_owners, label)
        if not child.facts.is_directory and child.facts.link_count != 1:
            raise IdentityBoundaryError(_C.OBJECT_LINKED, f"{label} has more than one hard link.")
        run.limit_object(child, {"execution": NO_ACCESS, "operator": operator_child_rights}, label)
        if child.facts.is_directory:
            run.inheritance(child, authority, {"execution": NO_ACCESS, "operator": operator_child_rights}, label)

    run.walk(obj, what, visit)


def _check_inbox(run: _Run, path: str) -> None:
    authority, operator = run.sid_of("authority"), run.sid_of("operator")
    what = "inbox"
    obj = run.declared(path, what)
    run.not_replaceable(path, _ADVERSARIES, what)
    run.owner_is(obj, frozenset({authority}), what)
    if not obj.descriptor.protected:
        raise IdentityBoundaryError(_C.OBJECT_UNPROTECTED, f"{what} does not have a protected DACL.")
    run.limit_object(obj, {"execution": NO_ACCESS, "operator": _INBOX_OPERATOR_RIGHTS}, what)
    run.inheritance(obj, operator, {"execution": NO_ACCESS}, what, kinds=(ObjectKind.FILE,))

    def visit(child: _Object, label: str) -> None:
        if child.facts.is_directory:
            raise IdentityBoundaryError(_C.OBJECT_KIND, f"{label} is a directory; the inbox holds files only.")
        run.owner_is(child, frozenset({authority, operator}), label)
        if child.facts.link_count != 1:
            raise IdentityBoundaryError(_C.OBJECT_LINKED, f"{label} has more than one hard link.")
        run.limit_object(child, {"execution": NO_ACCESS}, label)

    run.walk(obj, what, visit)


def _check_exchange_root(run: _Run, path: str) -> None:
    what = "exchange_root"
    obj = run.declared(path, what)
    run.not_replaceable(path, _ADVERSARIES, what)
    run.owner_is(obj, frozenset({run.sid_of("authority")}), what)
    if not obj.descriptor.protected:
        raise IdentityBoundaryError(_C.OBJECT_UNPROTECTED, f"{what} does not have a protected DACL.")
    limits = {"execution": READ_ONLY, "operator": READ_ONLY}
    run.limit_object(obj, limits, what)
    run.inheritance(obj, run.sid_of("authority"), limits, what)


def _check_clone(run: _Run, path: str) -> None:
    execution = run.sid_of("execution")
    what = "clone"
    obj = run.declared(path, what)
    run.not_replaceable(path, _ADVERSARIES, what)
    parent = run.object(ntpath.dirname(path), "the clone's parent")
    assert parent is not None  # proven by not_replaceable
    run.limit_object(parent, {"execution": READ_ONLY}, "the clone's parent")
    run.owner_is(obj, frozenset({execution}), what)
    if not obj.descriptor.protected:
        raise IdentityBoundaryError(_C.OBJECT_UNPROTECTED, f"{what} does not have a protected DACL.")
    run.require_owner_rights_ace(obj, what, inheritable=True)
    run.limit_object(obj, {"execution": _CLONE_ROOT_EXECUTION_RIGHTS, "operator": READ_ONLY}, what)
    run.inheritance(obj, execution, {"execution": _WORKING_TREE_CHILD_RIGHTS, "operator": READ_ONLY}, what)

    git_path = ntpath.join(path, ".git")
    git_what = "clone\\.git"
    git = run.object(git_path, git_what)
    if git is None:
        raise IdentityBoundaryError(_C.OBJECT_MISSING, f"{git_what} does not exist.")
    if git.facts.is_reparse_point:
        raise IdentityBoundaryError(_C.OBJECT_REPARSE, f"{git_what} is a reparse point.")
    if not git.facts.is_directory:
        raise IdentityBoundaryError(
            _C.OBJECT_KIND, f"{git_what} is not a directory (a gitfile redirects the repository)."
        )
    run.not_replaceable(git_path, _ADVERSARIES, git_what)
    run.owner_is(git, frozenset({execution}), git_what)
    if not git.descriptor.protected:
        raise IdentityBoundaryError(_C.OBJECT_UNPROTECTED, f"{git_what} does not have a protected DACL.")
    run.require_owner_rights_ace(git, git_what, inheritable=True)
    read_only = {"execution": READ_ONLY, "operator": READ_ONLY}
    run.limit_object(git, read_only, git_what)
    run.inheritance(git, execution, read_only, git_what)

    def visit(child: _Object, label: str) -> None:
        run.owner_is(child, frozenset({execution}), label)
        run.limit_object(child, read_only, label)
        if child.facts.is_directory:
            run.inheritance(child, execution, read_only, label)

    run.walk(git, git_what, visit)


def _check_install_root(run: _Run, index: int, path: str) -> str:
    """Returns the install root's final path, as Windows spells it."""
    what = f"install_root[{index}]"
    obj = run.declared(path, what)
    run.not_replaceable(path, _ALL, what)
    limits = {role: READ_ONLY for role in _ALL}
    run.owner_is(obj, ADMIN_OWNERS, what)
    run.limit_object(obj, limits, what)
    run.inheritance(obj, ADMINISTRATORS, limits, what)

    def visit(child: _Object, label: str) -> None:
        run.owner_is(child, ADMIN_OWNERS, label)
        run.limit_object(child, limits, label)
        if child.facts.is_directory:
            run.inheritance(child, ADMINISTRATORS, limits, label)

    run.walk(obj, what, visit)
    assert obj.facts.final_path is not None  # proven by declared()
    return obj.facts.final_path


def _canonical_code_path(run: _Run, raw: str, what: str) -> tuple[str, bool]:
    """The canonical spelling of a code location and whether it exists."""
    try:
        validate_local_path(raw)
    except ValueError:
        raise IdentityBoundaryError(
            _C.CODE_PATH_UNTRUSTED, f"{what} is not an absolute local path."
        ) from None
    existing, remainder = run.nearest_existing(raw, what)
    if existing.facts.is_reparse_point:
        raise IdentityBoundaryError(_C.OBJECT_REPARSE, f"{what} passes through a reparse point.")
    if existing.facts.final_path is None:
        raise run.malformed(f"the final path of {what}")
    # Windows follows a junction in any *intermediate* component even when the
    # last one is opened without following, so only an exact final path proves
    # that the path the interpreter uses is the path that was examined.
    if _key(existing.facts.final_path) != _key(existing.path):
        raise IdentityBoundaryError(
            _C.OBJECT_NOT_CANONICAL,
            f"{what} is not canonical: it passes through a reparse point, a short name or an alias.",
        )
    canonical = existing.facts.final_path
    if remainder:
        canonical = ntpath.join(canonical, remainder)
    return canonical, not remainder


def _check_code(run: _Run, boundary: IdentityBoundary) -> None:
    code = run.call("the code-load locations", run.facts.code_load)
    if type(code) is not CodeLoadFacts or any(
        type(getattr(code, field)) is not tuple or any(type(v) is not str for v in getattr(code, field))
        for field in ("executables", "prefixes", "import_paths", "search_paths", "profile_directories")
    ) or type(code.working_directory) is not str or type(code.package_directory) is not str:
        raise run.malformed("the code-load locations")
    if code.isolated_interpreter is not True:
        raise IdentityBoundaryError(
            _C.CODE_PATH_UNTRUSTED,
            "the interpreter was not started isolated (-I): PYTHON* variables, the user site "
            "and the script directory could have supplied code before this proof ran.",
        )
    roots = [
        _check_install_root(run, index, root) for index, root in enumerate(boundary.paths.install_roots)
    ]

    def inside_install_roots(raw: str, what: str, *, must_exist: bool) -> None:
        canonical, exists = _canonical_code_path(run, raw, what)
        if must_exist and not exists:
            raise IdentityBoundaryError(_C.OBJECT_MISSING, f"{what} does not exist.")
        if not any(_within_exact(canonical, root) for root in roots):
            raise IdentityBoundaryError(
                _C.CODE_PATH_UNTRUSTED, f"{what} is outside every declared install root."
            )

    for i, raw in enumerate(code.executables):
        inside_install_roots(raw, f"executable[{i}]", must_exist=True)
    for i, raw in enumerate(code.prefixes):
        inside_install_roots(raw, f"prefix[{i}]", must_exist=True)
    inside_install_roots(code.package_directory, "the AIDO package", must_exist=True)
    for i, raw in enumerate(code.import_paths):
        inside_install_roots(raw, f"import_path[{i}]", must_exist=False)

    for i, raw in enumerate(code.search_paths):
        if raw == "":
            continue  # an empty PATH entry means the working directory, checked below
        if raw.endswith("\\") and len(raw) > 3:
            raw = raw[:-1]  # "C:\dir\" names the same directory as "C:\dir"
        _check_search_directory(run, raw, f"search_path[{i}]", must_exist=False)
    _check_search_directory(run, code.working_directory, "the working directory", must_exist=True)
    if not code.profile_directories:
        raise run.malformed("the profile locations")
    for i, raw in enumerate(code.profile_directories):
        _check_profile_directory(run, raw, f"profile[{i}]")


def _check_search_directory(run: _Run, raw: str, what: str, *, must_exist: bool) -> None:
    """A directory searched for executables or DLLs: X and O cannot add to it,
    replace it, re-permission it, or modify a file directly in it, and no
    entry directly in it is a reparse point."""
    canonical, exists = _canonical_code_path(run, raw, what)
    limits = {role: READ_ONLY for role in _ADVERSARIES}
    if not exists:
        if must_exist:
            raise IdentityBoundaryError(_C.OBJECT_MISSING, f"{what} does not exist.")
        existing, _ = run.nearest_existing(canonical, what)
        for role in _ADVERSARIES:
            # WRITE_DAC or WRITE_OWNER would let it grant itself the add rights.
            if run.rights_of(existing, role) & (FILE_ADD_FILE | FILE_ADD_SUBDIRECTORY | WRITE_DAC | WRITE_OWNER):
                raise IdentityBoundaryError(
                    _C.CODE_PATH_UNTRUSTED,
                    f"{what} does not exist and the {role} identity could create it.",
                )
        run.not_replaceable(existing.path, _ADVERSARIES, f"the nearest existing ancestor of {what}")
        return
    obj = run.object(canonical, what)
    assert obj is not None
    if not obj.facts.is_directory:
        raise IdentityBoundaryError(_C.OBJECT_KIND, f"{what} is not a directory.")
    run.not_replaceable(canonical, _ADVERSARIES, what)
    run.owner_not_held_by(obj, _ADVERSARIES, what)
    run.limit_object(obj, limits, what)
    run.inheritance(obj, obj.descriptor.owner, limits, what, kinds=(ObjectKind.FILE,))
    # A link is examined without following it, so its own protection says
    # nothing about the image or DLL a search loads through it. No entry is
    # followed and no target is proven: any reparse entry refuses, a directory
    # one included (its attribute says nothing about what its target is).
    unproven = "is a reparse point; what a search would load through it is not proven."
    for entry in run.listing(canonical, what):
        label = f"{what}\\{entry.name}"
        if entry.is_reparse_point:
            raise IdentityBoundaryError(_C.OBJECT_REPARSE, f"{label} {unproven}")
        if entry.is_directory:
            # Only files directly in a search directory can be loaded from it.
            # A subdirectory is not opened: some (System32\config, for one)
            # deny a standard user even READ_CONTROL.
            continue
        child = run.object(ntpath.join(canonical, entry.name), label)
        if child is None:
            raise IdentityBoundaryError(
                _C.SECURITY_FACT_UNAVAILABLE, f"{label} vanished while being examined."
            )
        if child.facts.is_reparse_point:
            raise IdentityBoundaryError(_C.OBJECT_REPARSE, f"{label} {unproven}")
        if child.facts.is_directory:
            raise run.malformed(f"the listing of {what}")
        run.owner_not_held_by(child, _ADVERSARIES, label)
        run.limit_object(child, limits, label)


def _check_profile_directory(run: _Run, raw: str, what: str) -> None:
    try:
        validate_local_path(raw)
    except ValueError:
        raise IdentityBoundaryError(
            _C.OBJECT_MISSING, f"{what} is not defined as an absolute local path."
        ) from None
    canonical, exists = _canonical_code_path(run, raw, what)
    if not exists:
        raise IdentityBoundaryError(_C.OBJECT_MISSING, f"{what} does not exist.")
    obj = run.object(canonical, what)
    assert obj is not None
    if not obj.facts.is_directory:
        raise IdentityBoundaryError(_C.OBJECT_KIND, f"{what} is not a directory.")
    run.not_replaceable(canonical, _ADVERSARIES, what)
    run.owner_not_held_by(obj, _ADVERSARIES, what)
    limits = {role: NO_ACCESS for role in _ADVERSARIES}
    run.limit_object(obj, limits, what)
    run.inheritance(obj, run.sid_of("authority"), limits, what)


# -- entry points ---------------------------------------------------------------------


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _prove(
    facts: SecurityFacts,
    *,
    origin: Literal["windows", "injected"],
    expected_boundary_sha256: str | None,
    clock: Callable[[], datetime],
) -> IdentityBoundaryProof:
    if expected_boundary_sha256 is not None and (
        type(expected_boundary_sha256) is not str
        or len(expected_boundary_sha256) != 64
        or any(c not in "0123456789abcdef" for c in expected_boundary_sha256)
    ):
        raise IdentityBoundaryError(
            _C.BOUNDARY_DIGEST_MISMATCH, "the expected boundary digest is not a SHA-256 hex digest."
        )
    run = _Run(facts, require_independent=origin == "windows")
    _check_platform(run)
    _check_environment(run)
    token = _check_token(run)
    boundary, digest, path, directory = _read_boundary(run, expected_boundary_sha256)
    _check_identities(run, boundary, token)
    _check_anchor(run, path, directory)
    _check_session(run, boundary)
    _check_process(run)
    paths = boundary.paths
    authority = boundary.authority.sid
    _check_authority_directory(
        run, paths.state_root, "state_root", operator_rights=NO_ACCESS,
        operator_child_rights=NO_ACCESS, child_creator=authority,
        descendant_owners=frozenset({authority}),
    )
    _check_authority_directory(
        run, paths.published, "published", operator_rights=READ_ONLY,
        operator_child_rights=READ_ONLY, child_creator=authority,
        descendant_owners=frozenset({authority}),
    )
    _check_inbox(run, paths.inbox)
    _check_exchange_root(run, paths.exchange_root)
    _check_clone(run, paths.clone)
    _check_code(run, boundary)
    proven_at = clock()
    if type(proven_at) is not datetime or proven_at.tzinfo is None:
        raise IdentityBoundaryError(_C.SECURITY_FACT_UNAVAILABLE, "the clock is not timezone-aware.")
    return IdentityBoundaryProof(
        _token=_PROOF_TOKEN,
        boundary=boundary,
        boundary_sha256=digest,
        facts_origin=origin,
        independent_evaluation=run.independent_complete,
        proven_at=proven_at,
        objects_examined=run.examined,
    )


def prove_identity_boundary(*, expected_boundary_sha256: str | None = None) -> IdentityBoundaryProof:
    """Prove the FD-16 identity boundary for **this** process, from live Windows
    facts and the code-constant ``%ProgramData%\\AIDO\\identity-boundary.v1.json``.

    There is no parameter for a facts source, a path or a boundary.
    ``expected_boundary_sha256`` can only narrow: once a plan activation binds a
    boundary digest, a different boundary refuses.
    """
    if sys.platform != "win32" or os.name != "nt":
        raise IdentityBoundaryError(
            _C.PLATFORM_UNSUPPORTED,
            "the identity boundary is a Windows access-control boundary; no other platform "
            "can be proven isolated.",
        )
    from ai_dev_orchestrator.integration.windows_security import WindowsSecurityFacts

    try:
        facts = WindowsSecurityFacts()
    except Exception as exc:
        raise IdentityBoundaryError(
            _C.SECURITY_FACT_UNAVAILABLE, f"Windows security APIs are unavailable ({_failure_reason(exc)})."
        ) from None
    return _prove(facts, origin="windows", expected_boundary_sha256=expected_boundary_sha256,
                  clock=_utc_now)


def prove_identity_boundary_from_facts(
    facts: SecurityFacts,
    *,
    expected_boundary_sha256: str | None = None,
    clock: Callable[[], datetime] | None = None,
) -> IdentityBoundaryProof:
    """Run the same proof over a caller-supplied facts source.

    For offline tests and library composition. The result is always marked
    ``facts_origin="injected"`` and ``is_production`` is always ``False``,
    whatever the source is or claims to be.
    """
    return _prove(facts, origin="injected", expected_boundary_sha256=expected_boundary_sha256,
                  clock=clock or _utc_now)
