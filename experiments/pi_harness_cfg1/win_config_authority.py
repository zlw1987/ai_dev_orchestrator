"""L9's Windows directory-pin authority -- identity, never a pathname.

Design Sec. 37.2/Sec. 37.3 (FU15, frozen by FU15-D1). This module is the
**documented-Win32 layer only**: it acquires the two pins, proves what a
handle actually refers to, creates the two config children exclusively, and
mints the one unforgeable ``ProvenConfigChildren`` object that
:mod:`pi_harness_cfg1.config_issuance` requires before it will register an
issuance. The L9 SEQUENCE itself lives in
:func:`pi_harness_cfg1.cfg1_pi_config.write_cfg1_pi_config`, because Sec.
37.3.2 freezes both pins as locals of that one routine -- never transferable,
never stored on a public object, never returned to a caller.

**What this mechanism proves, and what it does not.** From the first pin
onward, and for the OBJECT rather than the name:

``pin``
    the pinned lexical name cannot be rebound -- rename and delete of the
    pinned directory, and of every ancestor at any depth, are refused
    (W2, W6), and an adversary's write-access open is itself refused so
    ``FSCTL_SET_REPARSE_POINT`` is never reached (W3);
``id``
    the bytes go into the pinned OBJECT -- containment and parentage are
    proven by 128-bit file id against a handle enumeration, with no pathname
    resolved anywhere in the proof (W8, W13).

``R-WINDOW`` (Sec. 37.3.6) is **not closed and is not claimed closed**. No
supported Windows API both creates a directory and returns proof of what it
created (``CreateFileW``/``CreateFile2`` cannot create directories;
``CreateDirectoryW`` returns no handle), so between ``CreateDirectoryW``
returning and the first identity-bearing pin, a same-user concurrent actor may
substitute another ORDINARY directory object at the same child name. FU15-D1
ACCEPTED that residual on explicit terms: whichever object wins, it is proven
-- not assumed -- to be a genuine non-reparse directory, to be contained by
file id inside the identity-proven owned root, and to receive **zero content
bytes** until the parentage gate passes. Nothing here may ever be read as
claiming the pinned object was necessarily created by CFG1, nor that the
generated directory is secure, isolated, tamper-proof or sandboxed: it is
*pinned for a bounded interval*, which is a statement about rename, delete and
reparse conversion and about nothing else.

``NtCreateFile`` is the only mechanism that would close ``R-WINDOW`` and is
explicitly **unauthorized** (Sec. 37.2's rejection table, Sec. 37.3.7's A2).
Do not adopt it here.

**Platform.** Every semantic above is a Win32 semantic, established
empirically on the target platform. There is deliberately **no** portable
fallback: a weaker mechanism under the same function names would reinstate
exactly the window the pins exist to close, and Sec. 37.2 rejects that
reasoning explicitly for ``NtCreateFile``'s own fallback. Off win32 every
entry point here refuses with ``UNSUPPORTED_PLATFORM`` and L9 fails closed.
"""

from __future__ import annotations

import io
import os
import secrets
import sys

from ai_dev_orchestrator.workspace.canonical import _is_symlink_or_reparse_point

#: Whether the frozen Sec. 37.2 mechanism is available at all in this process.
PLATFORM_SUPPORTED = sys.platform == "win32"


class Cfg1DirectoryAuthorityError(Exception):
    """A directory/child authority claim could not be proven.

    Carries a CLOSED reason code and never raw Win32 text, an error number
    rendered into a message, a path, or a handle value (Sec. 21.1's reduction
    rule). The numeric Win32 error is deliberately not retained: it is an
    unbounded diagnostic that must not reach a console or an artifact.
    """

    def __init__(self, reason_code: str) -> None:
        super().__init__(f"cfg1 directory authority refused: {reason_code}")
        self.reason_code = reason_code


