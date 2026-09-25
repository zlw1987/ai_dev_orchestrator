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

**CFG1-IMPL-FU4 -- Win32 semantics are open; CFG1 issuance provenance is
not.** Every entry point here stays callable, because the offline authority
suite must exercise real pins, real exclusive creates and the real parentage
gate against the real OS. What FU4 closes is the step after that: a caller
could previously assemble genuine pins, genuine children and a genuine
parentage proof from these module-level callables and hand them to
``config_issuance.register_config_issuance``, minting a GENUINE issuance for
caller-selected bytes without ever calling
:func:`~pi_harness_cfg1.cfg1_pi_config.write_cfg1_pi_config`. So every pin,
child and proof now records the :class:`GenerationInterval` that minted it,
an interval can be opened only from the bound generator's own code object,
and :func:`require_production_issuance_provenance` refuses anything else.
Authority minted without an interval is fully functional at the OS level and
worth exactly nothing at the issuance boundary -- which is the point:
provenance is a statement about ORIGIN, never about bytes, names or
identities.

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
import types

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
    # AMEND2 (Y6): the three additions the retained-handle scrub needs. All
    # are documented kernel32 entry points; nothing native, nothing from ntdll.
    _K32.ReOpenFile.restype = _wt.HANDLE
    _K32.ReOpenFile.argtypes = [_wt.HANDLE, _wt.DWORD, _wt.DWORD, _wt.DWORD]
    _K32.FlushFileBuffers.restype = _wt.BOOL
    _K32.FlushFileBuffers.argtypes = [_wt.HANDLE]
    _K32.GetHandleInformation.restype = _wt.BOOL
    _K32.GetHandleInformation.argtypes = [_wt.HANDLE, ctypes.POINTER(_wt.DWORD)]

    GENERIC_READ = 0x80000000
    GENERIC_WRITE = 0x40000000
    DELETE = 0x00010000
    FILE_LIST_DIRECTORY = 0x00000001
    FILE_READ_ATTRIBUTES = 0x00000080
    FILE_SHARE_READ = 0x00000001
    FILE_SHARE_WRITE = 0x00000002
    FILE_SHARE_DELETE = 0x00000004
    HANDLE_FLAG_INHERIT = 0x00000001
    OPEN_EXISTING = 3
    CREATE_NEW = 1
    FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
    FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
    FILE_ATTRIBUTE_DIRECTORY = 0x00000010
    FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
    _INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

    _FileStandardInfo = 1
    _FileDispositionInfo = 4
    _FileEndOfFileInfo = 6
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

    class _FILE_STANDARD_INFO(ctypes.Structure):
        _fields_ = [
            ("AllocationSize", ctypes.c_longlong),
            ("EndOfFile", ctypes.c_longlong),
            ("NumberOfLinks", _wt.DWORD),
            ("DeletePending", ctypes.c_ubyte),
            ("Directory", ctypes.c_ubyte),
        ]

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

#: nonce -> (raw handle, minting generation-interval nonce or ``None``), for
#: pins this module minted and has not yet released. Process-local, in-memory
#: only, never persisted and never an evidence field.
_PINS: dict[str, tuple[int, str | None]] = {}

#: nonce -> (fd, name, minting generation-interval nonce or ``None``), for
#: children this module created exclusively.
_CHILDREN: dict[str, tuple[int, str, str | None]] = {}

#: **AMEND2 (Y6).** nonce -> (raw zero-access HANDLE, kind, the identity proven
#: from handles at acquisition, the minting generation-interval nonce), for the
#: retained exact-object authorities this module minted and has not yet retired.
#: This dict is the ONLY place a retained raw handle exists: it is never a field,
#: attribute, ``repr`` fragment, record field, console line, exception text or
#: return value of any public object (RA-4). Process-local, in-memory only.
_RETAINED: dict[str, tuple[int, str, tuple[int, int], str]] = {}

#: The two -- and only two -- kinds of retained authority (RA-3). There is no
#: third kind and no generic retained-object API.
RETAINED_KIND_CONFIG_MODELS = "config_models"
RETAINED_KIND_EXTENSION_TOKEN = "extension_token"
_RETAINED_KIND_INTERVAL = {
    RETAINED_KIND_CONFIG_MODELS: "config",
    RETAINED_KIND_EXTENSION_TOKEN: "extension",
}

#: nonce -> (config-directory identity, the EXACT child nonces proved, the
#: minting generation-interval nonce or ``None``).
#: Binding the child nonces is what stops a genuine proof from being paired
#: with substituted children at the issuance boundary: the proof answers
#: "these objects are entries of that directory", and it must not be readable
#: as "some objects are".
_PROVEN: dict[str, tuple[tuple[int, int], frozenset[str], str | None]] = {}

