"""F5A R1 -- Windows premise probes P-R1-1 .. P-R1-4 (amendment Sec. 14). Evidence only.

The R1-FU2 amendment (``docs/PHASE_5F3B_CFG1_F5A_LIVE_LAUNCH_AUTHORITY_AMENDMENT.md``
Sec. 14) leaves four target-platform facts unmeasured. This module measures them
with the ATTACKER'S real Win32 operations, directly, against synthetic temporary
trees. It is a premise test, not an implementation: nothing here is production
code, nothing here is importable by production code, and **a failing premise is
left failing** -- no design is adjusted and no invariant relaxed to produce a
pass.

* P-R1-1  the final read-only pins (``GENERIC_READ``, share READ) refuse delete,
          rename, replace and overwrite of the four held files.
* P-R1-2  the same pins refuse a rename of every required ancestor
          (``dist``, ``C``, ``RT``, ``R``).
* P-R1-3  the genuine PI-PC1 file reader / directory walk and the leaves the
          L14 / L21A re-proofs call stay compatible with all four held pins over
          a full synthetic copy (the committed approved inventory's shape).
* P-R1-4  the Sec. 7.4A construction shape (pinned parent, child directory pins,
          exclusive zero-byte children, maximum fan-out, single-pass handle
          enumeration with exact file-id parentage, protection of the pinned
          directories, content written through the child handles only).

Discipline (the same one the Q1-Q6 module follows, whose helpers are REUSED
where their semantics match rather than copied):

* every refusal attributed to a pin carries a matched RELEASED-pin control that
  runs the identical operation on the identical path and must SUCCEED and change
  state; a mechanism the host does not support is ``UNSUPPORTED`` and is never
  counted as a safety PASS;
* a refusal only counts as evidence when it carries ``ERROR_SHARING_VIOLATION``
  or ``ERROR_ACCESS_DENIED`` AND the object is observably unchanged afterwards;
* a premise violation raises ``PREMISE_FAIL[...]``; a malfunctioning probe raises
  ``HARNESS[...]``, so the two are never confused;
* every handle this module opens is registered and an autouse fixture proves none
  survives a test.

Pure Python / ctypes. No Node, no Pi, no npm, no network, no model, no
credential. Every write is under pytest ``tmp_path`` / ``tmp_path_factory``.
Set ``F5A_PR1_REPORT_PATH`` to also write the machine-readable evidence report.
"""

from __future__ import annotations

import builtins
import collections
import ctypes
import hashlib
import json
import msvcrt
import os
import platform
import shutil
import struct
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform != "win32",
    reason="every premise here is a Win32 semantic; a skip on the target platform is not a pass",
)

if sys.platform == "win32":
    import cfg1_win_probe as probe
    import test_cfg1_f5a_windows_handle_probes as q  # the established Q1-Q6 helpers (unmodified)
    from pi_harness_cfg1 import pi_fs_leaves as leaves
    from pi_harness_cfg1 import pi_identity, pi_payload
    from pi_harness_cfg1 import win_config_authority as win

    _W = ctypes.WinDLL("kernel32", use_last_error=True)
    _W.CreateDirectoryW.restype = ctypes.c_int
    _W.CreateDirectoryW.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p]
    _W.RemoveDirectoryW.restype = ctypes.c_int
    _W.RemoveDirectoryW.argtypes = [ctypes.c_wchar_p]
    _W.GetVolumeInformationW.restype = ctypes.c_int
    _W.GetVolumeInformationW.argtypes = [
        ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_ulong,
    ]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_INVENTORY = (
    _REPO_ROOT / "experiments" / "pi_harness_cfg1" / "pi_profile_policy" / "inventories"
    / "66cf8a815d91aeaf3eb920763c6a4f3b98c17625dbaa93c540fb424c451664dc.json"
)

GENERIC_READ, GENERIC_WRITE, DELETE = q.GENERIC_READ, q.GENERIC_WRITE, q.DELETE
SHARE_READ, SHARE_WRITE, SHARE_ALL = q.SHARE_READ, q.SHARE_WRITE, q.SHARE_ALL
OPEN_EXISTING, CREATE_NEW = q.OPEN_EXISTING, q.CREATE_NEW
FLAG_REPARSE, NO_FOLLOW = q.FLAG_REPARSE, q.NO_FOLLOW
ATTR_DIRECTORY, ATTR_REPARSE = q.ATTR_DIRECTORY, q.ATTR_REPARSE
BLOCKING = q.BLOCKING_ERRORS
ERROR_FILE_EXISTS = q.ERROR_FILE_EXISTS
ERROR_SHARING_VIOLATION = q.ERROR_SHARING_VIOLATION
ERROR_DIRECTORY_NOT_EMPTY = probe.ERROR_DIRECTORY_NOT_EMPTY
ERROR_NO_MORE_FILES = 18
FILE_ID_EXTD_DIRECTORY_INFO = 19
FILE_RENAME_INFO = q.FILE_RENAME_INFO
FILE_RENAME_INFO_EX = q.FILE_RENAME_INFO_EX
RENAME_POSIX = q.RENAME_POSIX

#: Byte offsets inside ``FILE_ID_EXTD_DIR_INFO``; cross-checked against the
#: established production layout in ``test_layout_matches_the_established_helper``.
_X_NEXT, _X_ATTRS, _X_NAMELEN, _X_TAG, _X_FILEID, _X_NAME = 0, 56, 60, 68, 72, 88

FINAL_FILES = ("package.json", "dist/cli.js", "dist/main.js", "dist/config.js")
ANCESTORS = ("dist", "C", "RT", "R")
RENAMER_NAMES = ("MoveFileExW", "FileRenameInfo", "FileRenameInfoEx_posix")
DELETE_OPS = ("RemoveDirectoryW", "FileDispositionInfo", "FileDispositionInfoEx_delete", "FileDispositionInfoEx_posix")

# ---------------------------------------------------------------------------
# Evidence registry
# ---------------------------------------------------------------------------

def _op_open_existing_write(path, aux):
    """Overwrite in place: an ordinary write open of the existing file and a write
    through it (no truncation) -- the 'overwrite' that CREATE_ALWAYS / TRUNCATE do
    not cover."""
    handle, error = q._open(path, GENERIC_WRITE, SHARE_ALL, OPEN_EXISTING, FLAG_REPARSE)
    if handle is None:
        return q.OpResult(False, error)
    descriptor = msvcrt.open_osfhandle(handle, os.O_WRONLY | getattr(os, "O_BINARY", 0))
    try:
        os.write(descriptor, b"OVERWRITTEN-IN-PLACE")
    finally:
        os.close(descriptor)
    return q.OpResult(True, 0)


#: Q1's operation library plus the one overwrite shape it lacks.
ALL_OPS = {**q.OPS, "CreateFileW_OPEN_EXISTING_write_bytes": _op_open_existing_write} if sys.platform == "win32" else {}

EXPECTED_CASES = {
    "P-R1-1": [f"OP:{name}" for name in sorted(ALL_OPS)],
    "P-R1-2": [f"RENAME:{r}:{a}" for r in sorted(RENAMER_NAMES) for a in ANCESTORS],
    "P-R1-3": [
        "readers_on_held_pins",
        "directory_walk_over_chain",
        "payload_walk_held_equals_expected_equals_released",
        "l14_l21a_proof_leaves",
        "sensitivity_control_incompatible_shape",
    ],
    "P-R1-4": [
        "i_child_directory_create_and_pin",
        "ii_exclusive_zero_byte_children",
        "ii_iii_fanout_gate_and_peak",
        "iii_single_pass_cursor",
        "iii_gate_negative_controls",
        "iv_rename",
        "iv_delete",
        "iv_convert",
        "v_content_through_child_handles",
    ],
}
_RESULTS: dict[str, dict[str, dict]] = {p: {} for p in EXPECTED_CASES}
_SUPPLEMENTAL: dict[str, dict] = {}
_FACTS: dict[str, object] = {}


def _record(premise: str, case: str, status: str, **evidence) -> dict:
    entry = {"case": case, "status": status, "evidence": evidence}
    _RESULTS[premise][case] = entry
    detail = json.dumps(evidence, sort_keys=True, default=str)
    print(f"[F5A-{premise}] {status} {case}: {detail[:600]}")
    return entry


def _finish(premise: str, case: str, status: str, **evidence) -> None:
    """Record, then enforce: FAIL raises, UNSUPPORTED skips, PASS returns."""
    _record(premise, case, status, **evidence)
    if status == "FAIL":
        raise AssertionError(f"PREMISE_FAIL[{premise}:{case}]: {json.dumps(evidence, sort_keys=True, default=str)}")
    if status == "UNSUPPORTED":
        pytest.skip(f"UNSUPPORTED[{premise}:{case}]: {json.dumps(evidence, sort_keys=True, default=str)[:400]}")


def _supplemental(case: str, status: str, **evidence) -> None:
    _SUPPLEMENTAL[case] = {"case": case, "status": status, "evidence": evidence}
    print(f"[F5A-supplemental] {status} {case}: {json.dumps(evidence, sort_keys=True, default=str)[:400]}")


def _harness(text: str):
    raise AssertionError(f"HARNESS[{text}]")


# ---------------------------------------------------------------------------
# Handle hygiene: nothing this module opens may outlive its test
# ---------------------------------------------------------------------------

_LIVE: set[object] = set()