# ---------------------------------------------------------------------------
# The documented Win32 surface -- CreateFileW, GetFileInformationByHandleEx,
# SetFileInformationByHandle, CloseHandle. Nothing native, nothing from ntdll.
# ---------------------------------------------------------------------------

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
    _K32.SetFileInformationByHandle.restype = _wt.BOOL
    _K32.SetFileInformationByHandle.argtypes = [
        _wt.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        _wt.DWORD,
    ]

    GENERIC_READ = 0x80000000
    GENERIC_WRITE = 0x40000000
    DELETE = 0x00010000
    FILE_LIST_DIRECTORY = 0x00000001
    FILE_READ_ATTRIBUTES = 0x00000080
    FILE_SHARE_READ = 0x00000001
    FILE_SHARE_WRITE = 0x00000002
    OPEN_EXISTING = 3
    CREATE_NEW = 1
    FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
    FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
    FILE_ATTRIBUTE_DIRECTORY = 0x00000010
    FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
    _INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

    _FileDispositionInfo = 4
    _FileAttributeTagInfo = 9
    _FileIdInfo = 18
    _FileIdExtdDirectoryInfo = 19

    #: ``ERROR_NO_MORE_FILES`` -- W9's per-handle cursor exhaustion.
    _ERROR_NO_MORE_FILES = 18

    class _FILE_ID_128(ctypes.Structure):
        _fields_ = [("Identifier", ctypes.c_ubyte * 16)]

    class _FILE_ID_INFO(ctypes.Structure):
        _fields_ = [
            ("VolumeSerialNumber", ctypes.c_ulonglong),
            ("FileId", _FILE_ID_128),
        ]

    class _FILE_ATTRIBUTE_TAG_INFO(ctypes.Structure):
        _fields_ = [("FileAttributes", _wt.DWORD), ("ReparseTag", _wt.DWORD)]

    class _FILE_ID_EXTD_DIR_INFO(ctypes.Structure):
        """``FILE_ID_EXTD_DIR_INFO``, with ``FileName`` as the trailing array."""

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

    #: Byte offset of the trailing ``FileName`` array, taken from ctypes'
    #: own layout rather than hand-computed, so an alignment assumption can
    #: never silently drift from the real structure.
    _ENTRY_HEADER_BYTES = _FILE_ID_EXTD_DIR_INFO.FileName.offset

    #: One enumeration buffer. Continuation is handled by looping until the
    #: handle's own cursor reports exhaustion, so this size is a batching
    #: choice and never a bound on how many entries are seen.
    _ENUMERATION_BUFFER_BYTES = 64 * 1024


def _require_platform() -> None:
    if not PLATFORM_SUPPORTED:
        raise Cfg1DirectoryAuthorityError("UNSUPPORTED_PLATFORM")


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------


def directory_identity_of_path(path: str) -> tuple[int, int]:
    """``(volume_serial, file_id)`` for an existing path, via ``os.stat``.

    Used at L2 ONLY, to record the owned root's identity at the moment the
    frozen creator returned it (Sec. 37.3.1 step 1). Every later comparison is
    handle-derived; this is the one baseline reading, and it is taken before
    any adversary has been given a name to race against.

    ``os.stat``'s ``st_dev``/``st_ino`` on win32 ARE the volume serial number
    and the 128-bit file id (W13), so this value is directly comparable with
    the ``FILE_ID_INFO`` a handle reports (W8).
    """
    if type(path) is not str or not path:
        raise Cfg1DirectoryAuthorityError("MALFORMED_PATH")
    try:
        lexical = os.lstat(path)
        stat_result = os.stat(path)
    except OSError as exc:
        raise Cfg1DirectoryAuthorityError("ROOT_IDENTITY_UNREADABLE") from exc
    # Refuse to record the identity of something the name only POINTS at: a
    # redirect here would bind the run's whole root authority to the far end
    # of a reference the frozen creator never made.
    if _is_symlink_or_reparse_point(lexical):
        raise Cfg1DirectoryAuthorityError("ROOT_IDENTITY_REDIRECTED")
    return (stat_result.st_dev, stat_result.st_ino)


def _handle_identity(handle: int) -> tuple[int, int]:
    """``(volume_serial, file_id)`` FROM THE HANDLE. No pathname is resolved."""
    info = _FILE_ID_INFO()
    ok = _K32.GetFileInformationByHandleEx(
        handle, _FileIdInfo, ctypes.byref(info), ctypes.sizeof(info)
    )
    if not ok:
        raise Cfg1DirectoryAuthorityError("HANDLE_IDENTITY_UNREADABLE")
    return (
        int(info.VolumeSerialNumber),
        int.from_bytes(bytes(info.FileId.Identifier), "little"),
    )


def _handle_attributes(handle: int) -> tuple[int, int]:
    """``(FileAttributes, ReparseTag)`` from the handle (W1)."""
    info = _FILE_ATTRIBUTE_TAG_INFO()
    ok = _K32.GetFileInformationByHandleEx(
        handle, _FileAttributeTagInfo, ctypes.byref(info), ctypes.sizeof(info)
    )
    if not ok:
        raise Cfg1DirectoryAuthorityError("HANDLE_ATTRIBUTES_UNREADABLE")
    return int(info.FileAttributes), int(info.ReparseTag)


def _create_file(path: str, access: int, share: int, disposition: int, flags: int):
    """One ``CreateFileW`` call. Returns the handle, or ``None`` on refusal."""
    handle = _K32.CreateFileW(path, access, share, None, disposition, flags, None)
    if handle is None or handle == _INVALID_HANDLE_VALUE:
        return None
    return handle


