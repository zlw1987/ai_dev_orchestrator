"""DL-4B S0 — the Windows identity boundary (offline).

Every proof here runs over a **synthetic** world: synthetic SIDs for the
authority (A), execution (X) and operator (O) identities, and synthetic
self-relative security descriptors for every object, built in memory. No test
creates or modifies an account, an ACL, a scheduled task or a system
directory; none needs elevation; none runs a subprocess, opens a socket or
calls a model.

On Windows some tests also use the real, read-only Win32 fact reader: on
``tmp_path`` objects, on this process's own token, and through AuthZ over the
in-memory synthetic descriptors (``AuthzAccessCheck`` takes a descriptor, not a
file, so nothing is ever applied to an object).

Sections: descriptor parsing; the upper-bound evaluator; inheritance;
differential checks against AuthZ; the boundary document; the complete proof
over a correctly provisioned world; refusals by category; discovered bypasses
(regressions from the adversarial analysis); facts-source misbehaviour and
caller bypass attempts; the production entry point; static boundaries.
"""

from __future__ import annotations

import ast
import copy
import inspect
import json
import ntpath
import os
import pickle
import random
import sys
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

import ai_dev_orchestrator.integration as integration
from ai_dev_orchestrator.integration import identity_boundary as ib
from ai_dev_orchestrator.integration.boundary_facts import (
    CodeLoadFacts,
    DirectoryEntry,
    ObjectFacts,
    PrincipalFacts,
    ProcessFacts,
    SessionFacts,
    TokenFacts,
)
from ai_dev_orchestrator.integration.identity_boundary import (
    IdentityBoundaryError,
    IdentityBoundaryProof,
    IsolationCategory as C,
    parse_identity_boundary,
    prove_identity_boundary,
    prove_identity_boundary_from_facts,
    validate_local_path,
)
from ai_dev_orchestrator.integration.security_descriptor import (
    ADMINISTRATORS,
    CONTAINER_INHERIT_ACE as CI,
    CREATOR_OWNER,
    DELETE,
    EVERYONE,
    FILE_ADD_FILE,
    FILE_ADD_SUBDIRECTORY,
    FILE_ALL_ACCESS,
    FILE_DELETE_CHILD,
    FILE_GENERIC_READ,
    FILE_GENERIC_WRITE,
    FILE_WRITE_ATTRIBUTES,
    FILE_WRITE_DATA,
    FILE_WRITE_EA,
    GENERIC_ALL,
    GENERIC_WRITE,
    INHERIT_ONLY_ACE as IO,
    INHERITED_ACE as INH,
    KERNEL_OBJECT_ALL_ACCESS,
    LOCAL_SYSTEM,
    NO_PROPAGATE_INHERIT_ACE as NP,
    OBJECT_INHERIT_ACE as OI,
    OWNER_RIGHTS,
    PRINCIPAL_SELF,
    READ_CONTROL,
    READ_ONLY,
    TRUSTED_INSTALLER,
    WRITE_DAC,
    WRITE_OWNER,
    Ace,
    DescriptorError,
    ObjectKind,
    Principal,
    SecurityDescriptor,
    build_acl,
    build_security_descriptor,
    canonical_sid,
    inherited_descriptor,
    parse_acl,
    parse_security_descriptor,
    serialize,
    sid_from_bytes,
    sid_to_bytes,
    upper_bound_rights,
    upper_bound_transform,
)

WINDOWS = sys.platform == "win32"
windows_only = pytest.mark.skipif(not WINDOWS, reason="reads real Windows security facts")

# -- synthetic identities -----------------------------------------------------------

DOMAIN = "S-1-5-21-100-200-300"
A = f"{DOMAIN}-1001"
X = f"{DOMAIN}-1002"
O = f"{DOMAIN}-1003"
NONE_GROUP = f"{DOMAIN}-513"
A_LOGON = "S-1-5-5-0-4242"
X_LOGON = "S-1-5-5-0-7777"
A_LUID = 0x4242  # A's logon session; its service window station is Service-0x0-4242$
A_STATION = "Service-0x0-4242$"
USERS = "S-1-5-32-545"
AUTH = "S-1-5-11"
INTERACTIVE = "S-1-5-4"
NETWORK = "S-1-5-2"
CONSOLE = "S-1-2-1"
LOCAL = "S-1-2-0"
THIS_ORG = "S-1-5-15"
LOCAL_ACCOUNT = "S-1-5-113"
MEDIUM = "S-1-16-8192"
BACKUP_OPERATORS = "S-1-5-32-551"

OICI = OI | CI
MODIFY = 0x0013_01BF
RX = READ_ONLY
STANDARD_PRIVILEGES = (
    "SeShutdownPrivilege", "SeChangeNotifyPrivilege", "SeUndockPrivilege",
    "SeIncreaseWorkingSetPrivilege", "SeTimeZonePrivilege",
)
PROCESS_QUERY_LIMITED = 0x1000
SYNCH = 0x0010_0000
FIXED_NOW = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)


def allow(sid: str, mask: int, flags: int = 0) -> Ace:
    return Ace(0, flags, mask, sid)


def deny(sid: str, mask: int, flags: int = 0) -> Ace:
    return Ace(1, flags, mask, sid)


#: Shaped like this host's own WinSta0 and Default: admin-owned, granting the
#: logon session, SYSTEM and Administrators.
STATION_SD = build_security_descriptor(ADMINISTRATORS, [
    allow(A_LOGON, 0xF037F), allow(LOCAL_SYSTEM, 0xF037F), allow(ADMINISTRATORS, 0x20166),
], protected=False)
DESKTOP_SD = build_security_descriptor(ADMINISTRATORS, [
    allow(A_LOGON, 0xF01FF), allow(LOCAL_SYSTEM, 0xF01FF), allow(ADMINISTRATORS, 0x201C7),
], protected=False)


def session(station: str, visible: bool, station_sid: str | None, desktop: str, desktop_sid: str | None,
            *, station_sd: bytes = STATION_SD, desktop_sd: bytes = DESKTOP_SD) -> SessionFacts:
    return SessionFacts(station, visible, station_sid, desktop, desktop_sid, station_sd, desktop_sd)


def inherited(aces: list[Ace], *, child_dir: bool) -> list[Ace]:
    """What simple OI/CI parent ACEs become on a child (test-local, no CREATOR OWNER)."""
    out = []
    for ace in aces:
        if child_dir and ace.flags & CI:
            out.append(Ace(ace.ace_type, INH | (ace.flags & OICI), ace.mask, ace.sid))
        elif not child_dir and ace.flags & OI:
            out.append(Ace(ace.ace_type, INH, ace.mask, ace.sid))
    return out


# -- the synthetic world ------------------------------------------------------------


@dataclass
class Node:
    is_dir: bool
    owner: str
    aces: list[Ace]
    protected: bool
    reparse: bool = False
    links: int = 1
    final: str | None = None
    raw: bytes | None = None  # overrides the built descriptor
    target: str | None = None  # a junction's target, followed in intermediate components

    def descriptor(self) -> bytes:
        if self.raw is not None:
            return self.raw
        return build_security_descriptor(self.owner, self.aces, protected=self.protected)


@dataclass
class World:
    """A correctly provisioned host, as facts. Every test mutates one fact."""

    nodes: dict[str, Node] = field(default_factory=dict)
    names: dict[str, str] = field(default_factory=dict)
    children: dict[str, dict[str, str]] = field(default_factory=dict)
    windows: bool = True
    env: list[str] = field(default_factory=lambda: ["PATH", "TEMP", "TMP", "SystemRoot", "=C:"])
    token: TokenFacts | None = None
    principals: dict[str, PrincipalFacts] = field(default_factory=dict)
    session_facts: SessionFacts | None = None
    process_facts: ProcessFacts | None = None
    code: CodeLoadFacts | None = None
    boundary: dict | None = None
    boundary_raw: bytes | None = None
    independent: object = None
    calls: list[str] = field(default_factory=list)

    # -- building ----------------------------------------------------------

    def put(self, path: str, *, is_dir: bool, owner: str, aces: list[Ace], protected: bool = False,
            **extra) -> Node:
        node = Node(is_dir, owner, list(aces), protected, **extra)
        key = ntpath.normcase(path)
        self.nodes[key] = node
        self.names[key] = path
        parent = ntpath.dirname(path)
        if parent != path:
            self.children.setdefault(ntpath.normcase(parent), {})[ntpath.basename(path).casefold()] = (
                ntpath.basename(path)
            )
        return node

    def put_child(self, parent: str, name: str, *, is_dir: bool, owner: str | None = None) -> Node:
        p = self.node(parent)
        return self.put(ntpath.join(parent, name), is_dir=is_dir, owner=owner or p.owner,
                        aces=inherited(p.aces, child_dir=is_dir))

    def node(self, path: str) -> Node:
        return self.nodes[ntpath.normcase(path)]

    def remove(self, path: str) -> None:
        key = ntpath.normcase(path)
        del self.nodes[key]
        self.children[ntpath.normcase(ntpath.dirname(path))].pop(ntpath.basename(path).casefold())

    def boundary_bytes(self) -> bytes:
        if self.boundary_raw is not None:
            return self.boundary_raw
        return json.dumps(self.boundary).encode("utf-8")

    # -- SecurityFacts ----------------------------------------------------

    def is_windows(self):
        return self.windows

    def environment_names(self):
        return tuple(self.env)

    def current_token(self):
        return self.token

    def program_data_directory(self):
        return "C:\\ProgramData"

    def _resolve(self, path: str) -> str:
        """Follow junctions in intermediate components, as Win32 path parsing
        does even with FILE_FLAG_OPEN_REPARSE_POINT; never the last one."""
        parts = path[3:].split("\\")
        current = path[:3]
        for index, part in enumerate(parts):
            current = ntpath.join(current, part)
            node = self.nodes.get(ntpath.normcase(current))
            if node is not None and node.target and index < len(parts) - 1:
                current = node.target
        return current

    def _facts(self, path: str) -> ObjectFacts | None:
        self.calls.append(path)
        resolved = self._resolve(path) if len(path) > 3 else path
        node = self.nodes.get(ntpath.normcase(resolved))
        if node is None:
            return None
        final = node.final if node.final is not None else self.names[ntpath.normcase(resolved)]
        return ObjectFacts(final, node.is_dir, node.reparse, node.links, node.descriptor())

    def read_file(self, path, limit):
        facts = self._facts(path)
        return None if facts is None else (facts, self.boundary_bytes())

    def object_facts(self, path):
        return self._facts(path)

    def list_directory(self, path):
        entries = self.children.get(ntpath.normcase(path), {})
        return tuple(
            DirectoryEntry(name, node.is_dir, node.reparse)
            for name in entries.values()
            for node in (self.nodes[ntpath.normcase(ntpath.join(path, name))],)
        )

    def principal(self, sid):
        return self.principals[sid]

    def session(self):
        return self.session_facts

    def process(self):
        return self.process_facts

    def code_load(self):
        return self.code

    def independent_rights(self, descriptor, principal, kind):
        if callable(self.independent):
            return self.independent(descriptor, principal, kind)
        return None


STATE = "C:\\AIDO\\state"
PUBLISHED = "C:\\AIDO\\published"
INBOX = "C:\\AIDO\\inbox"
EXCHANGE = "C:\\AIDO\\exchange"
CLONES = "C:\\AIDO\\clones"
CLONE = "C:\\AIDO\\clones\\repo"
GIT = CLONE + "\\.git"
INSTALL = "C:\\AIDO\\install"
PROFILE = "C:\\Users\\aido-a"
WINDOWSAPPS = PROFILE + "\\AppData\\Local\\Microsoft\\WindowsApps"
SYSTEM32 = "C:\\Windows\\System32"
ANCHOR_DIR = "C:\\ProgramData\\AIDO"
ANCHOR = ANCHOR_DIR + "\\identity-boundary.v1.json"
ADMIN_FULL = [allow(LOCAL_SYSTEM, FILE_ALL_ACCESS, OICI), allow(ADMINISTRATORS, FILE_ALL_ACCESS, OICI)]


