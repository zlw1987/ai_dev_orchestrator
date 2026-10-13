"""TEST-ONLY second-actor Win32 operations for the F5-A A2 ordinary-handle evidence.

This module is imported by ``test_cfg1_f5a_a2_ordinary_handle_semantics.py`` and is
also run as a script (``python ordinary_handle_actor.py <json>``) so that the same
operations can be issued from a SEPARATE PROCESS of the same user. Having one
definition for both is deliberate: the in-process and out-of-process results are
then comparable operation for operation.

Every function reports the REAL OS result of one ordinary Win32 call --
``{"ok": bool, "winerror": int}`` where ``winerror`` is ``GetLastError`` captured
immediately after a failing call (``0`` on success). Nothing here fabricates or
maps a status code.

What this module never does: it creates no junction, symlink, hard link or other
reparse point, opens nothing with ``FILE_FLAG_OPEN_REPARSE_POINT`` and never
requests ``FILE_WRITE_ATTRIBUTES``, so it cannot convert or relabel anything. It
works only on paths the calling test hands it, all of which are test-owned.
"""

from __future__ import annotations

import ctypes
import json
import sys
from ctypes import wintypes

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
DELETE = 0x00010000
FILE_READ_DATA = 0x00000001
FILE_READ_ATTRIBUTES = 0x00000080
SHARE_ALL = 0x7  # READ | WRITE | DELETE: the actor never narrows what it lets others do
CREATE_NEW = 1
CREATE_ALWAYS = 2
OPEN_EXISTING = 3
TRUNCATE_EXISTING = 5
BACKUP_SEMANTICS = 0x02000000  # only so a DIRECTORY can be opened at all; no reparse flag
MOVEFILE_REPLACE_EXISTING = 0x1

PAYLOAD = b"SECOND-ACTOR"

if sys.platform == "win32":
    _K = ctypes.WinDLL("kernel32", use_last_error=True)
    _K.CreateFileW.restype = wintypes.HANDLE
    _K.CreateFileW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
    ]
    _K.CloseHandle.restype = wintypes.BOOL
    _K.CloseHandle.argtypes = [wintypes.HANDLE]
    _K.WriteFile.restype = wintypes.BOOL
    _K.WriteFile.argtypes = [wintypes.HANDLE, wintypes.LPCVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
    _K.MoveFileExW.restype = wintypes.BOOL
    _K.MoveFileExW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD]
    _K.DeleteFileW.restype = wintypes.BOOL
    _K.DeleteFileW.argtypes = [wintypes.LPCWSTR]
    _K.RemoveDirectoryW.restype = wintypes.BOOL
    _K.RemoveDirectoryW.argtypes = [wintypes.LPCWSTR]
    _K.GetVolumeInformationW.restype = wintypes.BOOL
    _K.GetVolumeInformationW.argtypes = [
        wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD), wintypes.LPWSTR, wintypes.DWORD,
    ]
    _INVALID = wintypes.HANDLE(-1).value


def _outcome(ok: bool) -> dict:
    return {"ok": bool(ok), "winerror": 0 if ok else int(ctypes.get_last_error())}


def delete_file(path: str) -> dict:
    return _outcome(_K.DeleteFileW(path))


def remove_dir(path: str) -> dict:
    return _outcome(_K.RemoveDirectoryW(path))


def rename(src: str, dst: str) -> dict:
    """``MoveFileExW`` WITHOUT replace: ``dst`` must not exist."""
    return _outcome(_K.MoveFileExW(src, dst, 0))


def replace_over(src: str, dst: str) -> dict:
    """``MoveFileExW(REPLACE_EXISTING)``: ``src`` is moved onto the existing ``dst``."""
    return _outcome(_K.MoveFileExW(src, dst, MOVEFILE_REPLACE_EXISTING))


def open_close(path: str, access: int, disposition: int = OPEN_EXISTING, *, write: bool = False,
               directory: bool = False, share: int = SHARE_ALL) -> dict:
    """ONE ordinary ``CreateFileW``; optionally write :data:`PAYLOAD` at the handle's
    start; always close. No reparse flag, no attribute-write access."""
    handle = _K.CreateFileW(path, access, share, None, disposition, BACKUP_SEMANTICS if directory else 0, None)
    if handle is None or handle == _INVALID:
        return _outcome(False)
    try:
        if write:
            written = wintypes.DWORD(0)
            if not _K.WriteFile(handle, PAYLOAD, len(PAYLOAD), ctypes.byref(written), None):
                return _outcome(False)
        return _outcome(True)
    finally:
        _K.CloseHandle(handle)


def filesystem_name(path: str) -> str:
    """The volume's file system name, from the OS, for the volume containing ``path``."""
    root = ctypes.create_unicode_buffer(260)
    ctypes.windll.kernel32.GetVolumePathNameW(path, root, 260)
    name = ctypes.create_unicode_buffer(64)
    ok = _K.GetVolumeInformationW(root.value, None, 0, None, None, None, name, 64)
    return name.value if ok else "UNKNOWN"


#: The named second-actor operations. ``path`` is the held object; ``other`` is a
#: test-owned scratch file for ``replace_by_other``.
def run(op: str, path: str, other: str | None = None) -> dict:
    if op == "delete":
        return delete_file(path)
    if op == "remove_dir":
        return remove_dir(path)
    if op == "rename_away":
        return rename(path, path + ".moved")
    if op == "replace_by_other":
        assert other is not None
        return replace_over(other, path)
    if op == "open_write_existing":
        return open_close(path, GENERIC_WRITE, OPEN_EXISTING, write=True)
    if op == "truncate_existing":
        return open_close(path, GENERIC_WRITE, TRUNCATE_EXISTING, write=True)
    if op == "create_always":
        return open_close(path, GENERIC_WRITE, CREATE_ALWAYS, write=True)
    if op == "create_new":
        return open_close(path, GENERIC_WRITE, CREATE_NEW)
    if op == "open_read":
        return open_close(path, GENERIC_READ)
    if op == "open_read_data":
        return open_close(path, FILE_READ_DATA)
    if op == "open_read_attributes":
        return open_close(path, FILE_READ_ATTRIBUTES)
    if op == "open_write":
        return open_close(path, GENERIC_WRITE)
    if op == "open_read_write":
        return open_close(path, GENERIC_READ | GENERIC_WRITE)
    if op == "open_delete_access":
        return open_close(path, DELETE)
    raise ValueError(op)


if __name__ == "__main__":  # the separate-process actor
    request = json.loads(sys.argv[1])
    print(json.dumps([{"op": op, "path": path, **run(op, path, other)} for op, path, other in request]))