# ---------------------------------------------------------------------------
# PinnedDirectory -- a mint-backed, non-transferable directory pin
# ---------------------------------------------------------------------------

#: nonce -> raw handle, for pins this module minted and has not yet released.
#: Process-local, in-memory only, never persisted and never an evidence field.
_PINS: dict[str, int] = {}

#: nonce -> (fd, name), for children this module created exclusively.
_CHILDREN: dict[str, tuple[int, str]] = {}

#: nonce -> (config-directory identity, the EXACT child nonces proved).
#: Binding the child nonces is what stops a genuine proof from being paired
#: with substituted children at the issuance boundary: the proof answers
#: "these objects are entries of that directory", and it must not be readable
#: as "some objects are".
_PROVEN: dict[str, tuple[tuple[int, int], frozenset[str]]] = {}

#: Handles and descriptors whose CLOSE ITSELF FAILED. They are leaked, and
#: saying so is the point: the registry entry is retired either way (a nonce
#: must not stay usable as authority), so without this counter a failed close
#: would be indistinguishable from a successful one. Never reset except by the
#: offline suite's own hygiene fixture.
_CLOSE_FAILURES: list[str] = []

_NONCE_BYTES = 16


class _MintBacked:
    """A value object whose authority is its registry entry, not its fields.

    Direct construction is refused unless the nonce is already registered, and
    the one slot cannot be rebound afterwards, so neither a forged instance nor
    a post-validation mutation can carry authority. This is the same shape
    :class:`~pi_harness_cfg1.stage_output.CFG1StageOutputAuthority` already
    uses, applied to a handle rather than to a directory path.
    """

    __slots__ = ("nonce",)
    _registry: dict = {}
    _unknown_code = "UNKNOWN_MINT_NONCE"

    def __init__(self, nonce: str) -> None:
        if type(nonce) is not str or nonce not in type(self)._registry:
            raise Cfg1DirectoryAuthorityError(type(self)._unknown_code)
        object.__setattr__(self, "nonce", nonce)

    def __setattr__(self, name: str, value: object) -> None:  # noqa: D105
        raise Cfg1DirectoryAuthorityError("AUTHORITY_IS_IMMUTABLE")

    def __delattr__(self, name: str) -> None:  # noqa: D105
        raise Cfg1DirectoryAuthorityError("AUTHORITY_IS_IMMUTABLE")

    def __repr__(self) -> str:  # noqa: D105 - handles are never rendered
        return f"{type(self).__name__}(<bound>)"


class PinnedDirectory(_MintBacked):
    """One held directory pin. Never transferable, never returned from L9."""

    __slots__ = ()
    _registry = _PINS
    _unknown_code = "PIN_NOT_HELD"


class ExclusiveChild(_MintBacked):
    """One exclusively-created config child, held by descriptor."""

    __slots__ = ()
    _registry = _CHILDREN
    _unknown_code = "CHILD_NOT_HELD"


class ProvenConfigChildren(_MintBacked):
    """Proof that the two children are entries OF the pinned config directory.

    Minted only by :func:`prove_config_parentage`, and only after the exact
    entry-set and file-id comparisons pass. :mod:`config_issuance` requires one
    of these before it will register an issuance, which is what makes "these
    bytes went into the pinned object" a mechanical fact at the issuance
    boundary rather than a caller convention.
    """

    __slots__ = ()
    _registry = _PROVEN
    _unknown_code = "PARENTAGE_NOT_PROVEN"


def _pin_handle(pin: object) -> int:
    if type(pin) is not PinnedDirectory:
        raise Cfg1DirectoryAuthorityError("NOT_A_PINNED_DIRECTORY")
    handle = _PINS.get(pin.nonce)
    if handle is None:
        raise Cfg1DirectoryAuthorityError("PIN_ALREADY_RELEASED")
    return handle


def _child_fd(child: object) -> int:
    if type(child) is not ExclusiveChild:
        raise Cfg1DirectoryAuthorityError("NOT_AN_EXCLUSIVE_CHILD")
    entry = _CHILDREN.get(child.nonce)
    if entry is None:
        raise Cfg1DirectoryAuthorityError("CHILD_ALREADY_CLOSED")
    return entry[0]


def _register_pin(handle: object) -> PinnedDirectory:
    """Register one RAW WIN32 HANDLE. The type gate is not decoration.

    T-124 sweeps every callable in every CFG1 module with a single positional
    argument, and found this one: without the gate it would happily register
    an arbitrary object as though it were a handle, minting a real
    ``PinnedDirectory`` for it. That is a forged pin, and it also leaked a
    registry entry. A handle is an ``int`` here and nothing else.
    """
    if type(handle) is not int:
        raise Cfg1DirectoryAuthorityError("NOT_A_WIN32_HANDLE")
    nonce = secrets.token_hex(_NONCE_BYTES)
    if nonce in _PINS:  # pragma: no cover - a 128-bit collision
        raise Cfg1DirectoryAuthorityError("PIN_NONCE_ALREADY_MINTED")
    _PINS[nonce] = handle
    return PinnedDirectory(nonce)


