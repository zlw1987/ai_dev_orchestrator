"""DL-4B S3 — the authority identity's file access (FD-14, FD-17, FD-18).

A runs no Git and no subprocess (C-10). Everything it learns about the clone
and everything it receives from the execution identity X comes through the
small :class:`AuthorityFiles` interface below, and every read is a plain file
read that never follows a reparse point:

```text
read_file(path, limit)        one handle, write and delete sharing DENIED, opened
                              without following a reparse point; facts (final path,
                              kind, reparse, link count, owner + DACL) from that handle
object_facts(path)            the same facts, without reading content
list_directory(path)          names, kinds and reparse flags from the listing itself
file_identity(path)           (volume, file id) of the object at path, not followed
create_directory(path, sd)    EXCLUSIVE create of one new directory whose protected
                              DACL is set AT CREATION from a code-constant descriptor
create_file(path, content)    EXCLUSIVE create of one new file, flushed
```

The two creating operations exist only so A can publish a per-ticket handoff
and create a per-ticket outbox in the exchange root it owns. A creates nothing
in the clone, removes nothing, renames nothing and changes no existing ACL.

:class:`WindowsAuthorityFiles` is the production implementation (read-only
facts from S0's :class:`~.windows_security.WindowsSecurityFacts`, and
``CreateDirectoryW``/``CreateFileW`` for the two creates). Offline tests supply
their own implementation over ``tmp_path`` with synthetic owners and
descriptors, exactly as S0's tests supply synthetic security facts; a session
built with one is never production (S2).
"""

from __future__ import annotations

import ctypes
import os
import sys
from ctypes import wintypes
from typing import Protocol

from ai_dev_orchestrator.integration.boundary_facts import DirectoryEntry, ObjectFacts


class AuthorityFiles(Protocol):
    """The file access the authority identity has. Every method may raise;
    every consumer turns an exception into a refusal."""

    def read_file(self, path: str, limit: int) -> tuple[ObjectFacts, bytes] | None:
        """Facts and at most ``limit + 1`` bytes, from one handle that denies
        write and delete sharing; ``None`` if nothing exists at ``path``."""
        ...

    def object_facts(self, path: str) -> ObjectFacts | None: ...

    def list_directory(self, path: str) -> tuple[DirectoryEntry, ...]: ...

    def file_identity(self, path: str) -> tuple[int, int]: ...

    def create_directory(self, path: str, security_descriptor: bytes) -> None:
        """Create ``path`` with exactly ``security_descriptor`` applied at
        creation. Raises :class:`FileExistsError` if anything exists there."""
        ...

    def create_file(self, path: str, content: bytes) -> None:
        """Create ``path`` exclusively, write ``content`` and flush it. Raises
        :class:`FileExistsError` if anything exists there."""
        ...


_LOAD_LIBRARY_SEARCH_SYSTEM32 = 0x0000_0800
_GENERIC_WRITE = 0x4000_0000
_CREATE_NEW = 1
_FILE_ATTRIBUTE_NORMAL = 0x80
_ERROR_FILE_EXISTS = 80
_ERROR_ALREADY_EXISTS = 183
_INVALID_HANDLE = ctypes.c_void_p(-1).value


class _SECURITY_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("nLength", wintypes.DWORD),
        ("lpSecurityDescriptor", ctypes.c_void_p),
        ("bInheritHandle", wintypes.BOOL),
    ]


def _created_error(call: str) -> OSError:
    error = ctypes.get_last_error()
    if error in (_ERROR_FILE_EXISTS, _ERROR_ALREADY_EXISTS):
        return FileExistsError(f"{call}: something already exists at that path.")
    return OSError(f"{call} failed (Win32 error {error}).")


class WindowsAuthorityFiles:
    """Production :class:`AuthorityFiles`. Windows only; every DLL from
    ``System32``. Reads are S0's read-only facts; the two creates are the only
    calls here that change anything, and each creates one new object."""

    def __init__(self) -> None:
        if sys.platform != "win32" or os.name != "nt":
            raise OSError("the authority identity's file access is Windows-only.")
        from ai_dev_orchestrator.integration.windows_security import WindowsSecurityFacts

        self._facts = WindowsSecurityFacts()
        kernel32 = ctypes.WinDLL("kernel32.dll", use_last_error=True, winmode=_LOAD_LIBRARY_SEARCH_SYSTEM32)
        H, D, B, P = wintypes.HANDLE, wintypes.DWORD, wintypes.BOOL, ctypes.c_void_p
        kernel32.CreateDirectoryW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(_SECURITY_ATTRIBUTES)]
        kernel32.CreateDirectoryW.restype = B
        kernel32.CreateFileW.argtypes = [wintypes.LPCWSTR, D, D, P, D, D, H]
        kernel32.CreateFileW.restype = H
        kernel32.WriteFile.argtypes = [H, P, D, ctypes.POINTER(D), P]
        kernel32.WriteFile.restype = B
        kernel32.FlushFileBuffers.argtypes = [H]
        kernel32.FlushFileBuffers.restype = B
        kernel32.CloseHandle.argtypes = [H]
        kernel32.CloseHandle.restype = B
        self._kernel32 = kernel32

    def read_file(self, path: str, limit: int) -> tuple[ObjectFacts, bytes] | None:
        return self._facts.read_file(path, limit)

    def object_facts(self, path: str) -> ObjectFacts | None:
        return self._facts.object_facts(path)

    def list_directory(self, path: str) -> tuple[DirectoryEntry, ...]:
        return self._facts.list_directory(path)

    def file_identity(self, path: str) -> tuple[int, int]:
        info = os.lstat(path)
        return info.st_dev, info.st_ino

    def create_directory(self, path: str, security_descriptor: bytes) -> None:
        if type(security_descriptor) is not bytes or not security_descriptor:
            raise OSError("a directory is created only with an explicit security descriptor.")
        buffer = ctypes.create_string_buffer(security_descriptor, len(security_descriptor))
        attributes = _SECURITY_ATTRIBUTES(
            ctypes.sizeof(_SECURITY_ATTRIBUTES), ctypes.cast(buffer, ctypes.c_void_p), False
        )
        if not self._kernel32.CreateDirectoryW(path, ctypes.byref(attributes)):
            raise _created_error("CreateDirectoryW")

    def create_file(self, path: str, content: bytes) -> None:
        handle = self._kernel32.CreateFileW(
            path, _GENERIC_WRITE, 0, None, _CREATE_NEW, _FILE_ATTRIBUTE_NORMAL, None
        )
        if handle in (None, _INVALID_HANDLE):
            raise _created_error("CreateFileW")
        try:
            view = memoryview(content)
            while view:
                written = wintypes.DWORD()
                chunk = view[: 1 << 20]
                buffer = (ctypes.c_char * len(chunk)).from_buffer_copy(chunk)
                if not self._kernel32.WriteFile(handle, buffer, len(chunk), ctypes.byref(written), None):
                    raise OSError(f"WriteFile failed (Win32 error {ctypes.get_last_error()}).")
                if written.value == 0:
                    raise OSError("WriteFile wrote nothing.")
                view = view[written.value:]
            if not self._kernel32.FlushFileBuffers(handle):
                raise OSError(f"FlushFileBuffers failed (Win32 error {ctypes.get_last_error()}).")
        finally:
            self._kernel32.CloseHandle(handle)
