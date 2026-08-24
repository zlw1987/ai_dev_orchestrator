"""Narrow Windows named-pipe primitives for the AR2 broker. EXPERIMENT ONLY.

Deliberately thin. FU1 section 6.2 established that ``_winapi`` -- not a public
API, but present in the shipped interpreter -- already exposes every pipe call
AR2 needs, including the ``Overlapped`` type with ``.cancel()``. ``ctypes`` is
used for **one** thing only: building the current-user ``SECURITY_ATTRIBUTES``
that ``_winapi.CreateNamedPipe`` accepts as a pointer. No full ctypes binding of
the pipe API is built, and ``CancelIoEx`` / ``CancelSynchronousIo`` are not bound
at all (FU1 section 7.6 option B, rejected).

Three ``_winapi`` gaps, each handled by a literal rather than a workaround:

    PIPE_REJECT_REMOTE_CLIENTS  absent -> 0x8
    PIPE_TYPE_BYTE              absent -> 0x0
    PIPE_READMODE_BYTE          absent -> 0x0
    DisconnectNamedPipe         absent -> not used; CloseHandle alone retires
                                          the name (measured: a later client
                                          CreateFile gets ERROR_FILE_NOT_FOUND)

Measured on this host and interpreter, and relied on by :mod:`ar2.broker`:

- an overlapped ``ConnectNamedPipe`` / ``ReadFile`` / ``WriteFile`` can be
  cancelled from **any** thread, and reaped in microseconds;
- a wait co-waiting an operation event and a manual-reset shutdown event is
  woken by ``SetEvent`` from another thread;
- ``Overlapped.GetOverlappedResult(False)`` **returns** ``(0, 995)`` for an
  aborted operation and **raises** ``OSError`` for anything else -- notably
  ``ERROR_BROKEN_PIPE`` (109) when the client's handle closes.

**This module makes no security claim.** A user-scoped DACL and an unpredictable
name are integrity and attribution controls, not OS isolation against a same-user
adversary (AR2D section 10.4).
"""

from __future__ import annotations

import _winapi
import ctypes
import secrets
from ctypes import wintypes
from dataclasses import dataclass

# -- constants -----------------------------------------------------------------

PIPE_PREFIX = "\\\\.\\pipe\\"
PIPE_NAME_PREFIX = "aido-ar2-"

PIPE_REJECT_REMOTE_CLIENTS = 0x8
PIPE_TYPE_BYTE = 0x0
PIPE_READMODE_BYTE = 0x0

ERROR_FILE_NOT_FOUND = 2
ERROR_BROKEN_PIPE = 109
ERROR_PIPE_BUSY = 231
ERROR_NO_DATA = 232
ERROR_MORE_DATA = 234
ERROR_OPERATION_ABORTED = 995
ERROR_IO_PENDING = 997

WAIT_OBJECT_0 = 0
WAIT_TIMEOUT = 258

PIPE_BUFFER_BYTES = 64 * 1024

TOKEN_QUERY = 0x0008
_TOKEN_USER_CLASS = 1
_SDDL_REVISION_1 = 1


class WindowsPipeError(Exception):
    """A named-pipe primitive failed. Always fails closed; never guesses."""


# -- ctypes surface, used ONLY for SECURITY_ATTRIBUTES -------------------------

_advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

_kernel32.GetCurrentProcess.restype = wintypes.HANDLE
_kernel32.GetCurrentProcess.argtypes = []
_kernel32.LocalFree.restype = ctypes.c_void_p
_kernel32.LocalFree.argtypes = [ctypes.c_void_p]
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
_kernel32.CloseHandle.restype = wintypes.BOOL
_advapi32.OpenProcessToken.argtypes = [
    wintypes.HANDLE,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.HANDLE),
]
_advapi32.OpenProcessToken.restype = wintypes.BOOL
_advapi32.GetTokenInformation.argtypes = [
    wintypes.HANDLE,
    ctypes.c_int,
    ctypes.c_void_p,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
]
_advapi32.GetTokenInformation.restype = wintypes.BOOL
_advapi32.ConvertSidToStringSidW.argtypes = [
    ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_wchar_p),
]
_advapi32.ConvertSidToStringSidW.restype = wintypes.BOOL
_advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
    wintypes.LPCWSTR,
    wintypes.DWORD,
    ctypes.POINTER(ctypes.c_void_p),
    ctypes.POINTER(wintypes.ULONG),
]
_advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = wintypes.BOOL


class _SECURITY_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("nLength", wintypes.DWORD),
        ("lpSecurityDescriptor", ctypes.c_void_p),
        ("bInheritHandle", wintypes.BOOL),
    ]