# ---------------------------------------------------------------------------
# Sec. 37.3.1 steps 2 and 4 -- the two pins
# ---------------------------------------------------------------------------


def acquire_root_pin(path: str, *, expected_identity: tuple[int, int]) -> PinnedDirectory:
    """Step 2. Pin the owned root and prove its IDENTITY from the handle.

    Share mode is ``FILE_SHARE_READ | FILE_SHARE_WRITE`` -- omitting **only**
    ``FILE_SHARE_DELETE``, which is what blocks rename and delete (W2, W6)
    while leaving the root openable for write by the fixture, Git and the
    verification child. Being non-empty it cannot be converted in place anyway
    (W5).

    A refusal here happens **before** ``CreateDirectoryW`` is ever called, so a
    root that is no longer the object L2 recorded produces zero directory
    creations, zero child creations and zero bytes anywhere.
    """
    _require_platform()
    if type(path) is not str or not path:
        raise Cfg1DirectoryAuthorityError("MALFORMED_PATH")
    if (
        type(expected_identity) is not tuple
        or len(expected_identity) != 2
        or type(expected_identity[0]) is not int
        or type(expected_identity[1]) is not int
    ):
        raise Cfg1DirectoryAuthorityError("MALFORMED_ROOT_IDENTITY")

    handle = _create_file(
        path,
        FILE_LIST_DIRECTORY | FILE_READ_ATTRIBUTES,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        OPEN_EXISTING,
        FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT,
    )
    if handle is None:
        raise Cfg1DirectoryAuthorityError("WORKSPACE_ROOT_NOT_PINNED")

    pin = _register_pin(handle)
    try:
        attributes, reparse_tag = _handle_attributes(handle)
        if not attributes & FILE_ATTRIBUTE_DIRECTORY:
            raise Cfg1DirectoryAuthorityError("WORKSPACE_ROOT_NOT_PINNED")
        if attributes & FILE_ATTRIBUTE_REPARSE_POINT or reparse_tag != 0:
            raise Cfg1DirectoryAuthorityError("WORKSPACE_ROOT_IDENTITY_MISMATCH")
        if _handle_identity(handle) != expected_identity:
            raise Cfg1DirectoryAuthorityError("WORKSPACE_ROOT_IDENTITY_MISMATCH")
    except Cfg1DirectoryAuthorityError:
        # A pin that never became authoritative is released here rather than
        # leaked to the caller's ``finally``: the caller never received it.
        release_pin_quietly(pin)
        raise
    return pin


def acquire_config_pin(path: str) -> PinnedDirectory:
    """Step 4. Pin the config directory and prove it is a plain directory.

    Share mode is ``FILE_SHARE_READ`` only: while this is held, an adversary's
    write-access open of the same object is itself refused, so
    ``FSCTL_SET_REPARSE_POINT`` is never reached (W3) and in-place junction
    conversion is impossible. W4 proves that conversion IS otherwise permitted
    against an unpinned EMPTY directory with no delete and no rename at all --
    which is why the reparse check below is a handle-derived attribute test and
    not a lexical name check.
    """
    _require_platform()
    if type(path) is not str or not path:
        raise Cfg1DirectoryAuthorityError("MALFORMED_PATH")

    handle = _create_file(
        path,
        FILE_LIST_DIRECTORY | FILE_READ_ATTRIBUTES,
        FILE_SHARE_READ,
        OPEN_EXISTING,
        FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT,
    )
    if handle is None:
        raise Cfg1DirectoryAuthorityError("CONFIG_DIR_NOT_PINNED")

    pin = _register_pin(handle)
    try:
        attributes, reparse_tag = _handle_attributes(handle)
        if attributes & FILE_ATTRIBUTE_REPARSE_POINT or reparse_tag != 0:
            raise Cfg1DirectoryAuthorityError("CONFIG_DIR_REDIRECTED")
        if not attributes & FILE_ATTRIBUTE_DIRECTORY:
            raise Cfg1DirectoryAuthorityError("CONFIG_DIR_NOT_PINNED")
    except Cfg1DirectoryAuthorityError:
        release_pin_quietly(pin)
        raise
    return pin


def pin_identity(pin: object) -> tuple[int, int]:
    """The pinned object's ``(volume_serial, file_id)``, read from the handle."""
    _require_platform()
    return _handle_identity(_pin_handle(pin))


