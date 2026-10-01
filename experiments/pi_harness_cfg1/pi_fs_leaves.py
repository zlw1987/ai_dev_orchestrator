"""The genuine leaf effects of the canonical static Pi identity proof P.

Design ``PHASE_5F3B_HARNESS_CFG1_L1_BOUNDARY_FU1_DESIGN.md`` (R6) Sec. 7.2,
as amended by ``..._OC3_AMEND1_DESIGN.md`` (AMD-1, AMD-2): P's injectable
leaves are ONLY (i) the Sec. 7.2 no-follow inspection/identity primitive and
(ii) a one-handle bounded digest reader, plus P's explicit ambient mapping.
This module holds the genuine binding of (i) and (ii) -- and, since
``PHASE_5F3B_PI_HARNESS_PROFILE_EVOLUTION_PE1_AMENDMENT.md`` Sec. 11.2 (X-1,
implemented by PE-2a), the ``PI-PC1`` payload-walk leaves: one no-follow
directory enumerator that lists THROUGH its own handle, and a one-handle
payload-file reader that reports the exact byte count, a SHA-256 and whether
the handle's size was stable across the read. Those are separate functions
with separate result types; P's two leaves are unchanged.

**Nothing here can create a process.** It imports no ``subprocess``,
``multiprocessing`` or ``asyncio.subprocess``, and its only native surface is
four documented ``kernel32`` calls -- ``CreateFileW``, ``GetFileInformationByHandleEx``,
``GetFileType`` and ``CloseHandle`` -- plus the CRT descriptor adoption
``msvcrt.open_osfhandle`` and ``os.read``/``os.close``. Test AA audits this
module's source statically for exactly that.

**Nothing here follows a reparse point.** Every open passes
``FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_BACKUP_SEMANTICS``, so a symlink,
junction or mount point is observed AS ITSELF and classified
``reparse_point`` -- a terminal answer about that one lexical entry, never a
hop to where it points.

**Nothing here is a network claim.** These are read-only filesystem opens of
lexical paths. Depending on operator-controlled ``PATH``, drive mappings and
filesystem topology, the OS may perform redirector I/O while servicing an
open; nothing here claims otherwise, and nothing here detects or refuses a
remote path beyond what the frozen candidate-resolution rules already do.
"""

from __future__ import annotations

import hashlib
import os
import struct
import sys

#: The five Sec. 7.2 classifications. Closed.
CLASSIFICATION_REGULAR_FILE = "regular_file"
CLASSIFICATION_DIRECTORY = "directory"
CLASSIFICATION_REPARSE_POINT = "reparse_point"
CLASSIFICATION_MISSING = "missing"
CLASSIFICATION_OTHER = "other"

CLASSIFICATIONS: frozenset[str] = frozenset(
    {
        CLASSIFICATION_REGULAR_FILE,
        CLASSIFICATION_DIRECTORY,
        CLASSIFICATION_REPARSE_POINT,
        CLASSIFICATION_MISSING,
        CLASSIFICATION_OTHER,
    }
)

PLATFORM_SUPPORTED = sys.platform == "win32"


class NoFollowObservation:
    """What, without following anything, is at one lexical path.

    ``identity`` is the Sec. 7.2 ``(volume_serial, file_id)`` pair, present
    exactly when the classification is ``regular_file`` or ``directory`` and
    ``None`` otherwise. Immutable; carries no path.
    """

    __slots__ = ("classification", "identity")

    def __init__(self, classification: str, identity: tuple[int, int] | None) -> None:
        object.__setattr__(self, "classification", classification)
        object.__setattr__(self, "identity", identity)

    def __setattr__(self, name: str, value: object) -> None:  # noqa: D105
        raise AttributeError("NoFollowObservation is immutable")

    def __repr__(self) -> str:  # noqa: D105 - identities are never rendered
        return f"{type(self).__name__}({self.classification!r})"


class BoundedSeamRead:
    """The result of one one-handle bounded digest read.

    ``sha256`` is present only for a ``regular_file`` whose size did not exceed
    the bound; ``within_bound`` is ``False`` for an oversize regular file.
    The bytes themselves are never retained.
    """

    __slots__ = ("classification", "within_bound", "sha256")

    def __init__(self, classification: str, within_bound: bool, sha256: str | None) -> None:
        object.__setattr__(self, "classification", classification)
        object.__setattr__(self, "within_bound", within_bound)
        object.__setattr__(self, "sha256", sha256)

    def __setattr__(self, name: str, value: object) -> None:  # noqa: D105
        raise AttributeError("BoundedSeamRead is immutable")

    def __repr__(self) -> str:  # noqa: D105
        return f"{type(self).__name__}({self.classification!r})"