@pytest.fixture(autouse=True)
def _no_leaked_handles():
    _LIVE.clear()
    yield
    leaked = [getattr(item, "path", repr(item)) for item in _LIVE]
    for item in list(_LIVE):
        item.release()
    assert not leaked, f"HARNESS[leaked handles: {len(leaked)}; first {leaked[:3]}]"


# ---------------------------------------------------------------------------
# Pins
# ---------------------------------------------------------------------------


class _FinalPin:
    """The Sec. 7.6 final pin, written out literally.

    ``CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, OPEN_EXISTING,
    FILE_FLAG_OPEN_REPARSE_POINT)`` -- no write, no delete access -- then proof
    FROM THE HANDLE that it is a regular file with no reparse attribute/tag and
    that its file id equals the id recorded before (standing in for "the id
    recorded from the creating handle").
    """

    def __init__(self, path, share: int = SHARE_READ, access: int = GENERIC_READ):
        self.path = str(path)
        recorded = leaves.inspect_no_follow(self.path)
        if recorded.classification != leaves.CLASSIFICATION_REGULAR_FILE:
            _harness(f"final-pin target is not a regular file: {self.path}")
        handle, error = q._open(self.path, access, share, OPEN_EXISTING, FLAG_REPARSE)
        if handle is None:
            _harness(f"final pin could not be acquired ({error}): {self.path}")
        attributes, tag = q._tag_info(handle)
        if attributes & ATTR_DIRECTORY or attributes & ATTR_REPARSE or tag != 0:
            q._close(handle)
            _harness("final pin target is not a plain regular file")
        self._identity = q._handle_identity(handle)
        if self._identity != recorded.identity:
            q._close(handle)
            _harness("pin identity differs from the recorded identity")
        self._fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | getattr(os, "O_BINARY", 0))
        _LIVE.add(self)

    def read(self) -> bytes:
        os.lseek(self._fd, 0, os.SEEK_SET)
        chunks = []
        while True:
            chunk = os.read(self._fd, 65536)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks)

    def identity(self) -> tuple[int, int]:
        return self._identity

    def release(self) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        _LIVE.discard(self)


class _DirPin:
    """A directory pin: ``GENERIC_READ``, share ``share``, ``OPEN_EXISTING``,
    ``BACKUP_SEMANTICS | OPEN_REPARSE_POINT``; refuses a reparse point or a
    non-directory FROM THE HANDLE."""

    def __init__(self, path, share: int = SHARE_READ):
        self.path = str(path)
        handle, error = q._open(self.path, GENERIC_READ, share, OPEN_EXISTING, NO_FOLLOW)
        if handle is None:
            raise _Refused(f"directory pin refused (Win32 {error})")
        attributes, tag = q._tag_info(handle)
        if not attributes & ATTR_DIRECTORY or attributes & ATTR_REPARSE or tag != 0:
            q._close(handle)
            raise _Refused("pinned object is not a plain directory")
        self.handle = handle
        self.identity = q._handle_identity(handle)
        self._open = True
        _LIVE.add(self)

    def release(self) -> None:
        if self._open:
            q._close(self.handle)
            self._open = False
        _LIVE.discard(self)


class _Refused(Exception):
    """A construction/gate step refused (the analogue of RUNTIME_PROVISIONING_FAILED)."""


def _enumerate_once(handle) -> list[tuple[str, int, int, int]]:
    """Every ``(name, file_id, attributes, reparse_tag)`` read FROM THE HANDLE in
    ONE pass (``FileIdExtdDirectoryInfo``; the cursor is per handle)."""
    buffer = ctypes.create_string_buffer(64 * 1024)
    entries: list[tuple[str, int, int, int]] = []
    while True:
        ok = q._K.GetFileInformationByHandleEx(handle, FILE_ID_EXTD_DIRECTORY_INFO, buffer, ctypes.sizeof(buffer))
        if not ok:
            error = ctypes.get_last_error()
            if error == ERROR_NO_MORE_FILES:
                return entries
            _harness(f"directory enumeration failed ({error})")
        raw = buffer.raw
        offset = 0
        while True:
            (next_offset,) = struct.unpack_from("<I", raw, offset + _X_NEXT)
            (attributes,) = struct.unpack_from("<I", raw, offset + _X_ATTRS)
            (name_length,) = struct.unpack_from("<I", raw, offset + _X_NAMELEN)
            (tag,) = struct.unpack_from("<I", raw, offset + _X_TAG)
            file_id = int.from_bytes(raw[offset + _X_FILEID:offset + _X_FILEID + 16], "little")
            start = offset + _X_NAME
            name = raw[start:start + name_length].decode("utf-16-le", "surrogatepass")
            entries.append((name, file_id, attributes, tag))
            if next_offset == 0:
                break
            offset += next_offset


def test_layout_matches_the_established_helper():
    """The enumeration layout used below is the production W8 layout, not a guess."""
    assert win._ENTRY_HEADER_BYTES == _X_NAME
    assert win._FileIdExtdDirectoryInfo == FILE_ID_EXTD_DIRECTORY_INFO
    assert win._FILE_ID_EXTD_DIR_INFO.FileId.offset == _X_FILEID
    assert win._FILE_ID_EXTD_DIR_INFO.FileAttributes.offset == _X_ATTRS


# ---------------------------------------------------------------------------
# Shared synthetic final-state tree (P-R1-1 / P-R1-2)
# ---------------------------------------------------------------------------


def _final_tree(base: Path) -> SimpleNamespace:
    """``R\\pi_runtime\\pi-coding-agent\\{package.json, dist\\{cli,main,config}.js}``
    plus unpinned siblings, written with ordinary I/O and then pinned."""
    root = base / "R"
    runtime = root / "pi_runtime"
    package = runtime / "pi-coding-agent"
    dist = package / "dist"
    dist.mkdir(parents=True)
    (package / "docs").mkdir()
    (package / "node_modules" / "dep").mkdir(parents=True)
    pinned = []
    for relative in FINAL_FILES:
        path = package / Path(*relative.split("/"))
        path.write_bytes(f"// final-pin payload {relative}\n".encode())
        pinned.append(path)
    (package / "docs" / "readme.md").write_bytes(b"docs\n")
    (dist / "other.js").write_bytes(b"unpinned sibling\n")
    (package / "node_modules" / "dep" / "index.js").write_bytes(b"dep\n")
    return SimpleNamespace(R=root, RT=runtime, C=package, dist=dist, pinned_files=pinned)


def _classify_held(result, before, after, pin) -> str:
    changed = after != before or (after[0] == leaves.CLASSIFICATION_REGULAR_FILE and after[1] != pin.identity())
    if result.ok or changed:
        return "succeeded_or_changed"
    if result.error in BLOCKING:
        return "blocked"
    return "other_refusal"


# ---------------------------------------------------------------------------
# P-R1-1 -- the operations of Q1 against the final read-only pins
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("op_name", sorted(ALL_OPS))
def test_p_r1_1_final_read_only_pins_refuse_delete_rename_replace_overwrite(tmp_path, op_name):
    tree = _final_tree(tmp_path)
    aux = tmp_path / "aux"
    aux.mkdir()
    operation = ALL_OPS[op_name]
    held = []
    pins = [_FinalPin(path) for path in tree.pinned_files]
    originals = [pin.read() for pin in pins]
    try:
        for pin in pins:
            before = q._snapshot(pin.path, pin.read)
            result = operation(pin.path, str(aux))
            after = q._snapshot(pin.path, pin.read)
            held.append({
                "file": os.path.relpath(pin.path, tree.C).replace(os.sep, "/"),
                "held_outcome": _classify_held(result, before, after, pin),
                "win32_error": result.error,
            })
        for pin, original in zip(pins, originals):  # the pinned bytes must be untouched after every attack
            if pin.read() != original:
                held.append({"file": "bytes", "held_outcome": "succeeded_or_changed", "win32_error": 0})
    finally:
        for pin in pins:
            pin.release()

    controls = []
    for pin in pins:
        before = q._snapshot(pin.path, q._read_released(pin.path))
        result = operation(pin.path, str(aux))
        after = q._snapshot(pin.path, q._read_released(pin.path))
        controls.append({
            "file": os.path.relpath(pin.path, tree.C).replace(os.sep, "/"),
            "released_control_ok": bool(result.ok and after != before),
            "win32_error": result.error,
        })

    outcomes = {item["held_outcome"] for item in held}
    controls_ok = all(item["released_control_ok"] for item in controls)
    if "succeeded_or_changed" in outcomes:
        status = "FAIL"
    elif outcomes != {"blocked"} or not controls_ok:
        status = "UNSUPPORTED"
    else:
        status = "PASS"
    _finish("P-R1-1", f"OP:{op_name}", status, held=held, released_controls=controls,
            held_errors=sorted({item["win32_error"] for item in held}))


# ---------------------------------------------------------------------------
# P-R1-2 -- ancestor renames while the four read-only pins are held
# ---------------------------------------------------------------------------


def _rename_with_move(path, new):
    ok = q._K.MoveFileExW(str(path), str(new), 0)
    return None if ok else ctypes.get_last_error()


def _rename_with_info(cls: int, flags: int):
    def rename(path, new):
        result = q._by_handle(
            path, DELETE, lambda h: q._K.SetFileInformationByHandle(h, cls, *q._rename_buffer(str(new), flags))
        )
        return None if result.ok else result.error

    return rename