def pin_attributes(pin: object) -> tuple[int, int]:
    """``(FileAttributes, ReparseTag)`` from the handle -- W1's own evidence.

    Exposed so a regression can assert the POSITIVE control FU15-D1 requires:
    against a genuine, non-redirected directory the same handle-based check
    must report the reparse attribute absent and the tag ``0``, which is what
    makes a junction refusal attributable to the reparse evidence rather than
    to a version of L9 that refused every directory.
    """
    _require_platform()
    return _handle_attributes(_pin_handle(pin))


# ---------------------------------------------------------------------------
# Sec. 37.3.1 steps 5 and 7 -- handle enumeration and the parentage gate
# ---------------------------------------------------------------------------


def enumerate_pin_once(pin: object) -> tuple[tuple[str, int], ...]:
    """Every ``(name, file_id)`` under the pin, read FROM THE HANDLE.

    No pathname is resolved: this is ``GetFileInformationByHandleEx`` with
    ``FileIdExtdDirectoryInfo`` (W8). The cursor is per-handle and does not
    restart (W9), so this drains it in ONE pass and a second call on the same
    pin legitimately yields nothing -- callers must therefore enumerate once
    and keep the result, never re-enumerate to re-check.
    """
    _require_platform()
    handle = _pin_handle(pin)
    buffer = ctypes.create_string_buffer(_ENUMERATION_BUFFER_BYTES)
    entries: list[tuple[str, int]] = []
    base_address = ctypes.addressof(buffer)
    while True:
        ok = _K32.GetFileInformationByHandleEx(
            handle, _FileIdExtdDirectoryInfo, buffer, ctypes.sizeof(buffer)
        )
        if not ok:
            if ctypes.get_last_error() == _ERROR_NO_MORE_FILES:
                return tuple(entries)
            raise Cfg1DirectoryAuthorityError("PIN_ENUMERATION_FAILED")
        offset = 0
        while True:
            entry = _FILE_ID_EXTD_DIR_INFO.from_buffer(buffer, offset)
            name = ctypes.wstring_at(
                base_address + offset + _ENTRY_HEADER_BYTES, entry.FileNameLength // 2
            )
            entries.append(
                (name, int.from_bytes(bytes(entry.FileId.Identifier), "little"))
            )
            if entry.NextEntryOffset == 0:
                break
            offset += entry.NextEntryOffset


def prove_child_directory_entry(
    root_pin: object, *, name: str, identity: tuple[int, int]
) -> None:
    """Step 5. Prove the pinned config object is a child ENTRY of the root.

    Entirely by file id -- no pathname is compared, so the "rename the parent
    aside and recreate it" counterexample that defeats every name-based
    re-proof (Sec. 37.2's rejection table) cannot produce agreement here. The
    volume serial is proven equal to the root's own, which is what rules out an
    entry that is really a mount point onto another volume.
    """
    _require_platform()
    root_identity = pin_identity(root_pin)
    if root_identity[0] != identity[0]:
        raise Cfg1DirectoryAuthorityError("CONFIG_DIR_NOT_IN_OWNED_ROOT")
    for entry_name, entry_file_id in enumerate_pin_once(root_pin):
        if entry_name == name and entry_file_id == identity[1]:
            return
    raise Cfg1DirectoryAuthorityError("CONFIG_DIR_NOT_IN_OWNED_ROOT")


def prove_config_parentage(
    config_pin: object, *, children: tuple[ExclusiveChild, ...]
) -> ProvenConfigChildren:
    """Step 7 -- THE GATE. Runs strictly before the first content byte.

    Requires the pinned directory's entry set to be **exactly**
    ``{".", "..", <each child's name>}`` and each child's own descriptor
    identity to equal the enumerated entry's file id. The exact-set
    requirement is what catches a foreign file planted into CFG1's own
    directory, which W11 proves remains possible even while the directory is
    pinned (a directory pin does not protect its children).

    A failure raises, and the caller's disposition removes the zero-byte
    children by handle. No content byte has been written at this point, so the
    only thing that can ever have existed at an unproven location is a
    content-free file -- never a byte of the base URL, the model id or the
    provider id.
    """
    _require_platform()
    if type(children) is not tuple or not children:
        raise Cfg1DirectoryAuthorityError("MALFORMED_CHILD_SET")
    config_identity = pin_identity(config_pin)

    expected_names = {".", ".."}
    by_name: dict[str, tuple[int, int]] = {}
    for child in children:
        if type(child) is not ExclusiveChild:
            raise Cfg1DirectoryAuthorityError("NOT_AN_EXCLUSIVE_CHILD")
        name = _CHILDREN[child.nonce][1] if child.nonce in _CHILDREN else None
        if name is None:
            raise Cfg1DirectoryAuthorityError("CHILD_ALREADY_CLOSED")
        if name in by_name:
            raise Cfg1DirectoryAuthorityError("MALFORMED_CHILD_SET")
        by_name[name] = child_identity(child)
        expected_names.add(name)

    observed = enumerate_pin_once(config_pin)
    if {entry_name for entry_name, _ in observed} != expected_names:
        raise Cfg1DirectoryAuthorityError("CONFIG_FILES_NOT_IN_PINNED_DIRECTORY")
    for entry_name, entry_file_id in observed:
        if entry_name in (".", ".."):
            continue
        expected = by_name[entry_name]
        if expected[0] != config_identity[0] or expected[1] != entry_file_id:
            raise Cfg1DirectoryAuthorityError("CONFIG_FILES_NOT_IN_PINNED_DIRECTORY")

    nonce = secrets.token_hex(_NONCE_BYTES)
    if nonce in _PROVEN:  # pragma: no cover - a 128-bit collision
        raise Cfg1DirectoryAuthorityError("PARENTAGE_NONCE_ALREADY_MINTED")
    _PROVEN[nonce] = (config_identity, frozenset(child.nonce for child in children))
    return ProvenConfigChildren(nonce)


