"""F5-A A2 -- the run-provisioned Pi runtime (L3R), OFFLINE CANDIDATE.

Design: ``docs/PHASE_5F3B_CFG1_F5A_LIVE_LAUNCH_AUTHORITY_AMENDMENT.md`` Sec. 7
(A2-R1 topology, Sec. 7.4A destination write authority, Sec. 7.4B
verify-before-persist), with ONE mechanism replaced, as recorded in the
non-frozen ``docs/PHASE_5F3B_CFG1_F5A_A2_OFFLINE_IMPLEMENTATION_CANDIDATE.md``:
Sec. 7.4A.2's pathname ``CreateDirectoryW``-then-pin and pathname
``CreateFileW(CREATE_NEW)`` are replaced by ONE handle-relative
``NtCreateFile(RootDirectory = <held parent>, <one component>, FILE_CREATE)``
per child. R1-FU3 (8343db1) measured that an attribute-only open converts an
EMPTY pinned directory into a junction under every share mode, after which a
PATHNAME create beneath it lands outside the run root before any gate runs.
A handle-relative create is resolved against the parent OBJECT, not a name.

**Status, stated exactly.** This module is NOT security-qualified, F5-A is NOT
frozen, and nothing here authorizes a launch. F5A-INT wired it into
:mod:`pi_harness_cfg1.run_executor` OFFLINE ONLY (the L3R step, the L14
precondition :func:`reprove_provision_for_launch`, the L27-entry release and
the derived release fact): the executor's genuine default binding is
:func:`live_runtime_provisioning_not_qualified`, which refuses before any
I/O, and only an explicitly composed offline port set binds
:func:`admit_runtime_provision_for_source`. The containment of a
handle-relative create beneath a CONVERTED parent rests on the FU4-A2
measurements (A2-3 INCOMPLETE, no racing-conversion measurement, one host, one
build) and is NOT established by this code or its tests.

**Authority (FU1).** The only way to obtain write authority is a workspace
CFG1's own registry minted (:class:`run_workspace.Cfg1RunWorkspace`), re-proved
by ``verify_cfg1_run_workspace``; the run root and its identity are DERIVED from
it, never supplied. The profile must be an eligible profile of the sealed HPP-1
snapshot and the inventory's content-derived fingerprint must equal that
profile's loader-bound one. Both are consumed at admission AND again immediately
before the first create (:func:`_consume_authority`). The private creation
primitives remain private: no public callable accepts a path, parent or
identity to write under. This is NOT a claim that the executor binds the
workspace to a claimed run (``claim_cfg1_run_workspace``): that, and the sealed
snapshot read at executor level, are integration obligations.

**Lifecycle (FU1).** One non-blocking guard per provision is held for the whole
of :func:`run_runtime_provision` and for :func:`release_at_l27_entry`, so a run
and a release can never own the same handles (cross-thread or re-entrant), a
second run is refused, and release is exactly once.

**What this module guarantees by construction (static, not empirical):**

* no pathname-based creation exists here -- the only creating call is the
  handle-relative native create, and there is no fallback of any kind;
* every child name is exactly one PI-PC1 path segment, checked before the
  native call (A2-4 measured a multi-component name escaping via a junction);
* the parent of every create is a directory entry of THIS provision's own
  ledger, still ``OPEN`` -- never a caller-supplied handle or path;
* every handle is entered in the ledger immediately after the call that
  produced it, before any check that can fail;
* no content byte is written to a file before its directory's exact-set
  parentage gate has passed, and only verified approved bytes are written
  (Sec. 7.4B), only through the file's own creating handle;
* L3R deletes nothing, by pathname or by handle disposition; there is no
  delete, rename or truncate call in this module.

Nothing here is a statement that the copy is secure, isolated or sandboxed, and
nothing here addresses hard-link aliasing of a created file (R-ALIAS, which
stays UNRESOLVED; see the candidate document).
"""

from __future__ import annotations

import hashlib
import ntpath
import secrets
import sys
import threading

from pi_harness_cfg1 import pi_fs_leaves as _leaves
from pi_harness_cfg1 import pi_identity as _identity
from pi_harness_cfg1 import pi_payload as _payload
from pi_harness_cfg1 import run_workspace as _workspace

PLATFORM_SUPPORTED = sys.platform == "win32"

#: The one refusal code an L3R failure maps to (amendment Sec. 11.1); the
#: executor records it in the v3 run record only (``records`` R3-S15).
RUNTIME_PROVISIONING_FAILED = "RUNTIME_PROVISIONING_FAILED"

#: Fixed topology (amendment Sec. 7.2). Constants, never parameters.
RUNTIME_DIR_NAME = "pi_runtime"
PACKAGE_DIR_NAME = "pi-coding-agent"
_NODE_MODULES = "node_modules"
_BUN_MARKERS = ("$bunfs", "~bun", "%7ebun")

#: The Launch Derivation Table (amendment Sec. 7.3), keyed by profile id.
LAUNCH_DERIVATION_TABLE = {
    "56651d0b2b6995e05b6de3aa012f5a82f276b2ac817dcce00844d1db2a9ffd67": {
        "quarantine_rule": "NO_NODE_MODULES_ANCESTOR_MEANS_NO_TARGET",
        "derivation_chain": ("dist/cli.js", "dist/main.js", "dist/config.js"),
        "package_manifest": "package.json",
        "forbidden_path_substrings": _BUN_MARKERS,
        "withheld_env": ("PI_PACKAGE_DIR", "PI_MANAGED_INSTALL_ROOT"),
    },
}

#: Provision lifecycle (amendment Sec. 15.1), as far as this candidate reaches.
STATE_ADMITTED = "ADMITTED"
STATE_ATTEMPTED = "ATTEMPTED"
STATE_SOURCE_PROVEN = "SOURCE_PROVEN"
STATE_CHAIN_CREATED = "CHAIN_CREATED"
STATE_POPULATED = "POPULATED"
STATE_PINNED = "PINNED"
STATE_PROVEN = "PROVEN"
#: Executor integration (F5A-INT): the launch identity ``L`` is recorded.
STATE_BOUND = "BOUND"
STATE_REFUSED = "REFUSED"
STATE_FAILED_UNEXPECTED = "FAILED_UNEXPECTED"

#: Handle-ledger entry states (amendment Sec. 7.4A.5). ``CLOSE_FAILED`` is
#: terminal: never retried, forced, or re-derived from a name.
HANDLE_OPEN = "OPEN"
HANDLE_CLOSED = "CLOSED"
HANDLE_CLOSE_FAILED = "CLOSE_FAILED"

_KIND_DIRECTORY = "directory"
_KIND_FILE = "file"
_KIND_FINAL_PIN = "final_read_only_pin"


class Cfg1RuntimeProvisionError(Exception):
    """An L3R step refused. Always ``RUNTIME_PROVISIONING_FAILED``.

    ``reason_code`` is closed. No message carries a path, a handle value, an
    NTSTATUS, an observed digest, size or byte. ``entry_path`` is set only for a
    source-verification refusal and is the APPROVED payload-relative path of the
    inventory entry (Sec. 7.4B), never anything observed.
    """

    refusal_code = RUNTIME_PROVISIONING_FAILED

    def __init__(self, reason_code: str, *, entry_path: str | None = None) -> None:
        super().__init__(f"runtime provisioning refused: {reason_code}")
        self.reason_code = reason_code
        self.entry_path = entry_path


def _refuse(reason_code: str, *, entry_path: str | None = None):
    raise Cfg1RuntimeProvisionError(reason_code, entry_path=entry_path)


# ---------------------------------------------------------------------------
# Names and topology (pure; no I/O)
# ---------------------------------------------------------------------------


def require_single_component(name: object) -> str:
    """Exactly ONE PI-PC1 path segment, or refuse BEFORE any native call.

    PI-PC1's segment grammar (``pi_payload.segment_is_valid``) already excludes
    every separator (``\\``, ``/``), the stream separator ``:``, wildcards,
    control characters and NUL, lone surrogates, ``.``/``..``, a trailing dot or
    space, reserved device stems and over-long segments. A name that passes it
    cannot address anything but one entry of the directory it is resolved in.
    """
    if type(name) is not str or not _payload.segment_is_valid(name):
        _refuse("NAME_NOT_A_SINGLE_COMPONENT")
    return name


