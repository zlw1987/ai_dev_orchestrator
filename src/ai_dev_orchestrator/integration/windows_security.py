"""DL-4B S0 — the production source of Windows security facts.

:class:`WindowsSecurityFacts` reads, and only reads:

- the running process's primary token (user, groups, privileges, elevation,
  integrity level, default DACL);
- the security descriptors of the running process, its current thread and its
  token;
- the owner, DACL, attributes, link count and final path of named file-system
  objects, each from **one** handle opened with ``FILE_FLAG_OPEN_REPARSE_POINT``
  (a reparse point is described, never followed);
- an account's groups and privileges as AuthZ computes them from its SID
  (``AuthzInitializeContextFromSid`` with ``AUTHZ_COMPUTE_PRIVILEGES``), and its
  name and type from ``LookupAccountSid``;
- the process's window station and desktop;
- environment variable **names** (never values, except ``PATH``, ``TEMP`` and
  ``TMP``, which are locations the proof must check).

It also offers AuthZ (``AuthzAccessCheck`` with ``MAXIMUM_ALLOWED``) as an
evaluator independent of the pure one, run over an in-memory descriptor.

It sets no ACL, owner or privilege, creates no account, file, directory, task
or process, writes nothing, opens no network connection, runs no subprocess and
enumerates no process. Every DLL is loaded from ``System32`` only
(``LOAD_LIBRARY_SEARCH_SYSTEM32``), so neither the working directory nor
``PATH`` can supply one. Outside Windows every method refuses.
"""

from __future__ import annotations

import ctypes
import os
import sys
import uuid
from ctypes import wintypes

from ai_dev_orchestrator.integration.boundary_facts import (
    CodeLoadFacts,
    DirectoryEntry,
    ObjectFacts,
    PrincipalFacts,
    ProcessFacts,
    SessionFacts,
    TokenFacts,
)
from ai_dev_orchestrator.integration.security_descriptor import (
    ObjectKind,
    Principal,
    is_logon_sid,
    parse_security_descriptor,
    sid_from_bytes,
    sid_to_bytes,
)

_LOAD_LIBRARY_SEARCH_SYSTEM32 = 0x0000_0800

_READ_CONTROL = 0x0002_0000
_GENERIC_READ = 0x8000_0000
_FILE_READ_ATTRIBUTES = 0x0080
_FILE_SHARE_READ = 0x1
_FILE_SHARE_WRITE = 0x2
_FILE_SHARE_DELETE = 0x4
_OPEN_EXISTING = 3
_FILE_FLAG_BACKUP_SEMANTICS = 0x0200_0000
_FILE_FLAG_OPEN_REPARSE_POINT = 0x0020_0000
_FILE_ATTRIBUTE_DIRECTORY = 0x10
_FILE_ATTRIBUTE_REPARSE_POINT = 0x400
_ERROR_FILE_NOT_FOUND = 2
_ERROR_PATH_NOT_FOUND = 3
_ERROR_BAD_LENGTH = 24
_ERROR_INSUFFICIENT_BUFFER = 122
_SE_FILE_OBJECT = 1
_SE_KERNEL_OBJECT = 6
_OWNER_SECURITY_INFORMATION = 0x1
_DACL_SECURITY_INFORMATION = 0x4
_TOKEN_QUERY = 0x0008

_TOKEN_USER = 1
_TOKEN_GROUPS = 2
_TOKEN_PRIVILEGES = 3
_TOKEN_DEFAULT_DACL = 6
_TOKEN_ELEVATION_TYPE = 18
_TOKEN_ELEVATION = 20
_TOKEN_INTEGRITY_LEVEL = 25

_AUTHZ_RM_FLAG_NO_AUDIT = 0x1
_AUTHZ_SKIP_TOKEN_GROUPS = 0x2
_AUTHZ_COMPUTE_PRIVILEGES = 0x8
_AUTHZ_CONTEXT_INFO_GROUPS = 2
_AUTHZ_CONTEXT_INFO_PRIVILEGES = 4
_MAXIMUM_ALLOWED = 0x0200_0000
_SE_GROUP_ENABLED_MANDATORY = 0x7