def _proven_entry(proven: object) -> tuple[tuple[int, int], frozenset[str]]:
    if type(proven) is not ProvenConfigChildren:
        raise Cfg1DirectoryAuthorityError("PARENTAGE_NOT_PROVEN")
    entry = _PROVEN.get(proven.nonce)
    if entry is None:
        raise Cfg1DirectoryAuthorityError("PARENTAGE_NOT_PROVEN")
    return entry


def proven_config_identity(proven: object) -> tuple[int, int]:
    """The config-directory identity a parentage proof was minted against."""
    return _proven_entry(proven)[0]


def require_proven_children(proven: object, children: tuple) -> None:
    """Refuse unless ``children`` is EXACTLY the set this proof was minted for.

    Without this, a genuine proof object and a genuine-but-different pair of
    ``ExclusiveChild`` handles could be presented together at the issuance
    boundary -- the "copied token plus substituted identities" attack, one
    layer down from the one CFG1-IMPL-FU1 Finding 2 already closed for
    ``GeneratedCfg1Config``. The proof is a statement about SPECIFIC objects,
    so it is checked against those objects and no others.
    """
    _identity, proved_nonces = _proven_entry(proven)
    supplied = []
    for child in children:
        if type(child) is not ExclusiveChild:
            raise Cfg1DirectoryAuthorityError("NOT_AN_EXCLUSIVE_CHILD")
        supplied.append(child.nonce)
    if frozenset(supplied) != proved_nonces or len(supplied) != len(proved_nonces):
        raise Cfg1DirectoryAuthorityError("PARENTAGE_CHILD_MISMATCH")


def discard_parentage_proof(proven: object) -> None:
    """Retire one parentage proof. Idempotent, no I/O."""
    if type(proven) is ProvenConfigChildren:
        _PROVEN.pop(proven.nonce, None)


# ---------------------------------------------------------------------------
# Sec. 37.3.1 step 6 -- exclusive child creation
# ---------------------------------------------------------------------------


def create_exclusive_child(*, config_dir: str, name: str) -> ExclusiveChild:
    """Create one config child exclusively, writing ZERO content bytes.

    ``CREATE_NEW`` refuses an occupied name, ``dwShareMode = 0`` denies another
    actor both delete and write for the descriptor's lifetime, and ``DELETE``
    access is what makes handle-based removal possible at all (W12).

    **``FILE_FLAG_OPEN_REPARSE_POINT`` is load-bearing here and is not
    optional.** Sec. 37.2's W10 attributes "refuses an occupied name, including
    a pre-planted symlink" to ``O_CREAT | O_EXCL``, and that half of W10 is
    **empirically false on win32**: without this flag, name resolution follows
    a planted symlink to its target, and ``CREATE_NEW`` then CREATES THE
    TARGET -- an endpoint-bearing file written outside the owned root. Python's
    own ``open(path, "x")`` has the identical defect, because it is the same
    ``CreateFileW(CREATE_NEW)`` underneath. With the flag, resolution stops at
    the reparse point, which exists, and the call refuses with
    ``ERROR_FILE_EXISTS`` having created nothing. See the FU3 report: the
    frozen INVARIANT (Sec. 37.3.4 row 3, T-147) is satisfied only with it.
    """
    _require_platform()
    if type(config_dir) is not str or not config_dir:
        raise Cfg1DirectoryAuthorityError("MALFORMED_PATH")
    if type(name) is not str or not name:
        raise Cfg1DirectoryAuthorityError("MALFORMED_CHILD_NAME")

    handle = _create_file(
        os.path.join(config_dir, name),
        GENERIC_READ | GENERIC_WRITE | DELETE,
        0,
        CREATE_NEW,
        FILE_FLAG_OPEN_REPARSE_POINT,
    )
    if handle is None:
        # Both "already occupied" and "planted redirect" arrive here, and both
        # mean the same thing to L9: this name was not ours to create.
        raise Cfg1DirectoryAuthorityError("CONFIG_FILE_ALREADY_EXISTS")

    try:
        descriptor = msvcrt.open_osfhandle(handle, os.O_RDWR)
    except OSError:
        _K32.CloseHandle(handle)
        raise Cfg1DirectoryAuthorityError("CONFIG_FILE_NOT_CREATED") from None

    nonce = secrets.token_hex(_NONCE_BYTES)
    if nonce in _CHILDREN:  # pragma: no cover - a 128-bit collision
        os.close(descriptor)
        raise Cfg1DirectoryAuthorityError("CHILD_NONCE_ALREADY_MINTED")
    _CHILDREN[nonce] = (descriptor, name)
    return ExclusiveChild(nonce)