def good_world() -> World:
    w = World()
    w.put("C:\\", is_dir=True, owner=TRUSTED_INSTALLER, protected=True, aces=[
        *ADMIN_FULL, allow(USERS, RX, OICI),
        allow(AUTH, FILE_ADD_SUBDIRECTORY),
        allow(AUTH, MODIFY, IO | OICI),
    ])
    w.put("C:\\ProgramData", is_dir=True, owner=LOCAL_SYSTEM, protected=True, aces=[
        *ADMIN_FULL, allow(CREATOR_OWNER, FILE_ALL_ACCESS, IO | OICI), allow(USERS, RX, OICI),
        allow(USERS, FILE_ADD_FILE | FILE_ADD_SUBDIRECTORY | FILE_WRITE_EA | FILE_WRITE_ATTRIBUTES, CI),
    ])
    w.put(ANCHOR_DIR, is_dir=True, owner=ADMINISTRATORS, protected=True,
          aces=[*ADMIN_FULL, allow(USERS, RX, OICI)])
    w.put_child(ANCHOR_DIR, "identity-boundary.v1.json", is_dir=False)
    w.put("C:\\AIDO", is_dir=True, owner=ADMINISTRATORS, protected=True,
          aces=[*ADMIN_FULL, allow(USERS, RX)])

    w.put(STATE, is_dir=True, owner=A, protected=True, aces=[allow(A, FILE_ALL_ACCESS, OICI), *ADMIN_FULL])
    w.put_child(STATE, "aido-state-root.json", is_dir=False)
    w.put_child(STATE, "evidence", is_dir=True)
    w.put_child(STATE + "\\evidence", "verification", is_dir=True)
    w.put_child(STATE + "\\evidence\\verification", "abc.json", is_dir=False)

    w.put(PUBLISHED, is_dir=True, owner=A, protected=True,
          aces=[allow(A, FILE_ALL_ACCESS, OICI), *ADMIN_FULL, allow(O, RX, OICI)])
    w.put_child(PUBLISHED, "bundle.json", is_dir=False)

    w.put(INBOX, is_dir=True, owner=A, protected=True, aces=[
        allow(A, FILE_ALL_ACCESS, OICI), *ADMIN_FULL, allow(O, RX | FILE_ADD_FILE),
        allow(CREATOR_OWNER, FILE_ALL_ACCESS, IO | OI),
    ])
    w.put(INBOX + "\\approval.sshsig", is_dir=False, owner=O, aces=[
        allow(A, FILE_ALL_ACCESS, INH), allow(LOCAL_SYSTEM, FILE_ALL_ACCESS, INH),
        allow(ADMINISTRATORS, FILE_ALL_ACCESS, INH), allow(O, FILE_ALL_ACCESS, INH),
    ])

    w.put(EXCHANGE, is_dir=True, owner=A, protected=True,
          aces=[allow(A, FILE_ALL_ACCESS, OICI), *ADMIN_FULL, allow(X, RX), allow(O, RX)])

    w.put(CLONES, is_dir=True, owner=ADMINISTRATORS, protected=True,
          aces=[*ADMIN_FULL, allow(X, RX), allow(O, RX), allow(A, RX)])
    w.put(CLONE, is_dir=True, owner=X, protected=True, aces=[
        allow(OWNER_RIGHTS, READ_CONTROL, OICI),
        allow(X, RX | FILE_ADD_FILE | FILE_ADD_SUBDIRECTORY | FILE_WRITE_EA | FILE_WRITE_ATTRIBUTES),
        allow(X, MODIFY, IO | OICI),
        allow(A, RX, OICI), allow(O, RX, OICI), *ADMIN_FULL,
    ])
    w.put_child(CLONE, "README.md", is_dir=False)
    w.put(GIT, is_dir=True, owner=X, protected=True, aces=[
        allow(OWNER_RIGHTS, READ_CONTROL, OICI), allow(X, RX, OICI),
        allow(A, RX, OICI), allow(O, RX, OICI), *ADMIN_FULL,
    ])
    for name, is_dir in (("HEAD", False), ("config", False), ("index", False), ("refs", True)):
        w.put_child(GIT, name, is_dir=is_dir)
    w.put_child(GIT + "\\refs", "heads", is_dir=True)
    w.put_child(GIT + "\\refs\\heads", "main", is_dir=False)

    w.put(INSTALL, is_dir=True, owner=ADMINISTRATORS, protected=True,
          aces=[*ADMIN_FULL, allow(USERS, RX, OICI)])
    for parent, name, is_dir in (
        (INSTALL, "python", True), (INSTALL + "\\python", "python.exe", False),
        (INSTALL + "\\python", "python314.dll", False), (INSTALL + "\\python", "Lib", True),
        (INSTALL + "\\python\\Lib", "os.py", False), (INSTALL + "\\python", "DLLs", True),
        (INSTALL, "venv", True), (INSTALL + "\\venv", "Scripts", True),
        (INSTALL + "\\venv\\Scripts", "python.exe", False), (INSTALL + "\\venv", "Lib", True),
        (INSTALL + "\\venv\\Lib", "site-packages", True),
        (INSTALL + "\\venv\\Lib\\site-packages", "ai_dev_orchestrator", True),
        (INSTALL + "\\venv\\Lib\\site-packages\\ai_dev_orchestrator", "__init__.py", False),
    ):
        w.put_child(parent, name, is_dir=is_dir)

    w.put("C:\\Windows", is_dir=True, owner=TRUSTED_INSTALLER, protected=True,
          aces=[allow(TRUSTED_INSTALLER, FILE_ALL_ACCESS, OICI), *ADMIN_FULL, allow(USERS, RX, OICI)])
    w.put_child("C:\\Windows", "System32", is_dir=True)
    w.put_child(SYSTEM32, "kernel32.dll", is_dir=False)
    w.put_child(SYSTEM32, "drivers", is_dir=True)

    w.put("C:\\Users", is_dir=True, owner=LOCAL_SYSTEM, protected=True,
          aces=[*ADMIN_FULL, allow(USERS, RX, OICI), allow(EVERYONE, RX)])
    w.put(PROFILE, is_dir=True, owner=A, protected=True, aces=[allow(A, FILE_ALL_ACCESS, OICI), *ADMIN_FULL])
    for parent, name in ((PROFILE, "AppData"), (PROFILE + "\\AppData", "Local"),
                         (PROFILE + "\\AppData", "Roaming"), (PROFILE + "\\AppData\\Local", "Temp"),
                         (PROFILE + "\\AppData\\Local", "Microsoft"),
                         (PROFILE + "\\AppData\\Local\\Microsoft", "WindowsApps")):
        w.put_child(parent, name, is_dir=True)
    alias = w.put_child(WINDOWSAPPS, "winget.exe", is_dir=False)
    alias.reparse = True

    w.boundary = {
        "schema_version": "identity-boundary.v1",
        "authority": {"sid": A, "account": "HOST\\aido-a"},
        "execution": {"sid": X, "account": "HOST\\aido-x"},
        "operator": {"sid": O, "account": "HOST\\human"},
        "launch_mechanism": "interactive_session",
        "paths": {
            "state_root": STATE, "published": PUBLISHED, "inbox": INBOX,
            "exchange_root": EXCHANGE, "clone": CLONE, "install_roots": [INSTALL],
        },
    }
    w.token = TokenFacts(
        user_sid=A,
        groups=(
            (NONE_GROUP, 7), (EVERYONE, 7), (USERS, 7), (INTERACTIVE, 7), (CONSOLE, 7), (AUTH, 7),
            (THIS_ORG, 7), (A_LOGON, 0xC000_0007), (LOCAL, 7), (LOCAL_ACCOUNT, 7), (MEDIUM, 0x60),
        ),
        privileges=STANDARD_PRIVILEGES,
        elevated=False,
        elevation_type=1,
        integrity_rid=0x2000,
        default_dacl=build_acl([allow(A, GENERIC_ALL), allow(LOCAL_SYSTEM, GENERIC_ALL),
                                allow(A_LOGON, 0xA000_0000)]),
        authentication_id=A_LUID,
    )
    base_groups = ((NONE_GROUP, 7), (EVERYONE, 7), (USERS, 7), (AUTH, 7), (THIS_ORG, 7), (MEDIUM, 0x60))
    for sid, name in ((A, "HOST\\aido-a"), (X, "HOST\\aido-x"), (O, "HOST\\human")):
        w.principals[sid] = PrincipalFacts(
            sid=sid, account_name=name, sid_type=1, is_local_account=True,
            groups=base_groups, privileges=STANDARD_PRIVILEGES,
        )
    w.session_facts = session("WinSta0", True, A_LOGON, "Default", A_LOGON)
    kernel = [allow(A, KERNEL_OBJECT_ALL_ACCESS), allow(LOCAL_SYSTEM, KERNEL_OBJECT_ALL_ACCESS),
              allow(A_LOGON, PROCESS_QUERY_LIMITED | SYNCH)]
    process_sd = build_security_descriptor(A, kernel, protected=False)
    w.process_facts = ProcessFacts(process_sd, process_sd, build_security_descriptor(
        A, [allow(A, KERNEL_OBJECT_ALL_ACCESS), allow(LOCAL_SYSTEM, KERNEL_OBJECT_ALL_ACCESS)],
        protected=False))
    w.code = CodeLoadFacts(
        executables=(INSTALL + "\\venv\\Scripts\\python.exe", INSTALL + "\\python\\python.exe"),
        prefixes=(INSTALL + "\\venv", INSTALL + "\\venv", INSTALL + "\\python", INSTALL + "\\python"),
        import_paths=(INSTALL + "\\python\\python314.zip", INSTALL + "\\python\\DLLs",
                      INSTALL + "\\python\\Lib", INSTALL + "\\python", INSTALL + "\\venv",
                      INSTALL + "\\venv\\Lib\\site-packages"),
        search_paths=(SYSTEM32, ""),
        working_directory=INSTALL,
        package_directory=INSTALL + "\\venv\\Lib\\site-packages\\ai_dev_orchestrator",
        profile_directories=(PROFILE, PROFILE + "\\AppData\\Local\\Temp", PROFILE + "\\AppData\\Local\\Temp",
                             PROFILE + "\\AppData\\Roaming", PROFILE + "\\AppData\\Local"),
        isolated_interpreter=True,
    )
    return w


def prove(w: World, **kwargs) -> IdentityBoundaryProof:
    return prove_identity_boundary_from_facts(w, clock=lambda: FIXED_NOW, **kwargs)


def refused(w: World, category: C, match: str | None = None, **kwargs) -> IdentityBoundaryError:
    with pytest.raises(IdentityBoundaryError) as info:
        prove(w, **kwargs)
    assert info.value.category is category, str(info.value)
    assert str(info.value).startswith(f"isolation_unproven:{category.value}:")
    if match is not None:
        assert match in str(info.value), str(info.value)
    return info.value


@pytest.fixture
def world() -> World:
    return good_world()


# =============================================================================
# 1. descriptor parsing
# =============================================================================


def test_sid_round_trip_and_canonical_form() -> None:
    for sid in (A, EVERYONE, OWNER_RIGHTS, TRUSTED_INSTALLER, "S-1-12-1-1-2-3-4", A_LOGON):
        raw = sid_to_bytes(sid)
        assert sid_from_bytes(raw, 0, len(raw)) == (sid, len(raw))
    for bad in ("S-1-5-21-01-2", "S-1-5", "s-1-5-21", "S-2-5-21", "S-1-5-x", "S-1-5-4294967296",
                "S-1-" + "-".join(["1"] * 17), "S-1-5-\u0661", 7, None):
        with pytest.raises(DescriptorError):
            canonical_sid(bad)


def test_binary_sid_rejects_bad_revision_count_and_truncation() -> None:
    raw = sid_to_bytes(A)
    with pytest.raises(DescriptorError):
        sid_from_bytes(b"\x02" + raw[1:], 0, len(raw))
    with pytest.raises(DescriptorError):
        sid_from_bytes(raw[:1] + b"\x00" + raw[2:], 0, len(raw))
    with pytest.raises(DescriptorError):
        sid_from_bytes(raw[:1] + b"\x10" + raw[2:], 0, len(raw))
    with pytest.raises(DescriptorError):
        sid_from_bytes(raw, 0, len(raw) - 1)


def test_descriptor_round_trip() -> None:
    aces = [allow(A, FILE_ALL_ACCESS, OICI), deny(X, FILE_GENERIC_WRITE), allow(USERS, RX, IO | OI)]
    raw = build_security_descriptor(A, aces, protected=True, group=NONE_GROUP)
    sd = parse_security_descriptor(raw)
    assert sd.owner == A and sd.group == NONE_GROUP and sd.protected and sd.dacl == tuple(aces)
    assert serialize(sd) == raw
    assert parse_acl(build_acl(aces)) == tuple(aces)


def _patch(raw: bytes, offset: int, value: bytes) -> bytes:
    return raw[:offset] + value + raw[offset + len(value):]


@pytest.mark.parametrize("mutate, reason", [
    (lambda r: r[:19], "length"),
    (lambda r: _patch(r, 0, b"\x02"), "revision"),
    (lambda r: _patch(r, 2, (0x0004).to_bytes(2, "little")), "self-relative"),
    (lambda r: _patch(r, 2, (0x8000).to_bytes(2, "little")), "no DACL"),
    (lambda r: _patch(r, 16, b"\x00\x00\x00\x00"), "no DACL"),
    (lambda r: _patch(r, 4, b"\x00\x00\x00\x00"), "no owner"),
    (lambda r: _patch(r, 4, (999).to_bytes(4, "little")), "offset"),
    (lambda r: _patch(r, 2, (0x8044).to_bytes(2, "little")), "unknown control"),
    (lambda r: r + b"\x00" * 70_000, "length"),
])
def test_malformed_descriptors_are_refused(mutate, reason) -> None:
    raw = build_security_descriptor(A, [allow(A, FILE_ALL_ACCESS)], protected=True)
    with pytest.raises(DescriptorError):
        parse_security_descriptor(mutate(raw))


def test_null_dacl_is_refused_not_read_as_empty() -> None:
    raw = build_security_descriptor(A, [], protected=True)
    assert parse_security_descriptor(raw).dacl == ()  # an empty DACL is fine: it grants nothing
    null = _patch(raw, 16, b"\x00\x00\x00\x00")
    with pytest.raises(DescriptorError, match="no DACL"):
        parse_security_descriptor(null)


@pytest.mark.parametrize("ace_type", [0x02, 0x05, 0x06, 0x09, 0x0A, 0x11, 0x12, 0x13])
def test_unsupported_ace_types_are_refused(ace_type) -> None:
    raw = bytearray(build_security_descriptor(A, [allow(X, RX)], protected=True))
    dacl_at = int.from_bytes(raw[16:20], "little")
    raw[dacl_at + 8] = ace_type
    with pytest.raises(DescriptorError, match="not supported"):
        parse_security_descriptor(bytes(raw))


def test_unknown_ace_flags_and_trailing_ace_bytes_are_refused() -> None:
    raw = bytearray(build_security_descriptor(A, [allow(X, RX)], protected=True))
    dacl_at = int.from_bytes(raw[16:20], "little")
    flagged = bytearray(raw)
    flagged[dacl_at + 9] = 0x40  # SUCCESSFUL_ACCESS: an audit flag in a DACL
    with pytest.raises(DescriptorError):
        parse_security_descriptor(bytes(flagged))
    padded = bytearray(raw)
    padded[dacl_at + 10:dacl_at + 12] = (8 + len(sid_to_bytes(X)) + 4).to_bytes(2, "little")
    with pytest.raises(DescriptorError):
        parse_security_descriptor(bytes(padded) + b"\x00" * 4)


def test_parse_requires_exact_bytes() -> None:
    raw = build_security_descriptor(A, [allow(A, FILE_ALL_ACCESS)], protected=True)
    for wrong in (bytearray(raw), memoryview(raw), raw.decode("latin-1")):
        with pytest.raises(DescriptorError):
            parse_security_descriptor(wrong)


# =============================================================================
# 2. the upper-bound evaluator
# =============================================================================


def principal_x(*, extra_certain=(), extra_possible=(), excluded=A_LOGON) -> Principal:
    certain = frozenset({X, EVERYONE, USERS, AUTH, *extra_certain})
    return Principal("execution", X, certain | {INTERACTIVE, NETWORK, *extra_possible}, certain, excluded)


def rights(aces, owner=A, kind=ObjectKind.FILE, principal=None) -> int:
    sd = SecurityDescriptor(owner, tuple(aces), 0x9004)
    return upper_bound_rights(sd, principal or principal_x(), kind)


def test_owner_gets_read_control_and_write_dac_implicitly_and_deny_cannot_remove_it() -> None:
    assert rights([], owner=X) == READ_CONTROL | WRITE_DAC
    assert rights([deny(X, WRITE_DAC)], owner=X) & WRITE_DAC