_UOI_FLAGS = 1
_UOI_NAME = 2
_UOI_USER_SID = 4
_WSF_VISIBLE = 0x1

_FOLDERID_PROGRAM_DATA = "62AB5D82-FDC1-4DC3-A9DD-070D1D495D97"
_FOLDERID_ROAMING_APP_DATA = "3EB685DB-65F9-4CF6-A03A-E3EF65729F3D"
_FOLDERID_LOCAL_APP_DATA = "F1B32785-6FBA-4FCF-9D55-7B8E7F157091"


class WindowsSecurityError(OSError):
    """A Win32 security query failed. Names the call and the error number only."""


def _require_windows() -> None:
    if sys.platform != "win32" or os.name != "nt":
        raise WindowsSecurityError(
            "the identity boundary reads Windows security facts and refuses to run elsewhere."
        )


class _FILETIME(ctypes.Structure):
    _fields_ = [("low", wintypes.DWORD), ("high", wintypes.DWORD)]


class _BY_HANDLE_FILE_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("dwFileAttributes", wintypes.DWORD),
        ("ftCreationTime", _FILETIME),
        ("ftLastAccessTime", _FILETIME),
        ("ftLastWriteTime", _FILETIME),
        ("dwVolumeSerialNumber", wintypes.DWORD),
        ("nFileSizeHigh", wintypes.DWORD),
        ("nFileSizeLow", wintypes.DWORD),
        ("nNumberOfLinks", wintypes.DWORD),
        ("nFileIndexHigh", wintypes.DWORD),
        ("nFileIndexLow", wintypes.DWORD),
    ]


class _SID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Sid", ctypes.c_void_p), ("Attributes", wintypes.DWORD)]


class _LUID(ctypes.Structure):
    _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]


class _AUTHZ_ACCESS_REQUEST(ctypes.Structure):
    _fields_ = [
        ("DesiredAccess", wintypes.DWORD),
        ("PrincipalSelfSid", ctypes.c_void_p),
        ("ObjectTypeList", ctypes.c_void_p),
        ("ObjectTypeListLength", wintypes.DWORD),
        ("OptionalArguments", ctypes.c_void_p),
    ]


class _AUTHZ_ACCESS_REPLY(ctypes.Structure):
    _fields_ = [
        ("ResultListLength", wintypes.DWORD),
        ("GrantedAccessMask", ctypes.POINTER(wintypes.DWORD)),
        ("SaclEvaluationResults", ctypes.POINTER(wintypes.DWORD)),
        ("Error", ctypes.POINTER(wintypes.DWORD)),
    ]


class _GUID(ctypes.Structure):
    _fields_ = [("raw", ctypes.c_ubyte * 16)]


class _USEROBJECTFLAGS(ctypes.Structure):
    _fields_ = [("fInherit", wintypes.BOOL), ("fReserved", wintypes.BOOL), ("dwFlags", wintypes.DWORD)]


_INVALID_HANDLE = ctypes.c_void_p(-1).value


def _fail(call: str) -> WindowsSecurityError:
    return WindowsSecurityError(f"{call} failed (Win32 error {ctypes.get_last_error()}).")