def lexical_topology_refusal(path: object) -> str | None:
    """T-CANON, T-NM and T-BUN over one lexical path (amendment Sec. 7.2).

    Returns the closed reason, or ``None``. Pure string analysis: no I/O.
    """
    if type(path) is not str or len(path) < 4:
        return "TOPOLOGY_NOT_CANONICAL"
    drive, rest = path[:3], path[3:]
    if not (drive[0].isascii() and drive[0].isalpha() and drive[1:] == ":\\"):
        return "TOPOLOGY_NOT_CANONICAL"
    if "/" in path or ntpath.normpath(path) != path:
        return "TOPOLOGY_NOT_CANONICAL"
    components = rest.split("\\")
    for component in components:
        if not component or component in (".", "..") or component.endswith((".", " ")):
            return "TOPOLOGY_NOT_CANONICAL"
        if component.lower() == _NODE_MODULES or component.casefold() == _NODE_MODULES:
            return "TOPOLOGY_NODE_MODULES_ANCESTOR"
    for folded in (path.lower(), path.casefold()):
        if any(marker in folded for marker in _BUN_MARKERS):
            return "TOPOLOGY_BUN_MARKER"
    return None


def _chain_prefixes(path: str) -> list[str]:
    """Every proper prefix from the volume root's first child through ``path``."""
    components = path[3:].split("\\")
    return [path[:3] + "\\".join(components[: index + 1]) for index in range(len(components))]


def _payload_tree(inventory) -> dict[str, tuple[list, list]]:
    """``dir_relative_path -> ([(name, rel, sha256, size)], [(name, rel)])``.

    ``""`` is the package root ``C``. Built only from a validated
    :class:`~pi_harness_cfg1.pi_payload.PayloadInventory`, whose grammar,
    ordering, case-fold uniqueness and tree closure are already enforced.
    """
    tree: dict[str, tuple[list, list]] = {"": ([], [])}
    for entry in inventory.entries:
        if entry[0] == _payload.INVENTORY_KIND_DIR:
            tree[entry[1]] = ([], [])
    for entry in inventory.entries:
        relative = entry[1]
        index = relative.rfind("/")
        parent = "" if index < 0 else relative[:index]
        name = relative[index + 1 :]
        if entry[0] == _payload.INVENTORY_KIND_DIR:
            tree[parent][1].append((name, relative))
        else:
            tree[parent][0].append((name, relative, entry[2], entry[3]))
    return tree


def construction_handle_peak(inventory) -> int:
    """The ledger's peak OPEN count for a successful construction of ``inventory``.

    A pure simulation of :func:`run_runtime_provision`'s order: the run-root pin,
    ``RT`` and ``C`` are held throughout; in each directory every file child and
    every directory child is created and held, the gate runs, each file is
    completed and closed, then each directory child is built in turn and closed.
    So the peak is the current ancestry plus the pending sibling pins plus the
    current directory's files (amendment Sec. 7.4A.6's accounting).
    """
    if type(inventory) is not _payload.PayloadInventory:
        _refuse("MALFORMED_INPUT")
    tree = _payload_tree(inventory)
    peak = 0

    def build(relative: str, held: int) -> None:
        nonlocal peak
        files, dirs = tree[relative]
        held += len(files) + len(dirs)
        peak = max(peak, held)
        held -= len(files)
        for _name, child in dirs:
            build(child, held)
            held -= 1

    # R pin, RT, C are held before build(C) starts.
    peak = 3
    build("", 3)
    return peak


# ---------------------------------------------------------------------------
# The Win32 / native layer -- this module's OWN thin layer (amendment Sec.
# 7.4A.5: it neither imports nor mints any ``win_config_authority`` type).
# ---------------------------------------------------------------------------

if PLATFORM_SUPPORTED:  # pragma: no branch - a platform constant
    import ctypes
    import ctypes.wintypes as _wt

    _K32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _K32.CreateFileW.restype = _wt.HANDLE
    _K32.CreateFileW.argtypes = [
        _wt.LPCWSTR, _wt.DWORD, _wt.DWORD, ctypes.c_void_p, _wt.DWORD, _wt.DWORD, _wt.HANDLE,
    ]
    _K32.CloseHandle.restype = _wt.BOOL
    _K32.CloseHandle.argtypes = [_wt.HANDLE]
    _K32.GetFileInformationByHandleEx.restype = _wt.BOOL
    _K32.GetFileInformationByHandleEx.argtypes = [_wt.HANDLE, ctypes.c_int, ctypes.c_void_p, _wt.DWORD]
    _K32.GetFileType.restype = _wt.DWORD
    _K32.GetFileType.argtypes = [_wt.HANDLE]
    _K32.WriteFile.restype = _wt.BOOL
    _K32.WriteFile.argtypes = [_wt.HANDLE, ctypes.c_char_p, _wt.DWORD, ctypes.POINTER(_wt.DWORD), ctypes.c_void_p]
    _K32.ReadFile.restype = _wt.BOOL
    _K32.ReadFile.argtypes = [_wt.HANDLE, ctypes.c_void_p, _wt.DWORD, ctypes.POINTER(_wt.DWORD), ctypes.c_void_p]
    _K32.SetFilePointerEx.restype = _wt.BOOL
    _K32.SetFilePointerEx.argtypes = [_wt.HANDLE, ctypes.c_longlong, ctypes.c_void_p, _wt.DWORD]
    _K32.FlushFileBuffers.restype = _wt.BOOL
    _K32.FlushFileBuffers.argtypes = [_wt.HANDLE]

    _INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

    class _UNICODE_STRING(ctypes.Structure):
        _fields_ = [("Length", ctypes.c_ushort), ("MaximumLength", ctypes.c_ushort), ("Buffer", ctypes.c_wchar_p)]

    class _OBJECT_ATTRIBUTES(ctypes.Structure):
        _fields_ = [
            ("Length", ctypes.c_ulong),
            ("RootDirectory", _wt.HANDLE),
            ("ObjectName", ctypes.POINTER(_UNICODE_STRING)),
            ("Attributes", ctypes.c_ulong),
            ("SecurityDescriptor", ctypes.c_void_p),
            ("SecurityQualityOfService", ctypes.c_void_p),
        ]

    class _IO_STATUS_BLOCK(ctypes.Structure):
        _fields_ = [("Status", ctypes.c_void_p), ("Information", ctypes.c_size_t)]

    class _FILE_ID_128(ctypes.Structure):
        _fields_ = [("Identifier", ctypes.c_ubyte * 16)]

    class _FILE_ID_INFO(ctypes.Structure):
        _fields_ = [("VolumeSerialNumber", ctypes.c_ulonglong), ("FileId", _FILE_ID_128)]

    class _FILE_ATTRIBUTE_TAG_INFO(ctypes.Structure):
        _fields_ = [("FileAttributes", _wt.DWORD), ("ReparseTag", _wt.DWORD)]

    class _FILE_STANDARD_INFO(ctypes.Structure):
        _fields_ = [
            ("AllocationSize", ctypes.c_longlong),
            ("EndOfFile", ctypes.c_longlong),
            ("NumberOfLinks", _wt.DWORD),
            ("DeletePending", ctypes.c_ubyte),
            ("Directory", ctypes.c_ubyte),
        ]

    class _FILE_ID_EXTD_DIR_INFO(ctypes.Structure):
        _fields_ = [
            ("NextEntryOffset", ctypes.c_ulong),
            ("FileIndex", ctypes.c_ulong),
            ("CreationTime", ctypes.c_longlong),
            ("LastAccessTime", ctypes.c_longlong),
            ("LastWriteTime", ctypes.c_longlong),
            ("ChangeTime", ctypes.c_longlong),
            ("EndOfFile", ctypes.c_longlong),
            ("AllocationSize", ctypes.c_longlong),
            ("FileAttributes", ctypes.c_ulong),
            ("FileNameLength", ctypes.c_ulong),
            ("EaSize", ctypes.c_ulong),
            ("ReparsePointTag", ctypes.c_ulong),
            ("FileId", _FILE_ID_128),
            ("FileName", ctypes.c_wchar * 1),
        ]

    _ENTRY_HEADER_BYTES = _FILE_ID_EXTD_DIR_INFO.FileName.offset