def test_owner_rights_ace_replaces_the_implicit_owner_grant() -> None:
    assert rights([allow(OWNER_RIGHTS, READ_CONTROL)], owner=X) == READ_CONTROL
    assert rights([allow(OWNER_RIGHTS, READ_CONTROL)], owner=A) == 0
    # An inherit-only OWNER RIGHTS ACE does not apply to the object itself.
    assert rights([allow(OWNER_RIGHTS, READ_CONTROL, IO | OICI)], owner=X) == READ_CONTROL | WRITE_DAC


def test_ace_order_decides_and_inherit_only_aces_are_skipped() -> None:
    assert rights([deny(X, FILE_GENERIC_WRITE), allow(X, FILE_ALL_ACCESS)]) == FILE_ALL_ACCESS & ~FILE_GENERIC_WRITE
    assert rights([allow(X, FILE_ALL_ACCESS), deny(X, FILE_GENERIC_WRITE)]) == FILE_ALL_ACCESS
    assert rights([allow(X, FILE_ALL_ACCESS, IO | OICI)]) == 0


def test_generic_bits_are_mapped_upwards() -> None:
    assert rights([allow(X, GENERIC_ALL)]) == FILE_ALL_ACCESS
    assert rights([allow(X, GENERIC_WRITE)]) & FILE_WRITE_DATA
    assert rights([allow(X, 0x0200_0000)]) == FILE_ALL_ACCESS  # MAXIMUM_ALLOWED inside an ACE


def test_a_deny_for_a_logon_dependent_sid_does_not_bind_every_token() -> None:
    """Deny INTERACTIVE does not stop X's network or batch token (B-6)."""
    assert rights([deny(INTERACTIVE, FILE_ALL_ACCESS), allow(USERS, FILE_ALL_ACCESS)]) == FILE_ALL_ACCESS
    assert rights([deny(X, FILE_ALL_ACCESS), allow(USERS, FILE_ALL_ACCESS)]) == 0


def test_allow_for_a_possible_sid_counts() -> None:
    assert rights([allow(NETWORK, FILE_WRITE_DATA)]) == FILE_WRITE_DATA


def test_foreign_logon_sids_may_match_but_the_excluded_one_does_not() -> None:
    assert rights([allow(X_LOGON, FILE_WRITE_DATA)]) == FILE_WRITE_DATA
    assert rights([allow(A_LOGON, FILE_WRITE_DATA)]) == 0


def test_creator_sids_and_app_package_sids_never_match_effective_aces() -> None:
    assert rights([allow(CREATOR_OWNER, FILE_ALL_ACCESS), allow("S-1-15-2-1", FILE_ALL_ACCESS)]) == 0


def test_principal_self_is_treated_as_matching() -> None:
    assert rights([allow(PRINCIPAL_SELF, FILE_WRITE_DATA)]) == FILE_WRITE_DATA


def test_owner_via_a_group_counts_as_owner() -> None:
    assert rights([], owner=USERS) == READ_CONTROL | WRITE_DAC


def test_principal_requires_certain_subset_of_possible() -> None:
    with pytest.raises(DescriptorError):
        Principal("x", X, frozenset({X}), frozenset({X, USERS}))
    with pytest.raises(DescriptorError):
        Principal("x", X, frozenset({USERS}), frozenset({USERS}))


def test_transform_keeps_only_certain_denies() -> None:
    sd = SecurityDescriptor(A, (deny(INTERACTIVE, FILE_ALL_ACCESS), deny(X, DELETE),
                               allow(USERS, GENERIC_ALL), allow(X, RX, IO | OI)), 0x9004)
    out = upper_bound_transform(sd, principal_x(), ObjectKind.FILE)
    assert out.dacl == (deny(X, DELETE), allow(USERS, FILE_ALL_ACCESS))


# =============================================================================
# 3. inheritance
# =============================================================================


def test_inheritance_reaches_files_and_directories_per_flags() -> None:
    parent = SecurityDescriptor(A, (
        allow(X, FILE_WRITE_DATA, OI), allow(O, FILE_WRITE_DATA, CI), allow(USERS, RX, OICI | NP),
        allow(AUTH, RX),
    ), 0x9004)
    file_ = inherited_descriptor(parent, ObjectKind.FILE, creator=A, creator_group=None, fallback_dacl=None)
    assert {(a.sid, a.inherit_only) for a in file_.dacl} == {(X, False), (USERS, False)}
    folder = inherited_descriptor(parent, ObjectKind.DIRECTORY, creator=A, creator_group=None, fallback_dacl=None)
    by_sid = {a.sid: a for a in folder.dacl}
    assert by_sid[X].inherit_only and by_sid[X].flags & OI          # OI-only: inherit-only on a dir
    assert not by_sid[O].inherit_only and by_sid[O].flags & CI      # CI: effective, propagates
    assert not by_sid[USERS].inherit_only and not by_sid[USERS].flags & OICI  # NP: stops here
    assert AUTH not in by_sid


def test_creator_owner_is_replaced_by_the_creator_and_kept_for_grandchildren() -> None:
    parent = SecurityDescriptor(A, (allow(CREATOR_OWNER, FILE_ALL_ACCESS, IO | OICI),), 0x9004)
    folder = inherited_descriptor(parent, ObjectKind.DIRECTORY, creator=X, creator_group=None, fallback_dacl=None)
    assert allow(X, FILE_ALL_ACCESS, INH) in folder.dacl
    assert any(a.sid == CREATOR_OWNER and a.inherit_only for a in folder.dacl)
    assert folder.owner == X


def test_no_inheritable_ace_falls_back_to_the_creators_default_dacl_or_cannot_be_stated() -> None:
    parent = SecurityDescriptor(A, (allow(A, FILE_ALL_ACCESS),), 0x9004)
    assert inherited_descriptor(parent, ObjectKind.FILE, creator=A, creator_group=None, fallback_dacl=None) is None
    fallback = (allow(A, GENERIC_ALL),)
    child = inherited_descriptor(parent, ObjectKind.FILE, creator=A, creator_group=None, fallback_dacl=fallback)
    assert child.dacl == fallback


# =============================================================================
# 4. differential checks against Windows AuthZ (real API, in-memory descriptors)
# =============================================================================

_SID_POOL = [X, USERS, EVERYONE, INTERACTIVE, NETWORK, OWNER_RIGHTS, CREATOR_OWNER, A_LOGON, X_LOGON,
             ADMINISTRATORS, A, "S-1-5-21-100-200-300-7000"]
_MASK_POOL = [FILE_ALL_ACCESS, RX, FILE_GENERIC_WRITE, DELETE, WRITE_DAC, WRITE_OWNER, FILE_DELETE_CHILD,
              FILE_WRITE_DATA | FILE_WRITE_ATTRIBUTES, READ_CONTROL, GENERIC_ALL, GENERIC_WRITE, MODIFY]


@windows_only
def test_upper_bound_matches_authz_on_random_descriptors() -> None:
    from ai_dev_orchestrator.integration.windows_security import WindowsSecurityFacts

    facts = WindowsSecurityFacts()
    generator = random.Random(4242)
    principal = principal_x(extra_certain=("S-1-5-21-100-200-300-7000",))
    for _ in range(400):
        aces = [
            Ace(generator.choice((0, 1)), generator.choice((0, 0, IO | OICI, OICI)),
                generator.choice(_MASK_POOL), generator.choice(_SID_POOL))
            for _ in range(generator.randint(0, 6))
        ]
        owner = generator.choice((X, A, USERS, ADMINISTRATORS))
        kind = generator.choice((ObjectKind.FILE, ObjectKind.DIRECTORY))
        sd = SecurityDescriptor(owner, tuple(aces), 0x9004)
        ours = upper_bound_rights(sd, principal, kind)
        theirs = facts.independent_rights(serialize(upper_bound_transform(sd, principal, kind)), principal, kind)
        assert ours == theirs, (sd, hex(ours), hex(theirs))


@windows_only
def test_authz_agrees_on_owner_rights_and_owner_implicit_rights() -> None:
    from ai_dev_orchestrator.integration.windows_security import WindowsSecurityFacts

    facts = WindowsSecurityFacts()
    p = principal_x()
    for aces, owner in (
        ([], X),
        ([allow(OWNER_RIGHTS, READ_CONTROL)], X),
        ([deny(X, WRITE_DAC), allow(X, RX)], X),
        ([deny(OWNER_RIGHTS, WRITE_DAC), allow(X, FILE_ALL_ACCESS)], X),
        ([allow(X, FILE_ALL_ACCESS)], A),
    ):
        sd = SecurityDescriptor(owner, tuple(aces), 0x9004)
        assert upper_bound_rights(sd, p, ObjectKind.FILE) == facts.independent_rights(
            serialize(upper_bound_transform(sd, p, ObjectKind.FILE)), p, ObjectKind.FILE)


@windows_only
def test_the_complete_proof_passes_with_real_authz_as_the_independent_evaluator(world) -> None:
    from ai_dev_orchestrator.integration.windows_security import WindowsSecurityFacts

    world.independent = WindowsSecurityFacts().independent_rights
    proof = prove(world)
    assert proof.independent_evaluation is True
    assert proof.is_production is False  # injected facts, whatever evaluated them


@windows_only
def test_real_authz_independently_refuses_an_x_writable_state_root(world) -> None:
    from ai_dev_orchestrator.integration.windows_security import WindowsSecurityFacts

    world.independent = WindowsSecurityFacts().independent_rights
    world.node(STATE).aces.append(allow(X, FILE_WRITE_DATA))
    refused(world, C.OBJECT_RIGHTS, "execution identity could be granted WRITE_DATA")


# =============================================================================
# 5. the boundary document
# =============================================================================


def boundary_bytes(**changes) -> bytes:
    document = good_world().boundary
    for dotted, value in changes.items():
        target = document
        keys = dotted.split("__")
        for key in keys[:-1]:
            target = target[key]
        target[keys[-1]] = value
    return json.dumps(document).encode()


def test_a_valid_boundary_parses() -> None:
    boundary = parse_identity_boundary(boundary_bytes())
    assert boundary.authority.sid == A and boundary.paths.install_roots == (INSTALL,)


@pytest.mark.parametrize("data", [
    b"\xef\xbb\xbf" + boundary_bytes(),
    b"not json",
    b"\xff\xfe",
    b"[]",
    boundary_bytes().replace(b'"launch_mechanism"', b'"launch_mechanism": "x", "launch_mechanism"'),
    boundary_bytes(schema_version="identity-boundary.v2"),
    boundary_bytes(extra=1),
    boundary_bytes(authority__sid="S-1-5-21-01-2-3-1001"),
    boundary_bytes(authority__account="aido-a"),
    boundary_bytes(execution__sid=A),
    boundary_bytes(operator__account="host\\AIDO-A"),
    boundary_bytes(launch_mechanism="runas"),
    boundary_bytes(paths__state_root="AIDO\\state"),
    boundary_bytes(paths__state_root="C:\\AIDO\\..\\state"),
    boundary_bytes(paths__state_root="\\\\server\\share\\state"),
    boundary_bytes(paths__state_root="\\\\?\\C:\\AIDO\\state"),
    boundary_bytes(paths__state_root="C:/AIDO/state"),
    boundary_bytes(paths__state_root="C:\\AIDO\\state:stream"),
    boundary_bytes(paths__state_root="C:\\AIDO\\state."),
    boundary_bytes(paths__state_root="C:\\AIDO\\NUL"),
    boundary_bytes(paths__state_root="C:\\AIDO\\com1.txt"),
    boundary_bytes(paths__state_root="C:\\"),
    boundary_bytes(paths__published=STATE + "\\published"),
    boundary_bytes(paths__install_roots=[]),
    boundary_bytes(paths__install_roots=[INSTALL, INSTALL + "\\venv"]),
    boundary_bytes(paths__install_roots=[CLONE + "\\tools"]),
    boundary_bytes(paths__install_roots=INSTALL),
    boundary_bytes(authority__sid=1001),
    b'{"schema_version": NaN}',
], ids=lambda data: str(len(data)))
def test_malformed_boundaries_are_refused(data) -> None:
    with pytest.raises(IdentityBoundaryError) as info:
        parse_identity_boundary(data)
    assert info.value.category is C.BOUNDARY_MALFORMED


def test_an_oversize_boundary_is_refused() -> None:
    with pytest.raises(IdentityBoundaryError) as info:
        parse_identity_boundary(b"{" + b" " * (64 * 1024) + b"}")
    assert info.value.category is C.BOUNDARY_MALFORMED


def test_validate_local_path_accepts_ordinary_paths() -> None:
    assert validate_local_path("C:\\AIDO\\state") == "C:\\AIDO\\state"
    assert validate_local_path("d:\\x y\\z.json") == "d:\\x y\\z.json"


# =============================================================================
# 6. the complete proof over a correctly provisioned world
# =============================================================================


def test_a_correctly_provisioned_world_is_proven(world) -> None:
    proof = prove(world)
    assert proof.boundary.authority.sid == A
    assert proof.boundary_sha256 == __import__("hashlib").sha256(world.boundary_bytes()).hexdigest()
    assert proof.facts_origin == "injected" and proof.is_production is False
    assert proof.independent_evaluation is False
    assert proof.proven_at == FIXED_NOW
    assert proof.objects_examined > 40


def test_the_bound_digest_must_match_when_given(world) -> None:
    digest = prove(world).boundary_sha256
    assert prove(world, expected_boundary_sha256=digest).boundary_sha256 == digest
    refused(world, C.BOUNDARY_DIGEST_MISMATCH, expected_boundary_sha256="0" * 64)
    refused(world, C.BOUNDARY_DIGEST_MISMATCH, expected_boundary_sha256="ABC")


def test_task_scheduler_launch_requires_a_non_interactive_window_station(world) -> None:
    world.boundary["launch_mechanism"] = "task_scheduler_s4u"
    refused(world, C.SESSION_FOREIGN, "non-interactive")
    world.session_facts = session(A_STATION, False, None, "Default", A_LOGON)
    prove(world)
    world.session_facts = session(A_STATION, False, None, "Default", X_LOGON)
    refused(world, C.SESSION_FOREIGN, "another logon session")


# =============================================================================
# 7. refusals by category
# =============================================================================


def test_non_windows_is_never_isolated(world) -> None:
    world.windows = False
    refused(world, C.PLATFORM_UNSUPPORTED)
    world.windows = 1  # truthy is not True
    refused(world, C.PLATFORM_UNSUPPORTED)


@pytest.mark.parametrize("name", [
    "AIDO_LITELLM_API_KEY", "aido_vllm_base_url", "GITHUB_TOKEN", "PYTHONPATH", "PythonHome",
    "PYTHONSTARTUP", "PYTHONUSERBASE", "PYTHONBREAKPOINT", "PYTHONINSPECT",
])
def test_credential_and_code_loading_environment_names_refuse(world, name) -> None:
    world.env.append(name)
    refused(world, C.ENVIRONMENT_UNSAFE, name)


