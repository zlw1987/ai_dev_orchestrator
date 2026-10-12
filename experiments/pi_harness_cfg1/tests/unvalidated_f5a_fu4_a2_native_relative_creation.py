"""F5A FU4-A2 -- native handle-relative creation feasibility. Evidence only.

R1-FU3 (commit 8343db1) measured that no share mode stops an attribute-only
(``FILE_WRITE_ATTRIBUTES``) open from converting an EMPTY pinned directory into a
junction, after which the PATHNAME creates of Sec. 7.4A.2 (``CreateDirectoryW``,
``CreateFileW(CREATE_NEW)``) land outside the minted root BEFORE any parentage
gate runs. This module measures the one candidate the reviewer selected (A2):
``NtCreateFile`` with ``OBJECT_ATTRIBUTES.RootDirectory`` = the already-proven
parent handle, ``FILE_CREATE``, and a SINGLE-component name.

The question is prevention, not detection: after the FU3 conversion, does a
handle-relative create still land outside the parent directory object?

* ``P-A2-1``  directory child: exclusive create relative to a held parent,
              returning an identity-bearing handle (no pre-pin window).
* ``P-A2-2``  regular-file child: exclusive share-0 create relative to a held
              parent; occupied names (file, junction, symlink) refuse.
* ``P-A2-3``  THE FU3 CASE: the held parent is emptied and converted (mount
              point, symlink and a non-Microsoft tag; ``FILE_WRITE_ATTRIBUTES`` and
              ``GENERIC_WRITE``; three pin shapes). The handle-relative create must
              create NOTHING anywhere. Matched controls: the identical converted
              state with the Sec. 7.4A.2 pathname creates (must escape -- proves the
              attack is live in this fixture), and the identical handle-relative
              create on an unconverted parent (must succeed).
* ``P-A2-4``  name forms: a multi-component name through a junction child, ``..``,
              ``.``, a stream name and an absolute name with a root handle. The
              multi-component raw call is measured to ESCAPE, which is why the
              candidate admits single components only (the wrapper refuses before
              any call).
* ``P-A2-5``  fail-closed: unavailable export, error NTSTATUS, success without
              ``FILE_CREATED``, failed handle proof -- each refuses, closes what it
              opened, and never reaches a pathname create API.
* ``P-A2-6``  the same window one level down: a handle-relative-created EMPTY child
              directory converted attribute-only; creates into it must refuse.
* ``P-A2-7``  content: bytes written through the creating handle stay in that
              object even after a same-user reparse conversion of the zero-byte
              child; nothing outside changes.
* ``P-A2-8``  compatibility: a nested construction (depth 11, the 362-entry
              directory size) built ONLY by handle-relative creates, every level
              passing the Sec. 7.4A.2 exact-set enumeration gate.

A supplemental row measures hard-link aliasing of a held share-0 child (R-ALIAS).
It does not depend on the creation mechanism and feeds no verdict.

Discipline (the P-R1 module's): a PASS is a measured requirement, a refusal is
evidence only with an observably unchanged outside sentinel (content AND
metadata) and an empty or unchanged parent, every attack has a matched control,
a failing premise is left failing. Pure Python / ctypes; every object lives under
pytest ``tmp_path``; no Node, Pi, npm, network, model or credential. Nothing here
is production code. Set ``F5A_FU4_A2_REPORT_PATH`` to write the report.
"""

from __future__ import annotations

import ctypes
import json
import os
import platform
import shutil
import struct
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform != "win32",
    reason="every premise here is a Win32/NTFS semantic; a skip on the target platform is not a pass",
)

if sys.platform == "win32":
    import ctypes.wintypes as wt

    import cfg1_win_probe as probe
    import test_cfg1_f5a_r1_windows_premises as r1  # FU3 helpers, reused unmodified
    import test_cfg1_f5a_windows_handle_probes as q  # Q1-Q6 helpers, reused unmodified
    from pi_harness_cfg1 import pi_fs_leaves as leaves

    _K = ctypes.WinDLL("kernel32", use_last_error=True)
    _K.CreateHardLinkW.restype = wt.BOOL
    _K.CreateHardLinkW.argtypes = [wt.LPCWSTR, wt.LPCWSTR, ctypes.c_void_p]
    _K.WriteFile.restype = wt.BOOL
    _K.WriteFile.argtypes = [wt.HANDLE, ctypes.c_char_p, wt.DWORD, ctypes.POINTER(wt.DWORD), ctypes.c_void_p]
    _K.ReadFile.restype = wt.BOOL
    _K.ReadFile.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.DWORD, ctypes.POINTER(wt.DWORD), ctypes.c_void_p]
    _K.SetFilePointerEx.restype = wt.BOOL
    _K.SetFilePointerEx.argtypes = [wt.HANDLE, ctypes.c_longlong, ctypes.c_void_p, wt.DWORD]
    _K.FlushFileBuffers.restype = wt.BOOL
    _K.FlushFileBuffers.argtypes = [wt.HANDLE]
    _K.GetFileInformationByHandleEx.restype = wt.BOOL
    _K.GetFileInformationByHandleEx.argtypes = [wt.HANDLE, ctypes.c_int, ctypes.c_void_p, wt.DWORD]
    _K.CloseHandle.restype = wt.BOOL
    _K.CloseHandle.argtypes = [wt.HANDLE]
    _K.GetVolumeInformationByHandleW.restype = wt.BOOL
    _K.GetVolumeInformationByHandleW.argtypes = [
        wt.HANDLE, ctypes.c_void_p, wt.DWORD, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        wt.LPWSTR, wt.DWORD,
    ]

    class _UnicodeString(ctypes.Structure):
        _fields_ = [("Length", ctypes.c_ushort), ("MaximumLength", ctypes.c_ushort), ("Buffer", ctypes.c_wchar_p)]

    class _ObjectAttributes(ctypes.Structure):
        _fields_ = [
            ("Length", ctypes.c_ulong), ("RootDirectory", wt.HANDLE),
            ("ObjectName", ctypes.POINTER(_UnicodeString)), ("Attributes", ctypes.c_ulong),
            ("SecurityDescriptor", ctypes.c_void_p), ("SecurityQualityOfService", ctypes.c_void_p),
        ]

    class _IoStatusBlock(ctypes.Structure):
        _fields_ = [("Status", ctypes.c_void_p), ("Information", ctypes.c_size_t)]

