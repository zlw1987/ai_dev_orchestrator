"""Windows-only atomic file replacement and metadata probing (Phase 5F2C).

The Phase 5F2C writer is **explicitly Windows-only**, and this module is why.
Pretending a writer is cross-platform when its metadata and atomicity guarantees
were only ever reasoned about on one platform is a worse outcome than saying
plainly that the other platforms are unsupported.

Two problems are solved here, and nothing else.

**1. Probing the file reliably.** ``os.stat`` on Windows does not always give a
trustworthy hard-link count, and §26.13's open question 11 makes that count
safety-relevant: replacement rebinds *the approved name* to a new file, so if
other hard links exist they keep the old content and the approved path silently
leaves the link set — which is not the in-place mutation a reviewer expects. So
:func:`query_windows_file_info` opens a handle with ``FILE_READ_ATTRIBUTES``
and calls ``GetFileInformationByHandle``, which returns both the attribute mask
and ``nNumberOfLinks`` from the filesystem itself. The handle is opened with
``FILE_FLAG_OPEN_REPARSE_POINT``, so a reparse point is described rather than
followed. **If the information cannot be established, this raises** — Phase
5F2C refuses rather than assuming a link count of one.

**2. Replacing the file without silently transforming its metadata.** A
content-only approved change must not become an uncontrolled ACL or attribute
change. ``os.replace`` is deliberately **not** used: it maps to ``MoveFileEx``
with ``MOVEFILE_REPLACE_EXISTING``, which gives the destination the *new* file's
security descriptor and attributes — so an approved one-line edit could quietly
re-inherit different ACLs from the directory. ``ReplaceFileW`` exists precisely
for this case: it preserves the **replaced** file's attributes, ACLs, and
creation time while swapping in the replacement's contents, atomically from a
reader's point of view.

**``dwReplaceFlags`` is zero** (Phase 5F2C-FU1). The original code passed
``REPLACEFILE_WRITE_THROUGH = 0x1``; Microsoft's ``ReplaceFileW`` documentation
states that flag is **not supported**, so passing it claimed a durability
guarantee the API does not offer. Durability comes from the ``fsync`` performed
on the temp file *before* the replacement, and from nothing else — this module
does not claim ``ReplaceFileW`` provides a supported write-through mode.

``REPLACEFILE_IGNORE_MERGE_ERRORS`` and ``REPLACEFILE_IGNORE_ACL_ERRORS`` are
**not** passed either. Both exist to make the call succeed when the metadata
contract could not be honored, which is the opposite of what this writer wants:
if the contract cannot be met, the failure is the correct outcome.

There is **no backup file and no journal** in this phase — ``lpBackupFileName``
is ``NULL``. The clean Git baseline the writer proves beforehand is the recovery
reference, and a human is the recovery mechanism.

**Cleanup is asymmetric, on purpose** (Phase 5F2C-FU1). Before
``ReplaceFileW`` is invoked, the known temp file is this module's own private
object and deleting it is safe. **Once ``ReplaceFileW`` has been invoked, no
automatic mutation is permitted at all** — a failed replacement may have already
altered filename or replacement state, so the filesystem is indeterminate and
"tidying up" could destroy the only remaining copy of something, or convert a
recoverable state into an unrecoverable one. See
:class:`WindowsReplacementAttemptedError`.

This module opens no network connection, runs no subprocess, reads no
environment variable, calls no model, and touches no path it is not handed.
"""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from dataclasses import dataclass

# -- Win32 constants -----------------------------------------------------------

FILE_READ_ATTRIBUTES = 0x0080
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
FILE_SHARE_DELETE = 0x00000004
OPEN_EXISTING = 3
FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

# The exact value passed as ``dwReplaceFlags``. It is zero, and there is no
# constant here for any flag — see the module docstring. In particular
# ``REPLACEFILE_WRITE_THROUGH`` (0x1) is **not supported** by ``ReplaceFileW``
# per Microsoft's documentation and is deliberately absent, and the two
# "ignore errors" flags are refused because their whole purpose is to succeed
# when the metadata contract could not be honored.
REPLACE_FILE_FLAGS = 0x00000000

# The complete set of file attributes an ordinary source file in a supported
# repository may carry. This is an **allowlist**, not a denylist: a file whose
# mask contains anything else — read-only, hidden, system, reparse, sparse,
# encrypted, compressed, offline, temporary, virtual, recall-on-open, a
# directory, a device — is refused, because preserving semantics this writer has
# not reasoned about is not something it can claim to do.
FILE_ATTRIBUTE_ARCHIVE = 0x00000020
FILE_ATTRIBUTE_NORMAL = 0x00000080
FILE_ATTRIBUTE_NOT_CONTENT_INDEXED = 0x00002000

SUPPORTED_FILE_ATTRIBUTE_MASK = (
    FILE_ATTRIBUTE_ARCHIVE
    | FILE_ATTRIBUTE_NORMAL
    | FILE_ATTRIBUTE_NOT_CONTENT_INDEXED
)

