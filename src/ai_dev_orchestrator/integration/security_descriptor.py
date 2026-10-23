"""DL-4B S0 — Windows security descriptors as data, and an upper-bound evaluator.

This module is pure: it parses and builds self-relative security descriptors,
and answers one question about them:

    What is the **most** a principal could ever be granted on this object?

It never asks the opposite question ("what is it certainly granted?"), because
the identity boundary only ever needs to prove that the execution identity X
*cannot* do something. Every approximation here therefore errs towards granting
more:

- **Allow and deny match different SID sets.** A principal carries the SIDs it
  *may* hold in some token (``allow_sids``: its user and groups, plus every
  logon-dependent SID such as ``INTERACTIVE``, ``NETWORK`` or ``BATCH``) and the
  SIDs it *certainly* holds in every token (``deny_sids``). An allow ACE matches
  the first set, a deny ACE only the second. A deny ACE for ``INTERACTIVE``
  therefore never "protects" an object from X's network or batch tokens.
  Granting is monotone in both directions, so the result bounds every real token.
- **Generic rights are mapped.** AuthZ does not map ``GENERIC_*`` bits found in
  an ACE (observed on Windows 11), the kernel may; the larger answer is used.
- **Logon SIDs** (``S-1-5-5-x-y``) are unknowable in advance, so every one may
  match, except a single excluded one (the authority's own logon session).
- **Owner rights** follow Windows: the owner is implicitly granted
  ``READ_CONTROL | WRITE_DAC`` before any ACE is read, unless the DACL holds an
  effective ``OWNER RIGHTS`` (``S-1-3-4``) ACE, in which case those ACEs replace
  the implicit grant.

What is refused rather than approximated, because a correct upper bound cannot
be stated for it: a missing or NULL DACL (grants everyone everything), an
absent owner, any ACE type other than basic allow/deny (object, callback and
conditional ACEs are evaluated by Windows against claims and attributes this
module cannot see), unknown ACE or control flags, and any malformed length,
offset or SID.

Privileges are deliberately **not** modelled. ``SeBackupPrivilege``,
``SeRestorePrivilege``, ``SeTakeOwnershipPrivilege`` and their kin bypass the
DACL entirely, so the identity boundary refuses any principal that holds one
before an evaluation result is ever used.

Mandatory integrity labels, AppContainer and restricted-token checks can only
remove access, so ignoring them keeps the bound an upper bound.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import Enum

# -- access rights ------------------------------------------------------------

DELETE = 0x0001_0000
READ_CONTROL = 0x0002_0000
WRITE_DAC = 0x0004_0000
WRITE_OWNER = 0x0008_0000
SYNCHRONIZE = 0x0010_0000
ACCESS_SYSTEM_SECURITY = 0x0100_0000
MAXIMUM_ALLOWED = 0x0200_0000
GENERIC_ALL = 0x1000_0000
GENERIC_EXECUTE = 0x2000_0000
GENERIC_WRITE = 0x4000_0000
GENERIC_READ = 0x8000_0000

FILE_READ_DATA = 0x0001  # FILE_LIST_DIRECTORY on a directory
FILE_WRITE_DATA = 0x0002  # FILE_ADD_FILE
FILE_APPEND_DATA = 0x0004  # FILE_ADD_SUBDIRECTORY
FILE_READ_EA = 0x0008
FILE_WRITE_EA = 0x0010
FILE_EXECUTE = 0x0020  # FILE_TRAVERSE
FILE_DELETE_CHILD = 0x0040
FILE_READ_ATTRIBUTES = 0x0080
FILE_WRITE_ATTRIBUTES = 0x0100
FILE_ADD_FILE = FILE_WRITE_DATA
FILE_ADD_SUBDIRECTORY = FILE_APPEND_DATA

FILE_ALL_ACCESS = 0x001F_01FF
FILE_GENERIC_READ = 0x0012_0089
FILE_GENERIC_WRITE = 0x0012_0116
FILE_GENERIC_EXECUTE = 0x0012_00A0
KERNEL_OBJECT_ALL_ACCESS = 0x001F_FFFF

#: Read, list, traverse and execute — nothing that changes the object, its
#: children, its attributes, its DACL or its owner.
READ_ONLY = FILE_GENERIC_READ | FILE_GENERIC_EXECUTE
NO_ACCESS = 0

_RIGHT_NAMES: tuple[tuple[int, str], ...] = (
    (FILE_READ_DATA, "READ_DATA"),
    (FILE_WRITE_DATA, "WRITE_DATA/ADD_FILE"),
    (FILE_APPEND_DATA, "APPEND_DATA/ADD_SUBDIRECTORY"),
    (FILE_READ_EA, "READ_EA"),
    (FILE_WRITE_EA, "WRITE_EA"),
    (FILE_EXECUTE, "EXECUTE/TRAVERSE"),
    (FILE_DELETE_CHILD, "DELETE_CHILD"),
    (FILE_READ_ATTRIBUTES, "READ_ATTRIBUTES"),
    (FILE_WRITE_ATTRIBUTES, "WRITE_ATTRIBUTES"),
    (DELETE, "DELETE"),
    (READ_CONTROL, "READ_CONTROL"),
    (WRITE_DAC, "WRITE_DAC"),
    (WRITE_OWNER, "WRITE_OWNER"),
    (SYNCHRONIZE, "SYNCHRONIZE"),
    (ACCESS_SYSTEM_SECURITY, "ACCESS_SYSTEM_SECURITY"),
)


def describe_rights(mask: int) -> str:
    """Name the bits of ``mask``, for refusal messages."""
    names = [name for bit, name in _RIGHT_NAMES if mask & bit]
    rest = mask & ~sum(bit for bit, _ in _RIGHT_NAMES)
    if rest:
        names.append(f"0x{rest:08x}")
    return "|".join(names) or "none"


class ObjectKind(Enum):
    FILE = "file"
    DIRECTORY = "directory"
    PROCESS = "process"
    THREAD = "thread"
    TOKEN = "token"
    WINDOW_STATION = "window_station"
    DESKTOP = "desktop"


def map_generic(mask: int, kind: ObjectKind) -> int:
    """Map ``GENERIC_*`` and ``MAXIMUM_ALLOWED`` bits to specific rights, upwards.

    ``MAXIMUM_ALLOWED`` has no meaning inside an ACE; it is treated as "all".
    """
    if kind in (ObjectKind.FILE, ObjectKind.DIRECTORY):
        everything = FILE_ALL_ACCESS
        table = (
            (GENERIC_READ, FILE_GENERIC_READ),
            (GENERIC_WRITE, FILE_GENERIC_WRITE),
            (GENERIC_EXECUTE, FILE_GENERIC_EXECUTE),
            (GENERIC_ALL, FILE_ALL_ACCESS),
        )
    else:
        everything = KERNEL_OBJECT_ALL_ACCESS
        table = tuple(
            (bit, KERNEL_OBJECT_ALL_ACCESS)
            for bit in (GENERIC_READ, GENERIC_WRITE, GENERIC_EXECUTE, GENERIC_ALL)
        )
    mapped = mask & ~(GENERIC_READ | GENERIC_WRITE | GENERIC_EXECUTE | GENERIC_ALL | MAXIMUM_ALLOWED)
    for bit, specific in table:
        if mask & bit:
            mapped |= specific
    if mask & MAXIMUM_ALLOWED:
        mapped |= everything
    return mapped


# -- SIDs -----------------------------------------------------------------------

EVERYONE = "S-1-1-0"
CREATOR_OWNER = "S-1-3-0"
CREATOR_GROUP = "S-1-3-1"
OWNER_RIGHTS = "S-1-3-4"
PRINCIPAL_SELF = "S-1-5-10"
LOCAL_SYSTEM = "S-1-5-18"
ADMINISTRATORS = "S-1-5-32-544"
TRUSTED_INSTALLER = "S-1-5-80-956008885-3459688365-3157278553-1931587221-3018813669"

_MAX_SUB_AUTHORITIES = 15


class DescriptorError(ValueError):
    """A security descriptor, ACL, ACE or SID is malformed or unsupported.

    Messages describe the structure only; they never carry file contents.
    """


def canonical_sid(text: object) -> str:
    """The canonical string form of a SID, or a refusal.

    Accepts only ``S-1-<authority>-<sub>...`` in decimal, with 1 to 15
    sub-authorities and no leading zeros, so one SID has exactly one spelling.
    """
    if not isinstance(text, str) or not text.isascii():
        raise DescriptorError("a SID must be ASCII text.")
    parts = text.split("-")
    if len(parts) < 4 or parts[0] != "S" or parts[1] != "1":
        raise DescriptorError("a SID must have the form S-1-<authority>-<sub-authority>...")
    numbers = parts[2:]
    if len(numbers) - 1 > _MAX_SUB_AUTHORITIES:
        raise DescriptorError("a SID has at most 15 sub-authorities.")
    for index, number in enumerate(numbers):
        if not number.isdigit() or (len(number) > 1 and number[0] == "0"):
            raise DescriptorError("a SID component must be a decimal number without leading zeros.")
        limit = 2**48 if index == 0 else 2**32
        if int(number) >= limit:
            raise DescriptorError("a SID component is out of range.")
    return text


def sid_to_bytes(sid: str) -> bytes:
    canonical_sid(sid)
    numbers = [int(n) for n in sid.split("-")[2:]]
    authority, subs = numbers[0], numbers[1:]
    return (
        bytes((1, len(subs)))
        + authority.to_bytes(6, "big")
        + b"".join(struct.pack("<I", s) for s in subs)
    )


def sid_from_bytes(data: bytes, offset: int, end: int) -> tuple[str, int]:
    """Parse one binary SID at ``offset`` that must end at or before ``end``.

    Returns the canonical string and the SID's length in bytes.
    """
    if offset < 0 or offset + 8 > end:
        raise DescriptorError("a SID is truncated.")
    revision, count = data[offset], data[offset + 1]
    if revision != 1:
        raise DescriptorError("a SID has an unsupported revision.")
    if not 1 <= count <= _MAX_SUB_AUTHORITIES:
        raise DescriptorError("a SID has an invalid sub-authority count.")
    length = 8 + 4 * count
    if offset + length > end:
        raise DescriptorError("a SID is truncated.")
    authority = int.from_bytes(data[offset + 2:offset + 8], "big")
    subs = struct.unpack_from(f"<{count}I", data, offset + 8)
    return "S-1-" + "-".join(str(n) for n in (authority, *subs)), length


def is_logon_sid(sid: str) -> bool:
    """``S-1-5-5-x-y``: a logon session SID. Unknowable in advance."""
    return sid.startswith("S-1-5-5-") and sid.count("-") == 5


def is_integrity_sid(sid: str) -> bool:
    return sid.startswith("S-1-16-")


def is_app_package_sid(sid: str) -> bool:
    """``S-1-15-*``: AppContainer and capability SIDs. An ACE naming one can
    only ever *add a second required check*, never grant to a normal token."""
    return sid.startswith("S-1-15-")


# -- ACEs, ACLs and descriptors ----------------------------------------------

ACCESS_ALLOWED_ACE_TYPE = 0x00
ACCESS_DENIED_ACE_TYPE = 0x01

OBJECT_INHERIT_ACE = 0x01
CONTAINER_INHERIT_ACE = 0x02
NO_PROPAGATE_INHERIT_ACE = 0x04
INHERIT_ONLY_ACE = 0x08
INHERITED_ACE = 0x10
_KNOWN_ACE_FLAGS = 0x1F

SE_OWNER_DEFAULTED = 0x0001
SE_GROUP_DEFAULTED = 0x0002
SE_DACL_PRESENT = 0x0004
SE_DACL_DEFAULTED = 0x0008
SE_SACL_PRESENT = 0x0010
SE_SACL_DEFAULTED = 0x0020
SE_DACL_AUTO_INHERIT_REQ = 0x0100
SE_SACL_AUTO_INHERIT_REQ = 0x0200
SE_DACL_AUTO_INHERITED = 0x0400
SE_SACL_AUTO_INHERITED = 0x0800
SE_DACL_PROTECTED = 0x1000
SE_SACL_PROTECTED = 0x2000
SE_RM_CONTROL_VALID = 0x4000
SE_SELF_RELATIVE = 0x8000
_KNOWN_CONTROL = (
    SE_OWNER_DEFAULTED | SE_GROUP_DEFAULTED | SE_DACL_PRESENT | SE_DACL_DEFAULTED
    | SE_SACL_PRESENT | SE_SACL_DEFAULTED | SE_DACL_AUTO_INHERIT_REQ
    | SE_SACL_AUTO_INHERIT_REQ | SE_DACL_AUTO_INHERITED | SE_SACL_AUTO_INHERITED
    | SE_DACL_PROTECTED | SE_SACL_PROTECTED | SE_RM_CONTROL_VALID | SE_SELF_RELATIVE
)

_MAX_DESCRIPTOR_BYTES = 64 * 1024


@dataclass(frozen=True)
class Ace:
    """One basic ACE: allow or deny ``mask`` to ``sid``."""

    ace_type: int
    flags: int
    mask: int
    sid: str

    def __post_init__(self) -> None:
        if self.ace_type not in (ACCESS_ALLOWED_ACE_TYPE, ACCESS_DENIED_ACE_TYPE):
            raise DescriptorError("only basic allow and deny ACEs are supported.")
        if not isinstance(self.flags, int) or self.flags & ~_KNOWN_ACE_FLAGS or self.flags < 0:
            raise DescriptorError("an ACE carries an unknown flag.")
        if not isinstance(self.mask, int) or not 0 <= self.mask < 2**32:
            raise DescriptorError("an ACE access mask is out of range.")
        canonical_sid(self.sid)

    @property
    def allows(self) -> bool:
        return self.ace_type == ACCESS_ALLOWED_ACE_TYPE

    @property
    def inherit_only(self) -> bool:
        return bool(self.flags & INHERIT_ONLY_ACE)


@dataclass(frozen=True)
class SecurityDescriptor:
    """The owner and DACL of one object. A NULL DACL cannot be represented."""

    owner: str
    dacl: tuple[Ace, ...]
    control: int
    group: str | None = None

    @property
    def protected(self) -> bool:
        """Inheritance from the parent is blocked (``SE_DACL_PROTECTED``)."""
        return bool(self.control & SE_DACL_PROTECTED)

    @property
    def effective_aces(self) -> tuple[Ace, ...]:
        return tuple(ace for ace in self.dacl if not ace.inherit_only)


def _parse_acl(data: bytes, offset: int, end: int) -> tuple[Ace, ...]:
    if offset + 8 > end:
        raise DescriptorError("an ACL header is truncated.")
    revision, sbz1, size, count, sbz2 = struct.unpack_from("<BBHHH", data, offset)
    if revision not in (2, 4) or sbz1 != 0 or sbz2 != 0:
        raise DescriptorError("an ACL has an unsupported revision or reserved bits.")
    if size < 8 or offset + size > end:
        raise DescriptorError("an ACL size is out of bounds.")
    acl_end = offset + size
    cursor = offset + 8
    aces = []
    for _ in range(count):
        if cursor + 8 > acl_end:
            raise DescriptorError("an ACE header is truncated.")
        ace_type, flags, ace_size = struct.unpack_from("<BBH", data, cursor)
        if ace_type not in (ACCESS_ALLOWED_ACE_TYPE, ACCESS_DENIED_ACE_TYPE):
            raise DescriptorError(
                f"ACE type 0x{ace_type:02x} is not supported; only basic allow and deny "
                "ACEs can be bounded."
            )
        if ace_size < 16 or ace_size % 4 or cursor + ace_size > acl_end:
            raise DescriptorError("an ACE size is out of bounds.")
        (mask,) = struct.unpack_from("<I", data, cursor + 4)
        sid, sid_length = sid_from_bytes(data, cursor + 8, cursor + ace_size)
        if 8 + sid_length != ace_size:
            raise DescriptorError("an ACE carries bytes beyond its SID.")
        aces.append(Ace(ace_type, flags, mask, sid))
        cursor += ace_size
    return tuple(aces)


def parse_security_descriptor(data: object) -> SecurityDescriptor:
    """Parse one self-relative security descriptor, or refuse it."""
    if type(data) is not bytes:
        raise DescriptorError("a security descriptor must be bytes.")
    end = len(data)
    if end < 20 or end > _MAX_DESCRIPTOR_BYTES:
        raise DescriptorError("a security descriptor has an invalid length.")
    revision, _sbz1, control, owner_at, group_at, sacl_at, dacl_at = struct.unpack_from(
        "<BBHIIII", data, 0
    )
    if revision != 1:
        raise DescriptorError("a security descriptor has an unsupported revision.")
    if not control & SE_SELF_RELATIVE:
        raise DescriptorError("a security descriptor must be self-relative.")
    if control & ~_KNOWN_CONTROL:
        raise DescriptorError("a security descriptor carries an unknown control flag.")
    if owner_at == 0:
        raise DescriptorError("a security descriptor has no owner.")
    if not control & SE_DACL_PRESENT or dacl_at == 0:
        raise DescriptorError(
            "a security descriptor has no DACL, which grants everyone every right."
        )
    for at in (owner_at, group_at, sacl_at, dacl_at):
        if at and (at < 20 or at >= end):
            raise DescriptorError("a security descriptor offset is out of bounds.")
    owner, _ = sid_from_bytes(data, owner_at, end)
    group = sid_from_bytes(data, group_at, end)[0] if group_at else None
    dacl = _parse_acl(data, dacl_at, end)
    return SecurityDescriptor(owner=owner, dacl=dacl, control=control, group=group)


def build_acl(aces: tuple[Ace, ...] | list[Ace]) -> bytes:
    body = b"".join(
        struct.pack("<BBHI", ace.ace_type, ace.flags, 8 + len(sid_to_bytes(ace.sid)), ace.mask)
        + sid_to_bytes(ace.sid)
        for ace in aces
    )
    return struct.pack("<BBHHH", 2, 0, 8 + len(body), len(aces), 0) + body


def parse_acl(data: object) -> tuple[Ace, ...]:
    """Parse a bare ACL (for example a token's default DACL)."""
    if type(data) is not bytes or len(data) > _MAX_DESCRIPTOR_BYTES:
        raise DescriptorError("an ACL must be bytes of bounded length.")
    return _parse_acl(data, 0, len(data))


def build_security_descriptor(
    owner: str,
    dacl: tuple[Ace, ...] | list[Ace],
    *,
    protected: bool,
    group: str | None = None,
    auto_inherited: bool = False,
) -> bytes:
    """Build a self-relative descriptor with an owner, an optional group and a DACL."""
    control = SE_SELF_RELATIVE | SE_DACL_PRESENT
    if protected:
        control |= SE_DACL_PROTECTED
    if auto_inherited:
        control |= SE_DACL_AUTO_INHERITED
    owner_bytes = sid_to_bytes(owner)
    group_bytes = sid_to_bytes(group) if group is not None else b""
    acl = build_acl(tuple(dacl))
    owner_at = 20
    group_at = owner_at + len(owner_bytes) if group_bytes else 0
    dacl_at = owner_at + len(owner_bytes) + len(group_bytes)
    return (
        struct.pack("<BBHIIII", 1, 0, control, owner_at, group_at, 0, dacl_at)
        + owner_bytes
        + group_bytes
        + acl
    )


def serialize(descriptor: SecurityDescriptor) -> bytes:
    """Self-relative bytes for an already-parsed descriptor."""
    return build_security_descriptor(
        descriptor.owner,
        descriptor.dacl,
        protected=descriptor.protected,
        group=descriptor.group,
        auto_inherited=bool(descriptor.control & SE_DACL_AUTO_INHERITED),
    )


# -- principals and the upper-bound evaluation ---------------------------------


@dataclass(frozen=True)
class Principal:
    """Everything one account could present to an access check.

    ``allow_sids`` — SIDs that may be in *some* token of this account.
    ``deny_sids`` — SIDs that are in *every* token of this account.
    Logon SIDs other than ``excluded_logon_sid`` are treated as possibly held.
    """

    role: str
    sid: str
    allow_sids: frozenset[str]
    deny_sids: frozenset[str]
    excluded_logon_sid: str | None = None

    def __post_init__(self) -> None:
        canonical_sid(self.sid)
        for sid in self.allow_sids | self.deny_sids:
            canonical_sid(sid)
        if self.sid not in self.deny_sids or not self.deny_sids <= self.allow_sids:
            raise DescriptorError("a principal's certain SIDs must be a subset of its possible SIDs.")

    def may_hold(self, sid: str) -> bool:
        if is_app_package_sid(sid) or sid in (CREATOR_OWNER, CREATOR_GROUP):
            return False
        if is_logon_sid(sid):
            return sid != self.excluded_logon_sid
        return sid in self.allow_sids

    def certainly_holds(self, sid: str) -> bool:
        return sid in self.deny_sids


def upper_bound_rights(descriptor: SecurityDescriptor, principal: Principal, kind: ObjectKind) -> int:
    """The most ``principal`` could be granted on an object with ``descriptor``.

    Implements the Windows maximum-allowed DACL walk (in ACE order, a deny
    removes only bits not yet granted, an allow adds only bits not yet denied),
    owner-implicit rights and ``OWNER RIGHTS``, with the asymmetric matching
    described in the module docstring. Privileges are not considered.
    """
    owner_possible = principal.may_hold(descriptor.owner)
    owner_certain = principal.certainly_holds(descriptor.owner)
    effective = descriptor.effective_aces
    granted = 0
    denied = 0
    if owner_possible and not any(ace.sid == OWNER_RIGHTS for ace in effective):
        granted |= READ_CONTROL | WRITE_DAC
    for ace in effective:
        mask = map_generic(ace.mask, kind)
        if ace.sid == OWNER_RIGHTS:
            allow_match, deny_match = owner_possible, owner_certain
        elif ace.sid == PRINCIPAL_SELF:
            # Only meaningful for directory-service objects; never "certain".
            allow_match, deny_match = True, False
        else:
            allow_match = principal.may_hold(ace.sid)
            deny_match = principal.certainly_holds(ace.sid)
        if ace.allows and allow_match:
            granted |= mask & ~denied
        elif not ace.allows and deny_match:
            denied |= mask & ~granted
    return granted


def upper_bound_transform(descriptor: SecurityDescriptor, principal: Principal, kind: ObjectKind) -> SecurityDescriptor:
    """A descriptor on which a *symmetric* evaluator computes the same upper bound.

    An evaluator such as AuthZ matches allow and deny ACEs against one SID set.
    Removing every deny ACE that ``principal`` does not *certainly* match, and
    mapping generic bits, lets such an evaluator, given ``allow_sids``, compute
    an independent upper bound comparable to :func:`upper_bound_rights`.
    """
    kept = []
    for ace in descriptor.dacl:
        if ace.inherit_only:
            continue
        if not ace.allows:
            sid_certain = (
                principal.certainly_holds(descriptor.owner)
                if ace.sid == OWNER_RIGHTS
                else principal.certainly_holds(ace.sid)
            )
            if not sid_certain:
                continue
        kept.append(Ace(ace.ace_type, ace.flags & INHERITED_ACE, map_generic(ace.mask, kind), ace.sid))
    return SecurityDescriptor(
        owner=descriptor.owner,
        dacl=tuple(kept),
        control=descriptor.control & (SE_SELF_RELATIVE | SE_DACL_PRESENT | SE_DACL_PROTECTED),
        group=descriptor.group,
    )


# -- inheritance -----------------------------------------------------------------


def inherited_descriptor(
    parent: SecurityDescriptor,
    child_kind: ObjectKind,
    *,
    creator: str,
    creator_group: str | None,
    fallback_dacl: tuple[Ace, ...] | None,
) -> SecurityDescriptor | None:
    """The descriptor a new child would get if ``creator`` made it with no
    explicit DACL. ``None`` if it cannot be stated (no inheritable ACE and no
    known creator default DACL).

    Follows the NTFS rules: ``OBJECT_INHERIT`` reaches files, and directories
    as inherit-only; ``CONTAINER_INHERIT`` reaches directories;
    ``NO_PROPAGATE`` stops after one level; ``CREATOR OWNER`` and
    ``CREATOR GROUP`` are replaced by the creator in the effective copy, and
    kept, inherit-only, in a copy that keeps propagating.
    """
    if child_kind not in (ObjectKind.FILE, ObjectKind.DIRECTORY):
        raise DescriptorError("inheritance is modelled for files and directories only.")
    inherited: list[Ace] = []
    for ace in parent.dacl:
        oi = bool(ace.flags & OBJECT_INHERIT_ACE)
        ci = bool(ace.flags & CONTAINER_INHERIT_ACE)
        np_ = bool(ace.flags & NO_PROPAGATE_INHERIT_ACE)
        if child_kind is ObjectKind.FILE:
            if oi:
                inherited.extend(_materialize(ace, INHERITED_ACE, creator, creator_group, False))
            continue
        if ci:
            onward = 0 if np_ else (ace.flags & (OBJECT_INHERIT_ACE | CONTAINER_INHERIT_ACE))
            inherited.extend(
                _materialize(ace, INHERITED_ACE | onward, creator, creator_group, bool(onward))
            )
        elif oi and not np_:
            inherited.append(
                Ace(ace.ace_type, INHERITED_ACE | INHERIT_ONLY_ACE | OBJECT_INHERIT_ACE, ace.mask, ace.sid)
            )
    if not inherited:
        if fallback_dacl is None:
            return None
        inherited = list(fallback_dacl)
    return SecurityDescriptor(
        owner=creator,
        dacl=tuple(inherited),
        control=SE_SELF_RELATIVE | SE_DACL_PRESENT | SE_DACL_AUTO_INHERITED,
        group=creator_group,
    )


def _materialize(
    ace: Ace, flags: int, creator: str, creator_group: str | None, propagates: bool
) -> list[Ace]:
    if ace.sid not in (CREATOR_OWNER, CREATOR_GROUP):
        return [Ace(ace.ace_type, flags, ace.mask, ace.sid)]
    substitute = creator if ace.sid == CREATOR_OWNER else creator_group
    copies = []
    if substitute is not None:
        copies.append(Ace(ace.ace_type, INHERITED_ACE, ace.mask, substitute))
    if propagates:
        copies.append(Ace(ace.ace_type, flags | INHERIT_ONLY_ACE, ace.mask, ace.sid))
    return copies