# Access, share and option values (winnt.h / winternl.h / ntifs.h).
_GENERIC_READ = 0x80000000
_GENERIC_WRITE = 0x40000000
_DELETE = 0x00010000
_SYNCHRONIZE = 0x00100000
_FILE_LIST_DIRECTORY = 0x00000001
_FILE_READ_ATTRIBUTES = 0x00000080
_FILE_SHARE_READ = 0x00000001
_FILE_SHARE_WRITE = 0x00000002
_OPEN_EXISTING = 3
_FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
_FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
_FILE_ATTRIBUTE_DIRECTORY = 0x00000010
_FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
_FILE_ATTRIBUTE_NORMAL = 0x00000080
_FILE_TYPE_DISK = 0x0001
_FileStandardInfo = 1
_FileAttributeTagInfo = 9
_FileIdInfo = 18
_FileIdExtdDirectoryInfo = 19
_ERROR_NO_MORE_FILES = 18
_ENUMERATION_BUFFER_BYTES = 64 * 1024
_IO_CHUNK_BYTES = 1 << 20

_STATUS_SUCCESS = 0x00000000
_FILE_CREATE = 0x00000002  # CreateDisposition
_FILE_CREATED = 0x00000002  # IO_STATUS_BLOCK.Information
_FILE_DIRECTORY_FILE = 0x00000001
_FILE_SYNCHRONOUS_IO_NONALERT = 0x00000020
_FILE_NON_DIRECTORY_FILE = 0x00000040
_FILE_OPEN_REPARSE_POINT = 0x00200000
_OBJ_CASE_INSENSITIVE = 0x00000040

#: The two create shapes. Directory: list + read-attributes, share READ only
#: (no WRITE, no DELETE): the created handle IS the directory's construction
#: pin, with no create-then-pin interval. File: Sec. 7.4A.2 step 1's access,
#: share 0. Both open the created object itself, never a reparse target.
_DIRECTORY_SHAPE = (
    _FILE_LIST_DIRECTORY | _FILE_READ_ATTRIBUTES | _SYNCHRONIZE,
    _FILE_SHARE_READ,
    _FILE_DIRECTORY_FILE | _FILE_SYNCHRONOUS_IO_NONALERT | _FILE_OPEN_REPARSE_POINT,
)
_FILE_SHAPE = (
    _GENERIC_READ | _GENERIC_WRITE | _DELETE | _SYNCHRONIZE,
    0,
    _FILE_NON_DIRECTORY_FILE | _FILE_SYNCHRONOUS_IO_NONALERT | _FILE_OPEN_REPARSE_POINT,
)


def _resolve_native_create():
    """``ntdll!NtCreateFile`` on this module's own DLL object, or ``None``.

    ``None`` refuses provisioning. There is no alternative creation path.
    """
    if not PLATFORM_SUPPORTED:
        return None
    try:
        function = ctypes.WinDLL("ntdll").NtCreateFile
    except (OSError, AttributeError):
        return None
    function.restype = ctypes.c_long
    function.argtypes = [
        ctypes.POINTER(_wt.HANDLE), ctypes.c_ulong, ctypes.POINTER(_OBJECT_ATTRIBUTES),
        ctypes.POINTER(_IO_STATUS_BLOCK), ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong,
        ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong,
    ]
    return function


def _close_raw_handle(raw: int) -> bool:
    """ONE ``CloseHandle``. The ledger is the only caller."""
    return bool(_K32.CloseHandle(raw))


def _raw_identity(raw: int) -> tuple[int, int]:
    info = _FILE_ID_INFO()
    if not _K32.GetFileInformationByHandleEx(raw, _FileIdInfo, ctypes.byref(info), ctypes.sizeof(info)):
        _refuse("HANDLE_PROOF_UNREADABLE")
    return int(info.VolumeSerialNumber), int.from_bytes(bytes(info.FileId.Identifier), "little")


def _raw_attributes(raw: int) -> tuple[int, int]:
    info = _FILE_ATTRIBUTE_TAG_INFO()
    if not _K32.GetFileInformationByHandleEx(raw, _FileAttributeTagInfo, ctypes.byref(info), ctypes.sizeof(info)):
        _refuse("HANDLE_PROOF_UNREADABLE")
    return int(info.FileAttributes), int(info.ReparseTag)


def _raw_end_of_file(raw: int) -> int:
    info = _FILE_STANDARD_INFO()
    if not _K32.GetFileInformationByHandleEx(raw, _FileStandardInfo, ctypes.byref(info), ctypes.sizeof(info)):
        _refuse("HANDLE_PROOF_UNREADABLE")
    return int(info.EndOfFile)


def _raw_is_plain(raw: int, kind: str) -> bool:
    """Kind and absence of any reparse attribute/tag, FROM THE HANDLE."""
    attributes, tag = _raw_attributes(raw)
    if attributes & _FILE_ATTRIBUTE_REPARSE_POINT or tag != 0:
        return False
    if _K32.GetFileType(raw) != _FILE_TYPE_DISK:
        return False
    return bool(attributes & _FILE_ATTRIBUTE_DIRECTORY) == (kind == _KIND_DIRECTORY)