#: nonce -> interval KIND, for generation intervals that are currently OPEN.
#:
#: **CFG1-IMPL-FU4.** This is the provenance registry the issuance boundary
#: consults. An entry exists only between :func:`open_generation_interval` and
#: :func:`close_generation_interval`, and the ONLY code that can open one is a
#: bound CFG1 generator's own code object (see
#: :func:`bind_config_generator_authority`). Every pin, child and parentage
#: proof records the interval that minted it -- or ``None`` when none was
#: supplied -- and ``None``-stamped authority is deliberately USELESS at the
#: issuance boundary however genuine its Win32 proofs are.
#:
#: **FU1 AM-10 -- intervals are TYPED.** Exactly two generator code objects are
#: bound: the config generator (kind ``config``) and the L11 extension writer
#: (kind ``extension``). Each issuance registry checks the kind, so a config
#: interval can never produce extension issuance provenance and vice versa.
#: There is no third binding and no generic registry of generators.
_INTERVALS: dict[str, str] = {}

INTERVAL_KIND_CONFIG = "config"
INTERVAL_KIND_EXTENSION = "extension"

#: The one code object permitted to open a production CONFIG generation
#: interval, captured from the CFG1 generator itself at that module's import.
#: ``None`` until then, and never rebindable afterwards.
_GENERATOR_CODE: object | None = None

#: The one code object permitted to open a production EXTENSION generation
#: interval (FU1 AM-10), captured from the CFG1 extension writer at that
#: module's import. ``None`` until then, and never rebindable afterwards.
_EXTENSION_WRITER_CODE: object | None = None

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


class RetainedAuthority(_MintBacked):
    """One private, zero-access, exact-object authority (AMEND2, RA-3).

    Minted only by :func:`retain_child`. The value carries a nonce and nothing
    else: the raw ``HANDLE`` lives in :data:`_RETAINED`, direct construction of
    an unregistered nonce is refused, and the slot cannot be rebound. It is
    handed only to the issuance registry that takes ownership of it (RA-5) and
    is never rendered, serialized or copied into any public object.
    """

    __slots__ = ()
    _registry = _RETAINED
    _unknown_code = "RETAINED_AUTHORITY_NOT_HELD"


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


class GenerationInterval(_MintBacked):
    """One OPEN L9 generation interval -- CFG1-IMPL-FU4's provenance carrier.

    Minted only by :func:`open_generation_interval`, which refuses every
    caller but the bound CFG1 generator's own code object, and retired by
    :func:`close_generation_interval` on L9's own exit path. It is a local of
    that one routine: it is never returned to a caller, never stored on a
    public object, never registered anywhere else, and never rendered.

    **What it is for.** Every Win32 semantic this module establishes is
    reachable by any caller, and that is deliberate -- the offline suite must
    be able to exercise real pins, real exclusive creates and the real
    parentage gate. What a caller must NOT be able to do is turn those genuine
    Win32 facts into a genuine CFG1 config issuance. So authority minted
    without an interval is ``None``-stamped, behaves identically at the OS
    level, and is refused at the issuance boundary by
    :func:`require_production_issuance_provenance`. Provenance here is a
    statement about ORIGIN, never about bytes, names or identities.
    """

    __slots__ = ()
    _registry = _INTERVALS
    _unknown_code = "NOT_AN_OPEN_GENERATION_INTERVAL"


def bind_config_generator_authority() -> None:
    """Bind THE one code object that may open a production interval. Once.

    Called from the CFG1 config generator module's own body, at import, after
    :func:`~pi_harness_cfg1.cfg1_pi_config.write_cfg1_pi_config` is defined.
    It takes no argument and cannot be steered: it derives the code object
    itself, from this package's own generator module, so a caller cannot
    nominate a different one.

    **Why it is one-shot, and why that is not merely hygiene.** A second bind
    is refused outright rather than replacing the first, so a caller who runs
    before the generator module is imported finds nothing to bind (and binds
    nothing), and a caller who runs afterwards finds the genuine code object
    already bound. Rebinding the generator module's ``write_cfg1_pi_config``
    ATTRIBUTE afterwards therefore confers nothing either: what is bound is
    the genuine code object captured at import, not a name looked up later.
    """
    global _GENERATOR_CODE
    if _GENERATOR_CODE is not None:
        raise Cfg1DirectoryAuthorityError("GENERATOR_AUTHORITY_ALREADY_BOUND")
    module = sys.modules.get(f"{__package__}.cfg1_pi_config")
    generator = getattr(module, "write_cfg1_pi_config", None)
    if type(generator) is not types.FunctionType:
        raise Cfg1DirectoryAuthorityError("GENERATOR_AUTHORITY_UNAVAILABLE")
    _GENERATOR_CODE = generator.__code__