#: PE-1 Sec. 11.2 (X-1): the three kinds an enumerated directory entry can be
#: reported as, from the enumeration record's own attributes. Closed. ``file``
#: means only "neither a directory nor a reparse point"; whether it is a
#: regular disk file is decided by the one-handle reader's own classification.
ENTRY_KIND_REPARSE = "reparse"
ENTRY_KIND_DIRECTORY = "directory"
ENTRY_KIND_FILE = "file"

ENTRY_KINDS: frozenset[str] = frozenset(
    {ENTRY_KIND_REPARSE, ENTRY_KIND_DIRECTORY, ENTRY_KIND_FILE}
)


class DirectoryListing:
    """The result of ONE no-follow directory enumeration through one handle.

    ``classification`` is the opened handle's own classification. ``entries``
    is a tuple of ``(name, kind)`` exactly when the handle classified
    ``directory`` and the enumeration ran to its end within the entry budget;
    otherwise it is ``None`` and ``complete`` is ``False``. ``over_budget`` is
    ``True`` exactly when enumeration stopped because the budget was exceeded.
    ``.`` and ``..`` are never reported. Immutable; carries no path.
    """

    __slots__ = ("classification", "complete", "over_budget", "entries")

    def __init__(
        self,
        classification: str,
        complete: bool,
        over_budget: bool,
        entries: tuple[tuple[str, str], ...] | None,
    ) -> None:
        object.__setattr__(self, "classification", classification)
        object.__setattr__(self, "complete", complete)
        object.__setattr__(self, "over_budget", over_budget)
        object.__setattr__(self, "entries", entries)

    def __setattr__(self, name: str, value: object) -> None:  # noqa: D105
        raise AttributeError("DirectoryListing is immutable")

    def __repr__(self) -> str:  # noqa: D105 - names are never rendered
        return f"{type(self).__name__}({self.classification!r}, complete={self.complete!r})"


class PayloadFileRead:
    """The result of one one-handle payload-file read (PE-1 Sec. 4.3 step 3).

    ``size`` and ``sha256`` come from the SAME opened handle: every byte read
    to EOF is hashed and counted. ``stable`` is ``True`` exactly when the
    handle's reported size before the first read and after EOF both equal the
    byte count. ``within_bound`` is ``False`` as soon as the count would exceed
    the caller's bound; then no digest is reported. ``content`` is ``None``
    unless the caller explicitly asked for the bytes (manifest capture only).
    """

    __slots__ = ("classification", "within_bound", "stable", "size", "sha256", "content")

    def __init__(
        self,
        classification: str,
        within_bound: bool,
        stable: bool,
        size: int | None,
        sha256: str | None,
        content: bytes | None,
    ) -> None:
        object.__setattr__(self, "classification", classification)
        object.__setattr__(self, "within_bound", within_bound)
        object.__setattr__(self, "stable", stable)
        object.__setattr__(self, "size", size)
        object.__setattr__(self, "sha256", sha256)
        object.__setattr__(self, "content", content)

    def __setattr__(self, name: str, value: object) -> None:  # noqa: D105
        raise AttributeError("PayloadFileRead is immutable")

    def __repr__(self) -> str:  # noqa: D105 - bytes and digests never rendered
        return f"{type(self).__name__}({self.classification!r})"


class Cfg1PiLeafError(Exception):
    """A leaf could not complete its own handle protocol (e.g. a failed close).

    Not an anticipated P refusal: it reaches L1's catch-all as an unexpected
    failure, because the leaf cannot say what it observed.
    """

    def __init__(self, reason_code: str) -> None:
        super().__init__(f"cfg1 pi identity leaf failed: {reason_code}")
        self.reason_code = reason_code