RENAMERS = {
    "MoveFileExW": _rename_with_move,
    "FileRenameInfo": _rename_with_info(FILE_RENAME_INFO, 0),
    "FileRenameInfoEx_posix": _rename_with_info(FILE_RENAME_INFO_EX, RENAME_POSIX),
}


@pytest.mark.parametrize("renamer_name", sorted(RENAMER_NAMES))
@pytest.mark.parametrize("ancestor", ANCESTORS)
def test_p_r1_2_no_required_ancestor_can_be_renamed_while_final_pins_are_held(tmp_path, ancestor, renamer_name):
    tree = _final_tree(tmp_path)
    renamer = RENAMERS[renamer_name]
    target = {"dist": tree.dist, "C": tree.C, "RT": tree.RT, "R": tree.R}[ancestor]
    moved = Path(str(target) + "_moved")
    before_identity = leaves.inspect_no_follow(str(target)).identity
    pins = [_FinalPin(path) for path in tree.pinned_files]
    evidence: dict = {"ancestor": ancestor, "renamer": renamer_name}
    try:
        held_error = renamer(target, moved)
        evidence["held_win32_error"] = held_error
        if held_error is None:
            renamer(moved, target)  # put it back so the tree is not left displaced
            _finish("P-R1-2", f"RENAME:{renamer_name}:{ancestor}", "FAIL",
                    reason="ancestor WAS renamed while the pins were held", **evidence)
        unchanged = (
            target.is_dir() and not moved.exists()
            and leaves.inspect_no_follow(str(target)).identity == before_identity
            and all(leaves.inspect_no_follow(pin.path).identity == pin.identity() for pin in pins)
        )
        evidence["ancestor_and_pins_unchanged"] = unchanged
        # a specificity control: an UNPINNED sibling directory renames fine in the same state
        sibling = tree.C / "docs"
        sibling_moved = tree.C / "docs_moved"
        sibling_error = _rename_with_move(sibling, sibling_moved)
        evidence["unpinned_sibling_rename_error"] = sibling_error
        if sibling_error is None:
            _rename_with_move(sibling_moved, sibling)
    finally:
        for pin in pins:
            pin.release()

    control_error = renamer(target, moved)
    evidence["released_control_win32_error"] = control_error
    control_changed = control_error is None and moved.is_dir() and not target.exists()
    restored = None
    if control_changed:
        restored = renamer(moved, target) is None and target.is_dir() and not moved.exists()
        evidence["released_control_renamed_back"] = restored
    if held_error not in BLOCKING or not unchanged:
        status = "UNSUPPORTED"  # refused for a reason that is not the sharing/access check, or state drifted
        evidence["note"] = "refusal is not a sharing violation / access denied, or the tree drifted"
    elif not control_changed or not restored:
        status = "UNSUPPORTED"
        evidence["note"] = "no working released-pin control for this rename"
    else:
        status = "PASS"
    _finish("P-R1-2", f"RENAME:{renamer_name}:{ancestor}", status, **evidence)


# ---------------------------------------------------------------------------
# P-R1-3 -- genuine PI-PC1 reader / walk / L14-L21A leaves vs. the four pins
# ---------------------------------------------------------------------------


def _inventory_entries():
    return json.loads(_INVENTORY.read_text(encoding="utf-8"))["entries"]


@pytest.fixture(scope="module")
def full_copy(tmp_path_factory):
    """A FULL synthetic copy: every directory and file path of the committed
    approved inventory, with small synthetic bytes (never the third-party source),
    at ``R\\pi_runtime\\pi-coding-agent``."""
    base = tmp_path_factory.mktemp("f5a_full")
    root = base / "R"
    package = root / "pi_runtime" / "pi-coding-agent"
    package.mkdir(parents=True)
    expected = []
    longest = 0
    for entry in sorted(_inventory_entries(), key=lambda e: e["path"]):
        parts = entry["path"].split("/")
        target = package.joinpath(*parts)
        longest = max(longest, len(str(target)))
        if entry["kind"] == "dir":
            os.makedirs(target, exist_ok=True)
            expected.append(("dir", entry["path"]))
        else:
            data = f"F5A synthetic payload for {entry['path']}\n".encode()
            os.makedirs(target.parent, exist_ok=True)
            with open(target, "wb") as handle:
                handle.write(data)
            expected.append(("file", entry["path"], hashlib.sha256(data).hexdigest(), len(data)))
    expected.sort(key=lambda e: e[1])
    inventory = pi_payload.inventory_from_entries(tuple(expected))
    _FACTS["full_copy"] = {
        "directories": sum(1 for e in expected if e[0] == "dir"),
        "files": sum(1 for e in expected if e[0] == "file"),
        "longest_absolute_path_chars": longest,
    }
    yield SimpleNamespace(base=base, R=root, RT=root / "pi_runtime", C=package, dist=package / "dist",
                          expected=inventory, expected_entries=tuple(expected))
    shutil.rmtree(base, ignore_errors=True)


def _expected_bytes(path: str) -> bytes:
    return f"F5A synthetic payload for {path}\n".encode()


def _pin_all(copy) -> list[_FinalPin]:
    return [_FinalPin(copy.C / Path(*relative.split("/"))) for relative in FINAL_FILES]


def _walk(path) -> object:
    return pi_payload.observe_payload(str(path), leaves=pi_payload.genuine_payload_leaves())


def test_p_r1_3_full_copy_has_the_approved_inventory_shape(full_copy):
    facts = _FACTS["full_copy"]
    assert (facts["directories"], facts["files"]) == (1436, 15046)
    if facts["longest_absolute_path_chars"] >= 260:
        _harness("synthetic copy exceeds MAX_PATH; the genuine leaves use un-prefixed paths")


def test_p_r1_3_pi_pc1_file_readers_succeed_on_every_held_pin(full_copy):
    pins = _pin_all(full_copy)
    cap = pi_payload.MAX_PAYLOAD_FILE_BYTES
    proof = pi_identity.genuine_pi_proof_leaves()
    failures = []
    try:
        for pin, relative in zip(pins, FINAL_FILES):
            data = _expected_bytes(relative)
            digest = hashlib.sha256(data).hexdigest()
            for name, reader in (
                ("read_payload_file_digest", leaves.read_payload_file_digest),
                ("read_payload_file_bytes", leaves.read_payload_file_bytes),
                ("proof_leaves.read_digest", proof.read_digest),
            ):
                read = reader(pin.path, cap)
                good = (
                    read.classification == leaves.CLASSIFICATION_REGULAR_FILE and read.within_bound
                    and read.stable and read.sha256 == digest and read.size == len(data)
                )
                if name == "read_payload_file_bytes":
                    good = good and read.content == data
                if not good:
                    failures.append(f"{name} {relative}: classification={read.classification!r}")
            inspected = leaves.inspect_no_follow(pin.path)
            if not (inspected.classification == leaves.CLASSIFICATION_REGULAR_FILE
                    and inspected.identity == pin.identity()):
                failures.append(f"inspect_no_follow {relative}")
    finally:
        for pin in pins:
            pin.release()
    released = {
        relative: leaves.read_payload_file_digest(str(full_copy.C / Path(*relative.split("/"))), cap).sha256
        for relative in FINAL_FILES
    }
    controls_ok = all(released[r] == hashlib.sha256(_expected_bytes(r)).hexdigest() for r in FINAL_FILES)
    status = "FAIL" if failures else ("PASS" if controls_ok else "UNSUPPORTED")
    _finish("P-R1-3", "readers_on_held_pins", status, failures=failures, released_control_ok=controls_ok,
            readers=["read_payload_file_digest", "read_payload_file_bytes", "proof_leaves.read_digest",
                     "inspect_no_follow"], files=list(FINAL_FILES))


def test_p_r1_3_pi_pc1_directory_enumeration_succeeds_over_the_held_chain(full_copy):
    chain = {"C": full_copy.C, "dist": full_copy.dist, "RT": full_copy.RT, "R": full_copy.R}
    expected_children = {
        "C": {e[1].split("/")[0] for e in full_copy.expected_entries},
        "dist": {e[1].split("/")[1] for e in full_copy.expected_entries
                 if e[1].startswith("dist/") and e[1].count("/") >= 1},
        "RT": {"pi-coding-agent"},
        "R": {"pi_runtime"},
    }
    pins = _pin_all(full_copy)
    held = {}
    try:
        for label, path in chain.items():
            listing = leaves.enumerate_directory_no_follow(str(path), 100000)
            held[label] = (listing.classification, listing.complete, {name for name, _kind in (listing.entries or ())})
    finally:
        for pin in pins:
            pin.release()
    released = {}
    for label, path in chain.items():
        listing = leaves.enumerate_directory_no_follow(str(path), 100000)
        released[label] = (listing.classification, listing.complete, {name for name, _kind in (listing.entries or ())})
    failures = [label for label, (cls, complete, names) in held.items()
                if not (cls == leaves.CLASSIFICATION_DIRECTORY and complete and names == expected_children[label])]
    controls_ok = held == released
    status = "FAIL" if failures else ("PASS" if controls_ok else "UNSUPPORTED")
    _finish("P-R1-3", "directory_walk_over_chain", status, failures=failures, released_equals_held=controls_ok,
            entry_counts={label: len(names) for label, (_c, _x, names) in held.items()})