# ---------------------------------------------------------------------------
# Constants (winternl.h / ntifs.h values; documented on the NtCreateFile page)
# ---------------------------------------------------------------------------

STATUS_SUCCESS = 0x00000000
STATUS_OBJECT_NAME_INVALID = 0xC0000033
STATUS_OBJECT_NAME_COLLISION = 0xC0000035
STATUS_IO_REPARSE_TAG_NOT_HANDLED = 0xC0000279
STATUS_REPARSE_POINT_NOT_RESOLVED = 0xC0000280
FILE_CREATED = 2
FILE_CREATE = 2
FILE_DIRECTORY_FILE = 0x00000001
FILE_SYNCHRONOUS_IO_NONALERT = 0x00000020
FILE_NON_DIRECTORY_FILE = 0x00000040
FILE_OPEN_REPARSE_POINT = 0x00200000
OBJ_CASE_INSENSITIVE = 0x00000040
FILE_ATTRIBUTE_NORMAL = 0x80
FILE_INTERNAL_INFORMATION = 6
FILE_LINKS_INFORMATION = 46
FILE_STANDARD_INFO = 1  # GetFileInformationByHandleEx class

GENERIC_READ, GENERIC_WRITE, DELETE = 0x80000000, 0x40000000, 0x00010000
SYNCHRONIZE = 0x00100000
FILE_LIST_DIRECTORY, FILE_READ_ATTRIBUTES, FILE_WRITE_ATTRIBUTES = 0x1, 0x80, 0x100
SHARE_READ, SHARE_WRITE, SHARE_ALL = 0x1, 0x2, 0x7
OPEN_EXISTING, CREATE_NEW = 3, 1
FLAG_REPARSE, NO_FOLLOW = 0x00200000, 0x02200000
ATTR_DIRECTORY, ATTR_REPARSE = 0x10, 0x400

#: The candidate's two create shapes. Directory: listed/attribute-read access,
#: share READ only (no DELETE, no WRITE) -- the P-R1-4 child-pin semantics, minted
#: by the create itself. File: the Sec. 7.4A.2 step 1 access, share 0.
DIR_ACCESS = FILE_LIST_DIRECTORY | FILE_READ_ATTRIBUTES | SYNCHRONIZE
DIR_SHARE = SHARE_READ
DIR_OPTIONS = FILE_DIRECTORY_FILE | FILE_SYNCHRONOUS_IO_NONALERT | FILE_OPEN_REPARSE_POINT
FILE_ACCESS = GENERIC_READ | GENERIC_WRITE | DELETE | SYNCHRONIZE
FILE_SHARE = 0
FILE_OPTIONS = FILE_NON_DIRECTORY_FILE | FILE_SYNCHRONOUS_IO_NONALERT | FILE_OPEN_REPARSE_POINT

#: The three parent-handle shapes the design actually holds.
PARENT_SHAPES = {
    "run_root_pin_current_share_READ_WRITE": (FILE_LIST_DIRECTORY | FILE_READ_ATTRIBUTES, SHARE_READ | SHARE_WRITE),
    "run_root_pin_candidate_share_READ": (FILE_LIST_DIRECTORY | FILE_READ_ATTRIBUTES, SHARE_READ),
    "p_r1_4_child_pin_GENERIC_READ_share_READ": (GENERIC_READ, SHARE_READ),
}
CONVERSIONS = {
    "mount_point": lambda target: None,  # issued through probe.set_mount_point_reparse
    "symlink_tag": lambda target: q._symlink_reparse_buffer(str(target)),
    "generic_tag_0x8000FFFF": lambda target: q._generic_reparse_buffer(str(target)),
}
CONVERT_MASKS = {"FILE_WRITE_ATTRIBUTES": FILE_WRITE_ATTRIBUTES, "GENERIC_WRITE": GENERIC_WRITE}

# ---------------------------------------------------------------------------
# Evidence registry
# ---------------------------------------------------------------------------

EXPECTED_CASES = [
    "A2_1_directory_child_created_relative_with_identity_bearing_handle",
    "A2_2_file_child_created_relative_exclusive_and_occupied_names_refuse",
    "A2_3_fu3_converted_parent_relative_create_creates_nothing_anywhere",
    "A2_4_only_single_component_names_are_contained",
    "A2_5_native_failure_fails_closed_without_pathname_fallback",
    "A2_6_converted_empty_child_directory_refuses_relative_creates",
    "A2_7_content_through_creating_handle_stays_in_the_object",
    "A2_8_nested_construction_by_relative_creates_passes_every_gate",
]
_RESULTS: dict[str, dict] = {}
_SUPPLEMENTAL: dict[str, dict] = {}


def _finish(case: str, status: str, **evidence) -> None:
    _RESULTS[case] = {"case": case, "status": status, "evidence": evidence}
    detail = json.dumps(evidence, sort_keys=True, default=str)
    print(f"[F5A-FU4-A2] {status} {case}: {detail[:700]}")
    if status == "FAIL":
        raise AssertionError(f"PREMISE_FAIL[{case}]: {detail}")
    if status == "UNSUPPORTED":
        pytest.skip(f"UNSUPPORTED[{case}]: {detail[:400]}")


def _supplemental(case: str, **evidence) -> None:
    _SUPPLEMENTAL[case] = {"case": case, "status": "OBSERVATION", "evidence": evidence}
    print(f"[F5A-FU4-A2-supplemental] {case}: {json.dumps(evidence, sort_keys=True, default=str)[:500]}")


def _harness(text: str):
    raise AssertionError(f"HARNESS[{text}]")


# ---------------------------------------------------------------------------
# Handle hygiene
# ---------------------------------------------------------------------------

_LIVE: dict[int, str] = {}


@pytest.fixture(autouse=True)
def _no_leaked_handles():
    _LIVE.clear()
    yield
    leaked = dict(_LIVE)
    for handle in list(_LIVE):
        _close(handle)
    assert not leaked, f"HARNESS[leaked handles: {len(leaked)}; {list(leaked.values())[:3]}]"


def _track(handle: int, label: str) -> int:
    _LIVE[handle] = label
    return handle


def _close(handle) -> None:
    if handle:
        _LIVE.pop(handle, None)
        _K.CloseHandle(handle)


# ---------------------------------------------------------------------------
# The native call (raw) and the candidate wrapper (test-local, never production)
# ---------------------------------------------------------------------------


