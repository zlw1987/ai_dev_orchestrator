"""F5A -- Windows filesystem / handle PREMISE probes (Q1-Q6). Verification only.

The F5A R0 design (``docs/PHASE_5F3B_CFG1_F5A_LIVE_LAUNCH_AUTHORITY_AMENDMENT.md``
Sec. 11.2) rests on six Windows facts. This module performs the ATTACKER'S real
operations, directly, against synthetic temporary trees and asserts each fact.
It is a premise test, not an implementation: nothing here is, imports or
changes production code, and **a failing premise is left failing** -- no
workaround is encoded and no design is adjusted to make a row pass.

Discipline (the same one the FU15 regressions follow):

* every refusal attributed to a pin carries a matched RELEASED-pin control that
  runs the identical operation on the identical path and must SUCCEED and change
  state; an operation the host does not support is reported as an explicit
  ``UNSUPPORTED[...]`` skip, never counted as a pass;
* a refusal only counts as evidence when it carries ``ERROR_SHARING_VIOLATION``
  or ``ERROR_ACCESS_DENIED`` AND the object is observably unchanged afterwards;
* a premise violation raises ``PREMISE_FAIL[Qn]``; a malfunctioning probe raises
  ``HARNESS[...]`` so the two are never confused.

Pure Python / ctypes. No Node, no Pi, no npm, no network, no model, no
credential. Every write is under pytest ``tmp_path`` or a freshly minted ``ar2``
disposable root.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import hashlib
import msvcrt
import os
import shutil
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform != "win32",
    reason="every premise here is a Win32 semantic; a skip on the target platform is not a pass",
)

if sys.platform == "win32":
    from ar2.fixtures import remove_disposable_tree
    from pi_harness_cfg1 import pi_fs_leaves as leaves
    from pi_harness_cfg1 import pi_payload, run_workspace
    from pi_harness_cfg1 import win_config_authority as win

    import cfg1_win_probe as probe

    # -- the attacker's own Win32 surface (deliberately NOT production's) -----
    _K = ctypes.WinDLL("kernel32", use_last_error=True)
    _K.CreateFileW.restype = wt.HANDLE
    _K.CreateFileW.argtypes = [
        wt.LPCWSTR, wt.DWORD, wt.DWORD, ctypes.c_void_p, wt.DWORD, wt.DWORD, wt.HANDLE,
    ]
    _K.CloseHandle.restype = wt.BOOL
    _K.CloseHandle.argtypes = [wt.HANDLE]
    _K.DeleteFileW.restype = wt.BOOL
    _K.DeleteFileW.argtypes = [wt.LPCWSTR]
    _K.MoveFileExW.restype = wt.BOOL
    _K.MoveFileExW.argtypes = [wt.LPCWSTR, wt.LPCWSTR, wt.DWORD]
    _K.ReplaceFileW.restype = wt.BOOL
    _K.ReplaceFileW.argtypes = [
        wt.LPCWSTR, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD, ctypes.c_void_p, ctypes.c_void_p,
    ]
    _K.SetFileInformationByHandle.restype = wt.BOOL
    _K.SetFileInformationByHandle.argtypes = [wt.HANDLE, ctypes.c_int, ctypes.c_void_p, wt.DWORD]
    _K.GetFileInformationByHandleEx.restype = wt.BOOL
    _K.GetFileInformationByHandleEx.argtypes = [wt.HANDLE, ctypes.c_int, ctypes.c_void_p, wt.DWORD]
    _K.DeviceIoControl.restype = wt.BOOL
    _K.DeviceIoControl.argtypes = [
        wt.HANDLE, wt.DWORD, ctypes.c_void_p, wt.DWORD, ctypes.c_void_p, wt.DWORD,
        ctypes.POINTER(wt.DWORD), ctypes.c_void_p,
    ]
    _K.ReOpenFile.restype = wt.HANDLE
    _K.ReOpenFile.argtypes = [wt.HANDLE, wt.DWORD, wt.DWORD, wt.DWORD]
    _K.GetFileAttributesW.restype = wt.DWORD
    _K.GetFileAttributesW.argtypes = [wt.LPCWSTR]
    _K.SetFileAttributesW.restype = wt.BOOL
    _K.SetFileAttributesW.argtypes = [wt.LPCWSTR, wt.DWORD]

    _INVALID = ctypes.c_void_p(-1).value

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
DELETE = 0x00010000
WRITE_DAC = 0x00040000
SYNCHRONIZE = 0x00100000
FILE_LIST_DIRECTORY = 0x00000001
FILE_READ_ATTRIBUTES = 0x00000080
FILE_WRITE_ATTRIBUTES = 0x00000100
SHARE_READ, SHARE_WRITE, SHARE_DELETE = 1, 2, 4
SHARE_ALL = SHARE_READ | SHARE_WRITE | SHARE_DELETE
CREATE_NEW, CREATE_ALWAYS, OPEN_EXISTING, TRUNCATE_EXISTING = 1, 2, 3, 5
FLAG_BACKUP = 0x02000000
FLAG_REPARSE = 0x00200000
NO_FOLLOW = FLAG_BACKUP | FLAG_REPARSE
ATTR_READONLY = 0x1
ATTR_DIRECTORY = 0x10
ATTR_NORMAL = 0x80
ATTR_REPARSE = 0x400

ERROR_ACCESS_DENIED = 5
ERROR_SHARING_VIOLATION = 32
ERROR_FILE_EXISTS = 80
BLOCKING_ERRORS = (ERROR_ACCESS_DENIED, ERROR_SHARING_VIOLATION)

FILE_ATTRIBUTE_TAG_INFO = 9
FILE_ID_INFO = 18
FILE_RENAME_INFO = 3
FILE_DISPOSITION_INFO = 4
FILE_DISPOSITION_INFO_EX = 21
FILE_RENAME_INFO_EX = 22
RENAME_REPLACE = 0x1
RENAME_POSIX = 0x2
DISPOSITION_DELETE = 0x1
DISPOSITION_POSIX = 0x2
FSCTL_SET_REPARSE_POINT = 0x000900A4

PAYLOAD = b"F5A-pinned-regular-file-bytes\n"
REPLACEMENT = b"F5A-REPLACEMENT-bytes-that-differ\n"

#: Every observation is echoed (visible with ``-s``) and kept for the summary.
_NOTES: list[str] = []


def _note(question: str, text: str) -> None:
    line = f"[F5A-{question}] {text}"
    _NOTES.append(line)
    print(line)


def _premise_fail(question: str, text: str) -> None:
    raise AssertionError(f"PREMISE_FAIL[{question}]: {text}")


def _harness_fail(text: str) -> None:
    raise AssertionError(f"HARNESS[{text}]")


def _unsupported(question: str, text: str) -> None:
    _note(question, f"UNSUPPORTED: {text}")
    pytest.skip(f"UNSUPPORTED[{question}]: {text}")


# ---------------------------------------------------------------------------
# Low-level Win32 helpers
# ---------------------------------------------------------------------------


def _open(path, access, share, disposition=OPEN_EXISTING, flags=NO_FOLLOW):
    """One ``CreateFileW``. Returns ``(handle_or_None, win32_error)``."""
    handle = _K.CreateFileW(str(path), access, share, None, disposition, flags, None)
    if handle is None or handle == _INVALID:
        return None, ctypes.get_last_error()
    return handle, 0


def _close(handle) -> None:
    if handle is not None:
        _K.CloseHandle(handle)


def _handle_identity(handle) -> tuple[int, int]:
    class _Id128(ctypes.Structure):
        _fields_ = [("Identifier", ctypes.c_ubyte * 16)]

    class _IdInfo(ctypes.Structure):
        _fields_ = [("VolumeSerialNumber", ctypes.c_ulonglong), ("FileId", _Id128)]

    info = _IdInfo()
    if not _K.GetFileInformationByHandleEx(handle, FILE_ID_INFO, ctypes.byref(info), ctypes.sizeof(info)):
        _harness_fail("FileIdInfo unreadable")
    return int(info.VolumeSerialNumber), int.from_bytes(bytes(info.FileId.Identifier), "little")


def _tag_info(handle) -> tuple[int, int]:
    class _TagInfo(ctypes.Structure):
        _fields_ = [("FileAttributes", wt.DWORD), ("ReparseTag", wt.DWORD)]

    info = _TagInfo()
    if not _K.GetFileInformationByHandleEx(handle, FILE_ATTRIBUTE_TAG_INFO, ctypes.byref(info), ctypes.sizeof(info)):
        _harness_fail("FileAttributeTagInfo unreadable")
    return int(info.FileAttributes), int(info.ReparseTag)


def _attributes(path) -> int:
    value = _K.GetFileAttributesW(str(path))
    return value


def _set_attributes(path, value: int) -> None:
    _K.SetFileAttributesW(str(path), value)


def _sha(data: bytes | None) -> str | None:
    return None if data is None else hashlib.sha256(data).hexdigest()


class _FilePin:
    """A regular file created ``CREATE_NEW | OPEN_REPARSE_POINT`` and kept open.

    The creating handle is adopted into a CRT descriptor so the bytes can be
    written and read back THROUGH IT -- a share-0 file cannot be read by any
    other handle, so this is the only honest way to prove it unchanged.
    """

    def __init__(self, path, share: int, access: int = GENERIC_READ | GENERIC_WRITE):
        self.path = str(path)
        self.share = share
        handle, error = _open(self.path, access, share, CREATE_NEW, FLAG_REPARSE)
        if handle is None:
            _harness_fail(f"pin creation failed ({error}) for {self.path}")
        self._fd = msvcrt.open_osfhandle(handle, os.O_RDWR | getattr(os, "O_BINARY", 0))

    @property
    def handle(self):
        return msvcrt.get_osfhandle(self._fd)

    def write(self, data: bytes) -> None:
        os.write(self._fd, data)

    def read(self) -> bytes:
        os.lseek(self._fd, 0, os.SEEK_SET)
        chunks = []
        while True:
            chunk = os.read(self._fd, 65536)
            if not chunk:
                break
            chunks.append(chunk)
        os.lseek(self._fd, 0, os.SEEK_END)
        return b"".join(chunks)

    def identity(self) -> tuple[int, int]:
        return _handle_identity(self.handle)

    def release(self) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None


@pytest.fixture()
def pins():
    held: list[_FilePin] = []
    yield held
    for pin in held:
        pin.release()


def _new_pin(pins, path, share: int, data: bytes | None = PAYLOAD) -> _FilePin:
    pin = _FilePin(path, share)
    pins.append(pin)
    if data:
        pin.write(data)
    return pin


def _snapshot(path, reader) -> tuple:
    """``(classification, identity, bytes)`` of one lexical path, no-follow."""
    observation = leaves.inspect_no_follow(str(path))
    data = None
    if observation.classification == leaves.CLASSIFICATION_REGULAR_FILE:
        data = reader()
    return observation.classification, observation.identity, data


def _read_released(path):
    return lambda: Path(path).read_bytes()


# ---------------------------------------------------------------------------
# The attacker's operation library (Q1 / Q3)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OpResult:
    ok: bool
    error: int


def _replacement(aux: str) -> str:
    path = os.path.join(aux, "replacement.bin")
    if not os.path.exists(path):
        Path(path).write_bytes(REPLACEMENT)
    return path


def _rename_buffer(new_path: str, flags: int):
    name = new_path.encode("utf-16-le")
    buffer = ctypes.create_string_buffer(24 + len(name) + 2)
    struct.pack_into("<I", buffer, 0, flags)
    struct.pack_into("<Q", buffer, 8, 0)
    struct.pack_into("<I", buffer, 16, len(name))
    ctypes.memmove(ctypes.addressof(buffer) + 20, name, len(name))
    return buffer, 24 + len(name) + 2


def _by_handle(path, access, apply) -> OpResult:
    handle, error = _open(path, access, SHARE_ALL)
    if handle is None:
        return OpResult(False, error)
    try:
        ok = apply(handle)
        return OpResult(bool(ok), 0 if ok else ctypes.get_last_error())
    finally:
        _close(handle)


def _op_delete_file(path, aux) -> OpResult:
    ok = _K.DeleteFileW(str(path))
    return OpResult(bool(ok), 0 if ok else ctypes.get_last_error())


def _op_disposition(cls: int, flags_or_bool: int):
    def op(path, aux) -> OpResult:
        if cls == FILE_DISPOSITION_INFO:
            payload = ctypes.c_ubyte(flags_or_bool)
        else:
            payload = wt.DWORD(flags_or_bool)
        return _by_handle(
            path, DELETE,
            lambda h: _K.SetFileInformationByHandle(h, cls, ctypes.byref(payload), ctypes.sizeof(payload)),
        )

    return op


def _op_move(replace: bool, reverse: bool = False):
    def op(path, aux) -> OpResult:
        if reverse:  # the pinned path is the REPLACEMENT TARGET
            ok = _K.MoveFileExW(_replacement(aux), str(path), 1)
        else:
            ok = _K.MoveFileExW(str(path), str(path) + ".renamed", 0)
        return OpResult(bool(ok), 0 if ok else ctypes.get_last_error())

    return op


def _op_rename_info(cls: int, flags: int, target_kind: str):
    """``target_kind``: ``away`` (pinned path is the source), ``over`` (pinned
    path is the replace TARGET of a file source) or ``dir_over`` (of a directory
    source)."""

    def op(path, aux) -> OpResult:
        if target_kind == "away":
            source, destination = str(path), str(path) + ".renamed"
        elif target_kind == "over":
            source, destination = _replacement(aux), str(path)
        else:
            source = os.path.join(aux, "replacement_dir")
            os.makedirs(source, exist_ok=True)
            destination = str(path)
        buffer, size = _rename_buffer(destination, flags)
        return _by_handle(source, DELETE, lambda h: _K.SetFileInformationByHandle(h, cls, buffer, size))

    return op


def _op_replace_file_w(path, aux) -> OpResult:
    ok = _K.ReplaceFileW(str(path), _replacement(aux), None, 0, None, None)
    return OpResult(bool(ok), 0 if ok else ctypes.get_last_error())


def _op_open_for_overwrite(disposition: int):
    def op(path, aux) -> OpResult:
        handle, error = _open(path, GENERIC_WRITE, SHARE_ALL, disposition, FLAG_REPARSE)
        if handle is None:
            return OpResult(False, error)
        _close(handle)
        return OpResult(True, 0)

    return op


OPS = {
    "DeleteFileW": _op_delete_file,
    "FileDispositionInfo": _op_disposition(FILE_DISPOSITION_INFO, 1),
    "FileDispositionInfoEx_delete": _op_disposition(FILE_DISPOSITION_INFO_EX, DISPOSITION_DELETE),
    "FileDispositionInfoEx_posix": _op_disposition(
        FILE_DISPOSITION_INFO_EX, DISPOSITION_DELETE | DISPOSITION_POSIX
    ),
    "MoveFileExW_rename": _op_move(False),
    "FileRenameInfo_rename": _op_rename_info(FILE_RENAME_INFO, 0, "away"),
    "FileRenameInfoEx_posix_rename": _op_rename_info(FILE_RENAME_INFO_EX, RENAME_POSIX, "away"),
    "MoveFileExW_replace_as_target": _op_move(True, reverse=True),
    "FileRenameInfo_replace_as_target": _op_rename_info(FILE_RENAME_INFO, 1, "over"),
    "FileRenameInfoEx_posix_replace_as_target": _op_rename_info(
        FILE_RENAME_INFO_EX, RENAME_REPLACE | RENAME_POSIX, "over"
    ),
    "FileRenameInfoEx_directory_replacing_file": _op_rename_info(
        FILE_RENAME_INFO_EX, RENAME_REPLACE | RENAME_POSIX, "dir_over"
    ),
    "ReplaceFileW_as_replaced": _op_replace_file_w,
    "CreateFileW_CREATE_ALWAYS_recreate": _op_open_for_overwrite(CREATE_ALWAYS),
    "CreateFileW_TRUNCATE_EXISTING_recreate": _op_open_for_overwrite(TRUNCATE_EXISTING),
}


def _attempt_held_then_control(question, op_name, victims, release, control_path, aux):
    """Run ``op`` against every held victim; release; run the SAME op on the
    SAME ``control_path``. Returns ``(held_findings, control_result, control_changed)``.

    ``victims`` is ``[(path, pin)]``. A held finding is a problem description,
    or nothing when the pin held and the object is observably unchanged.
    """
    op = OPS[op_name]
    findings: list[str] = []
    errors: list[int] = []
    for path, pin in victims:
        before = _snapshot(path, pin.read)
        result = op(path, aux)
        after = _snapshot(path, pin.read)
        errors.append(result.error)
        if result.ok:
            findings.append(f"{os.path.basename(path)}: operation SUCCEEDED")
        elif result.error not in BLOCKING_ERRORS:
            findings.append(f"{os.path.basename(path)}: refused with non-blocking error {result.error}")
        if after != before:
            findings.append(f"{os.path.basename(path)}: object changed ({before[0]}->{after[0]})")
        if after[1] != pin.identity() and after[0] == leaves.CLASSIFICATION_REGULAR_FILE:
            findings.append(f"{os.path.basename(path)}: pathname no longer resolves to the pinned identity")
    release()
    control_before = _snapshot(control_path, _read_released(control_path))
    control = op(control_path, aux)
    control_after = _snapshot(control_path, _read_released(control_path))
    return findings, errors, control, control_after != control_before


def _evaluate(question, op_name, findings, errors, control, control_changed):
    if findings and control.ok and control_changed:
        _premise_fail(question, f"{op_name} not blocked by the pin: {findings}")
    if not (control.ok and control_changed):
        _unsupported(
            question,
            f"{op_name} has no working released-handle control on this host "
            f"(ok={control.ok}, error={control.error}, changed={control_changed}); "
            f"pinned refusals {errors} are not counted as evidence",
        )
    if findings:  # pragma: no cover - covered by the first branch
        _premise_fail(question, f"{op_name}: {findings}")
    _note(question, f"PASS {op_name}: held refused with Win32 {sorted(set(errors))}; released control ok")


# ---------------------------------------------------------------------------
# Q1 -- a held regular file (share 0, data access) cannot be rebound
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("op_name", sorted(OPS))
def test_q1_held_share0_file_cannot_be_deleted_renamed_replaced_or_recreated(tmp_path, pins, op_name):
    """The pin is the creating handle: ``GENERIC_READ|GENERIC_WRITE``, share 0,
    ``CREATE_NEW | FILE_FLAG_OPEN_REPARSE_POINT``.

    Matched control: the very same file, the very same operation, after the pin
    is released. ``CREATE_NEW``/``CreateDirectoryW`` at the same name are NOT in
    this matrix: they fail with ``ERROR_FILE_EXISTS``/``ALREADY_EXISTS``
    whether or not anything is held, so they would prove nothing about the pin
    (see ``test_q1_create_new_at_the_same_name_is_not_evidence``).
    """
    aux = tmp_path / "aux"
    aux.mkdir()
    path = tmp_path / "held.bin"
    pin = _new_pin(pins, path, share=0)
    findings, errors, control, changed = _attempt_held_then_control(
        "Q1", op_name, [(str(path), pin)], pin.release, str(path), str(aux)
    )
    _evaluate("Q1", op_name, findings, errors, control, changed)


def test_q1_pathname_resolves_to_the_same_identity_while_held(tmp_path, pins):
    """After every Q1 attack, the name still resolves, no-follow, to the pinned
    object -- read from the genuine attribute-only leaf, compared with the
    identity the creating handle reports -- and its bytes are unchanged."""
    aux = tmp_path / "aux"
    aux.mkdir()
    path = tmp_path / "held.bin"
    pin = _new_pin(pins, path, share=0)
    pinned_identity = pin.identity()
    for op in OPS.values():
        op(str(path), str(aux))
    observation = leaves.inspect_no_follow(str(path))
    assert observation.classification == leaves.CLASSIFICATION_REGULAR_FILE
    if observation.identity != pinned_identity:
        _premise_fail("Q1", "the pathname no longer resolves to the pinned identity")
    assert pin.read() == PAYLOAD
    # The attribute-only open that proved it was ADMITTED on a share-0 file.
    _note("Q1", "attribute-only no-follow open admitted on the share-0 held file; identity equal")


def test_q1_create_new_at_the_same_name_is_not_evidence(tmp_path, pins):
    """Documented NON-EVIDENCE: ``CREATE_NEW`` over an existing name fails the
    same way with or without a pin, so it is excluded from the evidence set."""
    path = tmp_path / "held.bin"
    pin = _new_pin(pins, path, share=0)
    handle, held_error = _open(path, GENERIC_WRITE, SHARE_ALL, CREATE_NEW, FLAG_REPARSE)
    assert handle is None
    pin.release()
    handle, released_error = _open(path, GENERIC_WRITE, SHARE_ALL, CREATE_NEW, FLAG_REPARSE)
    assert handle is None
    assert held_error == released_error == ERROR_FILE_EXISTS
    _note("Q1", "CREATE_NEW at the same name: identical refusal held and released -- excluded, not evidence")


# ---------------------------------------------------------------------------
# Q2 -- reparse conversion of a held file
# ---------------------------------------------------------------------------


def _symlink_reparse_buffer(target: str) -> bytes:
    sub = ("\\??\\" + target).encode("utf-16-le")
    printed = target.encode("utf-16-le")
    data = struct.pack("<HHHHI", 0, len(sub), len(sub), len(printed), 0) + sub + printed
    return (0xA000000C).to_bytes(4, "little") + len(data).to_bytes(2, "little") + b"\0\0" + data


def _generic_reparse_buffer(_target: str) -> bytes:
    body = bytes(range(16)) + b"x"
    return (0x8000FFFF).to_bytes(4, "little") + len(body).to_bytes(2, "little") + b"\0\0" + body


REPARSE_MECHANISMS = {
    "FSCTL_SET_REPARSE_POINT_symlink_tag": _symlink_reparse_buffer,
    "FSCTL_SET_REPARSE_POINT_generic_tag_0x8000FFFF": _generic_reparse_buffer,
}

#: Opens a second actor may request. The first three are the share-check-exempt
#: attribute/metadata accesses (Windows does not apply sharing to them); the
#: last is data access, which the pin's share mode is meant to refuse.
CONVERSION_ACCESSES = {
    "FILE_READ_ATTRIBUTES": FILE_READ_ATTRIBUTES,
    "FILE_WRITE_ATTRIBUTES": FILE_WRITE_ATTRIBUTES,
    "FILE_READ|WRITE_ATTRIBUTES|SYNCHRONIZE": FILE_READ_ATTRIBUTES | FILE_WRITE_ATTRIBUTES | SYNCHRONIZE,
    "WRITE_DAC": WRITE_DAC,
    "GENERIC_WRITE": GENERIC_WRITE,
}


def _attempt_conversion(path, access, buffer: bytes) -> tuple[str, int]:
    handle, error = _open(path, access, SHARE_ALL)
    if handle is None:
        return "open_refused", error
    try:
        returned = wt.DWORD(0)
        ok = _K.DeviceIoControl(
            handle, FSCTL_SET_REPARSE_POINT, buffer, len(buffer), None, 0, ctypes.byref(returned), None
        )
        fsctl_error = 0 if ok else ctypes.get_last_error()
    finally:
        _close(handle)
    state = leaves.inspect_no_follow(str(path)).classification
    return ("converted" if state == leaves.CLASSIFICATION_REPARSE_POINT else "not_converted"), fsctl_error


def _conversion_probe(question, tmp_path, pins, share, content, access_name, mech_name, aux_name):
    buffer = REPARSE_MECHANISMS[mech_name](str(tmp_path / "nowhere"))
    access = CONVERSION_ACCESSES[access_name]
    held = tmp_path / f"{aux_name}_held.bin"
    pin = _new_pin(pins, held, share=share, data=content)
    held_outcome, held_error = _attempt_conversion(held, access, buffer)
    identity_ok = leaves.inspect_no_follow(str(held)).identity in (pin.identity(), None)
    pin.release()
    control = tmp_path / f"{aux_name}_control.bin"
    control_pin = _new_pin(pins, control, share=share, data=content)
    control_pin.release()
    control_outcome, control_error = _attempt_conversion(control, access, buffer)
    detail = (
        f"{access_name} / {mech_name} / {'non-empty' if content else 'empty'}: "
        f"held={held_outcome}({held_error}) released-control={control_outcome}({control_error})"
    )
    if held_outcome == "converted":
        _premise_fail(
            question,
            f"a second handle ADMITTED by the pin converted the held file to a reparse object -- {detail}",
        )
    if control_outcome != "converted":
        _unsupported(question, f"no usable released-pin positive control, so no evidence -- {detail}")
    if not identity_ok:  # pragma: no cover - defensive
        _harness_fail("identity drift")
    _note(question, f"PASS {detail}")


@pytest.mark.parametrize("content", [b"", PAYLOAD], ids=["empty_Q_shape", "non_empty"])
@pytest.mark.parametrize("mech_name", sorted(REPARSE_MECHANISMS))
@pytest.mark.parametrize("access_name", sorted(CONVERSION_ACCESSES))
def test_q2_no_admitted_second_handle_converts_a_share0_held_file(
    tmp_path, pins, access_name, mech_name, content
):
    _conversion_probe("Q2", tmp_path, pins, 0, content, access_name, mech_name, "q2")


def test_q2_which_second_opens_the_share0_pin_admits(tmp_path, pins):
    """Characterisation: exactly which access masks Windows admits on the held
    share-0 file (the premise text speaks of 'attribute-only opens')."""
    path = tmp_path / "held.bin"
    _new_pin(pins, path, share=0)
    admitted = {}
    for name, access in CONVERSION_ACCESSES.items():
        handle, error = _open(path, access, SHARE_ALL)
        admitted[name] = handle is not None or error
        _close(handle)
    for name in ("GENERIC_WRITE",):
        assert admitted[name] == ERROR_SHARING_VIOLATION, "data access must be refused by share 0"
    _note("Q2", f"second opens on the share-0 held file: {admitted}")


def test_q2_held_file_cannot_be_replaced_by_a_directory_at_the_same_name(tmp_path, pins):
    """Delete/rename-away are required before a directory can occupy the name;
    Q1 proves both blocked. The only direct directory-over-file attempt is the
    POSIX rename in the Q1 matrix (``FileRenameInfoEx_directory_replacing_file``);
    ``CreateDirectoryW`` at the name fails with or without a pin."""
    path = tmp_path / "held.bin"
    pin = _new_pin(pins, path, share=0)
    assert not ctypes.windll.kernel32.CreateDirectoryW(str(path), None)
    held_error = ctypes.get_last_error()
    pin.release()
    assert not ctypes.windll.kernel32.CreateDirectoryW(str(path), None)
    assert held_error == ctypes.get_last_error()
    _note("Q2", "CreateDirectoryW at the held name: identical refusal held/released -- NOT evidence; "
          "directory-over-file is covered only through the Q1 rename/delete rows")


# ---------------------------------------------------------------------------
# Q3 -- the derivation-pin files stabilise their required ancestors
# ---------------------------------------------------------------------------

DERIVATION_FILES = ("package.json", "dist/cli.js", "dist/main.js", "dist/config.js")
ANCESTORS = ("dist", "pi-coding-agent", "@earendil-works", "node_modules")


def _build_derivation_tree(tmp_path):
    root = tmp_path / "pi_runtime"
    node_modules = root / "node_modules"
    scope = node_modules / "@earendil-works"
    package = scope / "pi-coding-agent"
    dist = package / "dist"
    dist.mkdir(parents=True)
    return {
        "root": root,
        "node_modules": node_modules,
        "@earendil-works": scope,
        "pi-coding-agent": package,
        "dist": dist,
    }


def _pin_derivation_files(tmp_path, pins, share: int):
    tree = _build_derivation_tree(tmp_path)
    package = tree["pi-coding-agent"]
    made = []
    for relative in DERIVATION_FILES:
        path = package / relative
        pin = _new_pin(pins, path, share=share, data=f"// derivation file {relative}\n".encode())
        made.append((str(path), pin))
    return tree, made


R0_DERIVATION_SHARE = SHARE_READ  # F5A R0 Sec. 6.5 step 5


@pytest.mark.parametrize("op_name", sorted(OPS))
def test_q3_held_derivation_files_cannot_be_deleted_renamed_replaced_or_recreated(tmp_path, pins, op_name):
    aux = tmp_path / "aux"
    aux.mkdir()
    tree, victims = _pin_derivation_files(tmp_path, pins, R0_DERIVATION_SHARE)
    control_path = victims[1][0]  # dist/cli.js, same file, after release
    findings, errors, control, changed = _attempt_held_then_control(
        "Q3", op_name, victims, lambda: [pin.release() for _p, pin in victims], control_path, str(aux)
    )
    _evaluate("Q3", op_name, findings, errors, control, changed)


@pytest.mark.parametrize("content", [PAYLOAD], ids=["non_empty"])
@pytest.mark.parametrize("mech_name", sorted(REPARSE_MECHANISMS))
@pytest.mark.parametrize("access_name", sorted(CONVERSION_ACCESSES))
def test_q3_no_admitted_second_handle_converts_a_share_read_derivation_file(
    tmp_path, pins, access_name, mech_name, content
):
    _conversion_probe("Q3", tmp_path, pins, R0_DERIVATION_SHARE, content, access_name, mech_name, "q3")


def _rename_by_move(path, new):
    ok = _K.MoveFileExW(str(path), str(new), 0)
    return None if ok else ctypes.get_last_error()


def _rename_by_posix_info(path, new):
    result = _by_handle(
        path, DELETE,
        lambda h: _K.SetFileInformationByHandle(
            h, FILE_RENAME_INFO_EX, *_rename_buffer(str(new), RENAME_POSIX)
        ),
    )
    return None if result.ok else result.error


ANCESTOR_RENAMERS = {"MoveFileExW": _rename_by_move, "FileRenameInfoEx_posix": _rename_by_posix_info}


@pytest.mark.parametrize("renamer_name", sorted(ANCESTOR_RENAMERS))
@pytest.mark.parametrize("ancestor", ANCESTORS + ("root(extra)",))
def test_q3_no_required_ancestor_can_be_renamed_while_a_derivation_pin_is_held(
    tmp_path, pins, ancestor, renamer_name
):
    """Any ancestor the R0 design relies on that CAN be renamed => Q3 FAIL."""
    renamer = ANCESTOR_RENAMERS[renamer_name]
    tree, victims = _pin_derivation_files(tmp_path, pins, R0_DERIVATION_SHARE)
    path = tree["root" if ancestor == "root(extra)" else ancestor]
    moved = Path(str(path) + "_moved")

    held_error = renamer(path, moved)
    if held_error is None:
        # Put it back before reporting, so the tree is not left displaced.
        renamer(moved, path)
        _premise_fail("Q3", f"ancestor {ancestor!r} WAS renamed by {renamer_name} while pins were held")
    assert path.is_dir() and not moved.exists()
    for victim, pin in victims:
        assert leaves.inspect_no_follow(victim).identity == pin.identity()

    for _victim, pin in victims:
        pin.release()
    control_error = renamer(path, moved)
    if control_error is not None:
        _unsupported("Q3", f"{renamer_name} cannot rename {ancestor!r} even with no pin ({control_error})")
    assert moved.is_dir() and not path.exists()
    assert renamer(moved, path) is None
    _note("Q3", f"PASS ancestor {ancestor!r} via {renamer_name}: held refused Win32 {held_error}; "
          "released control renamed it and back")


def test_q3_reopen_successor_cannot_keep_the_r0_share_read_mode_gap_free(tmp_path, pins):
    """R0 Sec. 6.5 step 5 allows 'the creating handle (or a gap-free
    ``ReOpenFile`` successor)'. OBSERVATION, not a premise: a successor that
    keeps share ``FILE_SHARE_READ`` cannot be created while the writer handle is
    open, and the one that CAN be created permits writers once the creator
    closes -- i.e. it is a weaker pin. No workaround is encoded here."""
    path = tmp_path / "reopen.js"
    pin = _new_pin(pins, path, share=SHARE_READ)
    strict = _K.ReOpenFile(pin.handle, GENERIC_READ, SHARE_READ, NO_FOLLOW)
    strict_error = ctypes.get_last_error()
    strict_admitted = strict not in (None, _INVALID)
    _close(strict if strict_admitted else None)
    weaker = _K.ReOpenFile(pin.handle, GENERIC_READ, SHARE_READ | SHARE_WRITE, NO_FOLLOW)
    weaker_admitted = weaker not in (None, _INVALID)
    third_party_write_after_creator_closed = None
    if weaker_admitted:
        pin.release()
        handle, error = _open(path, GENERIC_WRITE, SHARE_ALL)
        third_party_write_after_creator_closed = handle is not None
        _close(handle)
    _close(weaker if weaker_admitted else None)
    _note(
        "Q3/Q4",
        "ReOpenFile successor: share READ admitted="
        f"{strict_admitted} (Win32 {strict_error}); share READ|WRITE admitted={weaker_admitted}; "
        f"third-party GENERIC_WRITE admitted once creator closed={third_party_write_after_creator_closed}",
    )
    assert not strict_admitted
    assert strict_error == ERROR_SHARING_VIOLATION


# ---------------------------------------------------------------------------
# Q4 -- ACTUAL PI-PC1 leaf compatibility with the proposed derivation pins
# ---------------------------------------------------------------------------


def _expected_files():
    return {f: f"// derivation file {f}\n".encode() for f in DERIVATION_FILES}


def _payload_cap() -> int:
    return 1 << 20


def _walk_observation(package_root):
    return pi_payload.observe_payload(str(package_root), leaves=pi_payload.genuine_payload_leaves())


def _assert_walk_complete(question, observation, label):
    if not observation.complete:
        _premise_fail(
            question,
            f"{label}: the genuine PI-PC1 walk REFUSED with {observation.refusal_code!r}; "
            "the copy tree cannot be observed",
        )
    inventory = observation.inventory
    for relative, content in _expected_files().items():
        entry = inventory.entry(relative)
        assert entry is not None and entry[0] == pi_payload.INVENTORY_KIND_FILE, (label, relative)
        assert entry[2] == _sha(content) and entry[3] == len(content)


def test_q4_pi_pc1_file_reads_succeed_on_every_held_derivation_file(tmp_path, pins):
    tree, victims = _pin_derivation_files(tmp_path, pins, R0_DERIVATION_SHARE)
    failures = []
    for path, _pin in victims:
        for name, reader in (
            ("read_payload_file_digest (PI-PC1)", leaves.read_payload_file_digest),
            ("read_payload_file_bytes (PI-PC1 capture)", leaves.read_payload_file_bytes),
        ):
            read = reader(path, _payload_cap())
            relative = os.path.relpath(path, tree["pi-coding-agent"]).replace(os.sep, "/")
            good = (
                read.classification == leaves.CLASSIFICATION_REGULAR_FILE
                and read.within_bound and read.stable
                and read.sha256 == _sha(_expected_files()[relative])
            )
            if not good:
                failures.append(f"{name} {relative}: classification={read.classification!r}")
    _note("Q4", f"PI-PC1 file reads vs R0 creating-handle pin (GENERIC_READ|GENERIC_WRITE, share READ): "
          f"{len(failures)} of {2 * len(victims)} refused")
    if failures:
        _premise_fail("Q4", "PI-PC1 cannot read the pinned derivation files: " + "; ".join(failures))


def test_q4_pi_pc1_directory_enumeration_succeeds_while_pins_are_held(tmp_path, pins):
    tree, _victims = _pin_derivation_files(tmp_path, pins, R0_DERIVATION_SHARE)
    for name in ("root", "node_modules", "@earendil-works", "pi-coding-agent", "dist"):
        listing = leaves.enumerate_directory_no_follow(str(tree[name]), 100)
        if not (listing.classification == leaves.CLASSIFICATION_DIRECTORY and listing.complete):
            _premise_fail("Q4", f"directory enumeration of {name!r} failed while pins were held")
    _note("Q4", "PI-PC1 directory enumeration complete for all five chain directories while pins held")


def test_q4_the_whole_copy_tree_can_still_be_observed_by_the_genuine_walk(tmp_path, pins):
    tree, victims = _pin_derivation_files(tmp_path, pins, R0_DERIVATION_SHARE)
    held = _walk_observation(tree["pi-coding-agent"])
    for _path, pin in victims:
        pin.release()
    # Matched control: the SAME tree, the SAME walk, pins released.
    released = _walk_observation(tree["pi-coding-agent"])
    if not released.complete:
        _harness_fail(f"control walk refused: {released.refusal_code}")
    _assert_walk_complete("Q4", released, "released control")
    _note("Q4", f"genuine PI-PC1 walk with pins held: complete={held.complete} refusal={held.refusal_code!r}")
    _assert_walk_complete("Q4", held, "pins held")


def test_q4_p_leaf_digest_reader_and_attribute_only_inspection_vs_the_pins(tmp_path, pins):
    """L1's ``read_bounded_digest`` (also share READ) and the attribute-only
    ``inspect_no_follow`` against the held files and against the share-0 ``Q``."""
    tree, victims = _pin_derivation_files(tmp_path, pins, R0_DERIVATION_SHARE)
    quarantine = tree["node_modules"] / ".pi-native-quarantine"
    _new_pin(pins, quarantine, share=0, data=b"")
    digest_failures = [
        os.path.basename(p) for p, _ in victims
        if leaves.read_bounded_digest(p, _payload_cap()).classification != leaves.CLASSIFICATION_REGULAR_FILE
        or not leaves.read_bounded_digest(p, _payload_cap()).within_bound
    ]
    for path, _pin in victims:
        assert leaves.inspect_no_follow(path).classification == leaves.CLASSIFICATION_REGULAR_FILE
    assert leaves.inspect_no_follow(str(quarantine)).classification == leaves.CLASSIFICATION_REGULAR_FILE
    _note("Q4", f"attribute-only inspect_no_follow succeeds on all four pins and on share-0 Q; "
          f"read_bounded_digest refused on {digest_failures or 'none'}")
    if digest_failures:
        _premise_fail("Q4", f"L1's read_bounded_digest cannot read: {digest_failures}")


@pytest.mark.parametrize(
    "access_name,access",
    [("GENERIC_WRITE", GENERIC_WRITE), ("FILE_APPEND_DATA|FILE_READ_ATTRIBUTES", 0x4 | FILE_READ_ATTRIBUTES)],
)
def test_q4_the_conflict_follows_the_creators_write_access_not_its_read_access(tmp_path, pins, access_name, access):
    """Any write-capable access on the creating handle, with share READ only,
    refuses the PI-PC1 reader (whose own share mode is READ); asking for less
    read access on the creator does not help."""
    path = tmp_path / "pinned.js"
    pin = _FilePin(path, SHARE_READ, access)
    pins.append(pin)
    pin.write(b"payload")
    read = leaves.read_payload_file_digest(str(path), _payload_cap())
    _note("Q4", f"creator access {access_name}, share READ: PI-PC1 read classification={read.classification!r}")
    if read.classification != leaves.CLASSIFICATION_REGULAR_FILE:
        _premise_fail("Q4", f"creator access {access_name} still refuses the PI-PC1 reader")


def test_q4_control_a_read_only_access_pin_is_compatible_with_the_pi_pc1_reader(tmp_path):
    """CAUSE-ISOLATING CONTROL, not the R0 shape and not a proposed fix.

    Populate with no pin, then hold ``GENERIC_READ`` (no write access) with share
    READ. The identical PI-PC1 walk then succeeds. This only establishes that
    the leaf itself is sound and that the incompatibility above comes from the
    WRITE access carried by the creating handle."""
    tree = _build_derivation_tree(tmp_path)
    package = tree["pi-coding-agent"]
    for relative, content in _expected_files().items():
        Path(package / relative).parent.mkdir(parents=True, exist_ok=True)
        Path(package / relative).write_bytes(content)
    handles = []
    try:
        for relative in DERIVATION_FILES:
            handle, error = _open(package / relative, GENERIC_READ, SHARE_READ, OPEN_EXISTING, FLAG_REPARSE)
            assert handle is not None, error
            handles.append(handle)
        observation = _walk_observation(package)
        _note("Q4", f"control (read-only-access pin, share READ): walk complete={observation.complete}")
        _assert_walk_complete("Q4", observation, "read-only-access control")
    finally:
        for handle in handles:
            _close(handle)


# ---------------------------------------------------------------------------
# Q5 -- reparse defence during construction
# ---------------------------------------------------------------------------


def _r0_pin_directory(path) -> tuple[str, int, object]:
    """R0 Sec. 6.5 step 4, written out literally: ``OPEN_EXISTING``,
    ``BACKUP_SEMANTICS | OPEN_REPARSE_POINT``, share ``FILE_SHARE_READ``; refuse
    a reparse point or a non-directory."""
    handle, error = _open(path, FILE_LIST_DIRECTORY | FILE_READ_ATTRIBUTES, SHARE_READ)
    if handle is None:
        return "not_pinned", error, None
    attributes, tag = _tag_info(handle)
    if attributes & ATTR_REPARSE or tag != 0:
        _close(handle)
        return "reparse_refused", 0, None
    if not attributes & ATTR_DIRECTORY:
        _close(handle)
        return "not_a_directory", 0, None
    return "pinned", 0, handle


def _outside(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel.txt"
    sentinel.write_bytes(b"OUTSIDE-SENTINEL-BYTES\n")
    return outside, sentinel


def _assert_untouched(outside, sentinel, before):
    assert sentinel.read_bytes() == b"OUTSIDE-SENTINEL-BYTES\n"
    assert sorted(os.listdir(outside)) == before


def test_q5_positive_controls_the_redirect_mechanism_is_usable_and_the_pin_is_what_stops_it(tmp_path):
    outside, _sentinel = _outside(tmp_path)
    unpinned = tmp_path / "unpinned"
    unpinned.mkdir()
    outcome, error = probe.attempt_in_place_reparse_conversion(unpinned, outside)
    assert outcome == "converted", (
        f"HARNESS: in-place junction conversion is not usable on this host ({outcome}, {error})"
    )
    assert leaves.inspect_no_follow(str(unpinned)).classification == leaves.CLASSIFICATION_REPARSE_POINT
    os.rmdir(unpinned)

    pinned = tmp_path / "pinned"
    pinned.mkdir()
    state, _error, handle = _r0_pin_directory(pinned)
    try:
        assert state == "pinned"
        outcome, error = probe.attempt_in_place_reparse_conversion(pinned, outside)
        assert (outcome, error) == ("open_refused", ERROR_SHARING_VIOLATION)
    finally:
        _close(handle)
    _note("Q5", "controls: unpinned empty dir converts to a junction in place; a share-READ pin refuses the "
          "conversion open with Win32 32; a plain directory pins as 'pinned'")


@pytest.mark.parametrize("substitution", ["junction_in_place", "dir_symlink_after_rmdir", "junction_after_rmdir"])
def test_q5_a_just_created_directory_turned_into_a_redirect_is_refused_at_the_pin(tmp_path, substitution):
    outside, sentinel = _outside(tmp_path)
    before = sorted(os.listdir(outside))
    root = tmp_path / "owned"
    root.mkdir()
    runtime = root / "pi_runtime"
    runtime.mkdir()
    state, _e, runtime_pin = _r0_pin_directory(runtime)
    assert state == "pinned"
    try:
        node_modules = runtime / "node_modules"
        node_modules.mkdir()  # CreateDirectoryW, then the window before its pin
        if substitution == "junction_in_place":
            outcome, error = probe.attempt_in_place_reparse_conversion(node_modules, outside)
            assert outcome == "converted", (outcome, error)
        else:
            os.rmdir(node_modules)
            if substitution == "dir_symlink_after_rmdir":
                os.symlink(str(outside), str(node_modules), target_is_directory=True)
            else:
                node_modules.mkdir()
                outcome, error = probe.attempt_in_place_reparse_conversion(node_modules, outside)
                assert outcome == "converted", (outcome, error)
        assert leaves.inspect_no_follow(str(node_modules)).classification == leaves.CLASSIFICATION_REPARSE_POINT

        state, _error, handle = _r0_pin_directory(node_modules)
        _close(handle)
        if state != "reparse_refused":
            _premise_fail("Q5", f"{substitution}: the R0 step-4 pin returned {state!r} for a redirect")
        # The production FU15 pin makes the same decision (shape reuse, not re-derivation).
        with pytest.raises(win.Cfg1DirectoryAuthorityError) as excinfo:
            win.acquire_config_pin(str(node_modules))
        assert excinfo.value.reason_code == "CONFIG_DIR_REDIRECTED"
        assert win.held_pin_count() == 0
        # Refused => nothing is ever created beneath the redirect.
        _assert_untouched(outside, sentinel, before)
    finally:
        _close(runtime_pin)
    _note("Q5", f"PASS {substitution}: R0 step-4 pin and production acquire_config_pin both refuse; outside untouched")


@pytest.mark.parametrize("target_exists", [True, False], ids=["existing_outside_file", "dangling"])
def test_q5_create_new_with_open_reparse_point_does_not_follow_a_planted_file_symlink(tmp_path, target_exists):
    outside, sentinel = _outside(tmp_path)
    target = sentinel if target_exists else outside / "never_created.bin"
    before_bytes = sentinel.read_bytes()
    before_listing = sorted(os.listdir(outside))
    attributes_before = _attributes(sentinel)

    link = tmp_path / "planted_link"
    try:
        os.symlink(str(target), str(link))
    except OSError as exc:
        _unsupported("Q5", f"no file-symlink creation on this host: {exc}")

    # POSITIVE CONTROL: the mechanism is real -- a following create DOES reach
    # the far end on this host. Uses a second, independent link and target.
    control_target = outside / "control_target.bin"
    control_link = tmp_path / "control_link"
    os.symlink(str(control_target), str(control_link))
    with open(control_link, "xb") as followed:
        followed.write(b"followed")
    if not control_target.exists():
        _harness_fail("a following exclusive create did not reach the redirect target; control invalid")
    before_listing = sorted(os.listdir(outside))  # now includes the control's own target

    handle, error = _open(link, GENERIC_READ | GENERIC_WRITE, SHARE_READ, CREATE_NEW, FLAG_REPARSE)
    try:
        if handle is not None:
            _premise_fail("Q5", "CREATE_NEW|OPEN_REPARSE_POINT created through/over the planted link")
    finally:
        _close(handle)
    assert error == ERROR_FILE_EXISTS
    assert sorted(os.listdir(outside)) == before_listing
    assert sentinel.read_bytes() == before_bytes
    assert _attributes(sentinel) == attributes_before
    if not target_exists:
        assert not target.exists()
    _note("Q5", f"PASS CREATE_NEW|OPEN_REPARSE_POINT vs {'existing' if target_exists else 'dangling'} link: "
          f"refused Win32 {error}; following-create control reached the target; outside unchanged")


# ---------------------------------------------------------------------------
# Q6 -- owned-root teardown does not follow redirects
# ---------------------------------------------------------------------------


@pytest.fixture()
def cfg1_workspace(git_executable):
    handle, _built = run_workspace.mint_cfg1_run_workspace(git_executable=git_executable)
    root = handle.experiment_root
    try:
        yield handle
    finally:
        run_workspace.discard_cfg1_run_workspace(handle)
        shutil.rmtree(root, ignore_errors=True)


class _Outside:
    """The outside redirect target, made hostile on purpose: every object is
    READONLY, so a teardown that ever chmod()ed THROUGH a redirect would both
    clear the attribute (observable) and be able to delete it."""

    def __init__(self, tmp_path):
        self.directory = tmp_path / "outside_dir"
        self.directory.mkdir()
        self.sentinel = self.directory / "sentinel.txt"
        self.sentinel.write_bytes(b"OUTSIDE-SENTINEL-BYTES\n")
        self.nested_dir = self.directory / "nested"
        self.nested_dir.mkdir()
        self.nested = self.nested_dir / "nested.txt"
        self.nested.write_bytes(b"OUTSIDE-NESTED\n")
        self.lone_file = tmp_path / "outside_lone.txt"
        self.lone_file.write_bytes(b"OUTSIDE-LONE-FILE\n")
        for path in (self.sentinel, self.nested, self.lone_file):
            _set_attributes(path, ATTR_READONLY)
        _set_attributes(self.directory, ATTR_DIRECTORY | ATTR_READONLY)

    def observe(self) -> dict:
        def stat(path):
            result = os.stat(path)
            return (_attributes(path), result.st_size, result.st_mtime_ns)

        return {
            "sentinel_bytes": self.sentinel.read_bytes(),
            "nested_bytes": self.nested.read_bytes(),
            "lone_bytes": self.lone_file.read_bytes(),
            "sentinel": stat(self.sentinel),
            "nested": stat(self.nested),
            "lone": stat(self.lone_file),
            "directory": stat(self.directory),
            "nested_dir": stat(self.nested_dir),
            "listing": sorted(os.listdir(self.directory)),
        }

    def restore(self) -> None:
        for path in (self.sentinel, self.nested, self.lone_file):
            if os.path.exists(path):
                _set_attributes(path, ATTR_NORMAL)
        if os.path.exists(self.directory):
            _set_attributes(self.directory, ATTR_DIRECTORY)


@pytest.fixture()
def outside(tmp_path):
    hostile = _Outside(tmp_path)
    yield hostile
    hostile.restore()


def _rpr_layout(experiment_root):
    runtime = Path(experiment_root) / "pi_runtime"
    node_modules = runtime / "node_modules"
    package = node_modules / "@earendil-works" / "pi-coding-agent"
    (package / "dist").mkdir(parents=True)
    return runtime, node_modules, package


def _populate_and_pin(package, node_modules, pins):
    held = []
    for relative in DERIVATION_FILES:
        held.append(_new_pin(pins, package / relative, share=R0_DERIVATION_SHARE,
                             data=f"// derivation file {relative}\n".encode()))
    held.append(_new_pin(pins, node_modules / ".pi-native-quarantine", share=0, data=b""))
    return held


def _plant_redirects(runtime, package, outside):
    """One of each: a junction (in-place converted), a directory symlink, a
    file symlink -- inside the owned subtree, all pointing OUT."""
    junction = package / "dist" / "planted_junction"
    junction.mkdir()
    outcome, error = probe.attempt_in_place_reparse_conversion(junction, outside.directory)
    assert outcome == "converted", f"HARNESS: junction planting unusable ({outcome}, {error})"
    dir_link = runtime / "planted_dir_symlink"
    os.symlink(str(outside.directory), str(dir_link), target_is_directory=True)
    file_link = runtime / "planted_file_symlink"
    os.symlink(str(outside.lone_file), str(file_link))
    return {"junction": junction, "dir_symlink": dir_link, "file_symlink": file_link}


def _assert_outside_unchanged(question, outside, before, label):
    after = outside.observe()
    if after != before:
        changed = sorted(k for k in before if before[k] != after[k])
        _premise_fail(question, f"{label}: outside target changed: {changed}")


def test_q6_teardown_after_pins_are_released_removes_the_root_and_follows_nothing(
    cfg1_workspace, outside, pins
):
    root = cfg1_workspace.experiment_root
    runtime, node_modules, package = _rpr_layout(root)
    held = _populate_and_pin(package, node_modules, pins)
    redirects = _plant_redirects(runtime, package, outside)
    for name, path in redirects.items():  # the planting is real, not vacuous
        assert leaves.inspect_no_follow(str(path)).classification == leaves.CLASSIFICATION_REPARSE_POINT, name
    before = outside.observe()

    for pin in held:  # deliberate release, each exactly once
        pin.release()
    result = run_workspace.remove_cfg1_run_workspace(cfg1_workspace)

    _note("Q6", f"teardown after release: result={result}; root exists={os.path.exists(root)}")
    assert result == {"removed": True, "residual_file_count": 0, "verified": True}
    assert not os.path.exists(root)
    assert outside.directory.exists() and outside.lone_file.exists()
    _assert_outside_unchanged("Q6", outside, before, "normal teardown")
    _note("Q6", "outside state, identical before and after (attributes, size, mtime_ns): "
          f"{ {k: v for k, v in before.items()} }")


def test_q6_teardown_while_critical_handles_are_pinned_does_not_report_removal(
    cfg1_workspace, outside, pins
):
    root = cfg1_workspace.experiment_root
    runtime, node_modules, package = _rpr_layout(root)
    held = _populate_and_pin(package, node_modules, pins)
    _plant_redirects(runtime, package, outside)
    before = outside.observe()

    result = run_workspace.remove_cfg1_run_workspace(cfg1_workspace)
    _note("Q6", f"teardown with pins HELD: result={result}")
    if result.get("removed") is not False:
        _premise_fail("Q6", f"teardown reported removal while critical handles were pinned: {result}")
    assert result["residual_file_count"] > 0
    assert os.path.exists(root)
    for pin in held:  # every pinned object is still there and still itself
        assert leaves.inspect_no_follow(pin.path).identity == pin.identity()
    _assert_outside_unchanged("Q6", outside, before, "teardown with pins held")

    # MATCHED CONTROL: release, and the identical frozen remover now succeeds.
    for pin in held:
        pin.release()
    control = remove_disposable_tree(root)
    assert control == {"removed": True, "residual_file_count": 0, "verified": True}, control
    _assert_outside_unchanged("Q6", outside, before, "control teardown after release")


def test_q6_error_retry_path_with_a_held_redirect_does_not_mutate_the_outside_target(
    cfg1_workspace, outside, monkeypatch
):
    """Mechanically drives ``remove_disposable_tree``'s ``onexc`` -> ``os.chmod``
    -> retry path ON the redirect objects themselves: each planted redirect is
    held open without ``FILE_SHARE_DELETE``, so its removal fails, the frozen
    handler calls ``os.chmod(<redirect path>, 0o700)`` and retries. A spy proves
    the retry really was invoked on those paths; the outside objects are
    READONLY so any chmod that followed would be visible."""
    root = cfg1_workspace.experiment_root
    runtime, _node_modules, package = _rpr_layout(root)
    redirects = _plant_redirects(runtime, package, outside)
    before = outside.observe()

    holds = []
    for name, path in redirects.items():
        access = GENERIC_READ if name == "file_symlink" else FILE_LIST_DIRECTORY | FILE_READ_ATTRIBUTES
        handle, error = _open(path, access, SHARE_READ | SHARE_WRITE)
        assert handle is not None, f"HARNESS: cannot hold {name}: {error}"
        holds.append(handle)

    chmod_calls: list[str] = []
    real_chmod = os.chmod

    def spy(path, mode, *args, **kwargs):
        chmod_calls.append(os.fspath(path))
        return real_chmod(path, mode, *args, **kwargs)

    monkeypatch.setattr(os, "chmod", spy)
    try:
        result = run_workspace.remove_cfg1_run_workspace(cfg1_workspace)
    finally:
        monkeypatch.undo()
        for handle in holds:
            _close(handle)

    on_redirects = {name: str(path) in chmod_calls for name, path in redirects.items()}
    _note("Q6", f"retry path with held redirects: result={result}; os.chmod invoked on "
          f"{on_redirects} (all chmod targets: {len(chmod_calls)})")
    if not any(on_redirects.values()):
        _note("Q6", "ERROR_RETRY_REDIRECT_BEHAVIOR_NOT_ESTABLISHED")
        pytest.skip("ERROR_RETRY_REDIRECT_BEHAVIOR_NOT_ESTABLISHED: the retry never reached a redirect path")
    _assert_outside_unchanged("Q6", outside, before, "error-retry path on redirects")

    control = remove_disposable_tree(root)
    assert control == {"removed": True, "residual_file_count": 0, "verified": True}, control
    _assert_outside_unchanged("Q6", outside, before, "control teardown after release")


def test_q6_control_what_a_direct_chmod_through_each_redirect_kind_does(tmp_path):
    """INFORMATION for interpreting the retry test: does ``os.chmod(0o700)`` on a
    redirect PATH act on the redirect or on its target on this host? Uses
    separate, disposable READONLY objects and asserts nothing about the answer."""
    results = {}
    # POSITIVE CONTROL: chmod(0o700) really does clear READONLY on a plain path,
    # so "the redirect target's attribute did not change" below is a meaningful
    # observation and not a chmod that can never alter anything here.
    plain = tmp_path / "plain_readonly.txt"
    plain.write_bytes(b"p")
    _set_attributes(plain, ATTR_READONLY)
    os.chmod(plain, 0o700)
    assert not _attributes(plain) & ATTR_READONLY, "HARNESS: chmod cannot clear READONLY on this host"
    for kind in ("dir_symlink", "junction", "file_symlink"):
        base = tmp_path / kind
        base.mkdir()
        if kind == "file_symlink":
            target = base / "target.txt"
            target.write_bytes(b"t")
            _set_attributes(target, ATTR_READONLY)
            link = base / "link"
            os.symlink(str(target), str(link))
        else:
            target = base / "target_dir"
            target.mkdir()
            _set_attributes(target, ATTR_DIRECTORY | ATTR_READONLY)
            link = base / "link"
            if kind == "dir_symlink":
                os.symlink(str(target), str(link), target_is_directory=True)
            else:
                link.mkdir()
                assert probe.attempt_in_place_reparse_conversion(link, target)[0] == "converted"
        before = _attributes(target)
        try:
            os.chmod(link, 0o700)
            error = None
        except OSError as exc:
            error = type(exc).__name__
        after = _attributes(target)
        results[kind] = {"target_attrs_before": hex(before), "after": hex(after),
                         "target_mutated": before != after, "chmod_error": error}
        _set_attributes(target, ATTR_NORMAL if kind == "file_symlink" else ATTR_DIRECTORY)
    _note("Q6", f"direct os.chmod(0o700) on a redirect path: {results}")


def test_zz_print_summary():
    print("\n".join(["", "==== F5A premise-probe notes ===="] + _NOTES))