def test_p_r1_3_full_pi_pc1_walk_completes_and_equals_the_expected_inventory(full_copy):
    pins = _pin_all(full_copy)
    try:
        held = _walk(full_copy.C)
        pinned_ids = [pin.identity() for pin in pins]
    finally:
        for pin in pins:
            pin.release()
    released = _walk(full_copy.C)
    expected = full_copy.expected
    held_equal = held.complete and held.inventory.entries == expected.entries
    released_equal = released.complete and released.inventory.entries == expected.entries
    evidence = {
        "held_complete": held.complete, "held_refusal_code": held.refusal_code,
        "held_entries": 0 if not held.complete else len(held.inventory.entries),
        "held_equals_independently_computed_expected": bool(held_equal),
        "released_control_complete": released.complete,
        "released_equals_independently_computed_expected": bool(released_equal),
        "fingerprint_held_equals_released": bool(held.complete and released.complete
                                                 and held.payload_fingerprint == released.payload_fingerprint),
        "pinned_files": len(pinned_ids),
    }
    if not released_equal:
        _harness(f"released-control walk did not equal the expected inventory: {evidence}")
    status = "PASS" if held_equal and evidence["fingerprint_held_equals_released"] else "FAIL"
    _finish("P-R1-3", "payload_walk_held_equals_expected_equals_released", status, **evidence)


SENSITIVITY_RESULTS: dict[str, bool] = {}
_SAMPLE_EXPOSURES = (("zod",), ("@esbuild", "linux-x64"), ("@modelcontextprotocol", "sdk"))


def test_p_r1_3_the_l14_and_l21a_leaves_complete_while_the_pins_are_held(full_copy):
    proof = pi_identity.genuine_pi_proof_leaves()

    def run_sequence(pins):
        observation = pi_identity._observe_payload(proof, str(full_copy.C))
        exposure = pi_identity.observe_profile_exposures(str(full_copy.C), _SAMPLE_EXPOSURES, inspect=proof.inspect)
        root = proof.inspect(str(full_copy.C))
        root_identity = root.identity
        root_holds = pi_identity._identity_still_holds(
            proof, str(full_copy.C), classification=leaves.CLASSIFICATION_DIRECTORY, expected=root_identity
        )
        pin_paths = {}
        for relative in FINAL_FILES:
            inspected = proof.inspect(str(full_copy.C / Path(*relative.split("/"))))
            pin_paths[relative] = inspected.classification, inspected.identity
        return {
            "walk_complete": observation.complete,
            "walk_equals_expected": bool(observation.complete
                                         and observation.inventory.entries == full_copy.expected.entries),
            "exposures": exposure,
            "root_identity_holds": root_holds,
            "pin_path_identity_equals_pin_handle": (
                None if pins is None else
                all(pin_paths[r] == (leaves.CLASSIFICATION_REGULAR_FILE, pin.identity())
                    for r, pin in zip(FINAL_FILES, pins))
            ),
        }

    pins = _pin_all(full_copy)
    try:
        held = run_sequence(pins)
    finally:
        for pin in pins:
            pin.release()
    released = run_sequence(None)
    held_cmp = {k: v for k, v in held.items() if k != "pin_path_identity_equals_pin_handle"}
    released_cmp = {k: v for k, v in released.items() if k != "pin_path_identity_equals_pin_handle"}
    ok = (
        held["walk_complete"] and held["walk_equals_expected"] and held["exposures"] == pi_identity.EXPOSURES_ABSENT
        and held["root_identity_holds"] and held["pin_path_identity_equals_pin_handle"] is True
    )
    status = "PASS" if ok and held_cmp == released_cmp else ("FAIL" if not ok else "UNSUPPORTED")
    _finish("P-R1-3", "l14_l21a_proof_leaves", status, held=held, released_control=released,
            leaves_used=["genuine_pi_proof_leaves().enumerate_directory", "…read_digest", "…inspect",
                         "observe_payload via pi_identity._observe_payload",
                         "pi_identity.observe_profile_exposures", "pi_identity._identity_still_holds"],
            not_exercised="reprove_pi_identity_for_launch / reobserve_pi_profile_after_runtime need a profile "
                          "fingerprint a synthetic tree cannot equal; the leaves they call are what is exercised")


@pytest.mark.parametrize("label,access,share", [
    ("R0_shape_GENERIC_WRITE_share_READ", GENERIC_READ | GENERIC_WRITE, SHARE_READ),
    ("share_0", GENERIC_READ, 0),
])
def test_p_r1_3_sensitivity_an_incompatible_pin_shape_is_visibly_refused(full_copy, label, access, share):
    """CONTROL that gives the compatibility result its meaning: with a pin shape
    that IS incompatible, the same walk must refuse -- otherwise 'complete while
    pinned' could be vacuous."""
    target = full_copy.dist / "cli.js"
    handle, error = q._open(str(target), access, share, OPEN_EXISTING, FLAG_REPARSE)
    if handle is None:
        _harness(f"control pin could not be acquired ({error})")
    try:
        read = leaves.read_payload_file_digest(str(target), pi_payload.MAX_PAYLOAD_FILE_BYTES)
        observation = _walk(full_copy.C)
        refused_read = read.classification != leaves.CLASSIFICATION_REGULAR_FILE
        refused_walk = not observation.complete
        evidence = {"shape": label, "reader_classification": read.classification,
                    "walk_complete": observation.complete, "walk_refusal_code": observation.refusal_code}
    finally:
        q._close(handle)
    discriminates = refused_read and refused_walk
    _SUPPLEMENTAL[f"sensitivity:{label}"] = {"case": f"sensitivity:{label}",
                                              "status": "PASS" if discriminates else "UNSUPPORTED", "evidence": evidence}
    SENSITIVITY_RESULTS[label] = discriminates
    assert discriminates, f"HARNESS[incompatible shape {label} was not refused: {evidence}]"



def test_p_r1_3_sensitivity_rollup():
    expected = {"R0_shape_GENERIC_WRITE_share_READ", "share_0"}
    if set(SENSITIVITY_RESULTS) != expected or not all(SENSITIVITY_RESULTS.values()):
        _finish("P-R1-3", "sensitivity_control_incompatible_shape", "UNSUPPORTED",
                observed=SENSITIVITY_RESULTS, note="no incompatible-shape control was demonstrated")
    _finish("P-R1-3", "sensitivity_control_incompatible_shape", "PASS",
            shapes_refused=sorted(SENSITIVITY_RESULTS))


# ---------------------------------------------------------------------------
# P-R1-4 -- the Sec. 7.4A construction shape
# ---------------------------------------------------------------------------


def _create_dir_and_pin(path, share: int = SHARE_READ) -> _DirPin:
    if not _W.CreateDirectoryW(str(path), None):
        raise _Refused(f"CreateDirectoryW refused (Win32 {ctypes.get_last_error()})")
    return _DirPin(path, share)


def _create_exclusive_zero_byte(path) -> "q._FilePin":
    """``CreateFileW(GENERIC_READ|GENERIC_WRITE|DELETE, share 0, CREATE_NEW,
    FILE_FLAG_OPEN_REPARSE_POINT)`` -- exactly the Sec. 7.4A.2 step 1 shape,
    through the established ``_FilePin`` creator."""
    pin = q._FilePin(path, 0, GENERIC_READ | GENERIC_WRITE | DELETE)
    _LIVE.add(pin)
    original_release = pin.release

    def release():
        original_release()
        _LIVE.discard(pin)

    pin.release = release
    return pin


def _gate(directory_pin: _DirPin, files: dict, dirs: dict, *, exact: bool, parent_identity=None) -> dict:
    """The parentage gate (Sec. 7.4A.2 step 3): ONE enumeration of the pinned
    parent, read from the handle; the entry set must equal exactly
    ``{'.', '..', every file, every dir}`` and each entry's file id must equal the
    identity of ITS OWN handle."""
    entries = _enumerate_once(directory_pin.handle)
    seen: dict[str, tuple[int, int, int]] = {}
    for name, file_id, attributes, tag in entries:
        if name in seen:
            raise _Refused("duplicate name in one enumeration")
        seen[name] = (file_id, attributes, tag)
    expected: dict[str, tuple[int, bool]] = {".": (directory_pin.identity[1], True)}
    if parent_identity is not None:
        expected[".."] = (parent_identity[1], True)
    for name, pin in files.items():
        serial, file_id = pin.identity()
        if serial != directory_pin.identity[0]:
            raise _Refused("child volume serial differs from the parent's")
        expected[name] = (file_id, False)
    for name, pin in dirs.items():
        if pin.identity[0] != directory_pin.identity[0]:
            raise _Refused("child volume serial differs from the parent's")
        expected[name] = (pin.identity[1], True)
    # ".." is checked when the parent's identity is known; the run root R has no pinned parent
    extra = set(seen) - set(expected) - ({".."} if parent_identity is None else set())
    missing = set(expected) - set(seen)
    # exact set for every directory but the run root, whose gate is membership (R -> RT)
    if missing or (exact and extra):
        raise _Refused(f"entry set differs: missing={sorted(missing)[:3]} foreign={sorted(extra)[:3]}")
    for name, (file_id, is_directory) in expected.items():
        got_id, attributes, tag = seen[name]
        if got_id != file_id:
            raise _Refused(f"file id of {name!r} differs from its own handle's")
        if bool(attributes & ATTR_DIRECTORY) != is_directory:
            raise _Refused(f"kind of {name!r} differs")
        if name not in (".", "..") and (attributes & ATTR_REPARSE or tag != 0):
            raise _Refused(f"{name!r} is a reparse point")
    return {"entries": len(entries), "names_checked": len(expected)}