def bind_extension_writer_authority() -> None:
    """FU1 AM-10: bind THE one extension-writer code object. Once.

    The exact counterpart of :func:`bind_config_generator_authority`, called
    from the CFG1 extension writer module's own body at import. It takes no
    argument and derives the code object itself, so a caller cannot nominate a
    different one, and a second bind is refused rather than replacing the first.
    """
    global _EXTENSION_WRITER_CODE
    if _EXTENSION_WRITER_CODE is not None:
        raise Cfg1DirectoryAuthorityError("EXTENSION_WRITER_AUTHORITY_ALREADY_BOUND")
    module = sys.modules.get(f"{__package__}.cfg1_extension")
    writer = getattr(module, "write_cfg1_extension", None)
    if type(writer) is not types.FunctionType:
        raise Cfg1DirectoryAuthorityError("EXTENSION_WRITER_AUTHORITY_UNAVAILABLE")
    _EXTENSION_WRITER_CODE = writer.__code__


def open_generation_interval() -> GenerationInterval:
    """Open one production generation interval. ONLY a bound generator may.

    The gate is CODE-OBJECT IDENTITY of the immediate caller's frame, not a
    module name, a function name, a leading underscore, an ``__all__`` entry
    or a docstring. A caller that is not executing a bound generator's own
    code is refused, so there is no supported callable, and no sequence of
    supported calls, that yields one of these.

    The interval's KIND is decided here, by which of the exactly two bound
    code objects is executing -- never by an argument (FU1 AM-10).
    """
    _require_platform()
    caller = sys._getframe(1).f_code
    if _GENERATOR_CODE is not None and caller is _GENERATOR_CODE:
        kind = INTERVAL_KIND_CONFIG
    elif _EXTENSION_WRITER_CODE is not None and caller is _EXTENSION_WRITER_CODE:
        kind = INTERVAL_KIND_EXTENSION
    elif _GENERATOR_CODE is None:
        raise Cfg1DirectoryAuthorityError("GENERATOR_AUTHORITY_UNBOUND")
    else:
        raise Cfg1DirectoryAuthorityError("NOT_THE_CONFIG_GENERATOR")
    nonce = secrets.token_hex(_NONCE_BYTES)
    if nonce in _INTERVALS:  # pragma: no cover - a 128-bit collision
        raise Cfg1DirectoryAuthorityError("GENERATION_INTERVAL_ALREADY_MINTED")
    _INTERVALS[nonce] = kind
    return GenerationInterval(nonce)


def close_generation_interval(interval: object) -> None:
    """Retire one generation interval. Idempotent, no I/O.

    After this, authority minted inside that interval is no longer production
    provenance: an issuance cannot be registered from it, so registration is
    possible only DURING the genuine generation, never afterwards from objects
    a caller kept.
    """
    if type(interval) is GenerationInterval:
        _INTERVALS.pop(interval.nonce, None)


def held_interval_count() -> int:
    """How many generation intervals are still open. A green run leaves zero."""
    return len(_INTERVALS)


def _interval_nonce(interval: object) -> str | None:
    """Resolve a supplied interval to its nonce, or ``None`` when none given.

    An interval that is not an OPEN one is refused rather than downgraded to
    ``None``: silently treating a retired interval as "no interval" would turn
    an authority error into a quietly weaker mint.
    """
    if interval is None:
        return None
    if type(interval) is not GenerationInterval or interval.nonce not in _INTERVALS:
        raise Cfg1DirectoryAuthorityError("NOT_AN_OPEN_GENERATION_INTERVAL")
    return interval.nonce


def _pin_entry(pin: object) -> tuple[int, str | None]:
    if type(pin) is not PinnedDirectory:
        raise Cfg1DirectoryAuthorityError("NOT_A_PINNED_DIRECTORY")
    entry = _PINS.get(pin.nonce)
    if entry is None:
        raise Cfg1DirectoryAuthorityError("PIN_ALREADY_RELEASED")
    return entry


def _pin_handle(pin: object) -> int:
    return _pin_entry(pin)[0]


def _child_entry(child: object) -> tuple[int, str, str | None]:
    if type(child) is not ExclusiveChild:
        raise Cfg1DirectoryAuthorityError("NOT_AN_EXCLUSIVE_CHILD")
    entry = _CHILDREN.get(child.nonce)
    if entry is None:
        raise Cfg1DirectoryAuthorityError("CHILD_ALREADY_CLOSED")
    return entry


def _child_fd(child: object) -> int:
    return _child_entry(child)[0]