@pytest.mark.parametrize("change, category", [
    ({"elevated": True}, C.TOKEN_ELEVATED),
    ({"elevation_type": 2}, C.TOKEN_ELEVATED),
    ({"elevation_type": 3}, C.TOKEN_ELEVATED),
    ({"integrity_rid": 0x3000}, C.TOKEN_ELEVATED),
    ({"privileges": STANDARD_PRIVILEGES + ("SeBackupPrivilege",)}, C.TOKEN_PRIVILEGED),
    ({"privileges": ("SeImpersonatePrivilege",)}, C.TOKEN_PRIVILEGED),
    ({"privileges": ("SeDebugPrivilege",)}, C.TOKEN_PRIVILEGED),
    ({"user_sid": X}, C.TOKEN_IDENTITY_MISMATCH),
])
def test_token_violations_refuse(world, change, category) -> None:
    world.token = replace(world.token, **change)
    refused(world, category)


def test_a_deny_only_administrators_group_means_an_administrator_account(world) -> None:
    world.token = replace(world.token, groups=world.token.groups + ((ADMINISTRATORS, 0x10),))
    refused(world, C.ACCOUNT_PRIVILEGED, "deny-only")


def test_the_token_must_carry_exactly_one_logon_sid(world) -> None:
    groups = tuple(g for g in world.token.groups if g[0] != A_LOGON)
    world.token = replace(world.token, groups=groups)
    refused(world, C.SESSION_FOREIGN, "logon SID")
    world.token = replace(world.token, groups=groups + ((A_LOGON, 0xC0000007), (X_LOGON, 0xC0000007)))
    refused(world, C.SESSION_FOREIGN, "logon SID")


def test_a_malformed_default_dacl_refuses(world) -> None:
    world.token = replace(world.token, default_dacl=b"\x02\x00")
    refused(world, C.DESCRIPTOR_UNSUPPORTED, "default DACL")


def test_a_missing_boundary_refuses(world) -> None:
    world.remove(ANCHOR)
    refused(world, C.BOUNDARY_UNREADABLE)


@pytest.mark.parametrize("mutate, match", [
    (lambda w: setattr(w.node(ANCHOR), "reparse", True), "reparse"),
    (lambda w: setattr(w.node(ANCHOR), "links", 2), "hard link"),
    (lambda w: setattr(w.node(ANCHOR), "final", "C:\\Elsewhere\\identity-boundary.v1.json"), "redirected"),
    (lambda w: setattr(w.node(ANCHOR), "owner", A), "owned by"),
    (lambda w: setattr(w.node(ANCHOR), "owner", X), "owned by"),
    (lambda w: setattr(w.node(ANCHOR_DIR), "owner", O), "admin-owned"),
    (lambda w: setattr(w.node(ANCHOR_DIR), "protected", False), "protected"),
    (lambda w: setattr(w.node(ANCHOR_DIR), "reparse", True), "reparse"),
    (lambda w: w.node(ANCHOR).aces.append(allow(X, FILE_WRITE_DATA)), "execution identity"),
    (lambda w: w.node(ANCHOR).aces.append(allow(A, FILE_WRITE_DATA)), "authority identity"),
    (lambda w: w.node(ANCHOR).aces.append(allow(O, WRITE_DAC)), "operator identity"),
    (lambda w: w.node(ANCHOR).aces.append(allow(USERS, DELETE)), "DELETE"),
    (lambda w: w.node(ANCHOR_DIR).aces.append(allow(X, FILE_ADD_FILE)), "ADD_FILE"),
    (lambda w: w.node(ANCHOR_DIR).aces.append(allow(AUTH, FILE_DELETE_CHILD)), "DELETE_CHILD"),
    (lambda w: w.node(ANCHOR_DIR).aces.append(allow(X, MODIFY, IO | OI)), "new file"),
    (lambda w: w.node("C:\\ProgramData").aces.append(allow(X, FILE_DELETE_CHILD)), "through its parent"),
])
def test_an_unprotected_anchor_refuses(world, mutate, match) -> None:
    mutate(world)
    refused(world, C.BOUNDARY_UNPROTECTED, match)


def test_a_malformed_boundary_document_refuses(world) -> None:
    world.boundary_raw = b"{}"
    refused(world, C.BOUNDARY_MALFORMED)


@pytest.mark.parametrize("change, category, match", [
    (("authority", "sid", f"{DOMAIN}-500"), C.IDENTITY_INVALID, "ordinary user"),
    (("execution", "sid", "S-1-5-18"), C.IDENTITY_INVALID, "ordinary user"),
    (("execution", "sid", "S-1-12-1-1-2-3-4"), C.IDENTITY_INVALID, "ordinary user"),
    (("execution", "sid", "S-1-5-21-9-9-9-1002"), C.IDENTITY_INVALID, "same local domain"),
    (("execution", "account", "HOST\\someone-else"), C.IDENTITY_INVALID, "declared account"),
])
def test_identity_declarations_refuse(world, change, category, match) -> None:
    role, key, value = change
    world.boundary[role][key] = value
    if key == "sid" and value not in world.principals:
        world.principals[value] = replace(world.principals[X], sid=value)
    refused(world, category, match)


def test_an_entra_operator_is_accepted_but_not_as_authority_or_execution(world) -> None:
    entra = "S-1-12-1-11-22-33-44"
    world.boundary["operator"]["sid"] = entra
    world.principals[entra] = replace(world.principals[O], sid=entra, is_local_account=False)
    for node in world.nodes.values():
        node.owner = entra if node.owner == O else node.owner
        node.aces = [Ace(a.ace_type, a.flags, a.mask, entra if a.sid == O else a.sid) for a in node.aces]
    prove(world)
    world.boundary["execution"]["sid"] = "S-1-12-1-11-22-33-45"
    refused(world, C.IDENTITY_INVALID, "ordinary user")


@pytest.mark.parametrize("role", ["authority", "execution", "operator"])
def test_each_account_must_be_verifiable(world, role) -> None:
    sid = world.boundary[role]["sid"]
    del world.principals[sid]
    refused(world, C.PRINCIPAL_UNVERIFIABLE)


@pytest.mark.parametrize("role, change, match", [
    ("execution", {"groups": ((ADMINISTRATORS, 0xF),)}, "member of S-1-5-32-544"),
    ("execution", {"groups": ((BACKUP_OPERATORS, 7),)}, "member of S-1-5-32-551"),
    ("operator", {"groups": ((ADMINISTRATORS, 0xF),)}, "member of S-1-5-32-544"),
    ("execution", {"groups": (("S-1-16-12288", 0x60),)}, "S-1-16-12288"),
    ("execution", {"groups": ((f"{DOMAIN}-512", 7),)}, "-512"),
    ("execution", {"privileges": ("SeRestorePrivilege",)}, "SeRestorePrivilege"),
    ("execution", {"privileges": ("SeTakeOwnershipPrivilege",)}, "SeTakeOwnershipPrivilege"),
    ("operator", {"privileges": ("SeBackupPrivilege",)}, "SeBackupPrivilege"),
    ("authority", {"groups": ((BACKUP_OPERATORS, 7),)}, "member of"),
])
def test_privileged_accounts_refuse(world, role, change, match) -> None:
    sid = world.boundary[role]["sid"]
    world.principals[sid] = replace(world.principals[sid], **change)
    refused(world, C.ACCOUNT_PRIVILEGED, match)


@pytest.mark.parametrize("change, match", [
    ({"sid_type": 2}, "not a user account"),
    ({"is_local_account": False}, "not a local account"),
    ({"account_name": "HOST\\other"}, "declared account"),
])
def test_execution_account_facts_refuse(world, change, match) -> None:
    world.principals[X] = replace(world.principals[X], **change)
    refused(world, C.IDENTITY_INVALID, match)


def test_a_custom_group_shared_by_authority_and_execution_refuses(world) -> None:
    shared = f"{DOMAIN}-7000"
    world.principals[A] = replace(world.principals[A], groups=world.principals[A].groups + ((shared, 7),))
    world.principals[X] = replace(world.principals[X], groups=world.principals[X].groups + ((shared, 7),))
    refused(world, C.IDENTITY_INVALID, "shares")


@pytest.mark.parametrize("session", [
    session("WinSta0", False, A_LOGON, "Default", A_LOGON),
    session("WinSta0", True, X_LOGON, "Default", X_LOGON),
    session("WinSta0", True, A_LOGON, "Default", X_LOGON),
    session("Service-0x0-3e7$", True, A_LOGON, "Default", A_LOGON),
])
def test_a_foreign_session_refuses(world, session) -> None:
    world.session_facts = session
    refused(world, C.SESSION_FOREIGN)


@pytest.mark.parametrize("field_name, ace", [
    ("process_descriptor", allow(EVERYONE, 0x0010)),  # PROCESS_VM_READ
    ("process_descriptor", allow(X, 0x0002)),  # PROCESS_CREATE_THREAD
    ("process_descriptor", allow(INTERACTIVE, PROCESS_QUERY_LIMITED)),
    ("process_descriptor", allow(X_LOGON, 0x0040)),  # a foreign logon SID: PROCESS_DUP_HANDLE
    ("thread_descriptor", allow(USERS, 0x0010)),  # THREAD_SET_CONTEXT
    ("token_descriptor", allow(AUTH, 0x0002)),  # TOKEN_DUPLICATE
    ("token_descriptor", allow(O, GENERIC_ALL)),
])
def test_process_thread_and_token_access_refuses(world, field_name, ace) -> None:
    raw = getattr(world.process_facts, field_name)
    sd = parse_security_descriptor(raw)
    patched = build_security_descriptor(sd.owner, sd.dacl + (ace,), protected=False)
    world.process_facts = replace(world.process_facts, **{field_name: patched})
    refused(world, C.PROCESS_ACCESS)


def test_a_default_dacl_granting_interactive_refuses(world) -> None:
    world.token = replace(world.token, default_dacl=build_acl(
        list(parse_acl(world.token.default_dacl)) + [allow(INTERACTIVE, GENERIC_ALL)]))
    refused(world, C.PROCESS_ACCESS, "default DACL")


@pytest.mark.parametrize("path, mutate, category, match", [
    (STATE, lambda n: setattr(n, "owner", X), C.OBJECT_OWNER, "state_root"),
    (STATE, lambda n: setattr(n, "owner", ADMINISTRATORS), C.OBJECT_OWNER, "state_root"),
    (STATE, lambda n: setattr(n, "protected", False), C.OBJECT_UNPROTECTED, "state_root"),
    (STATE, lambda n: n.aces.append(allow(USERS, RX)), C.OBJECT_RIGHTS, "READ_DATA"),
    (STATE, lambda n: setattr(n, "reparse", True), C.OBJECT_REPARSE, "state_root"),
    (STATE, lambda n: setattr(n, "is_dir", False), C.OBJECT_KIND, "state_root"),
    (STATE, lambda n: setattr(n, "final", "C:\\AIDO\\STATE~1"), C.OBJECT_NOT_CANONICAL, "state_root"),
    (STATE + "\\evidence\\verification\\abc.json", lambda n: n.aces.append(allow(X, FILE_WRITE_DATA)),
     C.OBJECT_RIGHTS, "abc.json"),
    (STATE + "\\evidence\\verification\\abc.json", lambda n: setattr(n, "links", 2), C.OBJECT_LINKED, "abc.json"),
    (STATE + "\\evidence\\verification\\abc.json", lambda n: setattr(n, "owner", O), C.OBJECT_OWNER, "abc.json"),
    (STATE + "\\evidence", lambda n: setattr(n, "reparse", True), C.OBJECT_REPARSE, "evidence"),
    (STATE + "\\evidence", lambda n: n.aces.append(allow(X, FILE_WRITE_DATA, IO | OI)),
     C.OBJECT_INHERITANCE, "evidence"),
    (PUBLISHED, lambda n: n.aces.append(allow(O, FILE_WRITE_DATA)), C.OBJECT_RIGHTS, "operator"),
    (PUBLISHED, lambda n: n.aces.append(allow(X, RX)), C.OBJECT_RIGHTS, "execution"),
    (PUBLISHED + "\\bundle.json", lambda n: n.aces.append(allow(O, DELETE)), C.OBJECT_RIGHTS, "bundle"),
    (INBOX, lambda n: n.aces.append(allow(X, FILE_ADD_FILE)), C.OBJECT_RIGHTS, "execution"),
    (INBOX, lambda n: n.aces.append(allow(O, FILE_ADD_SUBDIRECTORY)), C.OBJECT_RIGHTS, "operator"),
    (INBOX, lambda n: n.aces.append(allow(O, FILE_DELETE_CHILD)), C.OBJECT_RIGHTS, "operator"),
    (INBOX + "\\approval.sshsig", lambda n: n.aces.append(allow(X, FILE_WRITE_DATA)), C.OBJECT_RIGHTS, "approval"),
    (INBOX + "\\approval.sshsig", lambda n: setattr(n, "owner", X), C.OBJECT_OWNER, "approval"),
    (EXCHANGE, lambda n: n.aces.append(allow(X, FILE_ADD_SUBDIRECTORY)), C.OBJECT_RIGHTS, "exchange_root"),
    (EXCHANGE, lambda n: n.aces.append(allow(X, MODIFY, IO | OICI)), C.OBJECT_INHERITANCE, "exchange_root"),
    (EXCHANGE, lambda n: setattr(n, "owner", O), C.OBJECT_OWNER, "exchange_root"),
    (CLONE, lambda n: setattr(n, "owner", A), C.OBJECT_OWNER, "clone"),
    (CLONE, lambda n: n.aces.append(allow(X, DELETE)), C.OBJECT_REPLACEABLE, "clone"),
    (CLONE, lambda n: n.aces.append(allow(O, FILE_WRITE_DATA)), C.OBJECT_RIGHTS, "operator"),
    (CLONES, lambda n: n.aces.append(allow(X, FILE_ADD_SUBDIRECTORY)), C.OBJECT_RIGHTS, "parent"),
    (CLONES, lambda n: n.aces.append(allow(X, FILE_DELETE_CHILD)), C.OBJECT_REPLACEABLE, "clone"),
    (GIT, lambda n: setattr(n, "is_dir", False), C.OBJECT_KIND, "gitfile"),
    (GIT, lambda n: setattr(n, "reparse", True), C.OBJECT_REPARSE, ".git"),
    (GIT, lambda n: setattr(n, "owner", A), C.OBJECT_OWNER, ".git"),
    (GIT, lambda n: setattr(n, "protected", False), C.OBJECT_UNPROTECTED, ".git"),
    (GIT, lambda n: n.aces.append(allow(X, FILE_ADD_FILE)), C.OBJECT_RIGHTS, ".git"),
    (GIT + "\\HEAD", lambda n: n.aces.append(allow(X, FILE_WRITE_DATA)), C.OBJECT_RIGHTS, "HEAD"),
    (GIT + "\\refs\\heads\\main", lambda n: setattr(n, "owner", O), C.OBJECT_OWNER, "main"),
    (GIT + "\\refs", lambda n: setattr(n, "reparse", True), C.OBJECT_REPARSE, "refs"),
    (GIT + "\\refs", lambda n: n.aces.append(allow(X, FILE_WRITE_DATA, IO | OI)), C.OBJECT_INHERITANCE, "refs"),
])
def test_fd14_object_violations_refuse(world, path, mutate, category, match) -> None:
    mutate(world.node(path))
    refused(world, category, match)