def current_user_sid_string() -> str:
    """The launching user's SID in SDDL string form. No value is ever recorded."""
    token = wintypes.HANDLE()
    if not _advapi32.OpenProcessToken(
        _kernel32.GetCurrentProcess(), TOKEN_QUERY, ctypes.byref(token)
    ):
        raise WindowsPipeError("pipe error: the process token could not be opened")
    try:
        size = wintypes.DWORD(0)
        _advapi32.GetTokenInformation(
            token, _TOKEN_USER_CLASS, None, 0, ctypes.byref(size)
        )
        if size.value == 0:
            raise WindowsPipeError("pipe error: token user information is unavailable")
        buffer = ctypes.create_string_buffer(size.value)
        if not _advapi32.GetTokenInformation(
            token, _TOKEN_USER_CLASS, buffer, size, ctypes.byref(size)
        ):
            raise WindowsPipeError("pipe error: token user information could not be read")
        sid_pointer = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_void_p))[0]
        out = ctypes.c_wchar_p()
        if not _advapi32.ConvertSidToStringSidW(
            ctypes.c_void_p(sid_pointer), ctypes.byref(out)
        ):
            raise WindowsPipeError("pipe error: the user SID could not be stringified")
        try:
            value = out.value
        finally:
            _kernel32.LocalFree(ctypes.cast(out, ctypes.c_void_p))
        if not value:
            raise WindowsPipeError("pipe error: the user SID stringified to nothing")
        return value
    finally:
        _kernel32.CloseHandle(token)


@dataclass
class UserScopedSecurityAttributes:
    """A ``SECURITY_ATTRIBUTES`` granting the current user only.

    ``D:P`` makes the DACL **protected**, so nothing is inherited, and the single
    ACE grants ``GA`` (generic all) to exactly the launching user's SID. No
    Administrators or SYSTEM ACE is added: this is deliberately the narrowest
    descriptor the broker can run under, and it is **not** a defence against a
    same-user adversary (AR2D section 10.4).
    """

    sddl: str
    _descriptor: ctypes.c_void_p
    _structure: _SECURITY_ATTRIBUTES
    _released: bool = False

    @property
    def address(self) -> int:
        """The pointer ``_winapi.CreateNamedPipe`` accepts for lpSecurityAttributes.

        FU1A: fails closed once :meth:`release` has run. The struct's
        ``lpSecurityDescriptor`` field still points at freed memory after
        release, so handing this address to anything after that point would be
        a use-after-free waiting to happen -- refused rather than risked.
        """
        if self._released:
            raise WindowsPipeError(
                "pipe error: the security descriptor was already released; its "
                "address must not be reused"
            )
        return ctypes.addressof(self._structure)

    @property
    def released(self) -> bool:
        """Whether :meth:`release` has run. Test/diagnostic observability only."""
        return self._released

    def release(self) -> None:
        """Free the security descriptor ``ConvertStringSecurityDescriptorToSecurityDescriptorW``
        allocated (FU-A/F: this was previously never freed -- a per-run resource
        leak). Idempotent and never double-frees: a second call, or a call on an
        object that never successfully allocated one, is a safe no-op.

        The descriptor only needs to remain valid through the ONE
        ``CreateNamedPipe`` call that consumes it -- Windows copies what it needs
        from the security descriptor into the kernel pipe object at creation
        time, so there is nothing further for this memory to back once that call
        has returned (successfully or not). Call this once, immediately after
        that call, regardless of outcome.
        """
        if self._released:
            return
        if self._descriptor.value:
            _kernel32.LocalFree(self._descriptor)
        self._released = True

    def describe(self) -> dict[str, object]:
        """A recordable description. The SID itself is NOT recorded."""
        return {
            "security_descriptor_built": True,
            "dacl_protected": self.sddl.startswith("D:P"),
            "ace_count": self.sddl.count("(A;"),
            "grants_current_user_only": True,
            "inherit_handle": False,
            "note": (
                "An integrity and attribution control, not OS isolation. A "
                "same-user process does not need the broker at all."
            ),
        }


def build_current_user_security_attributes() -> UserScopedSecurityAttributes:
    """Build the user-scoped ``SECURITY_ATTRIBUTES``, or fail closed."""
    sid = current_user_sid_string()
    sddl = "D:P(A;;GA;;;" + sid + ")"
    descriptor = ctypes.c_void_p()
    if not _advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW(
        sddl, _SDDL_REVISION_1, ctypes.byref(descriptor), None
    ):
        raise WindowsPipeError(
            "pipe error: the user-scoped security descriptor could not be built"
        )
    structure = _SECURITY_ATTRIBUTES()
    structure.nLength = ctypes.sizeof(_SECURITY_ATTRIBUTES)
    structure.lpSecurityDescriptor = descriptor
    structure.bInheritHandle = False
    return UserScopedSecurityAttributes(
        sddl=sddl, _descriptor=descriptor, _structure=structure
    )