if PLATFORM_SUPPORTED:  # pragma: no branch - a platform constant
    import ctypes
    import ctypes.wintypes as _wt
    import msvcrt

    _K32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _K32.CreateFileW.restype = _wt.HANDLE
    _K32.CreateFileW.argtypes = [
        _wt.LPCWSTR,
        _wt.DWORD,
        _wt.DWORD,
        ctypes.c_void_p,
        _wt.DWORD,
        _wt.DWORD,
        _wt.HANDLE,
    ]
    _K32.CloseHandle.restype = _wt.BOOL
    _K32.CloseHandle.argtypes = [_wt.HANDLE]
    _K32.GetFileInformationByHandleEx.restype = _wt.BOOL
    _K32.GetFileInformationByHandleEx.argtypes = [
        _wt.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        _wt.DWORD,
    ]
    _K32.GetFileType.restype = _wt.DWORD
    _K32.GetFileType.argtypes = [_wt.HANDLE]

    _GENERIC_READ = 0x80000000
    _FILE_READ_ATTRIBUTES = 0x00000080
    _FILE_SHARE_READ = 0x00000001
    _FILE_SHARE_WRITE = 0x00000002
    _FILE_SHARE_DELETE = 0x00000004
    _OPEN_EXISTING = 3
    _FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
    _FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
    _FILE_ATTRIBUTE_DIRECTORY = 0x00000010
    _FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
    _FILE_TYPE_DISK = 0x0001
    _INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
    _ERROR_FILE_NOT_FOUND = 2
    _ERROR_PATH_NOT_FOUND = 3
    _FileAttributeTagInfo = 9
    _FileIdInfo = 18

    class _FILE_ID_128(ctypes.Structure):
        _fields_ = [("Identifier", ctypes.c_ubyte * 16)]

    class _FILE_ID_INFO(ctypes.Structure):
        _fields_ = [
            ("VolumeSerialNumber", ctypes.c_ulonglong),
            ("FileId", _FILE_ID_128),
        ]

    class _FILE_ATTRIBUTE_TAG_INFO(ctypes.Structure):
        _fields_ = [("FileAttributes", _wt.DWORD), ("ReparseTag", _wt.DWORD)]

    # -- PE-1 Sec. 11.2 (X-1): the same four calls, two more information
    # classes. Directory listing goes THROUGH the opened directory handle.
    _FILE_LIST_DIRECTORY = 0x00000001
    _ERROR_NO_MORE_FILES = 18
    _FileStandardInfo = 1
    _FileFullDirectoryInfo = 14
    _FileFullDirectoryRestartInfo = 15
    #: ``FILE_FULL_DIR_INFO`` field offsets (documented layout).
    _DIR_NEXT_ENTRY_OFFSET = 0
    _DIR_FILE_ATTRIBUTES = 56
    _DIR_FILE_NAME_LENGTH = 60
    _DIR_FILE_NAME = 68
    #: 64 KiB of 8-byte-aligned storage per enumeration call.
    _DIR_BUFFER_WORDS = 8192

    class _FILE_STANDARD_INFO(ctypes.Structure):
        _fields_ = [
            ("AllocationSize", ctypes.c_longlong),
            ("EndOfFile", ctypes.c_longlong),
            ("NumberOfLinks", _wt.DWORD),
            ("DeletePending", ctypes.c_ubyte),
            ("Directory", ctypes.c_ubyte),
        ]


def _open_no_follow(path: str, access: int, share: int):
    """One ``CreateFileW``, never following a reparse point.

    Returns ``(handle, None)`` or ``(None, classification)`` where the
    classification is ``missing`` for "file/path not found" and ``other`` for
    every other refusal (sharing violation, denial, an unreachable or invalid
    name). Nothing else is inferred from a refusal.
    """
    handle = _K32.CreateFileW(
        path,
        access,
        share,
        None,
        _OPEN_EXISTING,
        _FILE_FLAG_BACKUP_SEMANTICS | _FILE_FLAG_OPEN_REPARSE_POINT,
        None,
    )
    if handle is None or handle == _INVALID_HANDLE_VALUE:
        error = ctypes.get_last_error()
        if error in (_ERROR_FILE_NOT_FOUND, _ERROR_PATH_NOT_FOUND):
            return None, CLASSIFICATION_MISSING
        return None, CLASSIFICATION_OTHER
    return handle, None