def child_identity(child: object) -> tuple[int, int]:
    """``(volume_serial, file_id)`` from the child's OWN descriptor (W13)."""
    _require_platform()
    try:
        stat_result = os.stat(_child_fd(child))
    except OSError as exc:
        raise Cfg1DirectoryAuthorityError("CHILD_IDENTITY_UNREADABLE") from exc
    return (stat_result.st_dev, stat_result.st_ino)


def child_name(child: object) -> str:
    """The exact leaf name this child was created under."""
    if type(child) is not ExclusiveChild or child.nonce not in _CHILDREN:
        raise Cfg1DirectoryAuthorityError("CHILD_ALREADY_CLOSED")
    return _CHILDREN[child.nonce][1]


# ---------------------------------------------------------------------------
# Sec. 37.3.1 steps 8 and 9 -- content and finalization, through descriptors
# ---------------------------------------------------------------------------


def write_child_text(child: object, text: str) -> None:
    """Step 8. Write one document through the child's OWN proven descriptor.

    The text wrapper's newline translation is the SAME ``io`` translation
    ``Path.write_text(text, encoding="utf-8")`` performs -- ``\\n`` becoming
    ``os.linesep`` -- which is what keeps T-1's byte-for-byte agreement with
    the frozen qualification generator true through this mechanism change
    (T-149). The translation lives in :mod:`io`, not in the C runtime, so
    adopting the handle as a descriptor does not alter it.
    """
    _require_platform()
    if type(text) is not str:
        raise Cfg1DirectoryAuthorityError("MALFORMED_CONFIG_TEXT")
    descriptor = _child_fd(child)
    try:
        stream = io.TextIOWrapper(
            io.FileIO(descriptor, "w", closefd=False), encoding="utf-8"
        )
        stream.write(text)
        stream.flush()
        stream.close()
    except OSError as exc:
        raise Cfg1DirectoryAuthorityError("CONFIG_FILES_NOT_WRITTEN") from exc


def read_child_bytes(child: object) -> bytes:
    """Step 9. Read the finalized bytes back THROUGH THE SAME DESCRIPTOR.

    Seeks to zero and reads; never re-opens by pathname. This is what makes
    the finalization digest a statement about the object the parentage gate
    proved, rather than about whatever a name resolves to a moment later.
    """
    _require_platform()
    descriptor = _child_fd(child)
    try:
        os.lseek(descriptor, 0, os.SEEK_SET)
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 65536)
            if not chunk:
                break
            chunks.append(chunk)
    except OSError as exc:
        raise Cfg1DirectoryAuthorityError("CONFIG_FILES_UNREADABLE") from exc
    return b"".join(chunks)


# ---------------------------------------------------------------------------
# Disposition and release
# ---------------------------------------------------------------------------


def dispose_child_by_handle(child: object) -> bool:
    """Remove one child CFG1 itself created, through its own handle only.

    ``SetFileInformationByHandle`` / ``FileDispositionInfo`` (W12) -- never a
    pathname unlink, so no pathname-resolved victim is reachable and no
    same-name foreign object can be deleted by mistake. A failure leaves the
    zero-byte file untouched and is reported; it is never retried by pathname.
    """
    _require_platform()
    try:
        descriptor = _child_fd(child)
    except Cfg1DirectoryAuthorityError:
        return False
    disposition = ctypes.c_ubyte(1)
    try:
        handle = msvcrt.get_osfhandle(descriptor)
    except OSError:
        return False
    ok = bool(
        _K32.SetFileInformationByHandle(
            handle, _FileDispositionInfo, ctypes.byref(disposition), 1
        )
    )
    return ok