def _resolve_nt_create_file():
    """``ntdll!NtCreateFile`` or ``None``. The candidate resolves it once per
    call and refuses when absent; there is no alternative path."""
    try:
        ntdll = ctypes.WinDLL("ntdll")
        function = ntdll.NtCreateFile
    except (OSError, AttributeError):
        return None
    function.restype = ctypes.c_long
    function.argtypes = [
        ctypes.POINTER(wt.HANDLE), ctypes.c_ulong, ctypes.POINTER(_ObjectAttributes),
        ctypes.POINTER(_IoStatusBlock), ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong,
        ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong,
    ]
    return function


def _raw_relative_create(parent_handle, name: str, kind: str, *, resolver=None) -> tuple[int, int | None, int]:
    """ONE ``NtCreateFile`` relative to ``parent_handle``. Returns
    ``(ntstatus_u32, handle_or_None, io_information)``. No name validation: the
    raw form exists so the name-form probes can measure what the kernel does."""
    function = (resolver or _resolve_nt_create_file)()
    if function is None:
        raise _Refused("NATIVE_RELATIVE_CREATE_UNAVAILABLE")
    access, share, options = (DIR_ACCESS, DIR_SHARE, DIR_OPTIONS) if kind == "dir" else (FILE_ACCESS, FILE_SHARE, FILE_OPTIONS)
    buffer = ctypes.create_unicode_buffer(name)
    length = len(name) * 2
    us = _UnicodeString(length, length, ctypes.cast(buffer, ctypes.c_wchar_p))
    oa = _ObjectAttributes(ctypes.sizeof(_ObjectAttributes), parent_handle, ctypes.pointer(us),
                           OBJ_CASE_INSENSITIVE, None, None)
    iosb = _IoStatusBlock()
    out = wt.HANDLE()
    status = function(ctypes.byref(out), access, ctypes.byref(oa), ctypes.byref(iosb), None,
                      FILE_ATTRIBUTE_NORMAL, share, FILE_CREATE, options, None, 0) & 0xFFFFFFFF
    handle = out.value if status == STATUS_SUCCESS and out.value else None
    if handle:
        _track(handle, f"{kind}:{name}")
    return status, handle, int(iosb.Information)


class _Refused(Exception):
    """A candidate step refused (the analogue of RUNTIME_PROVISIONING_FAILED)."""


_FORBIDDEN_NAME_CHARS = set('\\/:*?"<>|') | {chr(c) for c in range(32)}


def _single_component(name: str) -> str:
    if type(name) is not str or not name or name in (".", "..") or any(ch in _FORBIDDEN_NAME_CHARS for ch in name):
        raise _Refused("NAME_NOT_A_SINGLE_COMPONENT")
    if name[-1] in ". ":
        raise _Refused("NAME_NOT_A_SINGLE_COMPONENT")
    return name


def _file_reference(handle) -> int:
    """64-bit NTFS file reference FROM THE HANDLE (``FileInternalInformation``)."""
    value = ctypes.c_longlong(0)
    iosb = _IoStatusBlock()
    status = _nt_query(handle, ctypes.byref(iosb), ctypes.byref(value), 8, FILE_INTERNAL_INFORMATION)
    if status != STATUS_SUCCESS:
        _harness(f"FileInternalInformation {status:#x}")
    return value.value & 0xFFFFFFFFFFFFFFFF


def _links(handle) -> list[tuple[int, str]] | None:
    """Every ``(parent_file_reference, name)`` link of the object, FROM ITS OWN
    HANDLE (``FileLinksInformation``). ``None`` if the class is unsupported."""
    buffer = ctypes.create_string_buffer(4096)
    iosb = _IoStatusBlock()
    status = _nt_query(handle, ctypes.byref(iosb), buffer, 4096, FILE_LINKS_INFORMATION)
    if status != STATUS_SUCCESS:
        return None
    raw = buffer.raw
    (_needed, returned) = struct.unpack_from("<II", raw, 0)
    entries, offset = [], 8
    for _ in range(returned):
        (next_offset,) = struct.unpack_from("<I", raw, offset)
        (parent,) = struct.unpack_from("<Q", raw, offset + 8)
        (name_length,) = struct.unpack_from("<I", raw, offset + 16)
        name = raw[offset + 20:offset + 20 + name_length * 2].decode("utf-16-le", "surrogatepass")
        entries.append((parent, name))
        if not next_offset:
            break
        offset += next_offset
    return entries


def _nt_query(handle, iosb, buffer, length, klass) -> int:
    ntdll = ctypes.WinDLL("ntdll")
    function = ntdll.NtQueryInformationFile
    function.restype = ctypes.c_long
    function.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int]
    return function(handle, iosb, buffer, length, klass) & 0xFFFFFFFF


def a2_create_child(parent_handle, name: str, kind: str, *, resolver=None, _inject=None) -> dict:
    """The candidate, written out: single-component name -> ONE handle-relative
    ``NtCreateFile(FILE_CREATE)`` -> require ``STATUS_SUCCESS`` AND
    ``Information == FILE_CREATED`` -> prove FROM THE RETURNED HANDLE the kind, no
    reparse attribute/tag, and (where the filesystem reports links) exactly one link
    whose parent reference is the parent handle's. Any failure closes what was
    opened and raises ``_Refused``. There is no other path: no pathname API is
    referenced here at all."""
    _single_component(name)
    status, handle, information = _raw_relative_create(parent_handle, name, kind, resolver=resolver)
    if _inject == "success_without_created" and handle:
        information = 1  # FILE_OPENED -- an unexpected success
    if status != STATUS_SUCCESS or not handle:
        raise _Refused(f"NATIVE_CREATE_REFUSED:{status:#010x}")
    try:
        if information != FILE_CREATED:
            raise _Refused(f"NATIVE_CREATE_UNEXPECTED_RESULT:{information}")
        attributes, tag = q._tag_info(handle)
        if _inject == "proof_failure":
            attributes |= ATTR_REPARSE
        is_dir = bool(attributes & ATTR_DIRECTORY)
        if is_dir != (kind == "dir") or attributes & ATTR_REPARSE or tag != 0:
            raise _Refused("CREATED_OBJECT_NOT_PLAIN")
        links = _links(handle)
        parent_ref = _file_reference(parent_handle)
        if links is not None and (len(links) != 1 or links[0] != (parent_ref, name)):
            raise _Refused("CREATED_OBJECT_PARENT_MISMATCH")
        return {"handle": handle, "identity": q._handle_identity(handle), "links": links, "parent_ref": parent_ref}
    except BaseException:
        _close(handle)
        raise


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _pin(path, access: int, share: int) -> int:
    """Open ``path`` as a directory pin (``OPEN_EXISTING``, BACKUP_SEMANTICS |
    OPEN_REPARSE_POINT) and prove FROM THE HANDLE a plain directory."""
    handle, error = q._open(str(path), access, share, OPEN_EXISTING, NO_FOLLOW)
    if handle is None:
        _harness(f"pin refused ({error}): {path}")
    _track(handle, f"pin:{path}")
    attributes, tag = q._tag_info(handle)
    if not attributes & ATTR_DIRECTORY or attributes & ATTR_REPARSE or tag:
        _close(handle)
        _harness("pinned object is not a plain directory")
    return handle