class WindowsSecurityFacts:
    """Read-only Windows security facts for the running process. See the module
    docstring for exactly what is read."""

    def __init__(self) -> None:
        _require_windows()
        load = lambda name: ctypes.WinDLL(  # noqa: E731
            name, use_last_error=True, winmode=_LOAD_LIBRARY_SEARCH_SYSTEM32
        )
        self._kernel32 = load("kernel32.dll")
        self._advapi32 = load("advapi32.dll")
        self._authz = load("authz.dll")
        self._user32 = load("user32.dll")
        self._shell32 = load("shell32.dll")
        self._ole32 = load("ole32.dll")
        self._userenv = load("userenv.dll")
        self._declare()

    # -- prototypes -------------------------------------------------------------

    def _declare(self) -> None:
        k, a, z, u = self._kernel32, self._advapi32, self._authz, self._user32
        H, D, B = wintypes.HANDLE, wintypes.DWORD, wintypes.BOOL
        P = ctypes.c_void_p
        k.CreateFileW.argtypes = [wintypes.LPCWSTR, D, D, P, D, D, H]
        k.CreateFileW.restype = H
        k.CloseHandle.argtypes = [H]
        k.CloseHandle.restype = B
        k.GetFileInformationByHandle.argtypes = [H, ctypes.POINTER(_BY_HANDLE_FILE_INFORMATION)]
        k.GetFileInformationByHandle.restype = B
        k.GetFinalPathNameByHandleW.argtypes = [H, wintypes.LPWSTR, D, D]
        k.GetFinalPathNameByHandleW.restype = D
        k.ReadFile.argtypes = [H, P, D, ctypes.POINTER(D), P]
        k.ReadFile.restype = B
        k.GetCurrentProcess.restype = H
        k.GetCurrentThread.restype = H
        k.GetCurrentThreadId.restype = D
        k.LocalFree.argtypes = [P]
        k.LocalFree.restype = P
        k.GetEnvironmentStringsW.restype = P
        k.FreeEnvironmentStringsW.argtypes = [P]
        k.FreeEnvironmentStringsW.restype = B
        k.GetComputerNameW.argtypes = [wintypes.LPWSTR, ctypes.POINTER(D)]
        k.GetComputerNameW.restype = B
        a.OpenProcessToken.argtypes = [H, D, ctypes.POINTER(H)]
        a.OpenProcessToken.restype = B
        a.GetTokenInformation.argtypes = [H, ctypes.c_int, P, D, ctypes.POINTER(D)]
        a.GetTokenInformation.restype = B
        a.GetSecurityInfo.argtypes = [H, ctypes.c_int, D, ctypes.POINTER(P), ctypes.POINTER(P),
                                      ctypes.POINTER(P), ctypes.POINTER(P), ctypes.POINTER(P)]
        a.GetSecurityInfo.restype = D
        a.GetSecurityDescriptorLength.argtypes = [P]
        a.GetSecurityDescriptorLength.restype = D
        a.GetLengthSid.argtypes = [P]
        a.GetLengthSid.restype = D
        a.LookupAccountSidW.argtypes = [wintypes.LPCWSTR, P, wintypes.LPWSTR, ctypes.POINTER(D),
                                        wintypes.LPWSTR, ctypes.POINTER(D), ctypes.POINTER(ctypes.c_int)]
        a.LookupAccountSidW.restype = B
        a.LookupPrivilegeNameW.argtypes = [wintypes.LPCWSTR, P, wintypes.LPWSTR, ctypes.POINTER(D)]
        a.LookupPrivilegeNameW.restype = B
        z.AuthzInitializeResourceManager.argtypes = [D, P, P, P, wintypes.LPCWSTR, ctypes.POINTER(P)]
        z.AuthzInitializeResourceManager.restype = B
        z.AuthzInitializeContextFromSid.argtypes = [D, P, P, P, _LUID, P, ctypes.POINTER(P)]
        z.AuthzInitializeContextFromSid.restype = B
        z.AuthzAddSidsToContext.argtypes = [P, ctypes.POINTER(_SID_AND_ATTRIBUTES), D,
                                            ctypes.POINTER(_SID_AND_ATTRIBUTES), D, ctypes.POINTER(P)]
        z.AuthzAddSidsToContext.restype = B
        z.AuthzGetInformationFromContext.argtypes = [P, ctypes.c_int, D, ctypes.POINTER(D), P]
        z.AuthzGetInformationFromContext.restype = B
        z.AuthzAccessCheck.argtypes = [D, P, ctypes.POINTER(_AUTHZ_ACCESS_REQUEST), P, P, P, D,
                                       ctypes.POINTER(_AUTHZ_ACCESS_REPLY), P]
        z.AuthzAccessCheck.restype = B
        z.AuthzFreeContext.argtypes = [P]
        z.AuthzFreeContext.restype = B
        z.AuthzFreeResourceManager.argtypes = [P]
        z.AuthzFreeResourceManager.restype = B
        u.GetProcessWindowStation.restype = H
        u.GetThreadDesktop.argtypes = [D]
        u.GetThreadDesktop.restype = H
        u.GetUserObjectInformationW.argtypes = [H, ctypes.c_int, P, D, ctypes.POINTER(D)]
        u.GetUserObjectInformationW.restype = B
        self._shell32.SHGetKnownFolderPath.argtypes = [ctypes.POINTER(_GUID), D, H, ctypes.POINTER(P)]
        self._shell32.SHGetKnownFolderPath.restype = ctypes.c_long
        self._ole32.CoTaskMemFree.argtypes = [P]
        self._ole32.CoTaskMemFree.restype = None
        self._userenv.GetUserProfileDirectoryW.argtypes = [H, wintypes.LPWSTR, ctypes.POINTER(D)]
        self._userenv.GetUserProfileDirectoryW.restype = B

    # -- small helpers -----------------------------------------------------------

    def _sid_at(self, pointer: int | None) -> str:
        if not pointer:
            raise WindowsSecurityError("a SID pointer was NULL.")
        length = self._advapi32.GetLengthSid(pointer)
        data = ctypes.string_at(pointer, length)
        sid, used = sid_from_bytes(data, 0, length)
        if used != length:
            raise WindowsSecurityError("a SID length disagreed with its structure.")
        return sid

    def _descriptor(self, handle: int, object_type: int, call: str) -> bytes:
        descriptor = ctypes.c_void_p()
        status = self._advapi32.GetSecurityInfo(
            handle, object_type, _OWNER_SECURITY_INFORMATION | _DACL_SECURITY_INFORMATION,
            None, None, None, None, ctypes.byref(descriptor),
        )
        if status != 0:
            raise WindowsSecurityError(f"{call} failed (Win32 error {status}).")
        try:
            length = self._advapi32.GetSecurityDescriptorLength(descriptor)
            return ctypes.string_at(descriptor, length)
        finally:
            self._kernel32.LocalFree(descriptor)

    def _token_information(self, token: int, cls: int) -> ctypes.Array:
        needed = wintypes.DWORD()
        self._advapi32.GetTokenInformation(token, cls, None, 0, ctypes.byref(needed))
        # Variable-size classes report ERROR_INSUFFICIENT_BUFFER, fixed-size
        # ones ERROR_BAD_LENGTH; both report the size needed.
        if ctypes.get_last_error() not in (_ERROR_INSUFFICIENT_BUFFER, _ERROR_BAD_LENGTH) or not needed.value:
            raise _fail(f"GetTokenInformation({cls})")
        buffer = ctypes.create_string_buffer(needed.value)
        if not self._advapi32.GetTokenInformation(token, cls, buffer, needed, ctypes.byref(needed)):
            raise _fail(f"GetTokenInformation({cls})")
        return buffer

    def _groups_at(self, buffer: ctypes.Array) -> tuple[tuple[str, int], ...]:
        count = ctypes.cast(buffer, ctypes.POINTER(wintypes.DWORD))[0]
        first = ctypes.addressof(buffer) + ctypes.sizeof(ctypes.c_void_p)
        entries = (_SID_AND_ATTRIBUTES * count).from_address(first)
        return tuple((self._sid_at(entry.Sid), int(entry.Attributes)) for entry in entries)

    def _privileges_at(self, buffer: ctypes.Array) -> tuple[str, ...]:
        count = ctypes.cast(buffer, ctypes.POINTER(wintypes.DWORD))[0]
        names = []
        for index in range(count):
            luid = ctypes.addressof(buffer) + 4 + index * 12
            name = ctypes.create_unicode_buffer(128)
            size = wintypes.DWORD(len(name))
            if not self._advapi32.LookupPrivilegeNameW(None, luid, name, ctypes.byref(size)):
                raise _fail("LookupPrivilegeNameW")
            names.append(name.value)
        return tuple(names)

    def _open_token(self, access: int) -> int:
        token = wintypes.HANDLE()
        if not self._advapi32.OpenProcessToken(
            self._kernel32.GetCurrentProcess(), access, ctypes.byref(token)
        ):
            raise _fail("OpenProcessToken")
        return token.value

    def _known_folder(self, guid: str) -> str:
        folder = _GUID()
        ctypes.memmove(folder.raw, uuid.UUID(guid).bytes_le, 16)
        path = ctypes.c_void_p()
        status = self._shell32.SHGetKnownFolderPath(ctypes.byref(folder), 0, None, ctypes.byref(path))
        try:
            if status != 0 or not path.value:
                raise WindowsSecurityError(f"SHGetKnownFolderPath failed (HRESULT 0x{status & 0xFFFFFFFF:08x}).")
            return ctypes.wstring_at(path.value)
        finally:
            self._ole32.CoTaskMemFree(path)

    def _open(self, path: str, access: int, share: int) -> int | None:
        handle = self._kernel32.CreateFileW(
            path, access, share, None, _OPEN_EXISTING,
            _FILE_FLAG_BACKUP_SEMANTICS | _FILE_FLAG_OPEN_REPARSE_POINT, None,
        )
        if handle in (None, _INVALID_HANDLE):
            error = ctypes.get_last_error()
            if error in (_ERROR_FILE_NOT_FOUND, _ERROR_PATH_NOT_FOUND):
                return None
            raise WindowsSecurityError(f"CreateFileW failed (Win32 error {error}).")
        return handle

    def _facts_from_handle(self, handle: int) -> ObjectFacts:
        info = _BY_HANDLE_FILE_INFORMATION()
        if not self._kernel32.GetFileInformationByHandle(handle, ctypes.byref(info)):
            raise _fail("GetFileInformationByHandle")
        buffer = ctypes.create_unicode_buffer(32_768)
        length = self._kernel32.GetFinalPathNameByHandleW(handle, buffer, len(buffer), 0)
        if not length or length >= len(buffer):
            raise _fail("GetFinalPathNameByHandleW")
        final = buffer.value
        if final.startswith("\\\\?\\UNC\\"):
            final = "\\\\" + final[8:]
        elif final.startswith("\\\\?\\"):
            final = final[4:]
        return ObjectFacts(
            final_path=final,
            is_directory=bool(info.dwFileAttributes & _FILE_ATTRIBUTE_DIRECTORY),
            is_reparse_point=bool(info.dwFileAttributes & _FILE_ATTRIBUTE_REPARSE_POINT),
            link_count=int(info.nNumberOfLinks),
            security_descriptor=self._descriptor(handle, _SE_FILE_OBJECT, "GetSecurityInfo(file)"),
        )

    # -- SecurityFacts ------------------------------------------------------------

    def is_windows(self) -> bool:
        return sys.platform == "win32" and os.name == "nt"

    def environment_names(self) -> tuple[str, ...]:
        _require_windows()
        names = set(os.environ)
        block = self._kernel32.GetEnvironmentStringsW()
        if not block:
            raise _fail("GetEnvironmentStringsW")
        try:
            cursor = block
            while True:
                entry = ctypes.wstring_at(cursor)
                if not entry:
                    break
                names.add(entry.split("=", 1)[0] if not entry.startswith("=") else entry)
                cursor += (len(entry) + 1) * ctypes.sizeof(ctypes.c_wchar)
        finally:
            self._kernel32.FreeEnvironmentStringsW(block)
        return tuple(sorted(names))

    def current_token(self) -> TokenFacts:
        _require_windows()
        token = self._open_token(_TOKEN_QUERY)
        try:
            user = self._token_information(token, _TOKEN_USER)
            user_sid = self._sid_at(ctypes.cast(user, ctypes.POINTER(ctypes.c_void_p))[0])
            groups = self._groups_at(self._token_information(token, _TOKEN_GROUPS))
            privileges = self._privileges_at(self._token_information(token, _TOKEN_PRIVILEGES))
            elevation = ctypes.cast(
                self._token_information(token, _TOKEN_ELEVATION), ctypes.POINTER(wintypes.DWORD)
            )[0]
            elevation_type = ctypes.cast(
                self._token_information(token, _TOKEN_ELEVATION_TYPE), ctypes.POINTER(wintypes.DWORD)
            )[0]
            label = self._token_information(token, _TOKEN_INTEGRITY_LEVEL)
            integrity_sid = self._sid_at(ctypes.cast(label, ctypes.POINTER(ctypes.c_void_p))[0])
            if not integrity_sid.startswith("S-1-16-"):
                raise WindowsSecurityError("the token's integrity label is not a mandatory label SID.")
            dacl_info = self._token_information(token, _TOKEN_DEFAULT_DACL)
            dacl_pointer = ctypes.cast(dacl_info, ctypes.POINTER(ctypes.c_void_p))[0]
            if not dacl_pointer:
                raise WindowsSecurityError("the token has no default DACL.")
            acl_size = ctypes.c_uint16.from_address(dacl_pointer + 2).value
            default_dacl = ctypes.string_at(dacl_pointer, acl_size)
        finally:
            self._kernel32.CloseHandle(token)
        return TokenFacts(
            user_sid=user_sid,
            groups=groups,
            privileges=privileges,
            elevated=bool(elevation),
            elevation_type=int(elevation_type),
            integrity_rid=int(integrity_sid.rsplit("-", 1)[1]),
            default_dacl=default_dacl,
        )

    def program_data_directory(self) -> str:
        _require_windows()
        return self._known_folder(_FOLDERID_PROGRAM_DATA)

    def read_file(self, path: str, limit: int) -> tuple[ObjectFacts, bytes] | None:
        _require_windows()
        handle = self._open(path, _GENERIC_READ, _FILE_SHARE_READ)
        if handle is None:
            return None
        try:
            facts = self._facts_from_handle(handle)
            if facts.is_directory:
                return facts, b""
            buffer = ctypes.create_string_buffer(limit + 1)
            read = wintypes.DWORD()
            if not self._kernel32.ReadFile(handle, buffer, limit + 1, ctypes.byref(read), None):
                raise _fail("ReadFile")
            return facts, buffer.raw[:read.value]
        finally:
            self._kernel32.CloseHandle(handle)

    def object_facts(self, path: str) -> ObjectFacts | None:
        _require_windows()
        handle = self._open(
            path, _READ_CONTROL | _FILE_READ_ATTRIBUTES,
            _FILE_SHARE_READ | _FILE_SHARE_WRITE | _FILE_SHARE_DELETE,
        )
        if handle is None:
            return None
        try:
            return self._facts_from_handle(handle)
        finally:
            self._kernel32.CloseHandle(handle)

    def list_directory(self, path: str) -> tuple[DirectoryEntry, ...]:
        _require_windows()
        with os.scandir(path) as entries:
            return tuple(
                DirectoryEntry(entry.name, entry.is_dir(follow_symlinks=False)) for entry in entries
            )

    def principal(self, sid: str) -> PrincipalFacts:
        _require_windows()
        sid_buffer = ctypes.create_string_buffer(sid_to_bytes(sid))
        name = ctypes.create_unicode_buffer(256)
        domain = ctypes.create_unicode_buffer(256)
        name_size, domain_size = wintypes.DWORD(256), wintypes.DWORD(256)
        use = ctypes.c_int()
        if not self._advapi32.LookupAccountSidW(
            None, sid_buffer, name, ctypes.byref(name_size), domain, ctypes.byref(domain_size),
            ctypes.byref(use),
        ):
            raise _fail("LookupAccountSidW")
        computer = ctypes.create_unicode_buffer(256)
        computer_size = wintypes.DWORD(256)
        if not self._kernel32.GetComputerNameW(computer, ctypes.byref(computer_size)):
            raise _fail("GetComputerNameW")
        manager = ctypes.c_void_p()
        if not self._authz.AuthzInitializeResourceManager(
            _AUTHZ_RM_FLAG_NO_AUDIT, None, None, None, None, ctypes.byref(manager)
        ):
            raise _fail("AuthzInitializeResourceManager")
        try:
            context = ctypes.c_void_p()
            if not self._authz.AuthzInitializeContextFromSid(
                _AUTHZ_COMPUTE_PRIVILEGES, sid_buffer, manager, None, _LUID(0, 0), None,
                ctypes.byref(context),
            ):
                raise _fail("AuthzInitializeContextFromSid")
            try:
                groups = self._groups_at(self._context_information(context, _AUTHZ_CONTEXT_INFO_GROUPS))
                privileges = self._privileges_at(
                    self._context_information(context, _AUTHZ_CONTEXT_INFO_PRIVILEGES)
                )
            finally:
                self._authz.AuthzFreeContext(context)
        finally:
            self._authz.AuthzFreeResourceManager(manager)
        return PrincipalFacts(
            sid=sid,
            account_name=f"{domain.value}\\{name.value}",
            sid_type=int(use.value),
            is_local_account=domain.value.casefold() == computer.value.casefold(),
            groups=groups,
            privileges=privileges,
        )

    def _context_information(self, context: ctypes.c_void_p, cls: int) -> ctypes.Array:
        needed = wintypes.DWORD()
        self._authz.AuthzGetInformationFromContext(context, cls, 0, ctypes.byref(needed), None)
        if not needed.value:
            raise _fail(f"AuthzGetInformationFromContext({cls})")
        buffer = ctypes.create_string_buffer(needed.value)
        if not self._authz.AuthzGetInformationFromContext(
            context, cls, needed.value, ctypes.byref(needed), buffer
        ):
            raise _fail(f"AuthzGetInformationFromContext({cls})")
        return buffer

    def session(self) -> SessionFacts:
        _require_windows()
        station = self._user32.GetProcessWindowStation()
        desktop = self._user32.GetThreadDesktop(self._kernel32.GetCurrentThreadId())
        if not station or not desktop:
            raise _fail("GetProcessWindowStation/GetThreadDesktop")
        flags = _USEROBJECTFLAGS()
        needed = wintypes.DWORD()
        if not self._user32.GetUserObjectInformationW(
            station, _UOI_FLAGS, ctypes.byref(flags), ctypes.sizeof(flags), ctypes.byref(needed)
        ):
            raise _fail("GetUserObjectInformationW(UOI_FLAGS)")
        return SessionFacts(
            window_station=self._object_name(station),
            window_station_visible=bool(flags.dwFlags & _WSF_VISIBLE),
            window_station_sid=self._object_sid(station),
            desktop=self._object_name(desktop),
            desktop_sid=self._object_sid(desktop),
        )

    def _object_name(self, handle: int) -> str:
        buffer = ctypes.create_unicode_buffer(512)
        needed = wintypes.DWORD()
        if not self._user32.GetUserObjectInformationW(
            handle, _UOI_NAME, buffer, ctypes.sizeof(buffer), ctypes.byref(needed)
        ):
            raise _fail("GetUserObjectInformationW(UOI_NAME)")
        return buffer.value

    def _object_sid(self, handle: int) -> str | None:
        buffer = ctypes.create_string_buffer(256)
        needed = wintypes.DWORD()
        if not self._user32.GetUserObjectInformationW(
            handle, _UOI_USER_SID, buffer, ctypes.sizeof(buffer), ctypes.byref(needed)
        ):
            raise _fail("GetUserObjectInformationW(UOI_USER_SID)")
        if needed.value == 0:
            return None
        return self._sid_at(ctypes.addressof(buffer))

    def process(self) -> ProcessFacts:
        _require_windows()
        token = self._open_token(_TOKEN_QUERY | _READ_CONTROL)
        try:
            token_descriptor = self._descriptor(token, _SE_KERNEL_OBJECT, "GetSecurityInfo(token)")
        finally:
            self._kernel32.CloseHandle(token)
        return ProcessFacts(
            process_descriptor=self._descriptor(
                self._kernel32.GetCurrentProcess(), _SE_KERNEL_OBJECT, "GetSecurityInfo(process)"
            ),
            thread_descriptor=self._descriptor(
                self._kernel32.GetCurrentThread(), _SE_KERNEL_OBJECT, "GetSecurityInfo(thread)"
            ),
            token_descriptor=token_descriptor,
        )

    def code_load(self) -> CodeLoadFacts:
        _require_windows()
        import ai_dev_orchestrator

        token = self._open_token(_TOKEN_QUERY)
        try:
            buffer = ctypes.create_unicode_buffer(32_768)
            size = wintypes.DWORD(len(buffer))
            if not self._userenv.GetUserProfileDirectoryW(token, buffer, ctypes.byref(size)):
                raise _fail("GetUserProfileDirectoryW")
            profile = buffer.value
        finally:
            self._kernel32.CloseHandle(token)
        return CodeLoadFacts(
            executables=(sys.executable, getattr(sys, "_base_executable", sys.executable)),
            prefixes=(sys.prefix, sys.exec_prefix, sys.base_prefix, sys.base_exec_prefix),
            import_paths=tuple(sys.path),
            search_paths=tuple(os.environ.get("PATH", "").split(";")),
            working_directory=os.getcwd(),
            package_directory=os.path.dirname(os.path.abspath(ai_dev_orchestrator.__file__)),
            profile_directories=(
                profile,
                os.environ.get("TEMP", ""),
                os.environ.get("TMP", ""),
                self._known_folder(_FOLDERID_ROAMING_APP_DATA),
                self._known_folder(_FOLDERID_LOCAL_APP_DATA),
            ),
            isolated_interpreter=bool(
                sys.flags.ignore_environment
                and sys.flags.no_user_site
                and getattr(sys.flags, "safe_path", False)
            ),
        )

    def independent_rights(self, descriptor: bytes, principal: Principal, kind: ObjectKind) -> int | None:
        _require_windows()
        parsed = parse_security_descriptor(descriptor)
        extra = {
            ace.sid for ace in parsed.dacl
            if is_logon_sid(ace.sid) and ace.sid != principal.excluded_logon_sid
        }
        groups = sorted((principal.allow_sids | extra) - {principal.sid})
        sid_buffers = [ctypes.create_string_buffer(sid_to_bytes(s)) for s in groups]
        user = ctypes.create_string_buffer(sid_to_bytes(principal.sid))
        sd = ctypes.create_string_buffer(descriptor, len(descriptor))
        manager = ctypes.c_void_p()
        if not self._authz.AuthzInitializeResourceManager(
            _AUTHZ_RM_FLAG_NO_AUDIT, None, None, None, None, ctypes.byref(manager)
        ):
            raise _fail("AuthzInitializeResourceManager")
        contexts: list[ctypes.c_void_p] = []
        try:
            base = ctypes.c_void_p()
            if not self._authz.AuthzInitializeContextFromSid(
                _AUTHZ_SKIP_TOKEN_GROUPS, user, manager, None, _LUID(0, 0), None, ctypes.byref(base)
            ):
                raise _fail("AuthzInitializeContextFromSid")
            contexts.append(base)
            context = base
            if groups:
                entries = (_SID_AND_ATTRIBUTES * len(groups))(
                    *[_SID_AND_ATTRIBUTES(ctypes.cast(b, ctypes.c_void_p), _SE_GROUP_ENABLED_MANDATORY)
                      for b in sid_buffers]
                )
                extended = ctypes.c_void_p()
                if not self._authz.AuthzAddSidsToContext(
                    base, entries, len(groups), None, 0, ctypes.byref(extended)
                ):
                    raise _fail("AuthzAddSidsToContext")
                contexts.append(extended)
                context = extended
            request = _AUTHZ_ACCESS_REQUEST(_MAXIMUM_ALLOWED, None, None, 0, None)
            granted, error = wintypes.DWORD(), wintypes.DWORD()
            reply = _AUTHZ_ACCESS_REPLY(1, ctypes.pointer(granted), None, ctypes.pointer(error))
            if not self._authz.AuthzAccessCheck(
                0, context, ctypes.byref(request), None, sd, None, 0, ctypes.byref(reply), None
            ):
                raise _fail("AuthzAccessCheck")
            return int(granted.value)
        finally:
            for context in reversed(contexts):
                self._authz.AuthzFreeContext(context)
            self._authz.AuthzFreeResourceManager(manager)