class _Constructor:
    """A faithful TEST-LOCAL model of Sec. 7.4A.2 -- the thing being measured.

    It exists only to exercise the Win32 construction shape. It is not importable
    by anything, it models no lifecycle, no ledger states, no cleanup and no
    provenance, and it must not grow into an implementation.
    """

    def __init__(self, hook=None):
        self.hook = hook
        self.live_dirs: list[_DirPin] = []
        self.live_files: list = []
        self.peak = 0
        self.gates = 0
        self.max_entries_in_one_gate = 0
        self.levels: list[dict] = []
        self.written: dict[str, bytes] = {}
        self.files_with_content_at_gate = 0
        self.files_seen_at_gate = 0
        self.hook_results = None

    def _peak(self):
        self.peak = max(self.peak, len(self.live_dirs) + len(self.live_files))

    def _pin_dir(self, path, share=SHARE_READ):
        pin = _create_dir_and_pin(path, share)
        self.live_dirs.append(pin)
        self._peak()
        return pin

    def _release_dir(self, pin):
        pin.release()
        self.live_dirs.remove(pin)

    def build(self, path: str, pin: _DirPin, spec: dict, *, exact=True, parent_identity=None):
        files = {}
        for name in spec["files"]:
            created = _create_exclusive_zero_byte(os.path.join(path, name))
            self.live_files.append(created)
            files[name] = created
            self._peak()
        dirs = {}
        for name in spec["dirs"]:
            dirs[name] = self._pin_dir(os.path.join(path, name))
        report = _gate(pin, files, dirs, exact=exact, parent_identity=parent_identity)
        self.files_seen_at_gate += len(files)
        self.files_with_content_at_gate += sum(1 for handle in files.values() if os.fstat(handle._fd).st_size != 0)
        self.gates += 1
        self.max_entries_in_one_gate = max(self.max_entries_in_one_gate, report["entries"])
        level = {"path": path, "pin": pin, "dirs": dirs, "done": set(), "building": None}
        self.levels.append(level)
        try:
            if spec.get("hook") and self.hook is not None:
                self.hook_results = self.hook(self, files)
            for name, data in spec["files"].items():  # step 4: content, only after the gate
                handle = files[name]
                handle.write(data)
                os.fsync(handle._fd)
                if handle.read() != data:
                    raise _Refused("read-back through the creating handle differs")
                self.written[os.path.join(path, name)] = data
                handle.release()
                self.live_files.remove(handle)
            for name, child_spec in spec["dirs"].items():  # step 5: recurse, then release
                level["building"] = name
                self.build(os.path.join(path, name), dirs[name], child_spec, parent_identity=pin.identity)
                level["done"].add(name)
                level["building"] = None
                self._release_dir(dirs[name])
        finally:
            self.levels.remove(level)
            # unwinding: close children before the directories that contain them
            for handle in files.values():
                if handle in self.live_files:
                    handle.release()
                    self.live_files.remove(handle)
            for name, child_pin in dirs.items():
                if child_pin in self.live_dirs:
                    self._release_dir(child_pin)

    def release_everything(self):
        for handle in list(self.live_files):
            handle.release()
        self.live_files.clear()
        for pin in reversed(list(self.live_dirs)):
            pin.release()
        self.live_dirs.clear()


def _spec_files(prefix: str, count: int) -> dict:
    return {f"{prefix}{i:03d}.js": f"// synthetic {prefix}{i:03d}\n".encode() for i in range(count)}


def _empty_dirs(extra: int = 0) -> dict:
    spec = {f"del{i}": {"files": {}, "dirs": {}} for i in range(len(DELETE_OPS))}
    spec["cv"] = {"files": {}, "dirs": {}}
    for i in range(extra):
        spec[f"fan{i:03d}"] = {"files": {}, "dirs": {}}
    return spec


def _level(child_name: str, child_spec: dict, files: dict) -> dict:
    """A directory holding ``files``, the chain child FIRST (so it is built first
    and every sibling stays pending and pinned while the chain descends), then the
    empty probe directories."""
    dirs = {child_name: child_spec}
    dirs.update(_empty_dirs())
    return {"files": files, "dirs": dirs}


def _chain_spec(depth: int, fan_files: int, fan_dirs: int) -> dict:
    """The spec of ``dist``: ``dist -> n1 -> ... -> n<depth>``. Every level has 2
    files and the five empty probe directories; ``n<depth>`` carries the maximum
    fan-out (``fan_files`` exclusive files and ``fan_dirs`` child directories)."""
    deepest = {"files": _spec_files("f", fan_files),
               "dirs": _empty_dirs(extra=fan_dirs - (len(DELETE_OPS) + 1)), "hook": True}
    current = deepest  # the spec of n<depth>
    for level in range(depth - 1, 0, -1):
        current = _level(f"n{level + 1}", current, _spec_files("g", 2))  # the spec of n<level>
    return _level("n1", current, _spec_files("g", 2))  # the spec of dist


def _run_root_spec(depth: int, fan_files: int, fan_dirs: int) -> dict:
    """The spec of ``R``: ``R -> pi_runtime (RT) -> pi-coding-agent (C) -> dist -> ...``."""
    c_spec = _level("dist", _chain_spec(depth, fan_files, fan_dirs), {"package.json": b'{"name":"synthetic"}\n'})
    rt_spec = _level("pi-coding-agent", c_spec, {})
    return _level("pi_runtime", rt_spec, {})


def _inventory_maxima():
    counts = collections.defaultdict(lambda: [0, 0])
    deepest = 0
    for entry in _inventory_entries():
        parent = entry["path"].rpartition("/")[0]
        counts[parent][0 if entry["kind"] == "file" else 1] += 1
        deepest = max(deepest, entry["path"].count("/") + 1)
    return {
        "max_file_children": max(v[0] for v in counts.values()),
        "max_dir_children": max(v[1] for v in counts.values()),
        "max_entries_in_one_directory": max(sum(v) for v in counts.values()),
        "max_depth_below_C": deepest,
    }


def _recomputed_peak_handles() -> dict:
    """Pure computation over the committed inventory (no Win32): the most handles
    the Sec. 7.4A.2 procedure holds at once -- at a directory's gate, every
    ancestor pin (R, RT, C and the directories below), every still-pending sibling
    pin of every ancestor, this directory's exclusive file handles and its child
    directory pins. Files are closed before recursion (step 4 precedes step 5)."""
    files, dirs = collections.defaultdict(int), collections.defaultdict(list)
    for entry in _inventory_entries():
        parent, _, name = entry["path"].rpartition("/")
        if entry["kind"] == "file":
            files[parent] += 1
        else:
            dirs[parent].append(name)
    best = {"peak": 0, "at": None}

    def visit(path: str, ancestor_pins: int, pending_above: int):
        held = ancestor_pins + pending_above + files[path] + len(dirs[path])
        if held > best["peak"]:
            best.update(peak=held, at=path)
        children = sorted(dirs[path])
        for index, name in enumerate(children):
            visit(f"{path}/{name}" if path else name, ancestor_pins + 1,
                  pending_above + (len(children) - 1 - index))

    visit("", 3, 0)  # R, RT and C are pinned before the first inventory directory is gated
    return best


def test_p_r1_4_fanout_bounds_are_recomputed_from_the_committed_inventory():
    maxima = _inventory_maxima()
    _FACTS["inventory_maxima"] = maxima
    peak = _recomputed_peak_handles()
    _FACTS["recomputed_peak_handles_real_tree"] = {
        "peak": peak["peak"], "at_directory": peak["at"], "frozen_bound_sec_7_4A_6": 462,
        "within_frozen_bound": peak["peak"] <= 462,
    }
    assert maxima == {"max_file_children": 360, "max_dir_children": 80,
                      "max_entries_in_one_directory": 362, "max_depth_below_C": 11}, maxima
    assert peak["peak"] <= 462, peak


# -- (i) --------------------------------------------------------------------


def test_p_r1_4_i_child_directory_is_created_and_pinned_inside_a_pinned_parent(tmp_path):
    evidence = {}
    for label, release_parent_first in (("pinned_parent", False), ("released_parent_control", True)):
        parent = tmp_path / f"parent_{label}"
        parent.mkdir()
        parent_pin = _DirPin(parent, SHARE_READ)
        try:
            if release_parent_first:
                parent_pin.release()
            child = _create_dir_and_pin(parent / "child")  # CreateDirectoryW then the same pin shape
            try:
                attributes, tag = q._tag_info(child.handle)
                evidence[label] = {"created_and_pinned": True, "directory": bool(attributes & ATTR_DIRECTORY),
                                   "reparse_attribute": bool(attributes & ATTR_REPARSE), "reparse_tag": tag}
                grandchild = _create_dir_and_pin(parent / "child" / "grandchild")  # nested: pin inside a child pin
                evidence[label]["nested_grandchild_pinned"] = True
                grandchild.release()
                if not release_parent_first:
                    names = {n for n, _f, _a, _t in _enumerate_once(parent_pin.handle)}
                    evidence[label]["parent_enumeration_lists_child"] = "child" in names
            finally:
                child.release()
        except _Refused as exc:
            evidence[label] = {"created_and_pinned": False, "refused": str(exc)}
        finally:
            parent_pin.release()
    held = evidence["pinned_parent"]
    ok = (held.get("created_and_pinned") and held.get("directory") and not held.get("reparse_attribute")
          and held.get("reparse_tag") == 0 and held.get("nested_grandchild_pinned")
          and held.get("parent_enumeration_lists_child"))
    control_ok = evidence["released_parent_control"].get("created_and_pinned") is True
    status = "PASS" if ok and control_ok else ("FAIL" if not ok else "UNSUPPORTED")
    _finish("P-R1-4", "i_child_directory_create_and_pin", status, **evidence)