def _convert(path, outside: Path, tag: str, mask: int) -> tuple[str, int]:
    """The same-user attacker: in-place reparse conversion through an open with
    exactly ``mask``, share ALL. Returns ``("converted"|..., error)``."""
    handle, error = q._open(str(path), mask, SHARE_ALL, OPEN_EXISTING, NO_FOLLOW)
    if handle is None:
        return "open_refused", error
    try:
        if tag == "mount_point":
            ok, fsctl_error = probe.set_mount_point_reparse(handle, str(outside))
        else:
            buffer = CONVERSIONS[tag](outside)
            returned = wt.DWORD(0)
            ok = q._K.DeviceIoControl(handle, q.FSCTL_SET_REPARSE_POINT, buffer, len(buffer), None, 0,
                                      ctypes.byref(returned), None)
            fsctl_error = 0 if ok else ctypes.get_last_error()
    finally:
        q._close(handle)
    state = leaves.inspect_no_follow(str(path)).classification
    return ("converted" if state == leaves.CLASSIFICATION_REPARSE_POINT else "not_converted"), fsctl_error


def _unconvert(path) -> None:
    if leaves.inspect_no_follow(str(path)).classification == leaves.CLASSIFICATION_REPARSE_POINT:
        os.rmdir(path)  # removes the reparse point itself, never its target


def _names(handle) -> list[str]:
    return sorted(n for n, _f, _a, _t in r1._enumerate_once(handle) if n not in (".", ".."))


def _write_via(handle, data: bytes) -> None:
    written = wt.DWORD(0)
    if not _K.WriteFile(handle, data, len(data), ctypes.byref(written), None) or written.value != len(data):
        _harness(f"WriteFile through the creating handle failed ({ctypes.get_last_error()})")
    _K.FlushFileBuffers(handle)


def _read_via(handle, limit: int = 1 << 20) -> bytes:
    if not _K.SetFilePointerEx(handle, 0, None, 0):
        _harness("SetFilePointerEx failed")
    buffer = ctypes.create_string_buffer(limit)
    got = wt.DWORD(0)
    if not _K.ReadFile(handle, buffer, limit, ctypes.byref(got), None):
        _harness(f"ReadFile failed ({ctypes.get_last_error()})")
    return buffer.raw[:got.value]


def _number_of_links(handle) -> int:
    class _Std(ctypes.Structure):
        _fields_ = [("AllocationSize", ctypes.c_longlong), ("EndOfFile", ctypes.c_longlong),
                    ("NumberOfLinks", wt.DWORD), ("DeletePending", ctypes.c_ubyte), ("Directory", ctypes.c_ubyte)]

    info = _Std()
    if not _K.GetFileInformationByHandleEx(handle, FILE_STANDARD_INFO, ctypes.byref(info), ctypes.sizeof(info)):
        _harness("FileStandardInfo unreadable")
    return int(info.NumberOfLinks)


def _filesystem(handle) -> str | None:
    name = ctypes.create_unicode_buffer(64)
    ok = _K.GetVolumeInformationByHandleW(handle, None, 0, None, None, None, name, 64)
    return name.value if ok else None


# ---------------------------------------------------------------------------
# P-A2-1 -- directory child, identity-bearing handle from the create itself
# ---------------------------------------------------------------------------


def test_a2_1_directory_child_is_created_relative_to_the_parent_with_an_identity_bearing_handle(tmp_path):
    outside = r1._Outside(tmp_path)
    root = r1._make_run_root(tmp_path)  # pre-existing marker + .git, as a minted root has
    rows = {}
    for label, (access, share) in PARENT_SHAPES.items():
        parent = _pin(root, access, share)
        name = f"pi_runtime_{len(rows)}"
        created = a2_create_child(parent, name, "dir")
        child = created["handle"]
        try:
            by_name = {n: fid for n, fid, _a, _t in r1._enumerate_once(parent)}
            nested = a2_create_child(child, "nested", "dir")  # the created handle is itself a valid parent
            nested_in_child = _names(child) == ["nested"]
            _close(nested["handle"])
            again, _h, _i = _raw_relative_create(parent, name, "dir")  # exclusive: a second FILE_CREATE collides
            moved = str(root / name) + "_moved"
            rename_error = q._K.MoveFileExW(str(root / name), moved, 0) or ctypes.get_last_error()
            rows[label] = {
                "parent_enumeration_lists_child_with_its_handle_id": by_name.get(name) == created["identity"][1],
                "links_from_child_handle": created["links"],
                "link_parent_equals_parent_handle_reference": created["links"] in (None, [(created["parent_ref"], name)]),
                "created_handle_usable_as_next_parent": nested_in_child,
                "second_FILE_CREATE_status": hex(again),
                "rename_while_created_handle_held_win32": rename_error,
                "rename_refused": rename_error in q.BLOCKING_ERRORS and (root / name).is_dir(),
            }
        finally:
            _close(child)
            _close(parent)
        # matched released control: once the creating handle is closed, the same rename succeeds
        ok = q._K.MoveFileExW(str(root / name), moved, 0)
        rows[label]["released_control_rename_ok"] = bool(ok)
        if ok:
            q._K.MoveFileExW(moved, str(root / name), 0)
    passed = all(
        r["parent_enumeration_lists_child_with_its_handle_id"] and r["link_parent_equals_parent_handle_reference"]
        and r["created_handle_usable_as_next_parent"] and r["second_FILE_CREATE_status"] == hex(STATUS_OBJECT_NAME_COLLISION)
        and r["rename_refused"] and r["released_control_rename_ok"] for r in rows.values()
    ) and outside.changed() == []
    _finish(EXPECTED_CASES[0], "PASS" if passed else "FAIL", shapes=rows, outside_changed=outside.changed(),
            reading="the directory and its share-READ handle come from ONE call: there is no interval between "
                    "creation and the first identity-bearing handle (the FU15 R-WINDOW does not arise)")