def _register_pin(handle: object, *, interval: object = None) -> PinnedDirectory:
    """Register one RAW WIN32 HANDLE. The type gate is not decoration.

    T-124 sweeps every callable in every CFG1 module with a single positional
    argument, and found this one: without the gate it would happily register
    an arbitrary object as though it were a handle, minting a real
    ``PinnedDirectory`` for it. That is a forged pin, and it also leaked a
    registry entry. A handle is an ``int`` here and nothing else.
    """
    if type(handle) is not int:
        raise Cfg1DirectoryAuthorityError("NOT_A_WIN32_HANDLE")
    interval_nonce = _interval_nonce(interval)
    nonce = secrets.token_hex(_NONCE_BYTES)
    if nonce in _PINS:  # pragma: no cover - a 128-bit collision
        raise Cfg1DirectoryAuthorityError("PIN_NONCE_ALREADY_MINTED")
    _PINS[nonce] = (handle, interval_nonce)
    return PinnedDirectory(nonce)


# ---------------------------------------------------------------------------
# Sec. 37.3.1 steps 2 and 4 -- the two pins
# ---------------------------------------------------------------------------


def acquire_root_pin(
    path: str, *, expected_identity: tuple[int, int], interval: object = None
) -> PinnedDirectory:
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
    # Resolved BEFORE the open, so an unusable interval refuses with no handle
    # ever created -- a later refusal would strand a raw handle that was never
    # registered and therefore could never be released.
    _interval_nonce(interval)

    handle = _create_file(
        path,
        FILE_LIST_DIRECTORY | FILE_READ_ATTRIBUTES,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        OPEN_EXISTING,
        FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT,
    )
    if handle is None:
        raise Cfg1DirectoryAuthorityError("WORKSPACE_ROOT_NOT_PINNED")

    pin = _register_pin(handle, interval=interval)
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


def acquire_config_pin(path: str, *, interval: object = None) -> PinnedDirectory:
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
    _interval_nonce(interval)  # see acquire_root_pin: refuse before the open

    handle = _create_file(
        path,
        FILE_LIST_DIRECTORY | FILE_READ_ATTRIBUTES,
        FILE_SHARE_READ,
        OPEN_EXISTING,
        FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT,
    )
    if handle is None:
        raise Cfg1DirectoryAuthorityError("CONFIG_DIR_NOT_PINNED")

    pin = _register_pin(handle, interval=interval)
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
    config_pin: object,
    *,
    children: tuple[ExclusiveChild, ...],
    interval: object = None,
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
    # CFG1-IMPL-FU4: the proof inherits the provenance of what it is about, and
    # inherits it EXACTLY. A pin or a child minted in a different interval --
    # or in none -- cannot be folded into this proof, so neither a
    # cross-generation mix nor a detached object can acquire production
    # provenance by being proved alongside one that has it.
    interval_nonce = _interval_nonce(interval)
    if _pin_entry(config_pin)[1] != interval_nonce:
        raise Cfg1DirectoryAuthorityError("GENERATION_PROVENANCE_MISMATCH")
    config_identity = pin_identity(config_pin)

    expected_names = {".", ".."}
    by_name: dict[str, tuple[int, int]] = {}
    for child in children:
        _descriptor, name, child_interval = _child_entry(child)
        if child_interval != interval_nonce:
            raise Cfg1DirectoryAuthorityError("GENERATION_PROVENANCE_MISMATCH")
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
    _PROVEN[nonce] = (
        config_identity,
        frozenset(child.nonce for child in children),
        interval_nonce,
    )
    return ProvenConfigChildren(nonce)


def _proven_entry(
    proven: object,
) -> tuple[tuple[int, int], frozenset[str], str | None]:
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
    _identity, proved_nonces, _interval = _proven_entry(proven)
    supplied = []
    for child in children:
        if type(child) is not ExclusiveChild:
            raise Cfg1DirectoryAuthorityError("NOT_AN_EXCLUSIVE_CHILD")
        supplied.append(child.nonce)
    if frozenset(supplied) != proved_nonces or len(supplied) != len(proved_nonces):
        raise Cfg1DirectoryAuthorityError("PARENTAGE_CHILD_MISMATCH")


def require_production_issuance_provenance(proven: object, children: tuple) -> None:
    """CFG1-IMPL-FU4's issuance-provenance boundary. ORIGIN, not content.

    Refuse unless ``proven`` and every child in ``children`` were minted inside
    ONE generation interval that is still OPEN. That is the whole correction:

    * a caller may still acquire genuine pins, create genuine exclusive
      children and pass the genuine parentage gate -- every Win32 semantic
      this module establishes stays reachable, which is what keeps the offline
      authority suite honest;
    * but everything it mints that way is ``None``-stamped, and ``None`` is
      not a generation interval, so none of it can become a CFG1 issuance;
    * and because the interval must still be OPEN, even authority genuinely
      minted inside L9 stops being issuance provenance the instant L9's own
      exit path retires the interval.

    This says nothing about bytes. Content that is byte-for-byte identical to
    the legitimate documents confers no provenance, and caller-selected content
    is refused by the same rule and for the same reason: the question asked
    here is where the authority came from, never what is in the files.
    """
    _require_typed_provenance(proven, children, kind=INTERVAL_KIND_CONFIG)