@pytest.mark.parametrize("path", [STATE, PUBLISHED, INBOX, EXCHANGE, CLONE, GIT, INSTALL])
def test_missing_declared_objects_refuse(world, path) -> None:
    for key in [k for k in world.nodes if k.startswith(ntpath.normcase(path))]:
        world.remove(world.names[key])
    refused(world, C.OBJECT_MISSING)


def test_the_inbox_holds_files_only(world) -> None:
    world.put(INBOX + "\\nested", is_dir=True, owner=O, aces=[allow(A, FILE_ALL_ACCESS, INH)])
    refused(world, C.OBJECT_KIND, "files only")


@pytest.mark.parametrize("mutate, category, match", [
    (lambda w: setattr(w.node(INSTALL), "owner", O), C.OBJECT_OWNER, "install_root[0]"),
    (lambda w: setattr(w.node(INSTALL), "owner", A), C.OBJECT_OWNER, "install_root[0]"),
    (lambda w: w.node(INSTALL).aces.append(allow(A, FILE_WRITE_DATA)), C.OBJECT_RIGHTS, "authority"),
    (lambda w: w.node(INSTALL + "\\venv\\Lib\\site-packages\\ai_dev_orchestrator\\__init__.py")
     .aces.append(allow(X, FILE_WRITE_DATA)), C.OBJECT_RIGHTS, "__init__.py"),
    (lambda w: setattr(w.node(INSTALL + "\\python\\Lib\\os.py"), "owner", X), C.OBJECT_OWNER, "os.py"),
    (lambda w: setattr(w.node(INSTALL + "\\venv\\Lib\\site-packages"), "reparse", True),
     C.OBJECT_REPARSE, "site-packages"),
    (lambda w: w.node(INSTALL + "\\python\\DLLs").aces.append(allow(USERS, FILE_ADD_FILE)),
     C.OBJECT_RIGHTS, "DLLs"),
])
def test_install_root_violations_refuse(world, mutate, category, match) -> None:
    mutate(world)
    refused(world, category, match)


@pytest.mark.parametrize("field_name, value, category, match", [
    ("import_paths", ("",), C.CODE_PATH_UNTRUSTED, "import_path[0]"),
    ("import_paths", ("src",), C.CODE_PATH_UNTRUSTED, "import_path[0]"),
    ("import_paths", (CLONE,), C.CODE_PATH_UNTRUSTED, "outside every declared install root"),
    ("import_paths", ("C:\\nonexistent\\lib",), C.CODE_PATH_UNTRUSTED, "outside"),
    ("executables", ("C:\\Users\\aido-a\\python.exe",), C.OBJECT_MISSING, "executable[0]"),
    ("executables", (PROFILE,), C.CODE_PATH_UNTRUSTED, "outside"),
    ("prefixes", (INSTALL + "\\gone",), C.OBJECT_MISSING, "prefix[0]"),
    ("package_directory", STATE, C.CODE_PATH_UNTRUSTED, "AIDO package"),
])
def test_code_locations_outside_install_roots_refuse(world, field_name, value, category, match) -> None:
    world.code = replace(world.code, **{field_name: value})
    refused(world, category, match)


def test_a_code_path_ending_at_a_dangling_reparse_point_refuses(world) -> None:
    world.put("C:\\AIDO\\link", is_dir=True, owner=ADMINISTRATORS, aces=ADMIN_FULL, reparse=True)
    world.code = replace(world.code, import_paths=("C:\\AIDO\\link\\lib",))
    refused(world, C.OBJECT_REPARSE, "import_path[0]")


def test_the_interpreter_must_be_isolated(world) -> None:
    world.code = replace(world.code, isolated_interpreter=False)
    refused(world, C.CODE_PATH_UNTRUSTED, "-I")
    world.code = replace(world.code, isolated_interpreter=1)
    refused(world, C.CODE_PATH_UNTRUSTED, "-I")


def test_a_search_path_with_a_trailing_backslash_names_the_same_directory(world) -> None:
    world.code = replace(world.code, search_paths=(SYSTEM32 + "\\", "C:\\Windows\\"))
    prove(world)
    world.code = replace(world.code, search_paths=(SYSTEM32 + "\\\\",))
    refused(world, C.CODE_PATH_UNTRUSTED, "search_path[0]")


@pytest.mark.parametrize("name", ["evil.", "evil ", "NUL", "com1.dll", "a<b"])
def test_an_entry_win32_cannot_address_exactly_refuses(world, name) -> None:
    world.put(INSTALL + "\\python\\Lib\\" + name, is_dir=False, owner=ADMINISTRATORS,
              aces=inherited(world.node(INSTALL).aces, child_dir=False))
    refused(world, C.OBJECT_NOT_CANONICAL, "cannot address")


@pytest.mark.parametrize("mutate, category, match", [
    (lambda w: w.node(SYSTEM32).aces.append(allow(X, FILE_ADD_FILE)), C.OBJECT_RIGHTS, "search_path[0]"),
    (lambda w: w.node(SYSTEM32 + "\\kernel32.dll").aces.append(allow(USERS, FILE_WRITE_DATA)),
     C.OBJECT_RIGHTS, "kernel32.dll"),
    (lambda w: setattr(w.node(SYSTEM32 + "\\kernel32.dll"), "owner", X), C.OBJECT_OWNER, "kernel32.dll"),
    (lambda w: setattr(w.node(SYSTEM32), "owner", O), C.OBJECT_OWNER, "search_path[0]"),
    (lambda w: (setattr(w.node(WINDOWSAPPS + "\\winget.exe"), "reparse", False),
                w.node(WINDOWSAPPS + "\\winget.exe").aces.append(allow(X, FILE_WRITE_DATA)),
                setattr(w, "code", replace(w.code, search_paths=(SYSTEM32, WINDOWSAPPS)))),
     C.OBJECT_RIGHTS, "search_path[1]\\winget.exe"),
    (lambda w: setattr(w, "code", replace(w.code, search_paths=("bin",))), C.CODE_PATH_UNTRUSTED, "search_path[0]"),
    (lambda w: setattr(w.node(INSTALL), "aces", [*ADMIN_FULL, allow(USERS, RX, OICI), allow(X, FILE_ADD_FILE)]),
     C.OBJECT_RIGHTS, "install_root[0]"),
    (lambda w: setattr(w, "code", replace(w.code, working_directory=CLONE)), C.OBJECT_OWNER, "working directory"),
    (lambda w: setattr(w, "code", replace(w.code, working_directory=INBOX)), C.OBJECT_RIGHTS,
     "operator identity could be granted WRITE_DATA/ADD_FILE on the working directory"),
    (lambda w: setattr(w, "code", replace(w.code, working_directory="C:\\gone")), C.OBJECT_MISSING, "working"),
])
def test_search_directory_violations_refuse(world, mutate, category, match) -> None:
    mutate(world)
    refused(world, category, match)


@pytest.mark.parametrize("mutate, category, match", [
    (lambda w: w.node(PROFILE).aces.append(allow(X, RX)), C.OBJECT_RIGHTS, "profile[0]"),
    (lambda w: setattr(w.node(PROFILE), "owner", X), C.OBJECT_OWNER, "profile[0]"),
    (lambda w: w.node(PROFILE + "\\AppData\\Local\\Temp").aces.append(allow(O, FILE_ADD_FILE)),
     C.OBJECT_RIGHTS, "profile[1]"),
    (lambda w: setattr(w, "code", replace(w.code, profile_directories=(PROFILE, ""))),
     C.OBJECT_MISSING, "profile[1]"),
    (lambda w: setattr(w, "code", replace(w.code, profile_directories=(PROFILE + "\\Missing",))),
     C.OBJECT_MISSING, "profile[0]"),
    (lambda w: w.node("C:\\Users").aces.append(allow(X, FILE_DELETE_CHILD)), C.OBJECT_REPLACEABLE,
     "through its parent"),
    (lambda w: w.node(PROFILE + "\\AppData\\Roaming").aces.append(allow(X, DELETE)), C.OBJECT_REPLACEABLE,
     "profile[3]"),
])
def test_profile_violations_refuse(world, mutate, category, match) -> None:
    mutate(world)
    refused(world, category, match)


def test_the_examination_limit_refuses(world, monkeypatch) -> None:
    monkeypatch.setattr(ib, "MAX_EXAMINED_OBJECTS", 10)
    refused(world, C.EXAMINATION_LIMIT)


def test_an_unsupported_descriptor_on_an_authority_object_refuses(world) -> None:
    raw = bytearray(build_security_descriptor(A, [allow(A, FILE_ALL_ACCESS, OICI)], protected=True))
    raw[int.from_bytes(raw[16:20], "little") + 8] = 0x09  # callback (conditional) allow ACE
    world.node(STATE).raw = bytes(raw)
    refused(world, C.DESCRIPTOR_UNSUPPORTED, "state_root")


def test_a_null_dacl_on_an_authority_object_refuses(world) -> None:
    raw = build_security_descriptor(A, [], protected=True)
    world.node(PUBLISHED).raw = _patch(raw, 16, b"\x00\x00\x00\x00")
    refused(world, C.DESCRIPTOR_UNSUPPORTED, "no DACL")


# =============================================================================
# 8. discovered bypasses — regressions from the adversarial analysis
# =============================================================================


def test_b1_delete_child_on_the_clone_root_would_let_x_rename_dot_git(world) -> None:
    """B-1. ``.git`` denies X DELETE, but DELETE_CHILD on its parent lets X
    rename it away and create a ``.git`` it owns. Refused on the clone root."""
    clone = world.node(CLONE)
    clone.aces[1] = allow(X, clone.aces[1].mask | FILE_DELETE_CHILD)
    refused(world, C.OBJECT_RIGHTS, "DELETE_CHILD on clone")


def test_b1_parent_delete_child_overrides_an_explicit_deny_on_the_child(world) -> None:
    """Deny DELETE on the child does not stop deletion through the parent."""
    world.node(STATE).aces.insert(0, deny(X, DELETE))
    world.node("C:\\AIDO").aces.append(allow(X, FILE_DELETE_CHILD))
    refused(world, C.OBJECT_REPLACEABLE, "through its parent")


def test_b2_a_user_created_top_level_directory_is_replaceable_by_x(world) -> None:
    """B-2. A directory a user creates under C:\\ inherits "Authenticated Users:
    Modify" (DELETE included), and C:\\ lets them add subdirectories, so X can
    rename the ancestor away and recreate it."""
    world.node("C:\\AIDO").protected = False
    world.node("C:\\AIDO").aces = inherited(world.node("C:\\").aces, child_dir=True)
    refused(world, C.OBJECT_REPLACEABLE, "ancestor")


def test_b3_inherit_only_aces_on_a_code_directory_are_caught(world) -> None:
    """B-3. The directory's own rights look clean, but every new file in it
    would be X-writable."""
    world.node(INSTALL + "\\venv\\Lib\\site-packages").aces.append(allow(X, FILE_WRITE_DATA, IO | OI))
    refused(world, C.OBJECT_INHERITANCE, "site-packages")


def test_b4_a_missing_search_path_under_an_x_writable_ancestor_refuses(world) -> None:
    """B-4. ``C:\\tools\\bin`` does not exist, and X may add subdirectories to
    ``C:\\``, so X could create it and plant executables."""
    world.code = replace(world.code, search_paths=("C:\\tools\\bin",))
    refused(world, C.CODE_PATH_UNTRUSTED, "could create it")


def test_b4_a_missing_import_path_inside_an_install_root_is_safe(world) -> None:
    """``python314.zip`` normally does not exist; inside a walked install root
    no identity can create it."""
    assert ntpath.normcase(INSTALL + "\\python\\python314.zip") not in world.nodes
    prove(world)


def test_b5_an_x_owned_git_descendant_without_owner_rights_can_be_repermissioned(world) -> None:
    """B-5. Owner-implicit WRITE_DAC: an X-owned file under ``.git`` whose DACL
    does not carry OWNER RIGHTS lets X rewrite it."""
    head = world.node(GIT + "\\HEAD")
    head.aces = [a for a in head.aces if a.sid != OWNER_RIGHTS]
    refused(world, C.OBJECT_RIGHTS, "WRITE_DAC")


def test_b5_clone_root_without_owner_rights_refuses(world) -> None:
    world.node(CLONE).aces = [a for a in world.node(CLONE).aces if a.sid != OWNER_RIGHTS]
    refused(world, C.OWNER_RIGHTS_MISSING, "clone")


def test_b5_clone_root_owner_rights_not_inherited_refuses(world) -> None:
    aces = world.node(CLONE).aces
    aces[0] = allow(OWNER_RIGHTS, READ_CONTROL)  # this folder only
    refused(world, C.OWNER_RIGHTS_MISSING, "inherited")


def test_b6_deny_interactive_does_not_protect_an_authority_object(world) -> None:
    world.node(STATE).aces[:0] = [deny(INTERACTIVE, FILE_ALL_ACCESS), allow(USERS, FILE_WRITE_DATA)]
    refused(world, C.OBJECT_RIGHTS, "execution")


def test_b7_an_allow_to_an_unknown_logon_sid_counts_as_x(world) -> None:
    world.node(PUBLISHED).aces.append(allow(X_LOGON, FILE_WRITE_DATA))
    refused(world, C.OBJECT_RIGHTS, "execution")