# ---------------------------------------------------------------------------
# P-A2-2 -- regular-file child; occupied names
# ---------------------------------------------------------------------------


def test_a2_2_file_child_is_created_relative_exclusively_and_occupied_names_refuse(tmp_path):
    outside = r1._Outside(tmp_path)
    root = tmp_path / "R"
    root.mkdir()
    parent = _pin(root, *PARENT_SHAPES["run_root_pin_candidate_share_READ"])
    evidence: dict = {}
    created = a2_create_child(parent, "zero.bin", "file")
    try:
        handle = created["handle"]
        other, other_error = q._open(str(root / "zero.bin"), GENERIC_READ, SHARE_ALL, OPEN_EXISTING, FLAG_REPARSE)
        q._close(other)
        evidence["zero_bytes_at_create"] = os.stat(root / "zero.bin").st_size == 0
        evidence["second_actor_read_open_win32"] = other_error
        evidence["links"] = created["links"]
        evidence["parent_enumeration_id_matches"] = dict(
            (n, f) for n, f, _a, _t in r1._enumerate_once(parent)).get("zero.bin") == created["identity"][1]
    finally:
        _close(created["handle"])
    # occupied names: an ordinary file, a junction to the outside tree, a file symlink to the outside sentinel
    (root / "occupied_file").write_bytes(b"pre-existing")
    (root / "occupied_junction").mkdir()
    junction_handle, _e = q._open(str(root / "occupied_junction"), FILE_WRITE_ATTRIBUTES, SHARE_ALL, OPEN_EXISTING, NO_FOLLOW)
    probe.set_mount_point_reparse(junction_handle, str(outside.directory))
    q._close(junction_handle)
    try:
        os.symlink(outside.sentinel, root / "occupied_symlink")
        symlink_available = True
    except OSError as exc:
        symlink_available = f"unavailable: {exc.winerror}"
    occupied = {}
    for name in ("occupied_file", "occupied_junction", "occupied_symlink", "occupied_dangling"):
        if name == "occupied_dangling":
            try:
                os.symlink(outside.directory / "does_not_exist", root / name)
            except OSError:
                continue
        if name == "occupied_symlink" and symlink_available is not True:
            continue
        for kind in ("file", "dir"):
            status, handle, _info = _raw_relative_create(parent, name, kind)
            _close(handle)
            occupied[f"{name}:{kind}"] = hex(status)
    _close(parent)
    _unconvert(root / "occupied_junction")
    created_outside = outside.new_names()
    passed = (evidence["zero_bytes_at_create"] and evidence["second_actor_read_open_win32"] == q.ERROR_SHARING_VIOLATION
              and evidence["parent_enumeration_id_matches"] and created["links"] in (None, [(created["parent_ref"], "zero.bin")])
              # any refusal counts (a file create over a junction is STATUS_FILE_IS_A_DIRECTORY); a success never does
              and all(int(v, 16) & 0xC0000000 == 0xC0000000 for v in occupied.values())
              and outside.changed() == [] and not created_outside)
    _finish(EXPECTED_CASES[1], "PASS" if passed else "FAIL", **evidence, occupied_name_statuses=occupied,
            symlink_creation=symlink_available, outside_new_names=created_outside, outside_changed=outside.changed())


# ---------------------------------------------------------------------------
# P-A2-3 -- THE FU3 CASE
# ---------------------------------------------------------------------------


def _fu3_scenario(base: Path, label: str, shape: str, tag: str, mask_name: str) -> dict:
    scratch = base / label
    scratch.mkdir()
    outside = r1._Outside(scratch)
    root = r1._make_run_root(scratch)
    access, share = PARENT_SHAPES[shape]
    parent = _pin(root, access, share)
    row: dict = {"shape": shape, "tag": tag, "mask": mask_name}
    try:
        row["emptied_by_attacker"] = r1._empty_it(root)
        row["conversion"] = list(_convert(root, outside.directory, tag, CONVERT_MASKS[mask_name]))
        attributes, reparse_tag = q._tag_info(parent)
        row["parent_handle_sees_reparse"] = bool(attributes & ATTR_REPARSE) or reparse_tag != 0
        statuses = {}
        for kind, name in (("dir", "pi_runtime"), ("file", "zero.bin")):
            status, handle, info = _raw_relative_create(parent, name, kind)
            statuses[kind] = {"ntstatus": hex(status), "information": info, "handle_returned": handle is not None}
            if handle:
                statuses[kind]["links"] = _links(handle)
                _close(handle)
            try:
                wrapped = a2_create_child(parent, name + "_wrapped", kind)
                _close(wrapped["handle"])
                statuses[kind]["candidate"] = "CREATED"
            except _Refused as exc:
                statuses[kind]["candidate"] = str(exc)
        row["relative_creates"] = statuses
        row["parent_object_entries_after"] = _names(parent)
        row["outside_new_names"] = outside.new_names()
        row["outside_changed_keys"] = outside.changed()
    finally:
        _close(parent)
        _unconvert(root)
    row["contained"] = (row["conversion"][0] == "converted"
                        and all(not s["handle_returned"] and s["candidate"].startswith("NATIVE_CREATE_REFUSED")
                                for s in row["relative_creates"].values())
                        and not row["outside_new_names"] and not row["outside_changed_keys"]
                        and row["parent_object_entries_after"] == [])
    return row


def _pathname_control(base: Path, label: str, tag: str) -> dict:
    """Matched control 1: the IDENTICAL converted state, but the Sec. 7.4A.2
    pathname creates. They must escape, or the fixture proves nothing."""
    scratch = base / label
    scratch.mkdir()
    outside = r1._Outside(scratch)
    root = r1._make_run_root(scratch)
    parent = _pin(root, *PARENT_SHAPES["run_root_pin_current_share_READ_WRITE"])
    try:
        r1._empty_it(root)
        conversion = _convert(root, outside.directory, tag, FILE_WRITE_ATTRIBUTES)
        made_dir = bool(r1._W.CreateDirectoryW(str(root / "pi_runtime"), None))
        handle, _err = q._open(str(root / "zero.bin"), GENERIC_READ | GENERIC_WRITE | DELETE, 0, CREATE_NEW, FLAG_REPARSE)
        q._close(handle)
        escaped = outside.new_names()
    finally:
        _close(parent)
        _unconvert(root)
    return {"tag": tag, "conversion": list(conversion), "CreateDirectoryW_ok": made_dir,
            "CreateFileW_CREATE_NEW_ok": handle is not None, "outside_new_names": escaped}