# -- (ii) exclusive share-0 zero-byte children ----------------------------------


def test_p_r1_4_ii_exclusive_zero_byte_child_refuses_every_other_actor(tmp_path):
    parent = tmp_path / "parent"
    parent.mkdir()
    parent_pin = _DirPin(parent, SHARE_READ)
    target = parent / "child.js"
    evidence: dict = {}
    child = _create_exclusive_zero_byte(target)
    try:
        evidence["end_of_file_after_create"] = os.fstat(child._fd).st_size
        occupied, held_create_error = q._open(target, GENERIC_WRITE, SHARE_ALL, CREATE_NEW, FLAG_REPARSE)
        evidence["create_new_on_occupied_name_error"] = held_create_error
        q._close(occupied)
        read_handle, held_read_error = q._open(target, GENERIC_READ, SHARE_ALL, OPEN_EXISTING, FLAG_REPARSE)
        q._close(read_handle)
        evidence["other_read_open_error"] = held_read_error
        write_handle, held_write_error = q._open(target, GENERIC_WRITE, SHARE_ALL, OPEN_EXISTING, FLAG_REPARSE)
        q._close(write_handle)
        evidence["other_write_open_error"] = held_write_error
        delete_error = q.OPS["DeleteFileW"](str(target), str(tmp_path)).error
        evidence["delete_error"] = delete_error
        attribute_only, attribute_error = q._open(target, q.FILE_READ_ATTRIBUTES, SHARE_ALL, OPEN_EXISTING, FLAG_REPARSE)
        q._close(attribute_only)
        evidence["attribute_only_open_admitted"] = attribute_only is not None
    finally:
        child.release()
        parent_pin.release()
    after_read, after_error = q._open(target, GENERIC_READ, SHARE_ALL, OPEN_EXISTING, FLAG_REPARSE)
    q._close(after_read)
    evidence["released_control_read_open_error"] = after_error
    deleted = q.OPS["DeleteFileW"](str(target), str(tmp_path))
    evidence["released_control_delete_ok"] = deleted.ok and not target.exists()
    refusals = [evidence["other_read_open_error"], evidence["other_write_open_error"], evidence["delete_error"]]
    held_ok = (
        evidence["create_new_on_occupied_name_error"] == ERROR_FILE_EXISTS
        and all(error in BLOCKING for error in refusals) and evidence["end_of_file_after_create"] == 0
    )
    control_ok = after_error == 0 and evidence["released_control_delete_ok"]
    status = "PASS" if held_ok and control_ok else ("FAIL" if not held_ok else "UNSUPPORTED")
    _finish("P-R1-4", "ii_exclusive_zero_byte_children", status, **evidence)


# -- the nested + maximum-fan-out construction, with (iii) (iv) (v) ------------------


class _SpyCreateFile:
    """Records every ``CreateFileW`` this module issues through ``q._K`` while
    the construction runs, to prove content is written only through handles
    obtained by the exclusive CREATE_NEW open."""

    WRITE_BITS = GENERIC_WRITE | 0x2 | 0x4  # GENERIC_WRITE | FILE_WRITE_DATA | FILE_APPEND_DATA

    def __init__(self, original, root: str):
        self.original, self.root, self.calls = original, root, []

    def __call__(self, path, access, share, security, disposition, flags, template):
        handle = self.original(path, access, share, security, disposition, flags, template)
        if str(path).startswith(self.root):
            self.calls.append({"write_capable": bool(access & self.WRITE_BITS), "disposition": disposition,
                               "succeeded": handle not in (None, q._INVALID)})
        return handle


def _attempt_rename(renamer_name, path) -> tuple[int | None, bool]:
    path = Path(path)
    moved = Path(str(path) + "_moved")
    before = leaves.inspect_no_follow(str(path)).identity
    error = RENAMERS[renamer_name](path, moved)
    unchanged = path.is_dir() and not moved.exists() and leaves.inspect_no_follow(str(path)).identity == before
    if error is None:  # undo, so a FAIL does not corrupt later observations
        RENAMERS[renamer_name](moved, path)
    return error, unchanged


def _attempt_delete(op_name, path) -> tuple[int | None, bool]:
    before = leaves.inspect_no_follow(str(path)).identity
    if op_name == "RemoveDirectoryW":
        ok = _W.RemoveDirectoryW(str(path))
        error = None if ok else ctypes.get_last_error()
    else:
        result = q.OPS[op_name](str(path), str(path))
        error = None if result.ok else result.error
    unchanged = Path(path).is_dir() and leaves.inspect_no_follow(str(path)).identity == before
    return error, unchanged


def _attempt_convert(path, outside) -> tuple[str, int, bool]:
    outcome, error = probe.attempt_in_place_reparse_conversion(path, outside)
    classification = leaves.inspect_no_follow(str(path)).classification
    return outcome, error, classification != leaves.CLASSIFICATION_REPARSE_POINT


def _make_hook(outside: Path):
    """Held-phase attacks at the DEEPEST point of construction: every ancestor
    pin, every pending sibling pin and the 360 exclusive file handles are all
    still held."""

    def hook(constructor: _Constructor, files: dict):
        stack = [(f"level{index}", level["path"], level["pin"]) for index, level in enumerate(constructor.levels)]
        pending = []
        for level in constructor.levels:
            for name, pin in level["dirs"].items():
                if name not in level["done"] and name != level["building"]:
                    pending.append((name, os.path.join(level["path"], name), pin))
        deepest = constructor.levels[-1]
        results = {
            "stack_depth": len(stack),
            "pending_sibling_pins": len(pending),
            "file_handles_held": len(constructor.live_files),
            "directory_pins_held": len(constructor.live_dirs),
            "handles_held_at_hook": len(constructor.live_files) + len(constructor.live_dirs),
            "rename": [], "delete": [], "convert": [], "exclusive": [],
        }
        # (iv) rename: every stack directory and one pending empty directory per level
        rename_targets = [(label, path) for label, path, _pin in stack]
        rename_targets += [(f"pending:{os.path.basename(os.path.dirname(p))}/{n}", p)
                           for n, p, _pin in pending if n == "del0"]
        for label, path in rename_targets:
            for renamer in RENAMER_NAMES:
                error, unchanged = _attempt_rename(renamer, path)
                results["rename"].append({"target": label, "path": path, "renamer": renamer, "error": error,
                                          "unchanged": unchanged})
        # (iv) delete / convert: pending empty directories (op i -> del<i>), stack directories (non-empty)
        for name, path, _pin in pending:
            if name.startswith("del") and name[3:].isdigit():
                op = DELETE_OPS[int(name[3:])]
                error, unchanged = _attempt_delete(op, path)
                results["delete"].append({"target": path, "op": op, "error": error, "unchanged": unchanged,
                                          "empty": True})
            elif name == "cv":
                outcome, error, unchanged = _attempt_convert(path, outside)
                results["convert"].append({"target": path, "outcome": outcome, "error": error,
                                           "unchanged": unchanged, "empty": True})
        for label, path, _pin in stack:
            for op in DELETE_OPS:
                error, unchanged = _attempt_delete(op, path)
                results["delete"].append({"target": path, "op": op, "error": error, "unchanged": unchanged,
                                          "empty": False, "label": label})
            outcome, error, unchanged = _attempt_convert(path, outside)
            results["convert"].append({"target": path, "outcome": outcome, "error": error, "unchanged": unchanged,
                                       "empty": False, "label": label})
        # (ii) exclusivity of the held zero-byte children, sampled across the 360
        for name in sorted(files)[:5] + sorted(files)[-5:]:
            path = os.path.join(deepest["path"], name)
            read_handle, read_error = q._open(path, GENERIC_READ, SHARE_ALL, OPEN_EXISTING, FLAG_REPARSE)
            q._close(read_handle)
            occupied, create_error = q._open(path, GENERIC_WRITE, SHARE_ALL, CREATE_NEW, FLAG_REPARSE)
            q._close(occupied)
            results["exclusive"].append({"name": name, "other_open_error": read_error, "create_new_error": create_error})
        return results

    return hook