def test_b8_authz_omits_logon_type_sids_so_they_are_added(world) -> None:
    """X's AuthZ groups carry no INTERACTIVE, but X's real token does."""
    assert all(sid != INTERACTIVE for sid, _ in world.principals[X].groups)
    world.node(EXCHANGE).aces.append(allow(INTERACTIVE, FILE_ADD_FILE))
    refused(world, C.OBJECT_RIGHTS, "execution")


def test_a_short_name_alias_of_a_declared_path_refuses(world) -> None:
    world.node(INSTALL).final = "C:\\AIDO\\INSTAL~1"
    refused(world, C.OBJECT_NOT_CANONICAL, "install_root[0]")


def test_a_user_planted_boundary_is_not_admin_owned(world) -> None:
    """ProgramData lets Users create AIDO\\ if it is missing; anything they
    plant there is owned by them."""
    world.node(ANCHOR_DIR).owner = O
    world.node(ANCHOR).owner = O
    refused(world, C.BOUNDARY_UNPROTECTED, "owned by")


def test_write_attributes_on_an_authority_object_refuses(world) -> None:
    """An empty directory with WRITE_ATTRIBUTES can be turned into a junction."""
    world.node(PUBLISHED).aces.append(allow(X, FILE_WRITE_ATTRIBUTES))
    refused(world, C.OBJECT_RIGHTS, "WRITE_ATTRIBUTES")


def test_b9_a_code_path_through_an_intermediate_junction_refuses(world) -> None:
    """B-9 (found in the second review). ``C:\\AIDO\\link`` is a junction into
    the install root. Opening ``C:\\AIDO\\link\\Lib`` without following reparse
    points still follows ``link``: the facts describe the install root's
    ``Lib``, which is clean, while the path the interpreter uses depends on a
    junction outside every install root. Only the final path reveals it."""
    world.put("C:\\AIDO\\link", is_dir=True, owner=ADMINISTRATORS, aces=ADMIN_FULL, reparse=True,
              target=INSTALL + "\\python")
    world.code = replace(world.code, import_paths=("C:\\AIDO\\link\\Lib",))
    refused(world, C.OBJECT_NOT_CANONICAL, "import_path[0]")
    world.code = replace(good_world().code, search_paths=("C:\\AIDO\\link\\DLLs",))
    refused(world, C.OBJECT_NOT_CANONICAL, "search_path[0]")


def test_b10_path_identity_folds_ascii_only() -> None:
    """B-10 (found in the second review). Full Unicode lowering equates names
    NTFS keeps apart, so it must not decide that two paths are one object."""
    assert "C:\\AIDO\\\u212ait".lower() == "C:\\AIDO\\kit".lower()  # the trap
    assert ib._key("C:\\AIDO\\\u212ait") != ib._key("C:\\AIDO\\kit")
    assert ib._key("c:\\aido\\KIT") == ib._key("C:\\AIDO\\kit")
    assert not ib._within_exact("C:\\AIDO\\INSTALL\\x", "C:\\AIDO\\install")


def test_b10_containment_uses_the_spelling_windows_reports(world) -> None:
    """In a per-directory case-sensitive folder, ``INSTALL`` and ``install``
    are different directories; only the declared one was walked."""
    world.node(INSTALL + "\\python\\Lib").final = "C:\\AIDO\\INSTALL\\python\\Lib"
    refused(world, C.CODE_PATH_UNTRUSTED, "outside every declared install root")


def test_b10_overlapping_declared_paths_are_detected_beyond_ascii() -> None:
    with pytest.raises(IdentityBoundaryError):
        parse_identity_boundary(boundary_bytes(paths__published="C:\\AIDO\\STATE\\pub"))
    with pytest.raises(IdentityBoundaryError):
        parse_identity_boundary(boundary_bytes(paths__state_root="C:\\AIDO\\\u00c9", paths__published="C:\\AIDO\\\u00e9\\p"))


# -- FU1: bypasses confirmed by the independent review --------------------------------

ISOLATED = "C:\\Iso"


def relocate(w: World, old: str, new: str) -> None:
    """Move ``old`` and everything below it to ``new``, keeping every
    descriptor, and rewrite the boundary paths and code-load facts naming it."""
    old_key = ntpath.normcase(old)

    def moved(path: str) -> bool:
        key = ntpath.normcase(path)
        return key == old_key or key.startswith(old_key + "\\")

    def rewrite(path: str) -> str:
        return new + path[len(old):] if moved(path) else path

    nodes = sorted((w.names[k], w.nodes[k]) for k in list(w.nodes) if moved(w.names[k]))
    for path, _ in reversed(nodes):
        w.remove(path)
    for path, node in nodes:
        w.put(rewrite(path), is_dir=node.is_dir, owner=node.owner, aces=node.aces, protected=node.protected,
              reparse=node.reparse, links=node.links, final=node.final, raw=node.raw, target=node.target)
    paths = w.boundary["paths"]
    for name, value in paths.items():
        paths[name] = [rewrite(v) for v in value] if isinstance(value, list) else rewrite(value)
    w.code = replace(w.code, **{
        name: tuple(rewrite(v) for v in value) if isinstance(value, tuple) else rewrite(value)
        for name, value in w.code.__dict__.items() if name != "isolated_interpreter"
    })


def isolated_world(path: str) -> World:
    """A correct world in which ``path`` sits under an ancestor of its own."""
    w = good_world()
    w.put(ISOLATED, is_dir=True, owner=ADMINISTRATORS, protected=True, aces=[*ADMIN_FULL, allow(USERS, RX)])
    relocate(w, path, ISOLATED + "\\" + ntpath.basename(path))
    return w


def test_b13_write_dac_on_an_ancestor_refuses_a_protected_state_root(world) -> None:
    """B-13 (FU1 F1). X holds WRITE_DAC on ``C:\\AIDO`` but neither DELETE nor
    DELETE_CHILD there, and the state root itself is protected. X rewrites the
    ancestor's DACL, grants itself DELETE_CHILD and renames the state root
    away: the proof must refuse."""
    world.node("C:\\AIDO").aces.append(allow(X, WRITE_DAC))
    aido = parse_security_descriptor(world.node("C:\\AIDO").descriptor())
    assert upper_bound_rights(aido, principal_x(), ObjectKind.DIRECTORY) & (DELETE | FILE_DELETE_CHILD) == 0
    assert world.node(STATE).protected and world.node(STATE).owner == A
    refused(world, C.OBJECT_REPLACEABLE, "an ancestor of state_root")


@pytest.mark.parametrize("mutate", [
    lambda n: n.aces.append(allow(X, WRITE_OWNER)),
    lambda n: n.aces.append(allow(O, WRITE_DAC)),
    lambda n: n.aces.append(allow(USERS, WRITE_OWNER)),
    lambda n: n.aces.append(allow(INTERACTIVE, WRITE_DAC)),
    lambda n: setattr(n, "owner", X),
    lambda n: setattr(n, "owner", O),
], ids=["x-write-owner", "o-write-dac", "users-write-owner", "interactive-write-dac", "x-owner", "o-owner"])
def test_b13_taking_over_an_ancestor_refuses(world, mutate) -> None:
    """Ownership is an implicit WRITE_DAC; WRITE_OWNER takes ownership."""
    mutate(world.node("C:\\AIDO"))
    refused(world, C.OBJECT_REPLACEABLE, "an ancestor of state_root")


@pytest.mark.parametrize("moved, label", [
    (STATE, "state_root"), (PUBLISHED, "published"), (INBOX, "inbox"), (EXCHANGE, "exchange_root"),
    (CLONES, "clone"), (INSTALL, "install_root[0]"),
], ids=["state", "published", "inbox", "exchange", "clone", "install"])
@pytest.mark.parametrize("right", [WRITE_DAC, WRITE_OWNER], ids=["write-dac", "write-owner"])
def test_b13_every_protected_path_refuses_an_ancestor_takeover(moved, label, right) -> None:
    w = isolated_world(moved)
    prove(w)
    w.node(ISOLATED).aces.append(allow(X, right))
    refused(w, C.OBJECT_REPLACEABLE, f"an ancestor of {label}")


@pytest.mark.parametrize("path", ["C:\\", "C:\\ProgramData"], ids=["volume-root", "programdata"])
@pytest.mark.parametrize("right", [WRITE_DAC, WRITE_OWNER], ids=["write-dac", "write-owner"])
def test_b13_the_anchor_refuses_an_ancestor_takeover(world, path, right) -> None:
    world.node(path).aces.append(allow(X, right))
    refused(world, C.BOUNDARY_UNPROTECTED, "an ancestor of the identity boundary")


@pytest.mark.parametrize("path, label", [
    ("C:\\Windows", "an ancestor of search_path[0]"),
    ("C:\\Users", "an ancestor of profile[0]"),
    (PROFILE + "\\AppData", "an ancestor of profile[1]"),
], ids=["search-path", "profile", "profile-intermediate"])
@pytest.mark.parametrize("right", [WRITE_DAC, WRITE_OWNER], ids=["write-dac", "write-owner"])
def test_b13_code_and_profile_paths_refuse_an_ancestor_takeover(world, path, label, right) -> None:
    world.node(path).aces.append(allow(X, right))
    refused(world, C.OBJECT_REPLACEABLE, label)


def test_b13_an_adversary_owned_ancestor_is_safe_only_under_an_effective_owner_rights_ace() -> None:
    """The clone's ``.git`` sits below the X-owned clone root, so ownership
    alone cannot refuse; what decides is whether the owner keeps the implicit
    WRITE_DAC."""
    w = isolated_world(STATE)
    w.node(ISOLATED).owner = X
    refused(w, C.OBJECT_REPLACEABLE, "WRITE_DAC")
    w.node(ISOLATED).aces.insert(0, allow(OWNER_RIGHTS, READ_CONTROL))
    prove(w)
    w.node(ISOLATED).aces[0] = allow(OWNER_RIGHTS, READ_CONTROL, IO | OICI)  # inherit-only: not effective
    refused(w, C.OBJECT_REPLACEABLE, "WRITE_DAC")
    w.node(ISOLATED).aces[0] = allow(OWNER_RIGHTS, READ_CONTROL | WRITE_OWNER)
    refused(w, C.OBJECT_REPLACEABLE, "WRITE_OWNER")


def test_b13_a_missing_search_path_refuses_a_takeover_above_its_nearest_ancestor() -> None:
    w = isolated_world(INSTALL)
    w.put(ISOLATED + "\\tools", is_dir=True, owner=ADMINISTRATORS, protected=True,
          aces=[*ADMIN_FULL, allow(USERS, RX)])
    w.code = replace(w.code, search_paths=(ISOLATED + "\\tools\\bin",))
    prove(w)
    w.node(ISOLATED).aces.append(allow(X, WRITE_DAC))
    refused(w, C.OBJECT_REPLACEABLE, "ancestor")


@pytest.mark.parametrize("right", [WRITE_DAC, WRITE_OWNER], ids=["write-dac", "write-owner"])
def test_b13_a_missing_search_path_refuses_a_takeover_of_its_nearest_ancestor(right) -> None:
    """Found in the FU1 self-review: the nearest existing ancestor of a missing
    PATH entry was checked only for add rights, but re-permissioning it grants
    them."""
    w = isolated_world(INSTALL)
    w.put(ISOLATED + "\\tools", is_dir=True, owner=ADMINISTRATORS, protected=True,
          aces=[*ADMIN_FULL, allow(USERS, RX), allow(X, right)])
    w.code = replace(w.code, search_paths=(ISOLATED + "\\tools\\bin",))
    refused(w, C.CODE_PATH_UNTRUSTED, "could create it")


_PROTECTED_OBJECTS = [
    (ANCHOR, C.BOUNDARY_UNPROTECTED), (ANCHOR_DIR, C.BOUNDARY_UNPROTECTED),
    (STATE, C.OBJECT_RIGHTS), (STATE + "\\evidence", C.OBJECT_RIGHTS), (PUBLISHED, C.OBJECT_RIGHTS),
    (INBOX, C.OBJECT_RIGHTS), (EXCHANGE, C.OBJECT_RIGHTS), (CLONES, C.OBJECT_REPLACEABLE),
    (CLONE, C.OBJECT_RIGHTS), (GIT, C.OBJECT_RIGHTS), (GIT + "\\refs\\heads\\main", C.OBJECT_RIGHTS),
    (INSTALL, C.OBJECT_RIGHTS), (INSTALL + "\\python\\Lib\\os.py", C.OBJECT_RIGHTS),
    (SYSTEM32, C.OBJECT_RIGHTS), (SYSTEM32 + "\\kernel32.dll", C.OBJECT_RIGHTS),
    (PROFILE, C.OBJECT_RIGHTS), (PROFILE + "\\AppData\\Local\\Temp", C.OBJECT_RIGHTS),
]


@pytest.mark.parametrize("path, category", _PROTECTED_OBJECTS, ids=[p for p, _ in _PROTECTED_OBJECTS])
@pytest.mark.parametrize("right", [WRITE_DAC, WRITE_OWNER], ids=["write-dac", "write-owner"])
def test_b13_a_takeover_right_on_any_protected_object_itself_refuses(world, path, category, right) -> None:
    """The leaf half of B-13: each object's own limit excludes both rights."""
    world.node(path).aces.insert(0, allow(X, right))
    refused(world, category, {WRITE_DAC: "WRITE_DAC", WRITE_OWNER: "WRITE_OWNER"}[right])


@pytest.mark.parametrize("desktop_sid", [None, A_LOGON], ids=["desktop-sid-absent", "desktop-sid-own"])
@pytest.mark.parametrize("station_sid", [X_LOGON, X, LOCAL_SYSTEM], ids=["x-logon", "x-user", "system"])
def test_b14_a_foreign_non_interactive_window_station_refuses(world, station_sid, desktop_sid) -> None:
    """B-14 (FU1 F2). A non-interactive station that is not WinSta0 but
    belongs to someone else does not isolate A, whatever the desktop says."""
    world.boundary["launch_mechanism"] = "task_scheduler_s4u"
    world.session_facts = session(A_STATION, False, station_sid, "Default", desktop_sid)
    refused(world, C.SESSION_FOREIGN, "window station")


@pytest.mark.parametrize("station_sid, desktop_sid", [
    (None, None), (None, A_LOGON), (A_LOGON, None), (A_LOGON, A_LOGON),
], ids=["sid-less", "sid-less-own-desktop", "own-station", "own-station-own-desktop"])
def test_b14_the_station_of_as_own_logon_session_is_accepted(world, station_sid, desktop_sid) -> None:
    """A genuine S4U launch: the station Windows created for A's logon session."""
    world.boundary["launch_mechanism"] = "task_scheduler_s4u"
    world.session_facts = session(A_STATION, False, station_sid, "Default", desktop_sid)
    prove(world)
    world.session_facts = session(A_STATION.upper(), False, station_sid, "Default", desktop_sid)
    prove(world)
    world.token = replace(world.token, authentication_id=(1 << 32) | A_LUID)
    world.session_facts = session("Service-0x1-4242$", False, station_sid, "Default", desktop_sid)
    prove(world)