def _unconverted_control(base: Path, label: str, shape: str) -> dict:
    """Matched control 2: the same emptied, pinned parent WITHOUT conversion; the
    same handle-relative creates must succeed (the refusal above is caused by the
    conversion, not by the call shape)."""
    scratch = base / label
    scratch.mkdir()
    root = r1._make_run_root(scratch)
    parent = _pin(root, *PARENT_SHAPES[shape])
    try:
        r1._empty_it(root)
        results = {}
        for kind, name in (("dir", "pi_runtime"), ("file", "zero.bin")):
            created = a2_create_child(parent, name, kind)
            results[kind] = created["links"] in (None, [(created["parent_ref"], name)])
            _close(created["handle"])
        results["entries"] = _names(parent)
    finally:
        _close(parent)
    return results


def test_a2_3_fu3_converted_parent_relative_create_creates_nothing_anywhere(tmp_path):
    rows = [
        _fu3_scenario(tmp_path, f"s{i}", shape, tag, mask)
        for i, (shape, tag, mask) in enumerate(
            (shape, tag, mask) for shape in PARENT_SHAPES for tag in CONVERSIONS for mask in CONVERT_MASKS
        )
    ]
    pathname_controls = [_pathname_control(tmp_path, f"pc_{tag}", tag) for tag in ("mount_point", "symlink_tag")]
    unconverted_controls = {shape: _unconverted_control(tmp_path, f"uc{i}", shape) for i, shape in enumerate(PARENT_SHAPES)}
    # Which (tag, mask) pairs actually converted? GENERIC_WRITE is share-governed for some pin shapes,
    # so a refused open there is the pin working, not the case under test.
    converted = [r for r in rows if r["conversion"][0] == "converted"]
    not_converted = [r for r in rows if r["conversion"][0] != "converted"]
    escaped = [r for r in rows if r["outside_new_names"] or r["outside_changed_keys"]]
    uncontained_converted = [r for r in converted if not r["contained"]]
    controls_live = all(c["outside_new_names"] for c in pathname_controls)
    unconverted_ok = all(c["dir"] and c["file"] and c["entries"] == ["pi_runtime", "zero.bin"]
                         for c in unconverted_controls.values())
    every_attribute_only_converted = all(
        r["conversion"][0] == "converted" for r in rows if r["mask"] == "FILE_WRITE_ATTRIBUTES")
    if escaped or uncontained_converted:
        status = "FAIL"
    elif controls_live and unconverted_ok and every_attribute_only_converted:
        status = "PASS"
    else:
        status = "UNSUPPORTED"
    _finish(EXPECTED_CASES[2], status, scenarios=rows, converted_scenarios=len(converted),
            scenarios_where_the_pin_refused_the_conversion_open=[(r["shape"], r["tag"], r["mask"], r["conversion"])
                                                                  for r in not_converted],
            pathname_matched_controls=pathname_controls, unconverted_matched_controls=unconverted_controls,
            reading="after the FU3 conversion the kernel refuses a create relative to the converted directory "
                    "(STATUS_REPARSE_POINT_NOT_RESOLVED for name-surrogate tags, STATUS_IO_REPARSE_TAG_NOT_HANDLED "
                    "for the non-Microsoft tag); the identical pathname creates escape")


# ---------------------------------------------------------------------------
# P-A2-4 -- name forms
# ---------------------------------------------------------------------------


def test_a2_4_only_single_component_names_are_contained(tmp_path):
    outside = r1._Outside(tmp_path)
    root = tmp_path / "R"
    root.mkdir()
    (root / "j").mkdir()
    junction_handle, _e = q._open(str(root / "j"), FILE_WRITE_ATTRIBUTES, SHARE_ALL, OPEN_EXISTING, NO_FOLLOW)
    probe.set_mount_point_reparse(junction_handle, str(outside.directory))
    q._close(junction_handle)
    parent = _pin(root, *PARENT_SHAPES["run_root_pin_candidate_share_READ"])
    raw, wrapped = {}, {}
    try:
        names = ["j\\via_junction", "..\\dotdot", ".", "a:stream", "\\??\\" + str(outside.directory) + "\\abs",
                 "\\abs2", "trailingdot.", "fwd/slash"]
        for name in names:
            status, handle, _info = _raw_relative_create(parent, name, "dir")
            raw[name] = {"ntstatus": hex(status), "created": handle is not None}
            _close(handle)
            try:
                created = a2_create_child(parent, name, "dir")
                _close(created["handle"])
                wrapped[name] = "CREATED"
            except _Refused as exc:
                wrapped[name] = str(exc)
        after = outside.new_names()
    finally:
        _close(parent)
        _unconvert(root / "j")
    multi_escaped = raw["j\\via_junction"]["created"] and "via_junction" in after
    wrapper_refused_all = all(v == "NAME_NOT_A_SINGLE_COMPONENT" for v in wrapped.values())
    others_not_created_outside = set(after) <= {"via_junction"}
    # The PASS requirement: the candidate admits no multi-component name, and the raw measurement shows why.
    status = "PASS" if wrapper_refused_all and others_not_created_outside and multi_escaped else (
        "FAIL" if not wrapper_refused_all else "UNSUPPORTED")
    _finish(EXPECTED_CASES[3], status, raw_kernel_results=raw, candidate_results=wrapped, outside_new_names=after,
            reading="a relative name with an intermediate component IS resolved through a junction child and "
                    "creates outside: containment holds only for one component directly under the held parent")


# ---------------------------------------------------------------------------
# P-A2-5 -- fail closed, no pathname fallback
# ---------------------------------------------------------------------------