@pytest.fixture(scope="module")
def constructed(tmp_path_factory):
    """ONE nested construction at maximum fan-out, with the (iv) attacks run at
    its deepest point, then (after every handle is released) the matched controls."""
    base = tmp_path_factory.mktemp("f5a_construct")
    root = base / "R"
    root.mkdir()
    outside = base / "outside"
    outside.mkdir()
    maxima = _inventory_maxima()
    # dist is depth 1 below C; n1..n9 are depths 2..10; the fan-out directory n9 therefore
    # holds files at depth 11 -- the committed inventory's maximum depth below C.
    spec = _run_root_spec(maxima["max_depth_below_C"] - 2, maxima["max_file_children"], maxima["max_dir_children"])
    constructor = _Constructor(hook=_make_hook(outside))
    spy = _SpyCreateFile(q._K.CreateFileW, str(root))
    real_open, real_os_open = builtins.open, os.open

    def guarded_open(file, *args, **kwargs):
        if isinstance(file, (str, os.PathLike)) and str(file).startswith(str(root)):
            raise AssertionError("HARNESS[a pathname open of a constructed file during construction]")
        return real_open(file, *args, **kwargs)

    def guarded_os_open(path, *args, **kwargs):
        if isinstance(path, (str, os.PathLike)) and str(path).startswith(str(root)):
            raise AssertionError("HARNESS[a pathname os.open of a constructed file during construction]")
        return real_os_open(path, *args, **kwargs)

    root_pin = _DirPin(root, SHARE_READ | SHARE_WRITE)  # Sec. 7.4A.1: omit only FILE_SHARE_DELETE
    error = None
    q._K.CreateFileW = spy
    builtins.open, os.open = guarded_open, guarded_os_open
    try:
        constructor.live_dirs.append(root_pin)
        constructor.build(str(root), root_pin, spec, exact=False)
    except Exception as exc:  # noqa: BLE001 - recorded, then surfaced by every consuming test
        error = exc
    finally:
        builtins.open, os.open = real_open, real_os_open
        q._K.CreateFileW = spy.original
        constructor.release_everything()
        root_pin.release()
    yield SimpleNamespace(base=base, root=root, outside=outside, constructor=constructor, spy=spy, error=error,
                          spec=spec, hook=constructor.hook_results, maxima=maxima)
    shutil.rmtree(base, ignore_errors=True)


def _require_constructed(constructed):
    if constructed.error is not None:
        raise AssertionError(f"PREMISE_FAIL[P-R1-4:construction]: construction refused: "
                             f"{type(constructed.error).__name__}: {constructed.error}")
    assert constructed.hook is not None, "HARNESS[the deepest-point hook never ran]"


def test_p_r1_4_ii_iii_maximum_fanout_is_held_together_and_every_gate_passes(constructed):
    _require_constructed(constructed)
    spec = constructed.spec
    c = constructed.constructor
    hook = constructed.hook
    files_at_deepest = constructed.maxima["max_file_children"]
    dirs_at_deepest = constructed.maxima["max_dir_children"]
    expected_gates = 0

    def count(node):
        nonlocal expected_gates
        expected_gates += 1
        for child in node["dirs"].values():
            count(child)

    count(spec)
    evidence = {
        "gates_passed": c.gates, "directories_constructed": expected_gates,
        "largest_single_enumeration_entries": c.max_entries_in_one_gate,
        "file_handles_held_with_directory_pins_at_deepest": hook["file_handles_held"],
        "directory_pins_held_at_deepest": hook["directory_pins_held"],
        "total_handles_held_at_deepest": hook["handles_held_at_hook"],
        "peak_handles_during_construction": c.peak,
        "stack_depth_at_deepest": hook["stack_depth"], "pending_sibling_pins_at_deepest": hook["pending_sibling_pins"],
        "frozen_bound_for_the_real_tree_Sec_7_4A_6": 462,
        "host_held_at_least_the_frozen_bound_simultaneously": hook["handles_held_at_hook"] >= 462,
        "note": "this synthetic maximum-fan-out chain is not the real tree; the real tree's own peak is recomputed "
                "in facts.recomputed_peak_handles_real_tree. What is measured here is that the host holds this many "
                "exclusive file handles and directory pins at once, gating each directory by handle enumeration",
    }
    ok = (
        c.gates == expected_gates
        and hook["file_handles_held"] >= files_at_deepest
        and c.max_entries_in_one_gate >= files_at_deepest + dirs_at_deepest + 2
    )
    _finish("P-R1-4", "ii_iii_fanout_gate_and_peak", "PASS" if ok else "FAIL", **evidence)


def test_p_r1_4_iv_rename_of_every_pinned_directory_is_refused_with_matched_controls(constructed):
    _require_constructed(constructed)
    hook = constructed.hook
    held = hook["rename"]
    failures = [r for r in held if r["error"] is None or not r["unchanged"]]
    non_blocking = [r for r in held if r["error"] is not None and r["error"] not in BLOCKING]
    # matched released controls: every handle is released now; the same rename must work and be undone
    controls = []
    for entry in held:
        path = entry["path"]
        moved = Path(path + "_moved")
        error = RENAMERS[entry["renamer"]](Path(path), moved)
        worked = error is None and moved.is_dir() and not Path(path).exists()
        back = worked and RENAMERS[entry["renamer"]](moved, Path(path)) is None and Path(path).is_dir()
        controls.append({"target": entry["target"], "renamer": entry["renamer"], "control_ok": bool(worked and back),
                         "error": error})
    controls_ok = all(c["control_ok"] for c in controls)
    evidence = {
        "attempts": len(held), "targets": len({r["target"] for r in held}),
        "held_errors": sorted({r["error"] for r in held if r["error"] is not None}),
        "failures": failures[:5], "non_blocking_refusals": non_blocking[:5],
        "controls_ok": controls_ok, "controls_total": len(controls),
        "control_failures": [c for c in controls if not c["control_ok"]][:5],
    }
    if failures:
        status = "FAIL"
    elif non_blocking or not controls_ok:
        status = "UNSUPPORTED"
    else:
        status = "PASS"
    _finish("P-R1-4", "iv_rename", status, **evidence)


def test_p_r1_4_iv_delete_of_pinned_directories_is_refused_with_matched_controls(constructed):
    _require_constructed(constructed)
    hook = constructed.hook
    empties = [r for r in hook["delete"] if r["empty"]]
    non_empty = [r for r in hook["delete"] if not r["empty"]]
    failures = [r for r in hook["delete"] if r["error"] is None or not r["unchanged"]]
    empty_not_blocked = [r for r in empties if r["error"] not in BLOCKING]
    controls = []
    for entry in empties:
        path = entry["target"]
        error, _unchanged = _attempt_delete(entry["op"], path)
        controls.append({"op": entry["op"], "removed": error is None and not Path(path).exists(), "error": error})
    non_empty_mechanisms = collections.Counter(
        "sharing_or_access" if r["error"] in BLOCKING else ("directory_not_empty" if r["error"] == ERROR_DIRECTORY_NOT_EMPTY
                                                           else f"other:{r['error']}")
        for r in non_empty
    )
    controls_ok = bool(controls) and all(c["removed"] for c in controls)
    evidence = {
        "empty_pinned_directories_attacked": len(empties), "non_empty_pinned_directories_attacked": len(non_empty),
        "empty_held_errors": sorted({r["error"] for r in empties}),
        "non_empty_refusal_mechanisms": dict(non_empty_mechanisms),
        "failures": failures[:5], "empty_not_blocked_by_share_or_access": empty_not_blocked[:5],
        "controls_ok": controls_ok, "controls_total": len(controls),
        "ops": list(DELETE_OPS),
    }
    if failures:
        status = "FAIL"
    elif empty_not_blocked or not controls_ok:
        status = "UNSUPPORTED"
    else:
        status = "PASS"
    _finish("P-R1-4", "iv_delete", status, **evidence)


def test_p_r1_4_iv_in_place_junction_conversion_of_pinned_directories_is_refused(constructed):
    _require_constructed(constructed)
    hook = constructed.hook
    empties = [r for r in hook["convert"] if r["empty"]]
    non_empty = [r for r in hook["convert"] if not r["empty"]]
    failures = [r for r in hook["convert"] if r["outcome"] == "converted" or not r["unchanged"]]
    empty_not_pin_refused = [r for r in empties if (r["outcome"], r["error"]) != ("open_refused", ERROR_SHARING_VIOLATION)]
    # positive control: the same conversion DOES work on the same (now released) empty directories
    controls = []
    for entry in empties:
        outcome, error, _unchanged = _attempt_convert(entry["target"], constructed.outside)
        converted = outcome == "converted"
        controls.append({"outcome": outcome, "error": error})
        if converted:
            os.rmdir(entry["target"])  # removes the junction itself, never its target
    controls_ok = bool(controls) and all(c["outcome"] == "converted" for c in controls)
    mechanisms = collections.Counter(f"{r['outcome']}:{r['error']}" for r in non_empty)
    evidence = {
        "empty_pinned_directories_attacked": len(empties), "non_empty_pinned_directories_attacked": len(non_empty),
        "empty_outcomes": sorted({f"{r['outcome']}:{r['error']}" for r in empties}),
        "non_empty_outcomes": dict(mechanisms),
        "failures": failures[:5], "empty_not_refused_at_the_pin": empty_not_pin_refused[:5],
        "controls_ok": controls_ok, "controls_total": len(controls),
        "outside_directory_untouched": sorted(os.listdir(constructed.outside)) == [],
    }
    if failures:
        status = "FAIL"
    elif empty_not_pin_refused or not controls_ok:
        status = "UNSUPPORTED"
    else:
        status = "PASS"
    _finish("P-R1-4", "iv_convert", status, **evidence)