def require_extension_issuance_provenance(proven: object, children: tuple) -> None:
    """FU1 AM-10: the extension issuance boundary's ORIGIN check.

    Identical in shape to :func:`require_production_issuance_provenance`, but
    requires an OPEN interval of kind ``extension`` -- one only the bound L11
    extension writer's own code object can open. A config interval, however
    genuine, is refused here, and an extension interval is refused there.
    """
    _require_typed_provenance(proven, children, kind=INTERVAL_KIND_EXTENSION)


def _require_typed_provenance(proven: object, children: tuple, *, kind: str) -> None:
    _identity, _nonces, interval_nonce = _proven_entry(proven)
    if interval_nonce is None or interval_nonce not in _INTERVALS:
        raise Cfg1DirectoryAuthorityError("NOT_GENERATION_PROVENANCE")
    if _INTERVALS[interval_nonce] != kind:
        raise Cfg1DirectoryAuthorityError("GENERATION_INTERVAL_KIND_MISMATCH")
    for child in children:
        if _child_entry(child)[2] != interval_nonce:
            raise Cfg1DirectoryAuthorityError("GENERATION_PROVENANCE_MISMATCH")


def discard_parentage_proof(proven: object) -> None:
    """Retire one parentage proof. Idempotent, no I/O."""
    if type(proven) is ProvenConfigChildren:
        _PROVEN.pop(proven.nonce, None)


# ---------------------------------------------------------------------------
# Sec. 37.3.1 step 6 -- exclusive child creation
# ---------------------------------------------------------------------------


def create_exclusive_child(
    *, config_dir: str, name: str, interval: object = None
) -> ExclusiveChild:
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
    interval_nonce = _interval_nonce(interval)

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
    _CHILDREN[nonce] = (descriptor, name, interval_nonce)
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
    return _child_entry(child)[1]


def child_interval_nonce(child: object) -> str | None:
    """The generation interval that minted this child (``None`` if none)."""
    return _child_entry(child)[2]


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


def write_child_bytes(child: object, data: bytes) -> None:
    """FU1 (R6 E8): the bytes-mode sibling of :func:`write_child_text`.

    Writes ``data`` VERBATIM through the child's own proven descriptor -- no
    text wrapper, so no newline translation can alter a copied static file.
    Every byte is written (a short write is looped, never truncated); nothing
    is re-opened by pathname.
    """
    _require_platform()
    if type(data) is not bytes:
        raise Cfg1DirectoryAuthorityError("MALFORMED_CHILD_BYTES")
    descriptor = _child_fd(child)
    try:
        view = memoryview(data)
        while view:
            written = os.write(descriptor, view)
            if type(written) is not int or written <= 0:
                raise Cfg1DirectoryAuthorityError("CHILD_BYTES_NOT_WRITTEN")
            view = view[written:]
    except OSError as exc:
        raise Cfg1DirectoryAuthorityError("CHILD_BYTES_NOT_WRITTEN") from exc


