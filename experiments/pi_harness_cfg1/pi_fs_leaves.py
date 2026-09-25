"""The genuine leaf effects of the canonical static Pi identity proof P.

Design ``PHASE_5F3B_HARNESS_CFG1_L1_BOUNDARY_FU1_DESIGN.md`` (R6) Sec. 7.2,
as amended by ``..._OC3_AMEND1_DESIGN.md`` (AMD-1, AMD-2): P's injectable
leaves are ONLY (i) the Sec. 7.2 no-follow inspection/identity primitive and
(ii) a one-handle bounded digest reader, plus P's explicit ambient mapping.
This module holds the genuine binding of (i) and (ii) and nothing else.

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