def test_a2_5_native_failure_fails_closed_without_pathname_fallback(tmp_path, monkeypatch):
    root = tmp_path / "R"
    root.mkdir()
    parent = _pin(root, *PARENT_SHAPES["run_root_pin_candidate_share_READ"])
    pathname_calls: list[str] = []

    def spy(label):
        def _call(*args, **kwargs):
            pathname_calls.append(label)
            raise AssertionError(f"pathname fallback reached: {label}")
        return _call

    results = {}
    try:
        monkeypatch.setattr(r1._W, "CreateDirectoryW", spy("CreateDirectoryW"))
        monkeypatch.setattr(q._K, "CreateFileW", spy("CreateFileW"))
        cases = {
            "export_unavailable": dict(name="u", kind="dir", resolver=lambda: None),
            "error_ntstatus_collision": dict(name="collide", kind="dir"),
            "success_without_FILE_CREATED": dict(name="unexpected", kind="file", _inject="success_without_created"),
            "handle_proof_failure": dict(name="proof", kind="dir", _inject="proof_failure"),
        }
        first = a2_create_child(parent, "collide", "dir")  # occupy the name for the collision case
        _close(first["handle"])
        for label, kwargs in cases.items():
            live_before = set(_LIVE)
            try:
                a2_create_child(parent, kwargs.pop("name"), kwargs.pop("kind"), **kwargs)
                results[label] = {"refused": False}
            except _Refused as exc:
                results[label] = {"refused": True, "reason": str(exc), "handles_left_open": len(set(_LIVE) - live_before)}
        entries = _names(parent)
    finally:
        monkeypatch.undo()
        _close(parent)
    passed = (all(r["refused"] and r["handles_left_open"] == 0 for r in results.values()) and not pathname_calls
              and results["export_unavailable"]["reason"] == "NATIVE_RELATIVE_CREATE_UNAVAILABLE")
    _finish(EXPECTED_CASES[4], "PASS" if passed else "FAIL", cases=results, pathname_api_calls=pathname_calls,
            parent_entries_after=entries,
            reading="an unexpected success leaves an object in the parent (it is an entry of the held parent and "
                    "receives no content); the candidate refuses and does not delete it -- L27 owns teardown")


# ---------------------------------------------------------------------------
# P-A2-6 -- the window one level down
# ---------------------------------------------------------------------------


def test_a2_6_converted_empty_child_directory_refuses_relative_creates(tmp_path):
    outside = r1._Outside(tmp_path)
    root = tmp_path / "R"
    root.mkdir()
    parent = _pin(root, *PARENT_SHAPES["run_root_pin_candidate_share_READ"])
    created = a2_create_child(parent, "RT", "dir")
    child = created["handle"]
    try:
        conversion = _convert(root / "RT", outside.directory, "mount_point", FILE_WRITE_ATTRIBUTES)
        generic_write_conversion = None
        statuses = {}
        for kind, name in (("dir", "pi-coding-agent"), ("file", "package.json")):
            status, handle, _info = _raw_relative_create(child, name, kind)
            statuses[kind] = hex(status)
            _close(handle)
        child_entries = _names(child)
        escaped = outside.new_names()
    finally:
        _close(child)
        _close(parent)
        _unconvert(root / "RT")
    # matched: the data-write conversion of the same (re-created) empty child is refused by its share-READ handle
    created2 = a2_create_child(_pin(root, *PARENT_SHAPES["run_root_pin_candidate_share_READ"]), "RT2", "dir")
    try:
        generic_write_conversion = _convert(root / "RT2", outside.directory, "mount_point", GENERIC_WRITE)
    finally:
        _close(created2["handle"])
        for handle in list(_LIVE):
            _close(handle)
        _unconvert(root / "RT2")
    passed = (conversion[0] == "converted" and all(s == hex(STATUS_REPARSE_POINT_NOT_RESOLVED) for s in statuses.values())
              and not escaped and child_entries == [] and outside.changed() == [])
    _finish(EXPECTED_CASES[5], "PASS" if passed else "FAIL", attribute_only_conversion_of_created_child=list(conversion),
            relative_creates_into_converted_child=statuses, child_entries_after=child_entries,
            outside_new_names=escaped, data_write_conversion_against_created_handle=list(generic_write_conversion),
            reading="the FU3 conversion of an empty created directory still happens (no share mode governs it); "
                    "what changes is that every later create into it refuses instead of escaping")


# ---------------------------------------------------------------------------
# P-A2-7 -- content stays in the object
# ---------------------------------------------------------------------------


def test_a2_7_content_through_the_creating_handle_stays_in_the_object(tmp_path):
    outside = r1._Outside(tmp_path)
    root = tmp_path / "R"
    root.mkdir()
    parent = _pin(root, *PARENT_SHAPES["run_root_pin_candidate_share_READ"])
    rows = {}
    try:
        for attack in ("none", "file_symlink_tag_via_FILE_WRITE_ATTRIBUTES"):
            name = f"f_{attack[:4]}.js"
            created = a2_create_child(parent, name, "file")
            handle = created["handle"]
            try:
                conversion = None
                if attack != "none":
                    conversion = list(q._attempt_conversion(str(root / name), FILE_WRITE_ATTRIBUTES,
                                                            q._symlink_reparse_buffer(str(outside.sentinel))))
                payload = b"approved-bytes:" + name.encode()
                _write_via(handle, payload)
                read_back = _read_via(handle)
                attributes, tag = q._tag_info(handle)
                rows[attack] = {"conversion": conversion, "read_back_equals_payload": read_back == payload,
                                "child_handle_sees_reparse": bool(attributes & ATTR_REPARSE) or tag != 0,
                                "identity_unchanged": q._handle_identity(handle) == created["identity"]}
            finally:
                _close(handle)
        entries = _names(parent)
    finally:
        _close(parent)
    passed = (all(r["read_back_equals_payload"] and r["identity_unchanged"] for r in rows.values())
              and outside.changed() == [] and not outside.new_names())
    _finish(EXPECTED_CASES[6], "PASS" if passed else "FAIL", rows=rows, parent_entries=entries,
            outside_changed=outside.changed(),
            reading="content follows the handle, never a name: a reparse attribute acquired by the zero-byte child "
                    "after creation does not move the write; the child handle can see the attribute (detection only)")


# ---------------------------------------------------------------------------
# P-A2-8 -- a nested construction made only of relative creates
# ---------------------------------------------------------------------------