def read_regular_file_once(path: str, *, max_bytes: int) -> bytes:
    """FU1 (R6 E-1): ONE no-follow open of one source, at most ``max_bytes + 1``.

    ``FILE_FLAG_OPEN_REPARSE_POINT`` so a symlink or junction is observed as
    itself and refused; shared for READING only, so no writer holds the object
    open for write during the read. A directory, reparse point, device or any
    unreadable object refuses. Returns the bytes read -- at most one byte past
    the bound, so an oversize source is detectable by length without ever
    reading the whole of it. Closes the handle before returning; a close
    failure is counted and refused, never swallowed.
    """
    _require_platform()
    if type(path) is not str or not path:
        raise Cfg1DirectoryAuthorityError("MALFORMED_PATH")
    if type(max_bytes) is not int or max_bytes < 0:
        raise Cfg1DirectoryAuthorityError("MALFORMED_BOUND")
    handle = _create_file(
        path,
        GENERIC_READ | FILE_READ_ATTRIBUTES,
        FILE_SHARE_READ,
        OPEN_EXISTING,
        FILE_FLAG_OPEN_REPARSE_POINT,
    )
    if handle is None:
        raise Cfg1DirectoryAuthorityError("SOURCE_NOT_OPENED")
    try:
        descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY)
    except OSError:
        if not _K32.CloseHandle(handle):
            _CLOSE_FAILURES.append("source")
        raise Cfg1DirectoryAuthorityError("SOURCE_NOT_OPENED") from None
    data = None
    failure = None
    try:
        attributes, reparse_tag = _handle_attributes(msvcrt.get_osfhandle(descriptor))
        if attributes & FILE_ATTRIBUTE_REPARSE_POINT or reparse_tag != 0:
            failure = "SOURCE_REDIRECTED"
        elif attributes & FILE_ATTRIBUTE_DIRECTORY:
            failure = "SOURCE_NOT_A_REGULAR_FILE"
        else:
            chunks: list[bytes] = []
            total = 0
            limit = max_bytes + 1
            while total < limit:
                chunk = os.read(descriptor, min(65536, limit - total))
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
            data = b"".join(chunks)
    except (OSError, Cfg1DirectoryAuthorityError):
        failure = "SOURCE_UNREADABLE"
    finally:
        try:
            os.close(descriptor)
        except OSError:
            _CLOSE_FAILURES.append("source")
            failure = "SOURCE_NOT_CLOSED"
    if failure is not None:
        raise Cfg1DirectoryAuthorityError(failure)
    return data


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
    entry = _PINS.pop(pin.nonce, None)
    if entry is None:
        return
    if not _K32.CloseHandle(entry[0]):
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
# AMEND2 (Y6) -- retained exact-object authority and the handle-bound scrub
#
# Replaces R6 AM-12's link-count / exclusive-interval unlink. The old claim
# depended on "share-0 denies hard-link creation", which is FALSE on the
# supported host (Test Y-6), so nothing here depends on how many names an object
# has, on any name at all, or on excluding alias creation. Every hard link
# names the same file object and therefore the same default data stream, so
# truncating that stream through a handle to the OBJECT makes every name of it
# observe zero bytes.
#
# This is a CONTENT scrub of the exact AIDO-created object. It is not a delete,
# not a secure erase and not a forensic claim: truncation deallocates clusters
# but does not overwrite them. Names are L27's, never L24's.
# ---------------------------------------------------------------------------


def _reopen_file(handle: int, access: int, share: int, flags: int):
    """One ``ReOpenFile`` call, relative to a HELD object. Handle or ``None``.

    Never a pathname and never a file id: the new handle refers to the exact
    object ``handle`` refers to. A seam, so the offline suite can inject a
    refusal at each reopen (RETAIN, and SCRUB-R's H_s) without touching
    ``kernel32``. ``FILE_FLAG_OPEN_REPARSE_POINT`` is passed at every call site.
    """
    reopened = _K32.ReOpenFile(handle, access, share, flags)
    if reopened is None or reopened == _INVALID_HANDLE_VALUE:
        return None
    return reopened


def _handle_inheritable(handle: int) -> object:
    """``True``/``False`` from ``GetHandleInformation``; ``None`` when unreadable."""
    flags = _wt.DWORD(0)
    if not _K32.GetHandleInformation(handle, ctypes.byref(flags)):
        return None
    return bool(flags.value & HANDLE_FLAG_INHERIT)


def _truncate_handle(handle: int) -> bool:
    """``FileEndOfFileInfo`` with ``EndOfFile = 0`` through ``handle``. A seam."""
    end_of_file = ctypes.c_longlong(0)
    return bool(
        _K32.SetFileInformationByHandle(
            handle, _FileEndOfFileInfo, ctypes.byref(end_of_file), 8
        )
    )


def _flush_handle(handle: int) -> bool:
    """``FlushFileBuffers`` through ``handle``. A seam."""
    return bool(_K32.FlushFileBuffers(handle))


def _handle_end_of_file(handle: int) -> object:
    """``FILE_STANDARD_INFO.EndOfFile`` read FROM THE HANDLE; ``None`` if unreadable.

    ``NumberOfLinks``, ``DeletePending`` and ``AllocationSize`` come back in the
    same structure and are **never decision inputs**. A seam, so the suite can
    inject an unreadable, ``None``, ``bool`` or non-zero result.
    """
    info = _FILE_STANDARD_INFO()
    ok = _K32.GetFileInformationByHandleEx(
        handle, _FileStandardInfo, ctypes.byref(info), ctypes.sizeof(info)
    )
    if not ok:
        return None
    return int(info.EndOfFile)


def _close_handle(handle: int, kind: str) -> bool:
    """``CloseHandle``. A seam for close-failure injection; ``True`` iff it closed.

    ``kind`` (``"retained"`` | ``"scrub_handle"``) says which handle this is, so
    a test can fail exactly one of them without touching ``kernel32``.
    """
    return bool(_K32.CloseHandle(handle))


def _close_counted(handle: object, kind: str) -> bool:
    """Close one raw handle exactly once; a failure is COUNTED, never retried."""
    try:
        closed = _close_handle(handle, kind) is True
    except Exception:  # noqa: BLE001 - any close failure is accounted, never swallowed
        closed = False
    if not closed:
        _CLOSE_FAILURES.append(kind)
    return closed