def _classify_handle(handle) -> str:
    """Classify an open handle from the handle itself (no pathname)."""
    info = _FILE_ATTRIBUTE_TAG_INFO()
    ok = _K32.GetFileInformationByHandleEx(
        handle, _FileAttributeTagInfo, ctypes.byref(info), ctypes.sizeof(info)
    )
    if not ok:
        return CLASSIFICATION_OTHER
    attributes = int(info.FileAttributes)
    if attributes & _FILE_ATTRIBUTE_REPARSE_POINT or int(info.ReparseTag) != 0:
        return CLASSIFICATION_REPARSE_POINT
    if _K32.GetFileType(handle) != _FILE_TYPE_DISK:
        return CLASSIFICATION_OTHER
    if attributes & _FILE_ATTRIBUTE_DIRECTORY:
        return CLASSIFICATION_DIRECTORY
    return CLASSIFICATION_REGULAR_FILE


def _handle_identity(handle) -> tuple[int, int] | None:
    info = _FILE_ID_INFO()
    ok = _K32.GetFileInformationByHandleEx(
        handle, _FileIdInfo, ctypes.byref(info), ctypes.sizeof(info)
    )
    if not ok:
        return None
    return (
        int(info.VolumeSerialNumber),
        int.from_bytes(bytes(info.FileId.Identifier), "little"),
    )


def inspect_no_follow(path: str) -> NoFollowObservation:
    """Sec. 7.2 steps 1-2: topology, no-follow, then identity if accepted.

    The handle is opened with attribute access only and full sharing, so the
    inspection never blocks another reader and never needs data access. A
    ``regular_file`` or ``directory`` whose identity cannot be read is
    reported as ``other`` -- never as an identity-less acceptance.
    """
    if not PLATFORM_SUPPORTED:
        raise Cfg1PiLeafError("UNSUPPORTED_PLATFORM")
    if type(path) is not str or not path:
        return NoFollowObservation(CLASSIFICATION_OTHER, None)
    handle, refused = _open_no_follow(
        path,
        _FILE_READ_ATTRIBUTES,
        _FILE_SHARE_READ | _FILE_SHARE_WRITE | _FILE_SHARE_DELETE,
    )
    if handle is None:
        return NoFollowObservation(refused, None)
    try:
        classification = _classify_handle(handle)
        identity = None
        if classification in (CLASSIFICATION_REGULAR_FILE, CLASSIFICATION_DIRECTORY):
            identity = _handle_identity(handle)
            if identity is None:
                classification = CLASSIFICATION_OTHER
    finally:
        if not _K32.CloseHandle(handle):
            raise Cfg1PiLeafError("INSPECTION_HANDLE_NOT_CLOSED")
    return NoFollowObservation(classification, identity)


def read_bounded_digest(path: str, max_bytes: int) -> BoundedSeamRead:
    """ONE open, ONE handle: classify it, then digest at most ``max_bytes``.

    Shared for reading only, so no writer can hold the object open for write
    while it is being digested. Reads at most ``max_bytes + 1`` bytes; a file
    longer than the bound is reported ``within_bound = False`` with no digest.
    The bytes are hashed and dropped -- never returned, retained or parsed.
    """
    if not PLATFORM_SUPPORTED:
        raise Cfg1PiLeafError("UNSUPPORTED_PLATFORM")
    if type(path) is not str or not path:
        return BoundedSeamRead(CLASSIFICATION_OTHER, False, None)
    if type(max_bytes) is not int or max_bytes < 0:
        raise Cfg1PiLeafError("MALFORMED_BOUND")
    handle, refused = _open_no_follow(
        path, _GENERIC_READ | _FILE_READ_ATTRIBUTES, _FILE_SHARE_READ
    )
    if handle is None:
        return BoundedSeamRead(refused, False, None)
    try:
        descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY)
    except OSError:
        if not _K32.CloseHandle(handle):
            raise Cfg1PiLeafError("DIGEST_HANDLE_NOT_CLOSED") from None
        return BoundedSeamRead(CLASSIFICATION_OTHER, False, None)

    result: BoundedSeamRead | None = None
    try:
        classification = _classify_handle(msvcrt.get_osfhandle(descriptor))
        if classification != CLASSIFICATION_REGULAR_FILE:
            result = BoundedSeamRead(classification, False, None)
        else:
            digest = hashlib.sha256()
            total = 0
            limit = max_bytes + 1
            while total < limit:
                chunk = os.read(descriptor, min(65536, limit - total))
                if not chunk:
                    break
                total += len(chunk)
                digest.update(chunk)
            if total > max_bytes:
                result = BoundedSeamRead(CLASSIFICATION_REGULAR_FILE, False, None)
            else:
                result = BoundedSeamRead(
                    CLASSIFICATION_REGULAR_FILE, True, digest.hexdigest()
                )
    except OSError:
        result = BoundedSeamRead(CLASSIFICATION_OTHER, False, None)
    finally:
        try:
            os.close(descriptor)
        except OSError:
            raise Cfg1PiLeafError("DIGEST_HANDLE_NOT_CLOSED") from None
    return result