def close_child(child: object) -> None:
    """Close one child descriptor, retiring its registry entry either way."""
    if type(child) is not ExclusiveChild:
        return
    entry = _CHILDREN.pop(child.nonce, None)
    if entry is None:
        return
    try:
        os.close(entry[0])
    except OSError as exc:
        _CLOSE_FAILURES.append("child")
        raise Cfg1DirectoryAuthorityError("CONFIG_FILE_NOT_CLOSED") from exc


def close_child_quietly(child: object) -> bool:
    """Close one child, reporting rather than raising. Used on refusal paths."""
    try:
        close_child(child)
    except Cfg1DirectoryAuthorityError:
        return False
    return True


def release_pin(pin: object) -> None:
    """Step 11. Close one pin, and REPORT a close failure rather than hide it.

    A close failure is lifecycle-significant, not memory hygiene (Sec. 37.3.2
    row 11): a leaked pin makes L27's removal fail by construction (W2, W6), so
    the caller must surface it. There is deliberately no force-close, no retry,
    and no re-derivation of the handle from a name.

    The registry entry is retired regardless, because the nonce must not remain
    usable as authority whatever the close returned -- "Python lost its
    reference" is never what makes a handle closed, and the converse holds too.
    """
    if type(pin) is not PinnedDirectory:
        raise Cfg1DirectoryAuthorityError("NOT_A_PINNED_DIRECTORY")
    handle = _PINS.pop(pin.nonce, None)
    if handle is None:
        return
    if not _K32.CloseHandle(handle):
        _CLOSE_FAILURES.append("pin")
        raise Cfg1DirectoryAuthorityError("PIN_NOT_RELEASED")


def release_pin_quietly(pin: object) -> bool:
    """Release a pin, reporting failure rather than raising."""
    try:
        release_pin(pin)
    except Cfg1DirectoryAuthorityError:
        return False
    return True


def held_pin_count() -> int:
    """How many pins this module is still holding. A green run leaves zero."""
    return len(_PINS)


def close_failure_count() -> int:
    """How many handles/descriptors this module LEAKED to a failed close.

    ``held_pin_count()`` alone would read zero after a failed close, because a
    nonce must stop being usable as authority whatever the close returned. A
    leak must never be invisible, so it is counted separately rather than
    inferred from the registry's emptiness.
    """
    return len(_CLOSE_FAILURES)


def held_child_count() -> int:
    """How many child descriptors this module is still holding."""
    return len(_CHILDREN)


# ---------------------------------------------------------------------------
# Sec. 37.3.2 row 9 -- L24's precise, identity-bound child authority
# ---------------------------------------------------------------------------


def identity_bound_unlink(path: str, *, expected_identity: tuple[int, int]) -> bool:
    """Remove ONE generated file, only if it is still the exact object issued.

    Sec. 37.3.2a's precise child authority: L27's root-namespace teardown may
    truthfully reach a descendant CFG1 did not itself create, but an individual
    sensitive-file operation may not. So this opens the target WITHOUT
    following a redirect, re-proves ``os.stat(fd)`` against the identity the
    issuance record bound, and only then disposes of it **through that same
    handle**. On any mismatch it deletes nothing at all -- no pathname unlink,
    no fallback, no "the name matches so it must be ours".

    Returns ``True`` only when nothing the issuance authorized remains: either
    the object was absent already, or it was identity-matched and disposed of.
    """
    _require_platform()
    if type(path) is not str or not path:
        return False
    if (
        type(expected_identity) is not tuple
        or len(expected_identity) != 2
        or type(expected_identity[0]) is not int
        or type(expected_identity[1]) is not int
    ):
        return False

    handle = _create_file(
        path,
        GENERIC_READ | DELETE,
        0,
        OPEN_EXISTING,
        FILE_FLAG_OPEN_REPARSE_POINT,
    )
    if handle is None:
        # Absent is the correct "nothing the issuance authorized remains"
        # answer; anything else (a redirect, a sharing violation, a denial) is
        # NOT proof of absence and must not be reported as a verified scrub.
        return not os.path.lexists(path)

    try:
        descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY)
    except OSError:
        _K32.CloseHandle(handle)
        return False
    try:
        try:
            stat_result = os.stat(descriptor)
        except OSError:
            return False
        if (stat_result.st_dev, stat_result.st_ino) != expected_identity:
            return False
        disposition = ctypes.c_ubyte(1)
        return bool(
            _K32.SetFileInformationByHandle(
                msvcrt.get_osfhandle(descriptor),
                _FileDispositionInfo,
                ctypes.byref(disposition),
                1,
            )
        )
    finally:
        try:
            os.close(descriptor)
        except OSError:  # pragma: no cover - a close failure on a read handle
            pass