def _end_of_file_is_exactly_zero(handle: int) -> bool:
    """A type-exact ``int`` equal to ``0`` -- a ``bool`` is not ``0``."""
    end_of_file = _handle_end_of_file(handle)
    return type(end_of_file) is int and end_of_file == 0


def _scrub_open_handle(handle: int) -> bool:
    """Truncate -> flush -> ``EndOfFile`` exactly 0, all through ``handle``.

    ``True`` iff all three succeeded. Closes nothing. Shared by SCRUB-C (the
    writer's still-held creating handle) and SCRUB-R (the scrub handle H_s).
    """
    try:
        if _truncate_handle(handle) is not True:
            return False
        if _flush_handle(handle) is not True:
            return False
        return _end_of_file_is_exactly_zero(handle)
    except Exception:  # noqa: BLE001 - any failure inside the scrub is simply False
        return False


def retained_kind_is_valid(kind: object) -> bool:
    return type(kind) is str and kind in _RETAINED_KIND_INTERVAL


def retain_child(child: object, *, kind: str, interval: object) -> RetainedAuthority:
    """RETAIN (RA-1, RA-2): acquire H_r from the creating handle H_c.

    ``ReOpenFile(H_c, 0, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
    FILE_FLAG_OPEN_REPARSE_POINT)`` on the genuine creating handle of the
    sensitive child, **while H_c is still held**. No pathname is reopened and no
    file id is looked up. Then, from handles only:
    ``FILE_ID_INFO(H_r) == FILE_ID_INFO(H_c)`` and ``HANDLE_FLAG_INHERIT`` clear.
    A handle that fails either is **never written through**: it is released
    here and the closed reason code says whether that release itself failed.

    Closed reason codes (the writer maps them to its two local facts):

    * ``RETAINED_NOT_ACQUIRED`` -- ``ReOpenFile`` refused; nothing exists;
    * ``RETAINED_IDENTITY_MISMATCH`` / ``RETAINED_INHERITABLE`` -- acquired,
      not proven, released;
    * ``RETAINED_NOT_RELEASED`` -- acquired, not proven, and its release FAILED
      (counted as ``"retained"``).

    ``kind`` must be one of exactly two, and must agree with the KIND of the
    open generation interval that minted the child (AM-10's typing, extended
    to this one new object).
    """
    _require_platform()
    if not retained_kind_is_valid(kind):
        raise Cfg1DirectoryAuthorityError("MALFORMED_RETAINED_KIND")
    interval_nonce = _interval_nonce(interval)
    if interval_nonce is None:
        raise Cfg1DirectoryAuthorityError("NOT_AN_OPEN_GENERATION_INTERVAL")
    if _INTERVALS[interval_nonce] != _RETAINED_KIND_INTERVAL[kind]:
        raise Cfg1DirectoryAuthorityError("GENERATION_INTERVAL_KIND_MISMATCH")
    descriptor, _name, child_interval = _child_entry(child)
    if child_interval != interval_nonce:
        raise Cfg1DirectoryAuthorityError("GENERATION_PROVENANCE_MISMATCH")
    try:
        creating = msvcrt.get_osfhandle(descriptor)
    except OSError:
        raise Cfg1DirectoryAuthorityError("RETAINED_NOT_ACQUIRED") from None

    retained_handle = _reopen_file(
        creating,
        0,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        FILE_FLAG_OPEN_REPARSE_POINT,
    )
    if retained_handle is None:
        raise Cfg1DirectoryAuthorityError("RETAINED_NOT_ACQUIRED")

    failure = None
    identity = None
    try:
        identity = _handle_identity(creating)
        if _handle_identity(retained_handle) != identity:
            failure = "RETAINED_IDENTITY_MISMATCH"
        elif _handle_inheritable(retained_handle) is not False:
            failure = "RETAINED_INHERITABLE"
    except Exception:  # noqa: BLE001 - an unreadable identity is not a proven one
        failure = "RETAINED_IDENTITY_MISMATCH"
    if failure is not None:
        if not _close_counted(retained_handle, "retained"):
            failure = "RETAINED_NOT_RELEASED"
        raise Cfg1DirectoryAuthorityError(failure)

    nonce = secrets.token_hex(_NONCE_BYTES)
    if nonce in _RETAINED:  # pragma: no cover - a 128-bit collision
        _close_counted(retained_handle, "retained")
        raise Cfg1DirectoryAuthorityError("RETAINED_NONCE_ALREADY_MINTED")
    _RETAINED[nonce] = (retained_handle, kind, identity, interval_nonce)
    return RetainedAuthority(nonce)