# ---------------------------------------------------------------------------
# PE-1 Sec. 4.3 / Sec. 11.2 (X-1): the payload-walk leaves
#
# The SAME four kernel32 calls and the SAME CRT adoption as above; nothing
# here can create a process, follow a reparse point, write, or delete. The
# canonical proof P's two leaves above are unchanged: these are additional
# functions with their own result types, consumed only by the PI-PC1 walk.
# ---------------------------------------------------------------------------


def _directory_listing_failure() -> DirectoryListing:
    return DirectoryListing(CLASSIFICATION_DIRECTORY, False, False, None)


def _list_through_handle(handle, max_entries: int) -> DirectoryListing:
    """Enumerate one already-classified directory THROUGH its own handle."""
    buffer = (ctypes.c_ulonglong * _DIR_BUFFER_WORDS)()
    size = ctypes.sizeof(buffer)
    entries: list[tuple[str, str]] = []
    info_class = _FileFullDirectoryRestartInfo
    while True:
        ok = _K32.GetFileInformationByHandleEx(handle, info_class, ctypes.byref(buffer), size)
        if not ok:
            if ctypes.get_last_error() == _ERROR_NO_MORE_FILES:
                break
            return _directory_listing_failure()
        info_class = _FileFullDirectoryInfo
        raw = bytes(buffer)
        offset = 0
        while True:
            if offset + _DIR_FILE_NAME > size:
                return _directory_listing_failure()
            (next_offset,) = struct.unpack_from("<I", raw, offset + _DIR_NEXT_ENTRY_OFFSET)
            (attributes,) = struct.unpack_from("<I", raw, offset + _DIR_FILE_ATTRIBUTES)
            (name_length,) = struct.unpack_from("<I", raw, offset + _DIR_FILE_NAME_LENGTH)
            start = offset + _DIR_FILE_NAME
            end = start + name_length
            if name_length % 2 or end > size:
                return _directory_listing_failure()
            # surrogatepass: a lone surrogate in an on-disk name survives
            # decoding so the payload grammar can REFUSE it, never repair it.
            name = raw[start:end].decode("utf-16-le", "surrogatepass")
            if name not in (".", ".."):
                if attributes & _FILE_ATTRIBUTE_REPARSE_POINT:
                    kind = ENTRY_KIND_REPARSE
                elif attributes & _FILE_ATTRIBUTE_DIRECTORY:
                    kind = ENTRY_KIND_DIRECTORY
                else:
                    kind = ENTRY_KIND_FILE
                entries.append((name, kind))
                if len(entries) > max_entries:
                    return DirectoryListing(CLASSIFICATION_DIRECTORY, False, True, None)
            if next_offset == 0:
                break
            if next_offset < _DIR_FILE_NAME:
                return _directory_listing_failure()
            offset += next_offset
    return DirectoryListing(CLASSIFICATION_DIRECTORY, True, False, tuple(entries))


def enumerate_directory_no_follow(path: str, max_entries: int) -> DirectoryListing:
    """ONE no-follow open, classify the handle, list THROUGH that handle.

    Opened with list/attribute access and full sharing (AIDO never locks the
    Pi tree). A handle that is not a plain directory -- a reparse point of any
    tag, a file, anything else -- is reported as such with no entries. Stops
    and reports ``over_budget`` as soon as more than ``max_entries`` entries
    (excluding ``.`` and ``..``) have been seen. Any enumeration failure is an
    incomplete listing, never a partial one.
    """
    if not PLATFORM_SUPPORTED:
        raise Cfg1PiLeafError("UNSUPPORTED_PLATFORM")
    if type(path) is not str or not path:
        return DirectoryListing(CLASSIFICATION_OTHER, False, False, None)
    if type(max_entries) is not int or max_entries < 0:
        raise Cfg1PiLeafError("MALFORMED_BOUND")
    handle, refused = _open_no_follow(
        path,
        _FILE_LIST_DIRECTORY | _FILE_READ_ATTRIBUTES,
        _FILE_SHARE_READ | _FILE_SHARE_WRITE | _FILE_SHARE_DELETE,
    )
    if handle is None:
        return DirectoryListing(refused, False, False, None)
    try:
        classification = _classify_handle(handle)
        if classification != CLASSIFICATION_DIRECTORY:
            result = DirectoryListing(classification, False, False, None)
        else:
            result = _list_through_handle(handle, max_entries)
    finally:
        if not _K32.CloseHandle(handle):
            raise Cfg1PiLeafError("ENUMERATION_HANDLE_NOT_CLOSED")
    return result