# Named purely so a refusal can say *which* unsupported attribute was present,
# without echoing anything about the file's contents.
_ATTRIBUTE_NAMES: tuple[tuple[int, str], ...] = (
    (0x00000001, "READONLY"),
    (0x00000002, "HIDDEN"),
    (0x00000004, "SYSTEM"),
    (0x00000010, "DIRECTORY"),
    (0x00000040, "DEVICE"),
    (0x00000100, "TEMPORARY"),
    (0x00000200, "SPARSE_FILE"),
    (0x00000400, "REPARSE_POINT"),
    (0x00000800, "COMPRESSED"),
    (0x00001000, "OFFLINE"),
    (0x00004000, "ENCRYPTED"),
    (0x00008000, "INTEGRITY_STREAM"),
    (0x00010000, "VIRTUAL"),
    (0x00020000, "NO_SCRUB_DATA"),
    (0x00040000, "RECALL_ON_OPEN"),
    (0x00080000, "PINNED"),
    (0x00100000, "UNPINNED"),
    (0x00400000, "RECALL_ON_DATA_ACCESS"),
)


class WindowsWriteError(Exception):
    """A Windows file operation could not be performed under this contract.

    Messages name the *category* and, where relevant, the Win32 error number.
    They never echo file contents, and never carry environment or model data.
    """


class WindowsPlatformError(WindowsWriteError):
    """This module was used somewhere that is not Windows."""


class WindowsStagingError(WindowsWriteError):
    """A failure that happened **entirely before** ``ReplaceFileW`` was invoked.

    The destination is untouched, and the known temp file — this module's own
    private object, at a path it chose — has been removed. Callers may safely
    treat this as a pre-write refusal.
    """


class WindowsReplacementAttemptedError(WindowsWriteError):
    """``ReplaceFileW`` was invoked and returned failure (Phase 5F2C-FU1).

    **Nothing was cleaned up, and nothing may be.** A failed replacement can
    leave filename and replacement state partially changed, so the filesystem is
    indeterminate: deleting the temp file might discard the only intact copy of
    the new content, and any rename/restore attempt would be a second mutation
    layered on an unknown state.

    The temp file's *name* is carried on the exception so a human can be told
    where to look. The caller must surface this as the indeterminate outcome —
    never as "nothing changed" — and must not retry, roll back, or run any Git
    mutation.
    """

    def __init__(self, message: str, *, temp_name: str) -> None:
        super().__init__(message)
        self.temp_name = temp_name


class _BY_HANDLE_FILE_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("dwFileAttributes", wintypes.DWORD),
        ("ftCreationTime", wintypes.FILETIME),
        ("ftLastAccessTime", wintypes.FILETIME),
        ("ftLastWriteTime", wintypes.FILETIME),
        ("dwVolumeSerialNumber", wintypes.DWORD),
        ("nFileSizeHigh", wintypes.DWORD),
        ("nFileSizeLow", wintypes.DWORD),
        ("nNumberOfLinks", wintypes.DWORD),
        ("nFileIndexHigh", wintypes.DWORD),
        ("nFileIndexLow", wintypes.DWORD),
    ]


@dataclass(frozen=True)
class WindowsFileInfo:
    """What the filesystem said about one file, at one moment. Data only.

    Carries no file contents. ``file_index`` identifies the underlying file on
    its volume and is recorded so that the pre-write and post-write observations
    can be compared as *observations*, never used as durable authority.
    """

    attributes: int
    link_count: int
    volume_serial_number: int
    file_index: int


def _require_windows() -> None:
    if os.name != "nt":
        raise WindowsPlatformError(
            "platform error: the Phase 5F2C writer is Windows-only and refuses "
            "to operate anywhere else. Nothing was touched."
        )


def _kernel32():
    _require_windows()
    return ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]


def query_windows_file_info(path: str) -> WindowsFileInfo:
    """Return the attribute mask and hard-link count of one existing file.

    The handle is opened with ``FILE_FLAG_OPEN_REPARSE_POINT``, so a reparse
    point at ``path`` is *described* rather than followed — the caller can then
    refuse it, which is what the writer does.

    Raises:
        WindowsPlatformError: not running on Windows.
        WindowsWriteError: the file could not be opened for attribute reading,
            or the information could not be retrieved. **This is the fail-closed
            path for "the link count could not be established."**
    """
    kernel32 = _kernel32()

    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]

    handle = kernel32.CreateFileW(
        path,
        FILE_READ_ATTRIBUTES,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        None,
        OPEN_EXISTING,
        FILE_FLAG_OPEN_REPARSE_POINT,
        None,
    )
    if handle == INVALID_HANDLE_VALUE or handle is None:
        error = ctypes.get_last_error()
        raise WindowsWriteError(
            "metadata error: the write destination could not be opened to read "
            f"its attributes and hard-link count (Win32 error {error}). Phase "
            "5F2C refuses rather than assuming."
        )

    try:
        kernel32.GetFileInformationByHandle.restype = wintypes.BOOL
        kernel32.GetFileInformationByHandle.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(_BY_HANDLE_FILE_INFORMATION),
        ]
        information = _BY_HANDLE_FILE_INFORMATION()
        if not kernel32.GetFileInformationByHandle(handle, ctypes.byref(information)):
            error = ctypes.get_last_error()
            raise WindowsWriteError(
                "metadata error: the write destination's attributes and "
                f"hard-link count could not be established (Win32 error {error}). "
                "Phase 5F2C refuses rather than assuming a link count of one."
            )
        return WindowsFileInfo(
            attributes=int(information.dwFileAttributes),
            link_count=int(information.nNumberOfLinks),
            volume_serial_number=int(information.dwVolumeSerialNumber),
            file_index=(int(information.nFileIndexHigh) << 32)
            | int(information.nFileIndexLow),
        )
    finally:
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle(handle)