def _retained_entry(retained: object) -> tuple[int, str, tuple[int, int], str]:
    if type(retained) is not RetainedAuthority:
        raise Cfg1DirectoryAuthorityError("NOT_A_RETAINED_AUTHORITY")
    entry = _RETAINED.get(retained.nonce)
    if entry is None:
        raise Cfg1DirectoryAuthorityError("RETAINED_AUTHORITY_NOT_HELD")
    return entry


def retained_kind(retained: object) -> str:
    return _retained_entry(retained)[1]


def retained_identity(retained: object) -> tuple[int, int]:
    """The identity proven from handles at acquisition (never a pathname)."""
    return _retained_entry(retained)[2]


def retained_interval_nonce(retained: object) -> str:
    return _retained_entry(retained)[3]


def held_retained_count() -> int:
    """How many retained authorities are still held. A green run leaves zero (RA-9)."""
    return len(_RETAINED)


def scrub_child_through_creating_handle(child: object) -> bool:
    """SCRUB-C: scrub through the writer's still-held creating handle H_c.

    Writer failure paths only. Truncate -> flush -> ``EndOfFile`` type-exact 0,
    on the descriptor's own handle. Returns ``True`` iff all three succeeded and
    closes nothing. Reaches an alias created while H_c was held (Y-6's
    behavior), because an alias is the same object.
    """
    _require_platform()
    try:
        handle = msvcrt.get_osfhandle(_child_fd(child))
    except (OSError, Cfg1DirectoryAuthorityError):
        return False
    return _scrub_open_handle(handle)


def release_retained(retained: object) -> bool:
    """RELEASE-R: close H_r only, writing nothing. Returns the close result.

    Used when RA-2 failed (never written through) and in a writer failure path
    after SCRUB-C already scrubbed the object through H_c. The registry entry is
    removed FIRST (RA-7), so a second call finds nothing, does no I/O and
    returns ``False``. A close failure is counted as ``"retained"`` and is
    never retried through a pathname.
    """
    if type(retained) is not RetainedAuthority:
        return False
    entry = _RETAINED.pop(retained.nonce, None)
    if entry is None:
        return False
    return _close_counted(entry[0], "retained")


def scrub_retire_retained(retained: object) -> bool:
    """SCRUB-R: scrub-retire through the retained handle (L24; writer reclaim).

    ::

        1  remove the private entry FIRST (single-shot, RA-7)        -> else False, no I/O
        2  H_s := ReOpenFile(H_r, GENERIC_WRITE | FILE_READ_ATTRIBUTES, 0,
                             FILE_FLAG_OPEN_REPARSE_POINT)            -> failure: False
        3  FILE_ID_INFO(H_s) == issued identity; H_s not inheritable -> else False, NOTHING written
        4  truncate EOF=0   5  FlushFileBuffers   6  EndOfFile exactly int 0
        7  CloseHandle(H_s)                                          -> else False ("scrub_handle")
        8  CloseHandle(H_r)                                          -> else False ("retained")

    ``True`` only if 2-8 all succeeded. Every handle obtained is closed exactly
    once whatever happened earlier; a failed close is counted, never retried,
    never swallowed. No pathname is named, opened, renamed or deleted, and
    ``NumberOfLinks`` is never read as a decision input.

    ``True`` means exactly: the exact AIDO-issued object's default-stream
    contents were set to ``EndOfFile == 0`` through a handle descended from its
    creating handle, and every handle that had to be released was released. It
    says nothing about names, aliases, copies or forensic recoverability.
    """
    _require_platform()
    if type(retained) is not RetainedAuthority:
        return False
    entry = _RETAINED.pop(retained.nonce, None)
    if entry is None:
        return False
    handle, kind, identity, _interval = entry
    if (
        type(handle) is not int
        or not retained_kind_is_valid(kind)
        or type(identity) is not tuple
        or len(identity) != 2
    ):
        # A malformed entry can only be produced by tampering. Release what
        # exists, and never write through it.
        if type(handle) is int:
            _close_counted(handle, "retained")
        return False

    scrubbed = False
    scrub_handle = None
    try:
        scrub_handle = _reopen_file(
            handle,
            GENERIC_WRITE | FILE_READ_ATTRIBUTES,
            0,
            FILE_FLAG_OPEN_REPARSE_POINT,
        )
        if scrub_handle is not None:
            if (
                _handle_identity(scrub_handle) == identity
                and _handle_inheritable(scrub_handle) is False
            ):
                scrubbed = _scrub_open_handle(scrub_handle)
    except Exception:  # noqa: BLE001 - any failure before the scrub completes is False
        scrubbed = False
    scrub_closed = True
    if scrub_handle is not None:
        scrub_closed = _close_counted(scrub_handle, "scrub_handle")
    retained_closed = _close_counted(handle, "retained")
    return scrubbed and scrub_closed and retained_closed