# -- pipe primitives -----------------------------------------------------------


def random_pipe_name() -> str:
    """A per-run, unpredictable pipe name: 128 bits from ``secrets.token_hex``."""
    return PIPE_PREFIX + PIPE_NAME_PREFIX + secrets.token_hex(16)


def create_first_instance_pipe(
    name: str, security: UserScopedSecurityAttributes
) -> int:
    """Create the ONE overlapped pipe instance, refusing a squatted name.

    ``FILE_FLAG_FIRST_PIPE_INSTANCE`` makes squatting fail closed: if the name
    already exists, creation raises ``ERROR_PIPE_BUSY`` and the run refuses to
    start rather than talking to somebody else's pipe.
    """
    try:
        return _winapi.CreateNamedPipe(
            name,
            _winapi.PIPE_ACCESS_DUPLEX
            | _winapi.FILE_FLAG_FIRST_PIPE_INSTANCE
            | _winapi.FILE_FLAG_OVERLAPPED,
            PIPE_TYPE_BYTE
            | PIPE_READMODE_BYTE
            | _winapi.PIPE_WAIT
            | PIPE_REJECT_REMOTE_CLIENTS,
            1,
            PIPE_BUFFER_BYTES,
            PIPE_BUFFER_BYTES,
            0,
            security.address,
        )
    except OSError as exc:
        raise WindowsPipeError(
            "pipe error: the per-run named pipe instance could not be created "
            f"(winerror {exc.winerror}); the run refuses to start"
        ) from exc


def create_shutdown_event() -> int:
    """A manual-reset, initially unsignalled event the controller sets once."""
    return _winapi.CreateEventW(0, True, False, None)


def set_event(handle: int) -> None:
    _winapi.SetEvent(handle)


def close_handle(handle: int) -> None:
    _winapi.CloseHandle(handle)


def wait_any(handles: list[int], timeout_ms: int) -> int:
    """Bounded ``WaitForMultipleObjects``. Returns the index, or ``WAIT_TIMEOUT``."""
    return _winapi.WaitForMultipleObjects(handles, False, timeout_ms)


def connect_overlapped(pipe_handle: int):
    """Issue one overlapped ``ConnectNamedPipe``. Returns the ``Overlapped``."""
    return _winapi.ConnectNamedPipe(pipe_handle, overlapped=True)


def read_overlapped(pipe_handle: int, size: int):
    """Issue one overlapped ``ReadFile``. Returns ``(Overlapped, err)``."""
    return _winapi.ReadFile(pipe_handle, size, True)


def write_overlapped(pipe_handle: int, payload: bytes):
    """Issue one overlapped ``WriteFile``. Returns ``(Overlapped, err)``."""
    return _winapi.WriteFile(pipe_handle, payload, True)


@dataclass(frozen=True)
class ReapResult:
    """What a bounded reap of one overlapped operation actually observed."""

    reaped: bool
    transferred: int
    error_code: int | None
    aborted: bool
    broken_pipe: bool


def reap_overlapped(overlapped, timeout_ms: int) -> ReapResult:
    """Bounded reap: wait on the operation's event, then read its result.

    Never an unbounded ``GetOverlappedResult(True)`` gamble. If the wait times
    out the operation is reported **unreaped**, and the caller must then neither
    close the handle nor release the ``Overlapped`` object (FU1 section 7.5).
    """
    rc = wait_any([overlapped.event], timeout_ms)
    if rc != WAIT_OBJECT_0:
        return ReapResult(
            reaped=False, transferred=0, error_code=None, aborted=False, broken_pipe=False
        )
    try:
        transferred, error_code = overlapped.GetOverlappedResult(False)
    except OSError as exc:
        code = exc.winerror
        return ReapResult(
            reaped=True,
            transferred=0,
            error_code=code,
            aborted=code == ERROR_OPERATION_ABORTED,
            broken_pipe=code in (ERROR_BROKEN_PIPE, ERROR_NO_DATA),
        )
    return ReapResult(
        reaped=True,
        transferred=transferred,
        error_code=error_code,
        aborted=error_code == ERROR_OPERATION_ABORTED,
        broken_pipe=error_code in (ERROR_BROKEN_PIPE, ERROR_NO_DATA),
    )


def overlapped_buffer(overlapped, length: int) -> bytes:
    """The bytes an overlapped read actually transferred."""
    return bytes(overlapped.getbuffer())[:length]


def connect_client(name: str) -> int:
    """Open a client handle to a local pipe. Test/local use only, never in AIDO."""
    return _winapi.CreateFile(
        name,
        _winapi.GENERIC_READ | _winapi.GENERIC_WRITE,
        0,
        0,
        _winapi.OPEN_EXISTING,
        0,
        0,
    )
