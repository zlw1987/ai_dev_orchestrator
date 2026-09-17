"""The ADVERSARY's own Win32 operations, for the FU15 authority regressions.

Test-only scaffolding. This is deliberately NOT a helper that calls production
code: every function here performs the attacker's operation directly, because
the whole point of Sec. 37.2's regressions is that the attacker's real call
must be observed to fail (or, for the no-pin control, to succeed).

**Why ``mklink`` is not used and must not be.** ``mklink /J`` refuses an
existing name with ``ERROR_ALREADY_EXISTS`` because it tries to CREATE the
name first; it never attempts in-place conversion, so its refusal proves
nothing about whether an existing directory can be turned into a junction
where it stands. Sec. 37.2's changelog row A' records that this exact
unsound oracle is what hid W4 during the investigation. The probe below
issues a direct ``DeviceIoControl(FSCTL_SET_REPARSE_POINT)`` instead.
"""

from __future__ import annotations

import os
import sys

WIN32 = sys.platform == "win32"

if WIN32:  # pragma: no branch - a platform constant
    import ctypes
    import ctypes.wintypes as wt

    _K32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _K32.CreateFileW.restype = wt.HANDLE
    _K32.CreateFileW.argtypes = [
        wt.LPCWSTR,
        wt.DWORD,
        wt.DWORD,
        ctypes.c_void_p,
        wt.DWORD,
        wt.DWORD,
        wt.HANDLE,
    ]
    _K32.CloseHandle.restype = wt.BOOL
    _K32.CloseHandle.argtypes = [wt.HANDLE]
    _K32.DeviceIoControl.restype = wt.BOOL
    _K32.DeviceIoControl.argtypes = [
        wt.HANDLE,
        wt.DWORD,
        ctypes.c_void_p,
        wt.DWORD,
        ctypes.c_void_p,
        wt.DWORD,
        ctypes.POINTER(wt.DWORD),
        ctypes.c_void_p,
    ]

    GENERIC_WRITE = 0x40000000
    FILE_SHARE_READ = 0x00000001
    FILE_SHARE_WRITE = 0x00000002
    FILE_SHARE_DELETE = 0x00000004
    OPEN_EXISTING = 3
    FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
    FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
    _INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
    _IO_REPARSE_TAG_MOUNT_POINT = 0xA0000003
    _FSCTL_SET_REPARSE_POINT = 0x000900A4

#: ``ERROR_SHARING_VIOLATION`` -- what a pin makes the adversary's open return.
ERROR_SHARING_VIOLATION = 32
#: ``ERROR_DIRECTORY_NOT_EMPTY`` -- W5.
ERROR_DIRECTORY_NOT_EMPTY = 145


def open_for_reparse_write(path) -> tuple[object, int]:
    """The adversary's write-access open of a directory.

    Returns ``(handle_or_None, win32_error)``. A pinned directory returns
    ``(None, ERROR_SHARING_VIOLATION)``: the open itself is refused, so
    ``FSCTL_SET_REPARSE_POINT`` is never reached (W3).
    """
    handle = _K32.CreateFileW(
        str(path),
        GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        None,
        OPEN_EXISTING,
        FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT,
        None,
    )
    if handle is None or handle == _INVALID_HANDLE_VALUE:
        return None, ctypes.get_last_error()
    return handle, 0


def set_mount_point_reparse(handle, target) -> tuple[bool, int]:
    """Issue ``FSCTL_SET_REPARSE_POINT`` directly. Returns ``(ok, error)``."""
    substitute = ("\\??\\" + str(target)).encode("utf-16-le")
    printed = str(target).encode("utf-16-le")
    path_buffer = substitute + b"\x00\x00" + printed + b"\x00\x00"
    data_length = 8 + len(path_buffer)
    buffer = ctypes.create_string_buffer(8 + data_length)
    address = ctypes.addressof(buffer)
    ctypes.memmove(address, _IO_REPARSE_TAG_MOUNT_POINT.to_bytes(4, "little"), 4)
    ctypes.memmove(address + 4, data_length.to_bytes(2, "little"), 2)
    ctypes.memmove(address + 6, (0).to_bytes(2, "little"), 2)
    ctypes.memmove(address + 8, (0).to_bytes(2, "little"), 2)
    ctypes.memmove(address + 10, len(substitute).to_bytes(2, "little"), 2)
    ctypes.memmove(address + 12, (len(substitute) + 2).to_bytes(2, "little"), 2)
    ctypes.memmove(address + 14, len(printed).to_bytes(2, "little"), 2)
    ctypes.memmove(address + 16, path_buffer, len(path_buffer))
    returned = wt.DWORD(0)
    ok = _K32.DeviceIoControl(
        handle,
        _FSCTL_SET_REPARSE_POINT,
        buffer,
        8 + data_length,
        None,
        0,
        ctypes.byref(returned),
        None,
    )
    return bool(ok), ctypes.get_last_error()


def close_handle(handle) -> None:
    if handle is not None:
        _K32.CloseHandle(handle)


def attempt_in_place_reparse_conversion(path, target) -> tuple[str, int]:
    """The whole attack, in one call. Returns ``(outcome, win32_error)``.

    ``outcome`` is one of ``"converted"``, ``"open_refused"`` or
    ``"fsctl_refused"`` -- three genuinely different facts that a single
    boolean would collapse, and the difference is exactly what distinguishes
    "the pin stopped it" (``open_refused``, W3) from "the directory was
    non-empty" (``fsctl_refused`` with error 145, W5).
    """
    handle, error = open_for_reparse_write(path)
    if handle is None:
        return "open_refused", error
    try:
        ok, error = set_mount_point_reparse(handle, target)
        return ("converted" if ok else "fsctl_refused"), (0 if ok else error)
    finally:
        close_handle(handle)


def file_identity(path) -> tuple[int, int]:
    """``(st_dev, st_ino)`` WITHOUT following a redirect."""
    result = os.lstat(str(path))
    return (result.st_dev, result.st_ino)


def attempt_rename(source, destination) -> int | None:
    """Rename, returning the Win32 error, or ``None`` when it succeeded."""
    try:
        os.rename(str(source), str(destination))
    except OSError as exc:
        return getattr(exc, "winerror", None) or exc.errno
    return None


def attempt_rmdir(path) -> int | None:
    """Remove a directory, returning the Win32 error, or ``None`` on success."""
    try:
        os.rmdir(str(path))
    except OSError as exc:
        return getattr(exc, "winerror", None) or exc.errno
    return None