def test_a2_8_nested_construction_by_relative_creates_passes_every_gate(tmp_path):
    outside = r1._Outside(tmp_path)
    root = r1._make_run_root(tmp_path)
    parent = _pin(root, *PARENT_SHAPES["run_root_pin_candidate_share_READ"])
    gates, files, peak = 0, 0, 0

    def build(dir_handle, depth: int) -> None:
        nonlocal gates, files, peak
        fan_files = 360 if depth == 3 else 4
        fan_dirs = 2 if depth == 3 else (1 if depth < 11 else 0)
        file_handles = {f"f{i}.js": a2_create_child(dir_handle, f"f{i}.js", "file") for i in range(fan_files)}
        dir_handles = {f"d{i}": a2_create_child(dir_handle, f"d{i}", "dir") for i in range(fan_dirs)}
        peak = max(peak, len(_LIVE))
        entries = {n: fid for n, fid, _a, _t in r1._enumerate_once(dir_handle)}
        expected = {".", "..", *file_handles, *dir_handles}
        if set(entries) != expected or any(entries[n] != c["identity"][1] for n, c in {**file_handles, **dir_handles}.items()):
            raise _Refused("GATE")
        gates += 1
        for name, created in file_handles.items():
            _write_via(created["handle"], name.encode())
            if _read_via(created["handle"]) != name.encode():
                raise _Refused("READBACK")
            _close(created["handle"])
            files += 1
        for name, created in dir_handles.items():
            if depth < 11:
                build(created["handle"], depth + 1)
            _close(created["handle"])

    rt = a2_create_child(parent, "pi_runtime", "dir")
    try:
        membership = dict((n, f) for n, f, _a, _t in r1._enumerate_once(parent)).get("pi_runtime") == rt["identity"][1]
        build(rt["handle"], 1)
        refused = None
    except _Refused as exc:
        refused = str(exc)
    finally:
        filesystem = _filesystem(parent)
        for handle in list(_LIVE):
            _close(handle)
    passed = refused is None and membership and gates == 19 and outside.changed() == []
    _finish(EXPECTED_CASES[7], "PASS" if passed else "FAIL", rt_membership_gate=membership, gates_passed=gates,
            files_written=files, peak_open_handles=peak, refused=refused, filesystem=filesystem,
            outside_changed=outside.changed())


# ---------------------------------------------------------------------------
# Supplemental (feeds no verdict): R-ALIAS, hard links to a held share-0 child
# ---------------------------------------------------------------------------


def test_supplemental_hard_link_aliasing_of_a_held_share_0_child(tmp_path):
    outside = r1._Outside(tmp_path)
    root = tmp_path / "R"
    root.mkdir()
    parent = _pin(root, *PARENT_SHAPES["run_root_pin_candidate_share_READ"])
    created = a2_create_child(parent, "models.json", "file")
    handle = created["handle"]
    alias = outside.directory / "alias.json"
    try:
        links_before = _number_of_links(handle)
        ok = bool(_K.CreateHardLinkW(str(alias), str(root / "models.json"), None))
        error = 0 if ok else ctypes.get_last_error()
        links_after = _number_of_links(handle)
        link_entries = _links(handle)
        _write_via(handle, b"bytes-written-through-the-proven-handle")
    finally:
        _close(handle)
        _close(parent)
    alias_bytes = alias.read_bytes() if alias.exists() else None
    if alias.exists():
        os.remove(alias)
    _supplemental("R_ALIAS_hard_link_to_held_share_0_child", hard_link_created_while_held=ok, win32_error=error,
                  number_of_links_before=links_before, number_of_links_after=links_after,
                  links_from_child_handle=link_entries,
                  alias_reads_bytes_written_through_handle=alias_bytes == b"bytes-written-through-the-proven-handle",
                  reading="mechanism-independent: the same holds for a pathname-created child. A2 creates nothing "
                          "outside R; a same-user actor can give the object an extra outside NAME. Link count is "
                          "visible from the handle (detection only); no measured mechanism prevents it")


# ---------------------------------------------------------------------------
# Roll-up
# ---------------------------------------------------------------------------


def test_zz_rollup_and_report(tmp_path):
    statuses = {case: _RESULTS[case]["status"] for case in EXPECTED_CASES if case in _RESULTS}
    missing = [case for case in EXPECTED_CASES if case not in _RESULTS]
    if any(s == "FAIL" for s in statuses.values()):
        verdict = "FAIL"
    elif not missing and all(s == "PASS" for s in statuses.values()):
        verdict = "PASS"
    else:
        verdict = "PARTIAL"
    handle = _pin(tmp_path, FILE_READ_ATTRIBUTES, SHARE_ALL)
    filesystem = _filesystem(handle)
    _close(handle)
    report = {
        "record_kind": "aido-f5a-fu4-a2-native-relative-creation-evidence.v1",
        "environment": {
            "windows_build": ".".join(str(part) for part in sys.getwindowsversion()[:3]),
            "platform": platform.platform(),
            "python": platform.python_version(),
            "filesystem": filesystem,
        },
        "mechanism": {
            "call": "ntdll!NtCreateFile",
            "object_attributes": "RootDirectory = held parent handle; ObjectName = ONE component; OBJ_CASE_INSENSITIVE",
            "disposition": "FILE_CREATE",
            "directory": {"access": hex(DIR_ACCESS), "share": hex(DIR_SHARE), "options": hex(DIR_OPTIONS)},
            "file": {"access": hex(FILE_ACCESS), "share": hex(FILE_SHARE), "options": hex(FILE_OPTIONS)},
        },
        "verdict": verdict,
        "cases_pass": sum(1 for s in statuses.values() if s == "PASS"),
        "cases_fail": sum(1 for s in statuses.values() if s == "FAIL"),
        "cases_unsupported": sum(1 for s in statuses.values() if s == "UNSUPPORTED"),
        "cases_not_run": missing,
        "cases": [_RESULTS[case] for case in EXPECTED_CASES if case in _RESULTS],
        "supplemental": [_SUPPLEMENTAL[k] for k in sorted(_SUPPLEMENTAL)],
        "scope": "measured only against disposable synthetic trees under pytest tmp_path on this host; no Node, Pi, "
                 "npm, model or network; other builds, filesystems and filter drivers are not measured",
        "closure_claimed": False,
    }
    print(f"\n==== F5A FU4-A2 verdict: {verdict} ({statuses}) ====")
    destination = os.environ.get("F5A_FU4_A2_REPORT_PATH")
    if destination:
        Path(destination).write_text(json.dumps(report, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