def _raw_enumerate_once(raw: int) -> tuple[tuple[str, int, int, int], ...]:
    """Every ``(name, file_id, attributes, reparse_tag)`` FROM THE HANDLE.

    One pass; the cursor is per handle and does not restart (W9), so a
    directory handle is enumerated exactly once and the result is kept.
    """
    buffer = ctypes.create_string_buffer(_ENUMERATION_BUFFER_BYTES)
    base = ctypes.addressof(buffer)
    entries: list[tuple[str, int, int, int]] = []
    while True:
        if not _K32.GetFileInformationByHandleEx(raw, _FileIdExtdDirectoryInfo, buffer, ctypes.sizeof(buffer)):
            if ctypes.get_last_error() == _ERROR_NO_MORE_FILES:
                return tuple(entries)
            _refuse("ENUMERATION_FAILED")
        offset = 0
        while True:
            entry = _FILE_ID_EXTD_DIR_INFO.from_buffer(buffer, offset)
            name = ctypes.wstring_at(base + offset + _ENTRY_HEADER_BYTES, entry.FileNameLength // 2)
            entries.append(
                (
                    name,
                    int.from_bytes(bytes(entry.FileId.Identifier), "little"),
                    int(entry.FileAttributes),
                    int(entry.ReparsePointTag),
                )
            )
            if entry.NextEntryOffset == 0:
                break
            offset += entry.NextEntryOffset


def _raw_write_all(raw: int, data: bytes) -> bool:
    view = memoryview(data)
    offset = 0
    while offset < len(data):
        chunk = bytes(view[offset : offset + _IO_CHUNK_BYTES])
        written = _wt.DWORD(0)
        if not _K32.WriteFile(raw, chunk, len(chunk), ctypes.byref(written), None) or written.value <= 0:
            return False
        offset += written.value
    return bool(_K32.FlushFileBuffers(raw))


def _raw_read_from_start(raw: int, limit: int) -> bytes | None:
    """Rewind THE SAME handle and read at most ``limit`` bytes."""
    if not _K32.SetFilePointerEx(raw, 0, None, 0):
        return None
    chunks: list[bytes] = []
    total = 0
    buffer = ctypes.create_string_buffer(_IO_CHUNK_BYTES)
    while total < limit:
        want = min(_IO_CHUNK_BYTES, limit - total)
        got = _wt.DWORD(0)
        if not _K32.ReadFile(raw, buffer, want, ctypes.byref(got), None):
            return None
        if got.value == 0:
            break
        chunks.append(buffer.raw[: got.value])
        total += got.value
    return b"".join(chunks)


# ---------------------------------------------------------------------------
# The handle ledger -- provisioning-only, non-transferable
# ---------------------------------------------------------------------------

_LEDGER_KEY = object()


class _LedgerEntry:
    """One OS handle this provision acquired. The raw value never leaves here."""

    __slots__ = ("owner", "raw", "kind", "state", "identity", "name", "gate_passed", "content_written")

    def __init__(self, owner: "_HandleLedger", raw: int, kind: str) -> None:
        self.owner = owner
        self.raw = raw
        self.kind = kind
        self.state = HANDLE_OPEN
        self.identity: tuple[int, int] | None = None
        self.name: str | None = None
        self.gate_passed = False
        self.content_written = False

    def __repr__(self) -> str:  # noqa: D105 - handles and names never rendered
        return f"_LedgerEntry({self.kind!r}, {self.state!r})"


class _HandleLedger:
    """Amendment Sec. 7.4A.5: entered at acquisition; ``OPEN -> CLOSED |
    CLOSE_FAILED``; ``CloseHandle`` is called only from ``OPEN``, once."""

    __slots__ = ("_entries", "_open", "peak_open", "_kinds")

    def __init__(self, key: object, kinds: frozenset[str]) -> None:
        if key is not _LEDGER_KEY:
            _refuse("LEDGER_NOT_MINTED_HERE")
        self._entries: list[_LedgerEntry] = []
        self._open = 0
        self.peak_open = 0
        self._kinds = kinds

    def __repr__(self) -> str:  # noqa: D105
        return f"_HandleLedger(entries={len(self._entries)}, open={self._open})"

    def enter(self, raw: object, kind: str) -> _LedgerEntry:
        """Record a just-acquired raw handle. Called before ANY check on it."""
        if type(raw) is not int or raw == 0 or kind not in self._kinds:
            _refuse("LEDGER_ENTRY_MALFORMED")
        entry = _LedgerEntry(self, raw, kind)
        self._entries.append(entry)
        self._open += 1
        self.peak_open = max(self.peak_open, self._open)
        return entry

    def raw_handle(self, entry: object, kind: str) -> int:
        """The raw handle of an OPEN entry of THIS ledger, of exactly ``kind``.

        The only way any creating, enumerating or writing call obtains a handle:
        a raw integer, a closed entry, another provision's entry or an entry of
        the wrong kind is refused, so no caller can inject a parent.
        """
        if (
            type(entry) is not _LedgerEntry
            or entry.owner is not self
            or entry.state != HANDLE_OPEN
            or entry.kind != kind
        ):
            _refuse("PARENT_HANDLE_NOT_AUTHORITATIVE")
        return entry.raw

    def close(self, entry: _LedgerEntry) -> bool:
        """Close once from ``OPEN``. Never raises; a failure is terminal."""
        if type(entry) is not _LedgerEntry or entry.owner is not self:
            return False
        if entry.state != HANDLE_OPEN:
            return entry.state == HANDLE_CLOSED
        try:
            closed = _close_raw_handle(entry.raw)
        except Exception:  # noqa: BLE001 - a raising close is a failed close
            closed = False
        entry.state = HANDLE_CLOSED if closed else HANDLE_CLOSE_FAILED
        self._open -= 1
        return closed

    def close_all(self) -> None:
        """Close every ``OPEN`` entry, most recently acquired first.

        Every object is acquired after the directory that contains it, so
        reverse acquisition order closes children before their directories,
        deepest first. Never raises.
        """
        for entry in reversed(self._entries):
            if entry.state == HANDLE_OPEN:
                self.close(entry)

    @property
    def open_count(self) -> int:
        return self._open

    @property
    def entry_count(self) -> int:
        return len(self._entries)

    def all_proven_closed(self) -> bool:
        """``True`` iff every entry is ``CLOSED`` (vacuously, when there is none)."""
        return all(entry.state == HANDLE_CLOSED for entry in self._entries)

    def any_close_failed(self) -> bool:
        return any(entry.state == HANDLE_CLOSE_FAILED for entry in self._entries)


# ---------------------------------------------------------------------------
# The provision object
# ---------------------------------------------------------------------------

_PROVISION_KEY = object()

#: Nonces of admitted provisions that have not yet been run. Running consumes
#: the nonce, so a provision runs at most once and a copy cannot run at all.
_ADMITTED_NONCES: set[str] = set()


class RuntimeProvision:
    """One run's provisioning attempt. Constructible only by
    :func:`admit_runtime_provision`; never copied, pickled, or rendered with a
    handle. Holds no authority outside this module: it is accepted by no
    config-issuance, generation-interval, retained-authority or
    extension-issuance consumer, and is not a launch identity."""

    __slots__ = (
        "_nonce",
        "_state",
        "_reason",
        "_workspace",
        "_run_root",
        "_run_root_identity",
        "_profile_id",
        "_inventory",
        "_source_root",
        "_construction",
        "_final_pins",
        "_created_identity",
        "_package_root_identity",
        "_guard",
        "_released",
        "_launch_identity",
    )

    def __init__(self, key: object, **values) -> None:
        if key is not _PROVISION_KEY:
            _refuse("PROVISION_NOT_MINTED_HERE")
        object.__setattr__(self, "_nonce", secrets.token_hex(16))
        object.__setattr__(self, "_state", STATE_ADMITTED)
        object.__setattr__(self, "_reason", None)
        for name, value in values.items():
            object.__setattr__(self, name, value)
        object.__setattr__(self, "_construction", None)
        object.__setattr__(self, "_final_pins", None)
        object.__setattr__(self, "_created_identity", {})
        object.__setattr__(self, "_package_root_identity", None)
        object.__setattr__(self, "_run_root_identity", None)
        # Lifecycle exclusion (A2 FU1, Finding B): held, non-blocking, for the
        # WHOLE of a run and for a release -- so the two can never own the same
        # handles, whether racing from another thread or re-entering from a
        # callback on the running thread.
        object.__setattr__(self, "_guard", threading.Lock())
        object.__setattr__(self, "_released", False)
        object.__setattr__(self, "_launch_identity", None)

    def __setattr__(self, name: str, value: object) -> None:  # noqa: D105
        raise AttributeError("RuntimeProvision is immutable from outside its module")

    def __delattr__(self, name: str) -> None:  # noqa: D105
        raise AttributeError("RuntimeProvision is immutable from outside its module")

    def __reduce_ex__(self, protocol):  # noqa: D105 - no copy, no pickle
        raise TypeError("RuntimeProvision is not transferable")

    def __copy__(self):  # noqa: D105
        raise TypeError("RuntimeProvision is not transferable")

    def __deepcopy__(self, memo):  # noqa: D105
        raise TypeError("RuntimeProvision is not transferable")

    def __repr__(self) -> str:  # noqa: D105 - no path, identity or handle
        return f"RuntimeProvision({self._state!r})"

    def _set(self, name: str, value: object) -> None:
        object.__setattr__(self, name, value)

    @property
    def state(self) -> str:
        return self._state

    @property
    def refusal_reason(self) -> str | None:
        return self._reason

    @property
    def package_root(self) -> str:
        """``C``: a constant path below the admitted run root. A name, not proof."""
        return _package_root_path(self._run_root)

    @property
    def package_root_identity(self) -> tuple[int, int]:
        """``I_c``. Available ONLY after post-pin validation passed."""
        if self._state not in (STATE_PROVEN, STATE_BOUND) or self._package_root_identity is None:
            _refuse("PROVISION_NOT_PROVEN")
        return self._package_root_identity

    @property
    def launch_identity(self):
        """``L`` once :func:`record_launch_identity` bound it, else ``None``."""
        return self._launch_identity

    @property
    def construction_peak_open(self) -> int:
        return 0 if self._construction is None else self._construction.peak_open

    @property
    def construction_open_count(self) -> int:
        return 0 if self._construction is None else self._construction.open_count

    @property
    def final_pins_held(self) -> int:
        return 0 if self._final_pins is None else self._final_pins.open_count

    @property
    def live_references_released(self) -> bool:
        """Amendment Sec. 7.8.1, for THIS provision's handles: ``True`` iff
        every construction entry and every final pin is ``CLOSED`` (or none was
        ever opened). A ``CLOSE_FAILED`` entry never becomes ``CLOSED``, so a
        failure latches ``False``. An entry still ``OPEN`` is not proven
        released. Derived from the ledger, never from a Python reference."""
        return all(
            handles is None or handles.all_proven_closed()
            for handles in (self._construction, self._final_pins)
        )


def _package_root_path(run_root: str) -> str:
    return run_root + "\\" + RUNTIME_DIR_NAME + "\\" + PACKAGE_DIR_NAME


def _runtime_dir_path(run_root: str) -> str:
    return run_root + "\\" + RUNTIME_DIR_NAME


def _payload_path(base: str, relative: str) -> str:
    return base + "\\" + relative.replace("/", "\\")


# ---------------------------------------------------------------------------
# L3R step 1-2: admission (no write)
# ---------------------------------------------------------------------------


def _require_plain_directory_chain(path: str) -> None:
    for prefix in _chain_prefixes(path):
        if _leaves.inspect_no_follow(prefix).classification != _leaves.CLASSIFICATION_DIRECTORY:
            _refuse("TOPOLOGY_NOT_PLAIN")


def _require_missing(path: str, reason: str) -> None:
    if _leaves.inspect_no_follow(path).classification != _leaves.CLASSIFICATION_MISSING:
        _refuse(reason)


def _consume_authority(
    workspace: object, profile_id: object, inventory: object
) -> tuple[str, tuple[int, int]]:
    """The ONE place this module obtains write authority. ``(run_root, identity)``.

    Called at admission AND again immediately before the first create, so loss
    of authority between the two refuses rather than being trusted from before.
    Nothing here comes from the caller as a claim:

    * the run root is the ``experiment_root`` of a :class:`Cfg1RunWorkspace`
      that CFG1's own registry minted, re-proved against the filesystem
      (``verify_cfg1_run_workspace``); there is no parameter naming a path;
    * its identity is ``registered_root_identity`` -- the value read when the
      frozen creator returned the root, never re-derived from the path;
    * the profile must be an ELIGIBLE profile of the sealed HPP-1 snapshot
      (read at call time), and the inventory's content-derived
      ``payload_fingerprint`` must equal THAT profile's loader-bound
      fingerprint. The comparison is against loader-sealed policy, not against
      another value the same caller supplied.

    Frozen CFG1 facilities are used unmodified.
    """
    if type(workspace) is not _workspace.Cfg1RunWorkspace:
        _refuse("MALFORMED_INPUT")
    try:
        _workspace.verify_cfg1_run_workspace(workspace)
        identity = _workspace.registered_root_identity(workspace)
    except _workspace.Cfg1WorkspaceAuthorityError:
        _refuse("WORKSPACE_AUTHORITY_UNVERIFIED")
    if type(identity) is not tuple or len(identity) != 2 or any(type(part) is not int for part in identity):
        _refuse("WORKSPACE_AUTHORITY_UNVERIFIED")
    run_root = workspace.experiment_root
    if type(run_root) is not str:
        _refuse("WORKSPACE_AUTHORITY_UNVERIFIED")
    if type(profile_id) is not str or type(inventory) is not _payload.PayloadInventory:
        _refuse("MALFORMED_INPUT")
    try:
        view = _identity.eligible_profile_view(profile_id)
    except _identity.Cfg1PiIdentityError:
        _refuse("PROFILE_NOT_APPROVED")
    if view.payload_fingerprint != inventory.payload_fingerprint:
        _refuse("INVENTORY_NOT_APPROVED_FOR_PROFILE")
    return run_root, identity


def admit_runtime_provision(
    *,
    workspace: _workspace.Cfg1RunWorkspace,
    profile_id: str,
    approved_inventory: _payload.PayloadInventory,
    source_package_root: str,
) -> RuntimeProvision:
    """Steps 1-2 of amendment Sec. 7.4: bind inputs, LDT, topology. NO write.

    There is no run-root parameter and no identity parameter: both are derived
    from ``workspace`` by :func:`_consume_authority`, which also refuses any
    ``(profile_id, approved_inventory)`` pair the sealed policy snapshot does
    not itself approve. ``source_package_root`` is only ever READ, and every
    byte read from it is verified against the approved inventory before it is
    persisted (Sec. 7.4B).
    """
    if not PLATFORM_SUPPORTED:
        _refuse("UNSUPPORTED_PLATFORM")
    if (
        type(workspace) is not _workspace.Cfg1RunWorkspace
        or type(profile_id) is not str
        or type(source_package_root) is not str
        or type(approved_inventory) is not _payload.PayloadInventory
    ):
        _refuse("MALFORMED_INPUT")
    run_root, _identity_at_admission = _consume_authority(workspace, profile_id, approved_inventory)
    ldt = LAUNCH_DERIVATION_TABLE.get(profile_id)
    if ldt is None:
        _refuse("NO_LDT_ENTRY")
    for relative in (ldt["package_manifest"], *ldt["derivation_chain"]):
        if not approved_inventory.is_file(relative):
            _refuse("LDT_PATH_NOT_IN_INVENTORY")

    package_root = _package_root_path(run_root)
    reason = lexical_topology_refusal(_payload_path(package_root, "dist/config.js"))
    if reason is not None:
        _refuse(reason)
    _require_plain_directory_chain(run_root)
    _require_missing(_runtime_dir_path(run_root), "RUNTIME_ROOT_ALREADY_PRESENT")
    _require_missing(run_root + "\\" + _NODE_MODULES, "RUN_ROOT_NODE_MODULES_PRESENT")

    provision = RuntimeProvision(
        _PROVISION_KEY,
        _workspace=workspace,
        _run_root=run_root,
        _profile_id=profile_id,
        _inventory=approved_inventory,
        _source_root=source_package_root,
    )
    _ADMITTED_NONCES.add(provision._nonce)
    return provision


# ---------------------------------------------------------------------------
# Construction primitives
# ---------------------------------------------------------------------------


def _native_relative_create(handles: _HandleLedger, native, parent_raw: int, name: str, kind: str):
    """ONE ``NtCreateFile(FILE_CREATE)`` relative to ``parent_raw``.

    Returns ``(ntstatus_u32, entry_or_None, information)``. A returned handle is
    entered in the ledger IMMEDIATELY -- before the status is even examined --
    so no later failure can leave it untracked.
    """
    if kind == _KIND_DIRECTORY:
        access, share, options = _DIRECTORY_SHAPE
    elif kind == _KIND_FILE:
        access, share, options = _FILE_SHAPE
    else:
        _refuse("MALFORMED_INPUT")
    encoded = name.encode("utf-16-le")
    # Length is in BYTES of UTF-16: a code-point count would silently truncate
    # a name containing a supplementary-plane character to a DIFFERENT name.
    buffer = ctypes.create_unicode_buffer(name)
    unicode_name = _UNICODE_STRING(len(encoded), len(encoded) + 2, ctypes.cast(buffer, ctypes.c_wchar_p))
    attributes = _OBJECT_ATTRIBUTES(
        ctypes.sizeof(_OBJECT_ATTRIBUTES), parent_raw, ctypes.pointer(unicode_name), _OBJ_CASE_INSENSITIVE, None, None
    )
    status_block = _IO_STATUS_BLOCK()
    out = _wt.HANDLE()
    status = native(
        ctypes.byref(out), access, ctypes.byref(attributes), ctypes.byref(status_block), None,
        _FILE_ATTRIBUTE_NORMAL, share, _FILE_CREATE, options, None, 0,
    ) & 0xFFFFFFFF
    entry = handles.enter(out.value, kind) if out.value else None
    return status, entry, int(status_block.Information)


def _create_child(handles: _HandleLedger, native, parent: _LedgerEntry, name: str, kind: str) -> _LedgerEntry:
    """Create one child of ``parent`` and prove it FROM ITS OWN HANDLE.

    Requires ``STATUS_SUCCESS`` AND ``FILE_CREATED``; then kind, absence of any
    reparse attribute/tag, the parent's volume, and (for a file) zero length.
    Any failure closes the child's handle through the ledger and refuses; the
    object, if one was created, is left in place for L27 (nothing is deleted).
    """
    require_single_component(name)
    # Validated BEFORE the call: an unknown kind refused only at ledger entry
    # would leave a created object and an untracked handle behind it.
    if kind not in (_KIND_DIRECTORY, _KIND_FILE) or kind not in handles._kinds:
        _refuse("MALFORMED_INPUT")
    parent_raw = handles.raw_handle(parent, _KIND_DIRECTORY)
    status, entry, information = _native_relative_create(handles, native, parent_raw, name, kind)
    if status != _STATUS_SUCCESS or entry is None:
        if entry is not None:
            handles.close(entry)
        _refuse("NATIVE_CREATE_REFUSED")
    try:
        if information != _FILE_CREATED:
            _refuse("NATIVE_CREATE_UNEXPECTED_RESULT")
        if not _raw_is_plain(entry.raw, kind):
            _refuse("CREATED_OBJECT_NOT_PLAIN")
        identity = _raw_identity(entry.raw)
        if parent.identity is None or identity[0] != parent.identity[0]:
            _refuse("CREATED_OBJECT_VOLUME_MISMATCH")
        if kind == _KIND_FILE and _raw_end_of_file(entry.raw) != 0:
            _refuse("CREATED_FILE_NOT_EMPTY")
    except BaseException:
        handles.close(entry)
        raise
    entry.identity = identity
    entry.name = name
    return entry


def _pin_run_root(handles: _HandleLedger, run_root: str, expected: tuple[int, int]) -> _LedgerEntry:
    """Amendment Sec. 7.4A.1: open (never create) ``R`` and prove its identity.

    ``OPEN_EXISTING``, no-follow, share ``READ | WRITE`` (omitting only
    ``DELETE``). The path selects; the HANDLE proves: a directory, no reparse
    attribute or tag, and ``FileIdInfo`` equal to the identity registered at mint.
    """
    raw = _K32.CreateFileW(
        run_root,
        _FILE_LIST_DIRECTORY | _FILE_READ_ATTRIBUTES,
        _FILE_SHARE_READ | _FILE_SHARE_WRITE,
        None,
        _OPEN_EXISTING,
        _FILE_FLAG_BACKUP_SEMANTICS | _FILE_FLAG_OPEN_REPARSE_POINT,
        None,
    )
    if raw is None or raw == _INVALID_HANDLE_VALUE:
        _refuse("RUN_ROOT_NOT_PINNED")
    entry = handles.enter(raw, _KIND_DIRECTORY)
    if not _raw_is_plain(entry.raw, _KIND_DIRECTORY):
        _refuse("RUN_ROOT_NOT_PINNED")
    identity = _raw_identity(entry.raw)
    if identity != expected:
        _refuse("RUN_ROOT_IDENTITY_MISMATCH")
    entry.identity = identity
    return entry


def _gate_membership(handles: _HandleLedger, root: _LedgerEntry, child: _LedgerEntry) -> None:
    """``RT``'s gate: exactly one entry named ``pi_runtime`` in ONE enumeration of
    ``R``'s pin, with ``RT``'s own handle's file id, as a plain directory."""
    matches = [
        entry
        for entry in _raw_enumerate_once(handles.raw_handle(root, _KIND_DIRECTORY))
        if entry[0] == child.name
    ]
    if (
        len(matches) != 1
        or matches[0][1] != child.identity[1]
        or not matches[0][2] & _FILE_ATTRIBUTE_DIRECTORY
        or matches[0][2] & _FILE_ATTRIBUTE_REPARSE_POINT
        or matches[0][3] != 0
    ):
        _refuse("RUNTIME_ROOT_NOT_IN_RUN_ROOT")
    child.gate_passed = True


def _gate_exact_set(handles: _HandleLedger, directory: _LedgerEntry, children: list[_LedgerEntry]) -> None:
    """Amendment Sec. 7.4A.2 step 3 -- THE GATE, strictly before any content.

    ONE enumeration of the directory's own handle. The entry set must be
    exactly ``{".", "..", <every child name>}``; every child entry's file id
    must equal its own handle's, its directory bit must match its kind, and no
    entry may carry a reparse attribute or tag. A foreign name refuses.
    """
    observed = _raw_enumerate_once(handles.raw_handle(directory, _KIND_DIRECTORY))
    by_name: dict[str, tuple[int, int, int]] = {}
    for name, file_id, attributes, tag in observed:
        if name in by_name:
            _refuse("PARENTAGE_GATE_FAILED")
        by_name[name] = (file_id, attributes, tag)
    expected = {".", ".."} | {child.name for child in children}
    if len(expected) != len(children) + 2 or set(by_name) != expected:
        _refuse("PARENTAGE_GATE_FAILED")
    for child in children:
        file_id, attributes, tag = by_name[child.name]
        if (
            child.state != HANDLE_OPEN
            or file_id != child.identity[1]
            or bool(attributes & _FILE_ATTRIBUTE_DIRECTORY) != (child.kind == _KIND_DIRECTORY)
            or attributes & _FILE_ATTRIBUTE_REPARSE_POINT
            or tag != 0
        ):
            _refuse("PARENTAGE_GATE_FAILED")
    for child in children:
        child.gate_passed = True


def _read_verified_source(source_root: str, relative: str, sha256: str, size: int) -> bytes:
    """Amendment Sec. 7.4B shape (A): read in full, bounded, and VERIFY first.

    One no-follow, regular-file-only, one-handle read bounded by ``size``
    (the leaf refuses at ``size + 1``). The digest is recomputed here over the
    exact buffer that will be written, so the hashed bytes ARE the written
    bytes. Any mismatch refuses with the approved path only.
    """
    read = _leaves.read_payload_file_bytes(_payload_path(source_root, relative), size)
    content = read.content
    if (
        read.classification != _leaves.CLASSIFICATION_REGULAR_FILE
        or not read.within_bound
        or not read.stable
        or type(content) is not bytes
        or len(content) != size
        or hashlib.sha256(content).hexdigest() != sha256
    ):
        del content
        _refuse("SOURCE_BYTES_NOT_APPROVED", entry_path=relative)
    return content


def _write_verified_content(handles: _HandleLedger, child: _LedgerEntry, data: bytes, sha256: str) -> None:
    """Write approved bytes through the child's OWN creating handle only.

    Refuses unless the child passed its directory's gate and has received no
    content yet. Reads back through the same rewound handle and compares the
    digest, then re-proves from the handle that it is still a plain file.
    """
    raw = handles.raw_handle(child, _KIND_FILE)
    if not child.gate_passed:
        _refuse("CONTENT_BEFORE_GATE")
    if child.content_written:
        _refuse("CONTENT_ALREADY_WRITTEN")
    child.content_written = True
    if not _raw_write_all(raw, data):
        _refuse("CONTENT_NOT_WRITTEN")
    if _raw_end_of_file(raw) != len(data):
        _refuse("CONTENT_READBACK_MISMATCH")
    back = _raw_read_from_start(raw, len(data) + 1)
    if back is None or len(back) != len(data) or hashlib.sha256(back).hexdigest() != sha256:
        _refuse("CONTENT_READBACK_MISMATCH")
    if not _raw_is_plain(raw, _KIND_FILE):
        _refuse("CREATED_OBJECT_NOT_PLAIN")


# ---------------------------------------------------------------------------
# L3R steps 3-8
# ---------------------------------------------------------------------------


def _construct(provision: RuntimeProvision, handles: _HandleLedger, native) -> None:
    """Steps 5-6: ``R`` proven, then ``RT``, ``C`` and every descendant."""
    tree = _payload_tree(provision._inventory)
    ldt = LAUNCH_DERIVATION_TABLE[provision._profile_id]
    recorded = {ldt["package_manifest"], *ldt["derivation_chain"]}

    # Authority is consumed HERE, immediately before the first create -- not
    # trusted from admission, and after the (long) source observation. The
    # root's identity is the one registered at mint; the path only selects.
    run_root, run_root_identity = _consume_authority(
        provision._workspace, provision._profile_id, provision._inventory
    )
    if run_root != provision._run_root:
        _refuse("WORKSPACE_AUTHORITY_UNVERIFIED")
    provision._set("_run_root_identity", run_root_identity)
    root = _pin_run_root(handles, run_root, run_root_identity)
    runtime_dir = _create_child(handles, native, root, RUNTIME_DIR_NAME, _KIND_DIRECTORY)
    _gate_membership(handles, root, runtime_dir)
    package_dir = _create_child(handles, native, runtime_dir, PACKAGE_DIR_NAME, _KIND_DIRECTORY)
    _gate_exact_set(handles, runtime_dir, [package_dir])
    provision._created_identity["RT"] = runtime_dir.identity
    provision._created_identity["C"] = package_dir.identity
    provision._set("_state", STATE_CHAIN_CREATED)

    def build(directory: _LedgerEntry, relative: str) -> None:
        files, dirs = tree[relative]
        file_children = [
            (_create_child(handles, native, directory, name, _KIND_FILE), rel, sha256, size)
            for name, rel, sha256, size in files
        ]
        dir_children = [
            (_create_child(handles, native, directory, name, _KIND_DIRECTORY), rel) for name, rel in dirs
        ]
        _gate_exact_set(
            handles, directory, [child for child, *_ in file_children] + [child for child, _ in dir_children]
        )
        for child, rel, sha256, size in file_children:
            data = _read_verified_source(provision._source_root, rel, sha256, size)
            _write_verified_content(handles, child, data, sha256)
            del data
            if rel in recorded:
                provision._created_identity[rel] = child.identity
            if not handles.close(child):
                _refuse("CONSTRUCTION_HANDLE_NOT_CLOSED")
        for child, rel in dir_children:
            build(child, rel)
            if not handles.close(child):
                _refuse("CONSTRUCTION_HANDLE_NOT_CLOSED")

    build(package_dir, "")


def _acquire_final_pins(provision: RuntimeProvision, pins: _HandleLedger) -> list[tuple[str, _LedgerEntry]]:
    """Amendment Sec. 7.6: read-only pins of the four LDT files, AFTER population.

    ``GENERIC_READ``, share ``READ``, ``OPEN_EXISTING``, open-reparse-point: an
    OPEN, never a create. Each must be a plain regular file whose id equals the
    id recorded from its creating handle (the creator->pin interval is
    pre-authority: a substitute is refused here or by the content walk).
    """
    ldt = LAUNCH_DERIVATION_TABLE[provision._profile_id]
    package_root = provision.package_root
    held = []
    for relative in (ldt["package_manifest"], *ldt["derivation_chain"]):
        raw = _K32.CreateFileW(
            _payload_path(package_root, relative),
            _GENERIC_READ,
            _FILE_SHARE_READ,
            None,
            _OPEN_EXISTING,
            _FILE_FLAG_OPEN_REPARSE_POINT,
            None,
        )
        if raw is None or raw == _INVALID_HANDLE_VALUE:
            _refuse("FINAL_PIN_REFUSED")
        entry = pins.enter(raw, _KIND_FINAL_PIN)
        entry.name = relative
        if not _raw_is_plain(entry.raw, _KIND_FILE):
            _refuse("FINAL_PIN_REFUSED")
        entry.identity = _raw_identity(entry.raw)
        if entry.identity != provision._created_identity.get(relative):
            _refuse("FINAL_PIN_REFUSED")
        held.append((relative, entry))
    return held


def _post_pin_validation(provision: RuntimeProvision, held: list[tuple[str, _LedgerEntry]]) -> tuple[int, int]:
    """Amendment Sec. 7.6 items 1, 3, 4, 5 (read-only). Item 2 -- exposure
    absence against the profile's resolution exposures -- needs the matched
    profile object and is executor-integration work, NOT done here."""
    package_root = provision.package_root
    observation = _payload.observe_payload(package_root, leaves=_payload.genuine_payload_leaves())
    if (
        not observation.complete
        or observation.inventory.payload_fingerprint != provision._inventory.payload_fingerprint
    ):
        _refuse("POST_PIN_VALIDATION_FAILED")
    _reprove_topology(provision, held, "POST_PIN_VALIDATION_FAILED")
    return provision._created_identity["C"]


def _reprove_topology(provision: RuntimeProvision, held: list[tuple[str, _LedgerEntry]], reason: str) -> None:
    """T-NM, T-CANON, T-BUN, T-PLAIN, T-RT and pin/created identity, re-observed NOW.

    Read-only. Shared by post-pin validation (Sec. 7.6 items 3-5) and the L14
    executor precondition (Sec. 7.7), so both prove exactly the same rules.
    """
    package_root = provision.package_root
    runtime_dir = _runtime_dir_path(provision._run_root)
    if lexical_topology_refusal(_payload_path(package_root, "dist/config.js")) is not None:
        _refuse(reason)
    _require_plain_directory_chain(_payload_path(package_root, "dist"))
    listing = _leaves.enumerate_directory_no_follow(runtime_dir, 2)
    if not listing.complete or listing.entries != ((PACKAGE_DIR_NAME, _leaves.ENTRY_KIND_DIRECTORY),):
        _refuse(reason)
    _require_missing(runtime_dir + "\\" + _NODE_MODULES, reason)
    _require_missing(provision._run_root + "\\" + _NODE_MODULES, reason)
    for relative, entry in held:
        seen = _leaves.inspect_no_follow(_payload_path(package_root, relative))
        if seen.classification != _leaves.CLASSIFICATION_REGULAR_FILE or seen.identity != entry.identity:
            _refuse(reason)
    for path, key in ((runtime_dir, "RT"), (package_root, "C")):
        seen = _leaves.inspect_no_follow(path)
        if seen.classification != _leaves.CLASSIFICATION_DIRECTORY or seen.identity != provision._created_identity[key]:
            _refuse(reason)


def run_runtime_provision(provision: RuntimeProvision) -> None:
    """Amendment Sec. 7.4 steps 3-8 for one ADMITTED provision. At most once.

    Raises :class:`Cfg1RuntimeProvisionError` on every anticipated refusal (the
    caller maps it to ``RUNTIME_PROVISIONING_FAILED``); any other exception
    propagates (``UNEXPECTED_STEP_FAILURE``). On EVERY exit the construction
    ledger is closed before this returns, children before directories. Nothing
    is deleted on any path. Final read-only pins acquired before a later
    refusal stay held for :func:`release_at_l27_entry`, as amendment Sec. 7.8
    requires.

    The provision's guard is taken (non-blocking) BEFORE the admission nonce is
    claimed and held until this returns, so a second concurrent or re-entrant
    run, and :func:`release_at_l27_entry`, are refused while this one owns the
    handles.
    """
    guard = getattr(provision, "_guard", None) if type(provision) is RuntimeProvision else None
    if guard is None:
        _refuse("PROVISION_NOT_ADMITTED")
    if not guard.acquire(blocking=False):
        _refuse("PROVISION_ACTIVE")
    try:
        _run_guarded(provision)
    finally:
        guard.release()


def _run_guarded(provision: RuntimeProvision) -> None:
    if (
        getattr(provision, "_state", None) != STATE_ADMITTED
        or getattr(provision, "_released", True)
        or getattr(provision, "_nonce", None) not in _ADMITTED_NONCES
    ):
        _refuse("PROVISION_NOT_ADMITTED")
    _ADMITTED_NONCES.discard(provision._nonce)
    # Write-ahead (step 3): both ledgers exist before the first open.
    construction = _HandleLedger(_LEDGER_KEY, frozenset({_KIND_DIRECTORY, _KIND_FILE}))
    provision._set("_construction", construction)
    provision._set("_final_pins", _HandleLedger(_LEDGER_KEY, frozenset({_KIND_FINAL_PIN})))
    provision._set("_state", STATE_ATTEMPTED)
    try:
        native = _resolve_native_create()
        if native is None:
            _refuse("NATIVE_RELATIVE_CREATE_UNAVAILABLE")
        observation = _payload.observe_payload(provision._source_root, leaves=_payload.genuine_payload_leaves())
        if (
            not observation.complete
            or observation.inventory.payload_fingerprint != provision._inventory.payload_fingerprint
        ):
            _refuse("SOURCE_NOT_APPROVED_PAYLOAD")
        provision._set("_state", STATE_SOURCE_PROVEN)
        try:
            _construct(provision, construction, native)
        finally:
            construction.close_all()
        if not construction.all_proven_closed():
            _refuse("CONSTRUCTION_HANDLE_NOT_CLOSED")
        provision._set("_state", STATE_POPULATED)
        held = _acquire_final_pins(provision, provision._final_pins)
        provision._set("_state", STATE_PINNED)
        identity = _post_pin_validation(provision, held)
    except Cfg1RuntimeProvisionError as refusal:
        construction.close_all()
        provision._set("_state", STATE_REFUSED)
        provision._set("_reason", refusal.reason_code)
        raise
    except BaseException:
        construction.close_all()
        provision._set("_state", STATE_FAILED_UNEXPECTED)
        provision._set("_reason", "UNEXPECTED_STEP_FAILURE")
        raise
    provision._set("_package_root_identity", identity)
    provision._set("_state", STATE_PROVEN)


def release_at_l27_entry(provision: RuntimeProvision) -> None:
    """Amendment Sec. 7.8 / 7.4A.5: close every still-``OPEN`` construction
    entry (backstop), then every final pin -- each exactly once, by handle,
    never by name, no retry, no force. Never raises for a close failure: the
    failure is recorded and latches
    :attr:`RuntimeProvision.live_references_released` ``False``.

    **Lifecycle (A2 FU1, Finding B).** Legal only when no run owns the
    handles and the provision has not already been released:

    * while :func:`run_runtime_provision` is active -- another thread, or a
      callback re-entering on the running thread -- the guard is held and this
      REFUSES (``PROVISION_ACTIVE``) without closing anything;
    * a second release REFUSES (``PROVISION_ALREADY_RELEASED``): release is
      exactly once, and nothing is retried;
    * releasing a never-run ADMITTED provision closes nothing and consumes its
      admission nonce, so it can never run afterwards.

    Release deliberately re-verifies no workspace: it closes handles this
    provision already holds, and loss of workspace authority must never prevent
    that.
    """
    guard = getattr(provision, "_guard", None) if type(provision) is RuntimeProvision else None
    if guard is None:
        _refuse("MALFORMED_INPUT")
    if not guard.acquire(blocking=False):
        _refuse("PROVISION_ACTIVE")
    try:
        if provision._released:
            _refuse("PROVISION_ALREADY_RELEASED")
        _ADMITTED_NONCES.discard(provision._nonce)
        for handles in (provision._construction, provision._final_pins):
            if handles is not None:
                handles.close_all()
        provision._set("_released", True)
    finally:
        guard.release()


# ---------------------------------------------------------------------------
# Executor integration (F5A-INT, OFFLINE ONLY) -- amendment Sec. 7.4 steps 1
# and 9, Sec. 7.7 (L14 precondition), Sec. 7.8.1 (the derived release fact).
#
# Nothing below launches, and nothing below makes provisioning reachable from
# the default executor binding: ``run_executor.default_cfg1_run_ports`` binds
# :func:`live_runtime_provisioning_not_qualified`, which refuses before any
# observation or write. Only an explicitly composed (offline) port set binds
# :func:`admit_runtime_provision_for_source`.
# ---------------------------------------------------------------------------

#: The closed reason of the default (live) binding. A2-3 is not qualified, so
#: no default binding may provision; changing that is a code change under a
#: separate authorization, never a flag, an environment value or a caller claim.
LIVE_PROVISIONING_NOT_QUALIFIED = "LIVE_PROVISIONING_NOT_QUALIFIED"


def live_runtime_provisioning_not_qualified(*, workspace: object, source: object) -> RuntimeProvision:
    """The default executor's L3R port: ALWAYS refuses, before any I/O."""
    _refuse(LIVE_PROVISIONING_NOT_QUALIFIED)


def admit_runtime_provision_for_source(
    *, workspace: _workspace.Cfg1RunWorkspace, source: object
) -> RuntimeProvision:
    """The offline L3R port: admit one provision from the executor's own ``S``.

    ``source`` must be the exact :class:`pi_identity.Cfg1PiIdentity` a passing
    P produced. The profile is ``S.matched_profile_id`` and the byte source is
    ``S.pi_package_root`` -- never a caller choice. The copy manifest is the
    source's own complete PI-PC1 observation; :func:`admit_runtime_provision`
    then refuses it unless its content-derived fingerprint equals the sealed
    profile's (amendment Sec. 7.4 step 4: by that equality it IS the approved
    inventory). Returns an ADMITTED provision; nothing is created.
    """
    if type(source) is not _identity.Cfg1PiIdentity:
        _refuse("MALFORMED_INPUT")
    observation = _payload.observe_payload(source.pi_package_root, leaves=_payload.genuine_payload_leaves())
    if not observation.complete or type(observation.inventory) is not _payload.PayloadInventory:
        _refuse("SOURCE_NOT_APPROVED_PAYLOAD")
    return admit_runtime_provision(
        workspace=workspace,
        profile_id=source.matched_profile_id,
        approved_inventory=observation.inventory,
        source_package_root=source.pi_package_root,
    )


def _workspace_nonce(workspace: object) -> str | None:
    if type(workspace) is not _workspace.Cfg1RunWorkspace:
        return None
    nonce = workspace.run_workspace_nonce
    return nonce if type(nonce) is str and nonce else None


def provision_is_admitted_for(provision: object, *, workspace: object, source: object) -> bool:
    """Consumption check BEFORE the executor adopts a port-returned object.

    ``True`` only for an exact, never-run, never-released ADMITTED provision
    bound to THIS workspace (nonce equality), THIS profile and THIS byte source.
    A foreign, run, released, uninitialised or look-alike object is ``False``
    and is never adopted -- so it is never run and never released by this run.
    """
    if type(provision) is not RuntimeProvision or type(source) is not _identity.Cfg1PiIdentity:
        return False
    if getattr(provision, "_guard", None) is None:
        return False
    nonce = _workspace_nonce(workspace)
    return (
        nonce is not None
        and getattr(provision, "_state", None) == STATE_ADMITTED
        and getattr(provision, "_released", True) is False
        and getattr(provision, "_launch_identity", True) is None
        and getattr(provision, "_nonce", None) in _ADMITTED_NONCES
        and _workspace_nonce(getattr(provision, "_workspace", None)) == nonce
        and getattr(provision, "_run_root", None) == workspace.experiment_root
        and getattr(provision, "_profile_id", None) == source.matched_profile_id
        and getattr(provision, "_source_root", None) == source.pi_package_root
    )


def record_launch_identity(provision: RuntimeProvision, launch: object) -> None:
    """Amendment Sec. 7.4 step 9: record ``L`` in a PROVEN provision, once.

    ``L`` must be the exact identity type and must name exactly this
    provision's package root, its ``dist\\cli.js``, the ``I_c`` post-pin
    validation proved, and this provision's profile. Refuses otherwise; refuses
    while a run or release owns the provision.
    """
    guard = getattr(provision, "_guard", None) if type(provision) is RuntimeProvision else None
    if guard is None:
        _refuse("MALFORMED_INPUT")
    if not guard.acquire(blocking=False):
        _refuse("PROVISION_ACTIVE")
    try:
        if provision._state != STATE_PROVEN or provision._released or provision._launch_identity is not None:
            _refuse("PROVISION_NOT_PROVEN")
        package_root = provision.package_root
        if (
            type(launch) is not _identity.Cfg1PiIdentity
            or launch.pi_package_root != package_root
            or launch.pi_cli_js != _payload_path(package_root, "dist/cli.js")
            or launch.package_root_identity != provision._package_root_identity
            or launch.matched_profile_id != provision._profile_id
        ):
            _refuse("LAUNCH_IDENTITY_NOT_THIS_PROVISION")
        provision._set("_launch_identity", launch)
        provision._set("_state", STATE_BOUND)
    finally:
        guard.release()


def reprove_provision_for_launch(provision: object, *, workspace: object, launch: object) -> bool:
    """The L14 executor precondition (amendment Sec. 7.7), re-observed NOW.

    Exact ``True`` only when: the provision is exact, BOUND and unreleased; its
    workspace nonce equals ``workspace``'s; ``launch`` IS its recorded launch
    identity; its profile still has an LDT row; every construction handle is
    proven closed; exactly the four final pins are held, each re-proven FROM
    ITS HANDLE (plain regular file, same id); and the topology re-proof (T-NM,
    T-CANON, T-PLAIN, T-BUN, T-RT, pin and created identities) passes. Read-only.
    The caller still runs the frozen ``reprove_pi_identity_for_launch(L)``.
    """
    guard = getattr(provision, "_guard", None) if type(provision) is RuntimeProvision else None
    if guard is None or not guard.acquire(blocking=False):
        return False
    try:
        nonce = _workspace_nonce(workspace)
        construction = provision._construction
        pins = provision._final_pins
        ldt = LAUNCH_DERIVATION_TABLE.get(provision._profile_id)
        if (
            nonce is None
            or provision._state != STATE_BOUND
            or provision._released
            or provision._launch_identity is None
            or launch is not provision._launch_identity
            or _workspace_nonce(provision._workspace) != nonce
            or ldt is None
            or type(construction) is not _HandleLedger
            or not construction.all_proven_closed()
            or type(pins) is not _HandleLedger
        ):
            return False
        expected = (ldt["package_manifest"], *ldt["derivation_chain"])
        held = [(entry.name, entry) for entry in pins._entries]
        if pins.open_count != len(expected) or tuple(name for name, _ in held) != expected:
            return False
        for _name, entry in held:
            raw = pins.raw_handle(entry, _KIND_FINAL_PIN)
            if not _raw_is_plain(raw, _KIND_FILE) or _raw_identity(raw) != entry.identity:
                return False
        _reprove_topology(provision, held, "LAUNCH_PRECONDITION_FAILED")
        return True
    except Cfg1RuntimeProvisionError:
        return False
    finally:
        guard.release()


def provision_live_references_proven_released(provision: object) -> bool:
    """This provision's share of amendment Sec. 7.8.1's derived fact.

    ``True`` only when the provision was released through
    :func:`release_at_l27_entry` AND every construction entry and every final
    pin reads ``CLOSED``. ``False`` for an ``OPEN`` or ``CLOSE_FAILED`` entry
    (a latch: nothing turns it back), for a provision never released, and for
    a run that ended ``FAILED_UNEXPECTED`` -- an unexpected interruption can
    fall between a native create returning and its ledger entry (candidate
    Sec. 4 F-3), and an absent entry is never proof of a closed handle.
    """
    if type(provision) is not RuntimeProvision or getattr(provision, "_guard", None) is None:
        return False
    return (
        provision._released is True
        and provision._state != STATE_FAILED_UNEXPECTED
        and provision.live_references_released is True
    )