def test_p_r1_4_v_content_is_written_only_through_the_proven_child_handles(constructed):
    _require_constructed(constructed)
    c, spy = constructed.constructor, constructed.spy
    write_calls = [call for call in spy.calls if call["write_capable"]]
    successful_writes = [call for call in write_calls if call["succeeded"]]
    only_create_new = all(call["disposition"] == CREATE_NEW for call in successful_writes)
    mismatches = []
    for path, data in c.written.items():
        if Path(path).read_bytes() != data:
            mismatches.append(os.path.basename(path))
    hook = constructed.hook
    exclusive_ok = all(
        item["other_open_error"] in BLOCKING and item["create_new_error"] == ERROR_FILE_EXISTS
        for item in hook["exclusive"]
    )
    evidence = {
        "files_written": len(c.written), "successful_write_capable_opens": len(successful_writes),
        "every_write_capable_open_was_CREATE_NEW": only_create_new,
        "write_capable_opens_equal_files": len(successful_writes) == len(c.written),
        "pathname_open_guard": "builtins.open and os.open raised on any constructed path during construction",
        "files_seen_at_their_gate": c.files_seen_at_gate,
        "files_holding_any_content_when_their_gate_ran": c.files_with_content_at_gate,
        "byte_mismatches_after_release": mismatches[:5],
        "exclusive_sample_ok_at_fanout": exclusive_ok, "exclusive_samples": len(hook["exclusive"]),
    }
    ok = (only_create_new and len(successful_writes) == len(c.written) and not mismatches and exclusive_ok
          and len(c.written) > 0 and c.files_with_content_at_gate == 0
          and c.files_seen_at_gate == len(c.written))
    _finish("P-R1-4", "v_content_through_child_handles", "PASS" if ok else "FAIL", **evidence)


# -- (iii) single pass + the gate's teeth ----------------------------------------------


def test_p_r1_4_iii_the_enumeration_cursor_is_per_handle_and_single_pass(tmp_path):
    parent = tmp_path / "parent"
    parent.mkdir()
    pin = _DirPin(parent, SHARE_READ)
    names = []
    children = []
    try:
        for i in range(12):
            child = _create_exclusive_zero_byte(parent / f"c{i}.js")
            children.append(child)
            names.append(f"c{i}.js")
        by_id = {name: child.identity()[1] for name, child in zip(names, children)}
        first = _enumerate_once(pin.handle)
        second = _enumerate_once(pin.handle)  # the SAME handle: the cursor is exhausted
        fresh = _DirPin(parent, SHARE_READ)
        try:
            third = _enumerate_once(fresh.handle)  # a FRESH handle: the full listing again
        finally:
            fresh.release()
    finally:
        for child in children:
            child.release()
        pin.release()
    first_ids = {n: fid for n, fid, _a, _t in first if n in by_id}
    evidence = {
        "first_pass_entries": len(first), "second_pass_same_handle_entries": len(second),
        "fresh_handle_entries": len(third), "first_pass_names_equal_created": set(names) == set(first_ids),
        "every_file_id_equals_its_own_handle": all(first_ids.get(n) == fid for n, fid in by_id.items()),
        "dot_entry_file_id_equals_parent_pin": any(n == "." and fid == pin.identity[1] for n, fid, _a, _t in first),
    }
    ok = (evidence["first_pass_names_equal_created"] and evidence["every_file_id_equals_its_own_handle"]
          and evidence["second_pass_same_handle_entries"] == 0 and evidence["fresh_handle_entries"] == len(first)
          and evidence["dot_entry_file_id_equals_parent_pin"])
    _finish("P-R1-4", "iii_single_pass_cursor", "PASS" if ok else "FAIL", **evidence)


def test_p_r1_4_iii_the_gate_refuses_a_foreign_name_a_wrong_id_and_a_missing_child(tmp_path):
    results = {}
    grand = _DirPin(tmp_path, SHARE_ALL)  # the parent's own parent, so ".." is checked too

    def fresh(label):
        parent = tmp_path / label
        parent.mkdir()
        return parent, _DirPin(parent, SHARE_READ), _create_exclusive_zero_byte(parent / "mine.js")

    def gate(pin, files):
        return _gate(pin, files, {}, exact=True, parent_identity=grand.identity)

    try:
        # control: the honest state passes the same gate
        parent, pin, child = fresh("honest")
        try:
            results["honest_state_passes"] = gate(pin, {"mine.js": child})["names_checked"] == 3
        finally:
            child.release()
            pin.release()

        # a foreign name planted in the pinned parent (W11)
        parent, pin, child = fresh("foreign")
        try:
            (parent / "planted.js").write_bytes(b"foreign")
            try:
                gate(pin, {"mine.js": child})
                results["foreign_name_refused"] = False
            except _Refused:
                results["foreign_name_refused"] = True
        finally:
            child.release()
            pin.release()

        # a wrong identity: another object's file id presented for the name
        parent, pin, child = fresh("wrongid")
        other = _create_exclusive_zero_byte(parent / "other.js")
        try:
            try:
                gate(pin, {"mine.js": other, "other.js": other})
                results["wrong_file_id_refused"] = False
            except _Refused:
                results["wrong_file_id_refused"] = True
            try:
                gate(pin, {})  # children exist but are not presented: they are foreign names
                results["unpresented_children_refused"] = False
            except _Refused:
                results["unpresented_children_refused"] = True
        finally:
            other.release()
            child.release()
            pin.release()

        # a presented child that is absent from the directory
        parent, pin, child = fresh("missing")
        ghost = _create_exclusive_zero_byte(tmp_path / "elsewhere.js")
        try:
            try:
                gate(pin, {"mine.js": child, "ghost.js": ghost})
                results["missing_child_refused"] = False
            except _Refused:
                results["missing_child_refused"] = True
        finally:
            ghost.release()
            child.release()
            pin.release()
    finally:
        grand.release()
    ok = all(results.values()) and len(results) == 5
    _finish("P-R1-4", "iii_gate_negative_controls", "PASS" if ok else "FAIL", **results)


# -- supplemental characterization (does not feed any verdict) ----------------------------


def test_supplemental_run_root_pin_shape_on_an_empty_directory(tmp_path):
    """Sec. 7.4A.1 pins ``R`` with share READ|WRITE (omitting only DELETE). On an
    EMPTY directory that shape admits the conversion open. Reported, not judged:
    ``R`` is never empty when RT is created beneath it, and a non-empty directory
    refuses the conversion with ERROR_DIRECTORY_NOT_EMPTY regardless of any pin."""
    outside = tmp_path / "outside"
    outside.mkdir()
    empty = tmp_path / "empty_root"
    empty.mkdir()
    pin = _DirPin(empty, SHARE_READ | SHARE_WRITE)
    try:
        outcome, error = probe.attempt_in_place_reparse_conversion(empty, outside)
    finally:
        pin.release()
    if outcome == "converted":
        os.rmdir(empty)
    nonempty = tmp_path / "nonempty_root"
    (nonempty / "child").mkdir(parents=True)
    pin = _DirPin(nonempty, SHARE_READ | SHARE_WRITE)
    try:
        outcome_nonempty, error_nonempty = probe.attempt_in_place_reparse_conversion(nonempty, outside)
    finally:
        pin.release()
    _supplemental("run_root_pin_shape_READ_WRITE_conversion", "OBSERVATION",
                  empty_directory=[outcome, error], non_empty_directory=[outcome_nonempty, error_nonempty],
                  reading="the READ|WRITE run-root pin shape does not by itself refuse conversion of an EMPTY directory; "
                          "non-emptiness (W5) does for a non-empty one")


# ---------------------------------------------------------------------------
# Roll-up
# ---------------------------------------------------------------------------


def _volume_filesystem(path: str) -> dict:
    root = os.path.splitdrive(path)[0] + "\\"
    name = ctypes.create_unicode_buffer(64)
    flags = ctypes.c_ulong(0)
    ok = _W.GetVolumeInformationW(root, None, 0, None, None, ctypes.byref(flags), name, 64)
    return {"filesystem": name.value if ok else None, "flags": hex(flags.value) if ok else None}


def _verdict(premise: str) -> dict:
    expected = EXPECTED_CASES[premise]
    recorded = _RESULTS[premise]
    statuses = {case: recorded[case]["status"] for case in expected if case in recorded}
    missing = [case for case in expected if case not in recorded]
    if any(status == "FAIL" for status in statuses.values()):
        verdict = "FAIL"
    elif not missing and all(status == "PASS" for status in statuses.values()):
        verdict = "PASS"
    else:
        verdict = "PARTIAL"
    return {
        "verdict": verdict,
        "cases_expected": len(expected), "cases_recorded": len(recorded),
        "cases_pass": sum(1 for s in statuses.values() if s == "PASS"),
        "cases_fail": sum(1 for s in statuses.values() if s == "FAIL"),
        "cases_unsupported": sum(1 for s in statuses.values() if s == "UNSUPPORTED"),
        "cases_not_run": missing,
        "cases": [recorded[case] for case in expected if case in recorded],
    }


def test_zz_rollup_and_report(tmp_path):
    report = {
        "record_kind": "aido-f5a-pr1-windows-premise-evidence.v1",
        "environment": {
            "windows_build": ".".join(str(part) for part in sys.getwindowsversion()[:3]),
            "platform": platform.platform(),
            "python": platform.python_version(),
            **_volume_filesystem(str(tmp_path)),
        },
        "facts": _FACTS,
        "premises": {premise: _verdict(premise) for premise in EXPECTED_CASES},
        "supplemental": [_SUPPLEMENTAL[k] for k in sorted(_SUPPLEMENTAL)],
        "scope": "measured only against disposable synthetic trees on this host; no Node, Pi, npm, model or network "
                 "was used; this proves nothing about Node compatibility, which is first observable at E5",
    }
    print("\n==== F5A P-R1 verdicts ====")
    for premise, body in report["premises"].items():
        print(f"{premise}: {body['verdict']}  (pass {body['cases_pass']}, fail {body['cases_fail']}, "
              f"unsupported {body['cases_unsupported']}, not run {len(body['cases_not_run'])})")
    destination = os.environ.get("F5A_PR1_REPORT_PATH")
    if destination:
        Path(destination).write_text(json.dumps(report, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