@pytest.mark.parametrize("station", [
    "Service-0x0-3e7$",  # SYSTEM's: shared with every service in session 0
    "Service-0x0-3e5$",  # LocalService's
    "Service-0x0-7777$",  # another logon session's
    "Service-0x0-04242$", "Service-0x00-4242$", "Service-0x0-4242", "xService-0x0-4242$",
    "ſervice-0x0-4242$",  # LATIN SMALL LETTER LONG S casefolds to "s"
    "Service-0x0-4242$\\Default",
], ids=["system", "local-service", "other-session", "padded-low", "padded-high", "no-dollar",
        "prefixed", "long-s", "with-desktop"])
@pytest.mark.parametrize("desktop_sid", [None, A_LOGON], ids=["desktop-sid-absent", "desktop-sid-own"])
def test_b14_a_sid_less_station_not_named_for_as_logon_session_refuses(world, station, desktop_sid) -> None:
    """A station that reports no SID could be anyone's; only the name Windows
    derives from A's own logon LUID binds it to A."""
    world.boundary["launch_mechanism"] = "task_scheduler_s4u"
    world.session_facts = session(station, False, None, "Default", desktop_sid)
    refused(world, C.SESSION_FOREIGN, "own logon session")


@pytest.mark.parametrize("value", [None, "0x4242", True, 0, -1, 1 << 64], ids=repr)
def test_b14_a_malformed_logon_luid_refuses(world, value) -> None:
    world.token = replace(world.token, authentication_id=value)
    refused(world, C.SECURITY_FACT_UNAVAILABLE, "process token")


_SQUATTED = build_security_descriptor(X, [allow(X, 0xF037F), allow(A_LOGON, 0xF037F)], protected=False)


@pytest.mark.parametrize("mechanism", ["task_scheduler_s4u", "interactive_session"])
@pytest.mark.parametrize("field_name, value, match", [
    ("station_sd", _SQUATTED, "owned by"),
    ("station_sd", build_security_descriptor(LOCAL_SYSTEM, [allow(A_LOGON, 0xF037F), allow(USERS, 0x2)],
                                             protected=False), "WRITE"),
    ("station_sd", build_security_descriptor(LOCAL_SYSTEM, [allow(X_LOGON, 0xF037F)], protected=False),
     "execution"),
    ("station_sd", build_security_descriptor(O, [allow(A_LOGON, 0xF037F)], protected=False), "operator"),
    ("desktop_sd", build_security_descriptor(LOCAL_SYSTEM, [allow(A_LOGON, 0xF01FF), allow(X, 0x8)],
                                             protected=False), "desktop"),  # DESKTOP_HOOKCONTROL
    ("desktop_sd", build_security_descriptor(LOCAL_SYSTEM, [allow(EVERYONE, GENERIC_ALL)], protected=False),
     "desktop"),
    ("desktop_sd", build_security_descriptor(INTERACTIVE, [allow(A_LOGON, 0xF01FF)], protected=False),
     "owned by"),
], ids=["squatted-station", "users-on-station", "foreign-logon-on-station", "operator-owned-station",
        "x-hook-desktop", "everyone-desktop", "interactive-owned-desktop"])
def test_b14_x_or_o_able_to_use_the_station_or_desktop_refuses(world, mechanism, field_name, value, match) -> None:
    """Found in the FU1 self-review: the S4U name binding alone accepts a
    SID-less station that someone else created under A's name. What actually
    isolates A is that X and O can neither own nor open its station and
    desktop, so both are checked, for both launch mechanisms."""
    world.boundary["launch_mechanism"] = mechanism
    names = (A_STATION, False, None) if mechanism == "task_scheduler_s4u" else ("WinSta0", True, A_LOGON)
    world.session_facts = session(*names, "Default", A_LOGON)
    prove(world)
    world.session_facts = session(*names, "Default", A_LOGON, **{field_name: value})
    refused(world, C.SESSION_FOREIGN, match)


def test_b14_a_malformed_station_descriptor_refuses(world) -> None:
    world.session_facts = replace(world.session_facts, desktop_descriptor=b"\x01\x00")
    refused(world, C.DESCRIPTOR_UNSUPPORTED, "desktop")
    world.session_facts = replace(world.session_facts, desktop_descriptor="x")
    refused(world, C.SECURITY_FACT_UNAVAILABLE, "window station")


@pytest.mark.parametrize("name, is_dir", [
    ("version.dll", False), ("tool.exe", False), ("helper.dll", True),
], ids=["dll-file", "exe-file", "directory"])
def test_b15_a_reparse_entry_in_a_search_directory_refuses(world, name, is_dir) -> None:
    """B-15 (FU1 F3). The PATH directory is protected, but an entry directly
    in it is a link whose target X can write. A protected link does not make
    its target protected."""
    world.put(CLONE + "\\payload", is_dir=is_dir, owner=X, aces=[allow(X, MODIFY | WRITE_DAC)])
    link = world.put_child(SYSTEM32, name, is_dir=is_dir)
    link.reparse, link.target = True, CLONE + "\\payload"
    refused(world, C.OBJECT_REPARSE, name)


def test_b15_subdirectories_of_a_search_directory_are_classified_without_being_opened(world) -> None:
    """Found in the FU1 self-review, on this host: 13 subdirectories of the
    real System32 (``config`` among them) deny a standard user even
    READ_CONTROL. Opening every entry would refuse every real proof, so a
    subdirectory's reparse status comes from the listing, and it is never
    opened."""
    world.put_child(SYSTEM32, "config", is_dir=True)
    original = world.object_facts

    def denied(path):
        if ntpath.normcase(path) == ntpath.normcase(SYSTEM32 + "\\config"):
            raise PermissionError(13, "Access is denied")
        return original(path)

    world.object_facts = denied
    prove(world)
    world.node(SYSTEM32 + "\\config").reparse = True
    refused(world, C.OBJECT_REPARSE, "search_path[0]\\config")


def test_b15_a_reparse_point_reported_by_either_the_listing_or_the_handle_refuses(world) -> None:
    original = world.list_directory
    world.list_directory = lambda path: tuple(
        replace(e, is_reparse_point=True) if e.name in ("kernel32.dll", "abc.json") else e for e in original(path)
    )
    refused(world, C.OBJECT_REPARSE, "abc.json")  # a walked authority directory
    world.list_directory = lambda path: tuple(
        replace(e, is_reparse_point=True) if e.name == "kernel32.dll" else e for e in original(path)
    )
    refused(world, C.OBJECT_REPARSE, "kernel32.dll")  # a search directory
    world.node(SYSTEM32 + "\\kernel32.dll").reparse = True  # the handle says so, the listing does not
    world.list_directory = lambda path: tuple(replace(e, is_reparse_point=False) for e in original(path))
    refused(world, C.OBJECT_REPARSE, "kernel32.dll")


def test_b15_an_app_execution_alias_on_path_refuses(world) -> None:
    """Windows' own ``WindowsApps`` aliases are reparse points too; the
    dedicated authority account's PATH must not contain them."""
    world.code = replace(world.code, search_paths=(SYSTEM32, WINDOWSAPPS))
    refused(world, C.OBJECT_REPARSE, "winget.exe")


@windows_only
def test_b9_windows_follows_an_intermediate_junction_even_without_following_the_last(tmp_path) -> None:
    """The real API behaviour B-9 rests on."""
    import _winapi

    from ai_dev_orchestrator.integration.windows_security import WindowsSecurityFacts

    target = tmp_path / "target"
    (target / "child").mkdir(parents=True)
    _winapi.CreateJunction(str(target), str(tmp_path / "link"))
    info = WindowsSecurityFacts().object_facts(str(tmp_path / "link" / "child"))
    assert info.is_reparse_point is False
    assert ntpath.normcase(info.final_path) == ntpath.normcase(os.path.realpath(target / "child"))


_MUTATION_SIDS = [X, O, USERS, AUTH, EVERYONE, INTERACTIVE, NETWORK, X_LOGON, A, ADMINISTRATORS,
                  OWNER_RIGHTS, CREATOR_OWNER, f"{DOMAIN}-7000"]
_MUTATION_MASKS = [DELETE, WRITE_DAC, WRITE_OWNER, FILE_DELETE_CHILD, FILE_WRITE_DATA, FILE_ADD_SUBDIRECTORY,
                   FILE_WRITE_ATTRIBUTES, READ_CONTROL, RX, GENERIC_ALL, MODIFY, FILE_ALL_ACCESS]
_FD14_LIMITS = {  # declared root -> (execution limit, operator limit) on it and every descendant
    STATE: (0, 0), PUBLISHED: (0, RX), GIT: (RX, RX),
}


def _mutate(w: World, generator: random.Random) -> None:
    path = generator.choice(sorted(w.names.values()))
    node = w.node(path)
    action = generator.randrange(5)
    if action == 0:
        node.aces.insert(generator.randrange(len(node.aces) + 1), Ace(
            generator.choice((0, 0, 1)), generator.choice((0, OICI, IO | OICI, OI, CI)),
            generator.choice(_MUTATION_MASKS), generator.choice(_MUTATION_SIDS)))
    elif action == 1 and node.aces:
        node.aces.pop(generator.randrange(len(node.aces)))
    elif action == 2:
        node.owner = generator.choice((X, O, A, ADMINISTRATORS, USERS, LOCAL_SYSTEM))
    elif action == 3:
        node.protected = not node.protected
    else:
        node.links = generator.choice((1, 2))


def test_random_mutations_refuse_cleanly_or_still_satisfy_fd14() -> None:
    """A randomized counterexample search over the public entry point. Every
    mutated world must either be refused with an IdentityBoundaryError (never
    another exception), or — if accepted — still give X and O nothing beyond
    the FD-14 limits on every object of the authority plane and ``.git``,
    re-evaluated here object by object."""
    generator = random.Random(20261023)
    accepted = refused_count = 0
    for _ in range(400):
        w = good_world()
        for _ in range(generator.randint(1, 3)):
            _mutate(w, generator)
        try:
            proof = prove(w)
        except IdentityBoundaryError:
            refused_count += 1
            continue
        accepted += 1
        assert proof.boundary.authority.sid == A
        x = principal_x(excluded=A_LOGON)
        o = Principal("operator", O, x.allow_sids - {X} | {O}, x.deny_sids - {X} | {O}, A_LOGON)
        for root, (x_limit, o_limit) in _FD14_LIMITS.items():
            for key, node in w.nodes.items():
                if key == ntpath.normcase(root) or key.startswith(ntpath.normcase(root) + "\\"):
                    sd = parse_security_descriptor(node.descriptor())
                    kind = ObjectKind.DIRECTORY if node.is_dir else ObjectKind.FILE
                    assert upper_bound_rights(sd, x, kind) & ~x_limit == 0, (w.names[key], sd)
                    assert upper_bound_rights(sd, o, kind) & ~o_limit == 0, (w.names[key], sd)
        # FU1: no ancestor of a protected object can be re-permissioned, taken,
        # deleted or emptied by X or O.
        for root in (*_FD14_LIMITS, INBOX, EXCHANGE, CLONE, INSTALL, ANCHOR):
            chain = ib._components(root)
            for index, component in enumerate(chain[:-1]):
                sd = parse_security_descriptor(w.node(component).descriptor())
                for adversary in (x, o):
                    held = upper_bound_rights(sd, adversary, ObjectKind.DIRECTORY)
                    assert held & (WRITE_DAC | WRITE_OWNER | FILE_DELETE_CHILD) == 0, (component, root)
                    assert index == 0 or held & DELETE == 0, (component, root)
    assert refused_count > 100 and accepted > 20  # the search exercised both outcomes


def test_independent_evaluator_finding_more_is_honoured(world) -> None:
    """If AuthZ grants what the pure evaluator does not, the union refuses."""
    def evaluator(descriptor, principal, kind):
        sd = parse_security_descriptor(descriptor)
        return FILE_WRITE_DATA if principal.role == "execution" and sd.owner == A and kind is ObjectKind.DIRECTORY else 0

    world.independent = evaluator
    refused(world, C.OBJECT_RIGHTS, "execution")


# =============================================================================
# 9. facts-source misbehaviour and caller bypass attempts
# =============================================================================


def test_any_exception_from_the_facts_source_refuses(world) -> None:
    def broken(path):
        raise OSError(5, "Access is denied")

    world.object_facts = broken
    refused(world, C.SECURITY_FACT_UNAVAILABLE)


@pytest.mark.parametrize("bad", [
    {"is_directory": 1},
    {"link_count": 0},
    {"link_count": True},
    {"security_descriptor": "text"},
    {"final_path": b"C:\\x"},
])
def test_malformed_object_facts_refuse(world, bad) -> None:
    original = world.object_facts

    def lying(path):
        facts = original(path)
        if facts is None or ntpath.normcase(path) != ntpath.normcase(STATE):
            return facts
        return ObjectFacts(**{**facts.__dict__, **bad})

    world.object_facts = lying
    refused(world, C.SECURITY_FACT_UNAVAILABLE)


def test_an_object_facts_subclass_is_refused(world) -> None:
    class Lying(ObjectFacts):
        pass

    original = world.object_facts
    world.object_facts = lambda path: (lambda f: f and Lying(**f.__dict__))(original(path))
    refused(world, C.SECURITY_FACT_UNAVAILABLE)


@pytest.mark.parametrize("entries", [
    [DirectoryEntry("x", False, False)],
    (DirectoryEntry("..", True, False),),
    (DirectoryEntry("a\\b", False, False),),
    (DirectoryEntry("abc.json", False, False), DirectoryEntry("ABC.JSON", False, False)),
    (DirectoryEntry("abc.json", False, 0),),
    (("abc.json", False),),
])
def test_malformed_listings_refuse(world, entries) -> None:
    original = world.list_directory
    world.list_directory = lambda path: (
        entries if ntpath.normcase(path) == ntpath.normcase(STATE + "\\evidence\\verification")
        else original(path)
    )
    refused(world, C.SECURITY_FACT_UNAVAILABLE)


def test_a_listing_disagreeing_with_the_handle_refuses(world) -> None:
    original = world.list_directory
    world.list_directory = lambda path: tuple(
        DirectoryEntry(e.name, not e.is_dir, e.is_reparse_point) if ntpath.normcase(path) == ntpath.normcase(STATE) else e
        for e in original(path)
    )
    refused(world, C.SECURITY_FACT_UNAVAILABLE)