def describe_unsupported_attributes(attributes: int) -> list[str]:
    """Name every attribute outside the supported allowlist. Never echoes content."""
    unsupported = attributes & ~SUPPORTED_FILE_ATTRIBUTE_MASK
    if not unsupported:
        return []
    names = [name for bit, name in _ATTRIBUTE_NAMES if unsupported & bit]
    remainder = unsupported & ~sum(
        bit for bit, _ in _ATTRIBUTE_NAMES if unsupported & bit
    )
    if remainder:
        names.append(f"UNKNOWN(0x{remainder:08x})")
    return names


def replace_file_with_bytes(
    *, destination: str, parent_directory: str, data: bytes, temp_name: str
) -> None:
    """Write ``data`` into ``destination`` via a sibling temp file and ``ReplaceFileW``.

    The sequence is exactly:

    1. Create ``parent_directory/temp_name`` **exclusively** — a name collision
       is a failure, never an overwrite.
    2. Write ``data``, flush, and ``fsync`` so the bytes are on the device before
       anything is swapped. **This is where durability comes from**; the
       replacement call is not asked for a write-through mode it does not
       support.
    3. Call ``ReplaceFileW`` with ``dwReplaceFlags == 0`` and no backup file,
       which preserves the destination's attributes, ACLs, and creation time.

    Failure handling is **asymmetric around step 3**, and that asymmetry is the
    point:

    - **Before** the replacement call, the temp file is this module's own
      private object at a path it chose, so removing it is safe. The destination
      is untouched and :class:`WindowsStagingError` is raised.
    - **Once the replacement call has been made**, the filesystem state is
      indeterminate — a failed ``ReplaceFileW`` may have partially changed
      filename or replacement state. **No automatic mutation is permitted**: the
      temp file is *not* deleted, nothing is renamed, nothing is restored,
      nothing is retried. :class:`WindowsReplacementAttemptedError` is raised
      carrying the temp file's name so a human can be told where to look.

    The temp sibling is the single narrowly authorized path outside the approved
    destination itself. **No directory is created**, and no backup or journal
    file is written.
    """
    _require_windows()

    temp_path = os.path.join(parent_directory, temp_name)

    try:
        descriptor = os.open(
            temp_path,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_BINARY | os.O_NOINHERIT,
        )
    except OSError as exc:
        raise WindowsStagingError(
            "staging error: the sibling temp file could not be created "
            "exclusively, so nothing was written."
        ) from exc

    try:
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as exc:
        # Still entirely before the replacement call: safe to clean up.
        _remove_quietly(temp_path)
        raise WindowsStagingError(
            "staging error: the post-image bytes could not be written and "
            "flushed to the sibling temp file, so the destination was not "
            "touched."
        ) from exc

    kernel32 = _kernel32()
    kernel32.ReplaceFileW.restype = wintypes.BOOL
    kernel32.ReplaceFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.c_void_p,
        ctypes.c_void_p,
    ]

    # ---- The point of no return. Nothing below may mutate the filesystem. ----
    succeeded = kernel32.ReplaceFileW(
        destination,
        temp_path,
        None,  # No backup file: this phase ships no backup/journal framework.
        REPLACE_FILE_FLAGS,  # Exactly 0. See the module docstring.
        None,
        None,
    )
    if not succeeded:
        error = ctypes.get_last_error()
        # Deliberately NO cleanup here. See WindowsReplacementAttemptedError:
        # the replacement API has been invoked, so filename state may already
        # have changed and any further mutation could make a recoverable
        # situation unrecoverable.
        raise WindowsReplacementAttemptedError(
            f"replacement error: ReplaceFileW failed (Win32 error {error}). The "
            "destination's final state has NOT been established, and nothing "
            "was cleaned up, renamed, restored, or retried. An operational "
            f"temp file named {temp_name} may remain beside the target.",
            temp_name=temp_name,
        )


def _remove_quietly(path: str) -> None:
    """Delete a temp file this module created, ignoring an already-gone path.

    Only ever called with a path this module built and created itself, and
    **only on a failure path that occurred before ``ReplaceFileW`` was
    invoked**. It never recurses, never touches a directory, and never deletes
    the destination. After a replacement attempt it is not called at all — see
    :class:`WindowsReplacementAttemptedError`.
    """
    try:
        os.unlink(path)
    except OSError:
        # Cleanup is best effort even here: a leftover temp sibling is visible
        # to the caller's Git check, which is what decides the outcome.
        pass