def _standard_end_of_file(handle) -> int | None:
    info = _FILE_STANDARD_INFO()
    ok = _K32.GetFileInformationByHandleEx(
        handle, _FileStandardInfo, ctypes.byref(info), ctypes.sizeof(info)
    )
    if not ok:
        return None
    size = int(info.EndOfFile)
    return size if size >= 0 else None


def _failed_payload_read(classification: str) -> PayloadFileRead:
    return PayloadFileRead(classification, False, False, None, None, None)


def _read_payload_file(path: str, max_bytes: int, retain: bool) -> PayloadFileRead:
    if not PLATFORM_SUPPORTED:
        raise Cfg1PiLeafError("UNSUPPORTED_PLATFORM")
    if type(path) is not str or not path:
        return _failed_payload_read(CLASSIFICATION_OTHER)
    if type(max_bytes) is not int or max_bytes < 0:
        raise Cfg1PiLeafError("MALFORMED_BOUND")
    handle, refused = _open_no_follow(
        path, _GENERIC_READ | _FILE_READ_ATTRIBUTES, _FILE_SHARE_READ
    )
    if handle is None:
        return _failed_payload_read(refused)
    try:
        descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY)
    except OSError:
        if not _K32.CloseHandle(handle):
            raise Cfg1PiLeafError("PAYLOAD_HANDLE_NOT_CLOSED") from None
        return _failed_payload_read(CLASSIFICATION_OTHER)

    result: PayloadFileRead | None = None
    try:
        os_handle = msvcrt.get_osfhandle(descriptor)
        classification = _classify_handle(os_handle)
        if classification != CLASSIFICATION_REGULAR_FILE:
            result = _failed_payload_read(classification)
        else:
            before = _standard_end_of_file(os_handle)
            if before is None:
                result = _failed_payload_read(CLASSIFICATION_OTHER)
            elif before > max_bytes:
                result = _failed_payload_read(CLASSIFICATION_REGULAR_FILE)
            else:
                digest = hashlib.sha256()
                chunks: list[bytes] = []
                total = 0
                limit = max_bytes + 1
                while total < limit:
                    chunk = os.read(descriptor, min(65536, limit - total))
                    if not chunk:
                        break
                    total += len(chunk)
                    digest.update(chunk)
                    if retain:
                        chunks.append(chunk)
                if total > max_bytes:
                    result = _failed_payload_read(CLASSIFICATION_REGULAR_FILE)
                else:
                    after = _standard_end_of_file(os_handle)
                    if after is None or before != total or after != total:
                        # The file changed during the read: no size, no digest.
                        result = PayloadFileRead(
                            CLASSIFICATION_REGULAR_FILE, True, False, None, None, None
                        )
                    else:
                        result = PayloadFileRead(
                            CLASSIFICATION_REGULAR_FILE,
                            True,
                            True,
                            total,
                            digest.hexdigest(),
                            b"".join(chunks) if retain else None,
                        )
    except OSError:
        result = _failed_payload_read(CLASSIFICATION_OTHER)
    finally:
        try:
            os.close(descriptor)
        except OSError:
            raise Cfg1PiLeafError("PAYLOAD_HANDLE_NOT_CLOSED") from None
    return result


def read_payload_file_digest(path: str, max_bytes: int) -> PayloadFileRead:
    """ONE open, ONE handle: classify, size, digest to EOF, size again.

    The bytes are hashed, counted and dropped -- never returned or parsed.
    """
    return _read_payload_file(path, max_bytes, False)


def read_payload_file_bytes(path: str, max_bytes: int) -> PayloadFileRead:
    """As :func:`read_payload_file_digest`, also returning the exact bytes.

    Used ONLY by static discovery to capture ``package.json`` bytes, which the
    caller then binds to an inventory entry by size and SHA-256.
    """
    return _read_payload_file(path, max_bytes, True)