def test_a_principal_answer_for_another_sid_refuses(world) -> None:
    world.principals[X] = replace(world.principals[X], sid=O)
    refused(world, C.PRINCIPAL_UNVERIFIABLE)


@pytest.mark.parametrize("token_change", [
    {"groups": [("S-1-1-0", 7)]},
    {"groups": (("S-1-1-0", "7"),)},
    {"privileges": ["SeShutdownPrivilege"]},
    {"elevated": 0},
    {"user_sid": "S-1-5-21-01"},
    {"default_dacl": "x"},
])
def test_malformed_token_facts_refuse(world, token_change) -> None:
    world.token = replace(world.token, **token_change)
    refused(world, C.SECURITY_FACT_UNAVAILABLE)


@pytest.mark.parametrize("value", [None, 17, (1 << 32)])
def test_malformed_independent_results_refuse(world, value) -> None:
    if value is None:
        world.independent = lambda d, p, k: "x"
    else:
        world.independent = lambda d, p, k: value if p.role == "execution" else 0
    # 17 is READ_DATA|WRITE_EA: a well-formed result that the anchor check refuses first.
    category = C.SECURITY_FACT_UNAVAILABLE if value in (None, 1 << 32) else C.BOUNDARY_UNPROTECTED
    refused(world, category)


def test_production_origin_requires_the_independent_evaluator(world) -> None:
    with pytest.raises(IdentityBoundaryError) as info:
        ib._prove(world, origin="windows", expected_boundary_sha256=None, clock=lambda: FIXED_NOW)
    assert info.value.category is C.SECURITY_FACT_UNAVAILABLE and "AuthZ" in str(info.value)


def test_nothing_is_cached_between_proofs(world) -> None:
    prove(world)
    world.node(STATE + "\\evidence\\verification\\abc.json").aces.append(allow(X, FILE_WRITE_DATA))
    refused(world, C.OBJECT_RIGHTS)
    world.node(STATE + "\\evidence\\verification\\abc.json").aces.pop()
    world.boundary_raw = b"{}"
    refused(world, C.BOUNDARY_MALFORMED)


def test_each_proof_rereads_the_boundary(world) -> None:
    first = prove(world)
    world.boundary["launch_mechanism"] = "task_scheduler_s4u"
    world.session_facts = session(A_STATION, False, None, "Default", None)
    second = prove(world)
    assert first.boundary_sha256 != second.boundary_sha256
    refused(world, C.BOUNDARY_DIGEST_MISMATCH, expected_boundary_sha256=first.boundary_sha256)


def test_a_proof_cannot_be_constructed_mutated_subclassed_or_copied(world) -> None:
    proof = prove(world)
    with pytest.raises(TypeError):
        IdentityBoundaryProof(boundary=proof.boundary, boundary_sha256="0" * 64, facts_origin="windows",
                              independent_evaluation=True, proven_at=FIXED_NOW, objects_examined=1)
    with pytest.raises(TypeError):
        IdentityBoundaryProof(_token=object(), boundary=proof.boundary)
    with pytest.raises(AttributeError):
        proof.facts_origin = "windows"
    with pytest.raises(AttributeError):
        del proof.facts_origin
    with pytest.raises(TypeError):
        class Fake(IdentityBoundaryProof):  # noqa: F841
            pass
    for duplicate in (copy.copy, copy.deepcopy, pickle.dumps):
        with pytest.raises(TypeError):
            duplicate(proof)
    assert proof.is_production is False


def test_the_boundary_model_is_frozen(world) -> None:
    proof = prove(world)
    with pytest.raises(Exception):
        proof.boundary.authority = proof.boundary.execution


def test_a_facts_source_claiming_to_be_windows_never_yields_a_production_proof(world) -> None:
    world.independent = lambda d, p, k: upper_bound_rights(parse_security_descriptor(d), p, k)
    proof = prove(world)
    assert proof.facts_origin == "injected" and proof.independent_evaluation is True
    assert proof.is_production is False


def test_refusal_messages_do_not_echo_the_boundary_or_descriptor_bytes(world) -> None:
    world.boundary_raw = b'{"schema_version": "secret-value-123"}'
    error = refused(world, C.BOUNDARY_MALFORMED)
    assert "secret-value-123" not in str(error)


# =============================================================================
# 10. the production entry point
# =============================================================================


def test_the_production_prover_takes_no_facts_path_or_boundary() -> None:
    signature = inspect.signature(prove_identity_boundary)
    assert list(signature.parameters) == ["expected_boundary_sha256"]
    assert signature.parameters["expected_boundary_sha256"].kind is inspect.Parameter.KEYWORD_ONLY


def test_production_refuses_off_windows(monkeypatch) -> None:
    monkeypatch.setattr(ib.sys, "platform", "linux")
    with pytest.raises(IdentityBoundaryError) as info:
        prove_identity_boundary()
    assert info.value.category is C.PLATFORM_UNSUPPORTED


@windows_only
def test_production_refuses_here_before_touching_the_file_system(monkeypatch) -> None:
    """This development process holds a forbidden variable, so the live proof
    refuses at the environment check, before reading any object."""
    monkeypatch.setenv("PYTHONPATH", "x")
    from ai_dev_orchestrator.integration import windows_security

    touched: list[str] = []
    for name in ("object_facts", "read_file", "list_directory"):
        original = getattr(windows_security.WindowsSecurityFacts, name)
        monkeypatch.setattr(windows_security.WindowsSecurityFacts, name,
                            lambda self, *a, _o=original, _n=name: touched.append(_n) or _o(self, *a))
    with pytest.raises(IdentityBoundaryError) as info:
        prove_identity_boundary()
    assert info.value.category is C.ENVIRONMENT_UNSAFE
    assert "PYTHONPATH" in str(info.value)
    assert touched == []


@windows_only
def test_real_object_facts_are_read_from_one_handle(tmp_path) -> None:
    from ai_dev_orchestrator.integration.windows_security import WindowsSecurityFacts

    facts = WindowsSecurityFacts()
    token = facts.current_token()
    (tmp_path / "f.txt").write_bytes(b"x")
    for path, is_dir in ((tmp_path, True), (tmp_path / "f.txt", False)):
        info = facts.object_facts(str(path))
        assert info.is_directory is is_dir and info.is_reparse_point is False and info.link_count == 1
        assert ntpath.normcase(info.final_path) == ntpath.normcase(os.path.realpath(path))
        sd = parse_security_descriptor(info.security_descriptor)
        assert sd.owner in {token.user_sid} | {sid for sid, attrs in token.groups if attrs & 0x8}
    assert facts.object_facts(str(tmp_path / "missing")) is None
    data = facts.read_file(str(tmp_path / "f.txt"), 10)
    assert data[1] == b"x"
    names = {e.name: e.is_directory for e in facts.list_directory(str(tmp_path))}
    assert names == {"f.txt": False}


@windows_only
def test_real_facts_describe_a_junction_without_following_it(tmp_path) -> None:
    import _winapi

    from ai_dev_orchestrator.integration.windows_security import WindowsSecurityFacts

    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    _winapi.CreateJunction(str(target), str(link))
    info = WindowsSecurityFacts().object_facts(str(link))
    assert info.is_reparse_point is True and info.is_directory is True
    listed = {e.name: (e.is_directory, e.is_reparse_point) for e in WindowsSecurityFacts().list_directory(str(tmp_path))}
    assert listed == {"target": (True, False), "link": (True, True)}


@windows_only
def test_real_token_process_and_session_facts_are_well_formed() -> None:
    from ai_dev_orchestrator.integration.windows_security import WindowsSecurityFacts

    facts = WindowsSecurityFacts()
    token = facts.current_token()
    canonical_sid(token.user_sid)
    parse_acl(token.default_dacl)
    assert token.elevation_type in (1, 2, 3)
    assert type(token.authentication_id) is int and 0 < token.authentication_id < 2**64
    assert sum(1 for _, attrs in token.groups if attrs & 0xC0000000 == 0xC0000000) == 1
    process = facts.process()
    for raw in (process.process_descriptor, process.thread_descriptor, process.token_descriptor):
        assert parse_security_descriptor(raw).owner
    session = facts.session()
    assert session.window_station and session.desktop
    for raw in (session.window_station_descriptor, session.desktop_descriptor):
        assert parse_security_descriptor(raw).owner
    principal = facts.principal(token.user_sid)
    assert principal.sid == token.user_sid and principal.sid_type == 1
    assert ntpath.isabs(facts.program_data_directory())


# =============================================================================
# 11. static boundaries
# =============================================================================

_PACKAGE = Path(integration.__file__).resolve().parent
_MODULES = ("__init__.py", "security_descriptor.py", "boundary_facts.py", "windows_security.py",
            "identity_boundary.py")


def _tree(name: str) -> ast.AST:
    return ast.parse((_PACKAGE / name).read_text(encoding="utf-8"))


#: Added by DL-4B S1 (the attestation verifier); checked by its own suite.
_S1_MODULES = ("sshsig.py", "approver_registry.py", "attestation_verifier.py")
#: Added by DL-4B S2 (the integration store); checked by its own suite.
_S2_MODULES = ("integration_store.py", "integration_session.py")
_S3_MODULES = ("authority_files.py", "claim_readers.py", "claim_receiver.py", "exchange.py", "state_blobs.py",
               "workspace_observation.py", "write_handoff.py")
_S4_MODULES = ("execution_claim.py",)
#: Added by DL-4B S6 (the acceptance lifecycle); checked by its own suite.
_S6_MODULES = ("acceptance_bundle.py", "alpha_planner.py")


def test_the_package_has_exactly_the_s0_modules() -> None:
    assert sorted(p.name for p in _PACKAGE.glob("*.py")) == sorted(
        _MODULES + _S1_MODULES + _S2_MODULES + _S3_MODULES + _S4_MODULES + _S6_MODULES)


def test_no_execution_network_model_git_or_harness_surface() -> None:
    forbidden_modules = {"subprocess", "socket", "httpx", "requests", "aiohttp", "urllib", "http",
                         "asyncio", "multiprocessing", "shutil", "tempfile", "winreg", "_winapi"}
    forbidden_names = {"Popen", "max_tokens", "system", "popen", "startfile", "spawnv", "execv",
                       "remove", "unlink", "rename", "replace", "rmdir", "mkdir", "makedirs",
                       "chmod", "putenv", "unsetenv", "kill", "rmtree", "write_text", "write_bytes"}
    forbidden_win32 = ("SetSecurityInfo", "SetNamedSecurityInfo", "SetFileSecurity", "SetKernelObjectSecurity",
                       "SetTokenInformation", "AdjustTokenPrivileges", "CreateProcess", "LogonUser",
                       "ImpersonateLoggedOnUser", "DuplicateToken", "NetUserAdd", "NetLocalGroupAdd",
                       "DeleteFile", "MoveFile", "ReplaceFile", "WriteFile", "CreateDirectory",
                       "RemoveDirectory", "RegSetValue", "CreateToolhelp32Snapshot", "OpenProcess(",
                       "TerminateProcess", "ShellExecute", "WinExec", "SetEnvironmentVariable")
    harness_prefixes = ("ai_dev_orchestrator.llm", "ai_dev_orchestrator.github", "ai_dev_orchestrator.review",
                        "ai_dev_orchestrator.verification", "ai_dev_orchestrator.file_editing",
                        "ai_dev_orchestrator.supervised_implementer", "ai_dev_orchestrator.workspace",
                        "ai_dev_orchestrator.cli", "ai_dev_orchestrator.control_plane")
    for name in _MODULES:
        source = (_PACKAGE / name).read_text(encoding="utf-8")
        tree = _tree(name)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {alias.name for alias in node.names}
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
        assert not {m.split(".")[0] for m in imported} & forbidden_modules, (name, imported)
        assert not [m for m in imported if m.startswith(harness_prefixes)], (name, imported)
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        names |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        assert not names & forbidden_names, (name, names & forbidden_names)
        assert "open" not in {n.func.id for n in ast.walk(tree)
                              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}, name
        for call in forbidden_win32:
            assert call not in source, (name, call)


def test_every_dll_is_loaded_from_system32_only() -> None:
    tree = _tree("windows_security.py")
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Attribute) and n.func.attr in ("WinDLL", "CDLL", "LoadLibrary", "OleDLL")]
    assert len(calls) == 1
    winmode = {kw.arg: kw.value for kw in calls[0].keywords}["winmode"]
    assert isinstance(winmode, ast.Name) and winmode.id == "_LOAD_LIBRARY_SEARCH_SYSTEM32"
    assert ib.__dict__.get("_LOAD_LIBRARY_SEARCH_SYSTEM32") is None
    from ai_dev_orchestrator.integration import windows_security

    assert windows_security._LOAD_LIBRARY_SEARCH_SYSTEM32 == 0x800


def test_only_the_production_entry_point_can_mint_a_windows_origin() -> None:
    tree = _tree("identity_boundary.py")
    windows_literals = []
    for function in ast.walk(tree):
        if isinstance(function, ast.FunctionDef):
            for node in ast.walk(function):
                if isinstance(node, ast.Constant) and node.value == "windows":
                    windows_literals.append(function.name)
    # The literal appears in _prove's own signature and check, in the proof's
    # property, and in the one production call.
    assert set(windows_literals) == {"_prove", "is_production", "prove_identity_boundary"}
    source = inspect.getsource(ib.prove_identity_boundary)
    assert "WindowsSecurityFacts()" in source and 'origin="windows"' in source
    assert 'origin="injected"' in inspect.getsource(ib.prove_identity_boundary_from_facts)


def test_the_boundary_location_is_a_code_constant() -> None:
    assert (ib.BOUNDARY_DIRECTORY_NAME, ib.BOUNDARY_FILE_NAME) == ("AIDO", "identity-boundary.v1.json")
    tree = _tree("identity_boundary.py")
    attributes = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert not attributes & {"environ", "getenv", "environb"}


def test_no_cli_command_and_no_control_plane_module_reaches_s0() -> None:
    root = _PACKAGE.parent
    cli = (root / "cli.py").read_text(encoding="utf-8")
    for term in ("ai_dev_orchestrator.integration", "identity_boundary", "windows_security",
                 "prove_identity_boundary"):
        assert term not in cli
    for module in (root / "control_plane").glob("*.py"):
        assert "ai_dev_orchestrator.integration" not in module.read_text(encoding="utf-8"), module.name
