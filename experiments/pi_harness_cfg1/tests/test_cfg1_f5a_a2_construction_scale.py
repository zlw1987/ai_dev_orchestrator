"""F5-A A2 OFFLINE CANDIDATE -- construction-SCALE evidence (safe subset only).

What this module is. Ordinary offline regressions that drive the ACTUAL candidate
(``pi_runtime_provision``) through its public ``admit_runtime_provision`` /
``run_runtime_provision`` / ``release_at_l27_entry`` path, over an owned
disposable ``tmp_path`` source tree and a REAL minted CFG1 workspace, at the
construction geometry of the committed approved inventory:

* maximum depth 11 components below ``C``;
* up to 360 file children and up to 80 directory children in one directory;
* largest single directory 362 entries;
* the frozen construction handle bound 462 (candidate section 2 / amendment
  section 7.4A.6).

The geometry is NOT assumed. It is recomputed here, by code that does not call
the candidate, from the committed inventory file, and the synthetic source tree
is built from that inventory's exact directory structure (file CONTENT is
synthetic and tiny, save one file at the committed largest size) and
re-measured. Expected peaks are therefore never derived from the synthetic
fixture alone.

Observation sources, kept apart on purpose:

* **independent OS observation** -- the process handle count
  (``GetProcessHandleCount``), sampled after every real native create;
* **ledger observation** -- the candidate's own ``peak_open`` / ``open_count``;
* **spy observation** -- thin pass-through wrappers (they call the real
  function and change nothing) that record creation order, gate order, write
  order and close order from what the candidate actually did;
* **post-hoc filesystem observation** -- a plain walk of the destination.

What it is NOT. It creates no junction, symlink, hard link or other reparse
point, converts nothing, races nothing, and launches no runtime. Every object is
an ordinary directory or file inside an owned disposable fixture. It is not
Windows authority qualification, says nothing about the containment of a create
beneath a CONVERTED parent (A2-3, INCOMPLETE), and does not touch R-ALIAS. A
green run here is ordinary regression evidence.

The one injected seam is ``_close_raw_handle`` returning ``False`` for one
named object (the close-failure cases); it shows the candidate's own branches
refuse and keep truthful lifecycle state, not a native anomaly.
"""

from __future__ import annotations

import collections
import gc
import hashlib
import json
import os
import random
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from pe2a_support import synthetic_payload_files
from pe2b_support import Payload
from pe2c_support import install_synthetic_policy

from pi_harness_cfg1 import pi_payload
from pi_harness_cfg1 import pi_runtime_provision as rp
from pi_harness_cfg1 import run_workspace

_COMMITTED_INVENTORY = (
    Path(__file__).resolve().parent.parent
    / "pi_profile_policy"
    / "inventories"
    / "66cf8a815d91aeaf3eb920763c6a4f3b98c17625dbaa93c540fb424c451664dc.json"
)

#: The frozen numbers (amendment section 7.4A.6 / T-F5A-32). Quoted, then
#: CHECKED against the committed inventory below -- never trusted.
_FROZEN_DEPTH = 11
_FROZEN_MAX_FILES = 360
_FROZEN_MAX_DIRS = 80
_FROZEN_MAX_ENTRIES = 362
_FROZEN_HANDLE_BOUND = 462
_COMMITTED_DIRS = 1436
_COMMITTED_FILES = 15046
_COMMITTED_LARGEST_FILE = 11694592
#: The committed inventory's 362-entry directory (360 files + 2 directories).
_WIDEST = "node_modules/@earendil-works/pi-ai/dist/providers"

windows_only = pytest.mark.skipif(sys.platform != "win32", reason="Win32/NTFS semantics; a skip is not a pass")

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    _K32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _K32.GetCurrentProcess.restype = wintypes.HANDLE
    _K32.GetCurrentProcess.argtypes = []
    _K32.GetProcessHandleCount.restype = wintypes.BOOL
    _K32.GetProcessHandleCount.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    _K32.CloseHandle.restype = wintypes.BOOL
    _K32.CloseHandle.argtypes = [wintypes.HANDLE]

    def _os_handles() -> int:
        """The PROCESS's open handle count, from the OS -- not from the ledger."""
        count = wintypes.DWORD(0)
        assert _K32.GetProcessHandleCount(_K32.GetCurrentProcess(), ctypes.byref(count))
        return int(count.value)

else:  # pragma: no cover - the Windows-only tests are skipped

    def _os_handles() -> int:
        raise AssertionError("Windows only")


# ---------------------------------------------------------------------------
# Independent geometry (does NOT call pi_runtime_provision)
# ---------------------------------------------------------------------------


def _geometry(entries) -> dict:
    """Counts per directory from ``(kind, path)`` pairs; ``kind`` is ``file``/``dir``."""
    files: collections.Counter = collections.Counter()
    dirs: collections.Counter = collections.Counter()
    depth = 0
    for kind, path in entries:
        parent = path.rpartition("/")[0]
        (dirs if kind == "dir" else files)[parent] += 1
        depth = max(depth, path.count("/") + 1)
    parents = set(files) | set(dirs)
    return {
        "dirs": sum(dirs.values()),
        "files": sum(files.values()),
        "max_depth": depth,
        "max_files": max(files.values()),
        "max_dirs": max(dirs.values()),
        "max_entries": max(files[p] + dirs[p] for p in parents),
        "per_dir": {p: (files[p], dirs[p]) for p in parents},
        "dir_order": [path for kind, path in entries if kind == "dir"],
    }


def _independent_peak(entries) -> int:
    """The peak OPEN count of the documented construction order, recomputed from
    ``(kind, path)`` pairs in inventory order: ``R``, ``RT`` and ``C`` are held
    throughout; in each directory every file and every directory child is
    created and held, the gate runs, the files are completed and closed, then
    each directory child is built in turn and closed. Written from the
    amendment's accounting, not from the candidate's code."""
    geometry = _geometry(entries)
    per_dir = geometry["per_dir"]
    children: dict[str, list[str]] = collections.defaultdict(list)
    for kind, path in entries:
        if kind == "dir":
            children[path.rpartition("/")[0]].append(path)
    peak = 3

    def build(directory: str, held: int) -> None:
        nonlocal peak
        n_files, n_dirs = per_dir.get(directory, (0, 0))
        held += n_files + n_dirs
        peak = max(peak, held)
        held -= n_files
        for child in children[directory]:
            build(child, held)
            held -= 1

    build("", 3)
    return peak


def _committed_entries() -> list[tuple[str, str]]:
    record = json.loads(_COMMITTED_INVENTORY.read_text(encoding="utf-8"))
    return [(entry["kind"], entry["path"]) for entry in record["entries"]]


# ---------------------------------------------------------------------------
# Pure: the committed inventory's geometry and peak, recomputed independently
# ---------------------------------------------------------------------------


def test_committed_inventory_geometry_and_peak_are_recomputed_independently():
    """The frozen numbers are CHECKED against the committed inventory, by code
    that does not call the candidate, and the candidate's own simulation is then
    compared to that independent recomputation (not the reverse)."""
    entries = _committed_entries()
    geometry = _geometry(entries)
    assert geometry["dirs"] == _COMMITTED_DIRS
    assert geometry["files"] == _COMMITTED_FILES
    assert geometry["max_depth"] == _FROZEN_DEPTH
    assert geometry["max_files"] == _FROZEN_MAX_FILES
    assert geometry["max_dirs"] == _FROZEN_MAX_DIRS
    assert geometry["max_entries"] == _FROZEN_MAX_ENTRIES
    independent = _independent_peak(entries)
    inventory = pi_payload.inventory_from_record(
        json.loads(_COMMITTED_INVENTORY.read_text(encoding="utf-8"))
    )
    assert inventory.payload_fingerprint == _COMMITTED_INVENTORY.stem
    assert rp.construction_handle_peak(inventory) == independent == 449
    assert independent <= _FROZEN_HANDLE_BOUND
    print("SCALE_MEASUREMENT " + json.dumps({"committed_independent_peak": independent, "frozen_bound": _FROZEN_HANDLE_BOUND}))


# ---------------------------------------------------------------------------
# The committed-shape synthetic source (module scoped; built once)
# ---------------------------------------------------------------------------


def _build_committed_shape_files() -> tuple[dict[str, bytes], str]:
    """``(files, largest_path)``: every committed directory, with synthetic file
    CONTENT. Approvable: the PI-SC1 seams and the three manifests the floor
    needs keep the PE-2a synthetic bytes; any other ``package.json`` is renamed
    (one name per directory, counts unchanged) so it carries no manifest
    semantics; every other file's bytes are a unique tiny function of its path,
    except the largest committed file, which is the committed SIZE of seeded
    bytes (a multi-chunk write and read-back)."""
    base, _ = synthetic_payload_files()
    required = set(pi_payload.PI_SC1_PATHS) | {
        "package.json",
        "node_modules/@earendil-works/pi-ai/package.json",
        "node_modules/@earendil-works/pi-agent-core/package.json",
    }
    record = json.loads(_COMMITTED_INVENTORY.read_text(encoding="utf-8"))
    largest = max((entry for entry in record["entries"] if entry["kind"] == "file"), key=lambda e: e["size"])
    assert largest["size"] == _COMMITTED_LARGEST_FILE and largest["path"] not in required
    files: dict[str, bytes] = {}
    for entry in record["entries"]:
        if entry["kind"] != "file":
            continue
        path = entry["path"]
        if path in required:
            files[path] = base[path]
        elif path == largest["path"]:
            files[path] = random.Random(0xA2).randbytes(entry["size"])
        elif entry["size"] == 0:
            files[path] = b""
        elif path.rsplit("/", 1)[-1] == "package.json":
            files[path + ".geom"] = b"geom:" + path.encode("utf-8")
        else:
            files[path] = b"geom:" + path.encode("utf-8")
    return files, largest["path"]


@pytest.fixture(scope="module")
def committed_shape(tmp_path_factory):
    if sys.platform != "win32":
        pytest.skip("Win32/NTFS semantics; a skip is not a pass")
    files, largest = _build_committed_shape_files()
    top = tmp_path_factory.mktemp("scale")
    source = top / "src" / "pkg"
    for relative, data in files.items():
        target = source.joinpath(*relative.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    observation = pi_payload.observe_payload(str(source), leaves=pi_payload.genuine_payload_leaves())
    assert observation.complete
    payload = Payload(files, ())
    assert payload.fingerprint == observation.inventory.payload_fingerprint
    yield SimpleNamespace(
        files=files,
        largest=largest,
        source=source,
        payload=payload,
        inventory=observation.inventory,
        entries=[(entry[0], entry[1]) for entry in observation.inventory.entries],
    )
    shutil.rmtree(top)  # strict: a leftover is a teardown ERROR, not silence
    assert not top.exists()


@windows_only
def test_synthetic_fixture_reproduces_the_committed_geometry(committed_shape):
    """The fixture is built from the committed inventory's structure, and its
    geometry is RE-MEASURED from what was actually observed on disk -- per
    directory, not just in its maxima -- before any run relies on it."""
    committed = _geometry(_committed_entries())
    fixture = _geometry(committed_shape.entries)
    for key in ("dirs", "files", "max_depth", "max_files", "max_dirs", "max_entries", "per_dir", "dir_order"):
        assert fixture[key] == committed[key], key
    assert _independent_peak(committed_shape.entries) == _independent_peak(_committed_entries()) == 449
    assert committed_shape.largest.startswith("node_modules/")
    assert len(committed_shape.files[committed_shape.largest]) == _COMMITTED_LARGEST_FILE


# ---------------------------------------------------------------------------
# Environment: a REAL minted workspace + a genuine PE-2b approval of the payload
# ---------------------------------------------------------------------------


@pytest.fixture
def make_env(monkeypatch, git_executable):
    """Mint a real CFG1 workspace and approve ``payload`` through a genuine PE-2b
    load of a synthetic sealed policy. Teardown is STRICT: a workspace that is
    still registered is removed by the frozen remover, and any failure there is
    a test ERROR -- it is never swallowed, so a green case cannot hide a leaked
    tree."""
    if sys.platform != "win32":
        pytest.skip("Win32/NTFS semantics; a skip is not a pass")
    made = []

    def make(payload: Payload, source: Path, inventory):
        install_synthetic_policy(monkeypatch, payload)
        workspace, _built = run_workspace.mint_cfg1_run_workspace(git_executable=git_executable)
        made.append(workspace)
        return SimpleNamespace(
            workspace=workspace,
            run_root=Path(workspace.experiment_root),
            package_root=Path(workspace.experiment_root) / rp.RUNTIME_DIR_NAME / rp.PACKAGE_DIR_NAME,
            source=source,
            payload=payload,
            inventory=inventory,
        )

    yield make
    problems = []
    for workspace in made:
        if not run_workspace.workspace_is_registered(workspace):
            continue
        try:
            run_workspace.remove_cfg1_run_workspace(workspace)
        except Exception as exc:  # noqa: BLE001 - reported below, never swallowed
            problems.append(type(exc).__name__)
        finally:
            run_workspace.discard_cfg1_run_workspace(workspace)
    assert not problems, f"workspace teardown failed: {problems}"
    for workspace in made:
        assert not os.path.exists(workspace.experiment_root), "workspace tree still present after teardown"


def _admit(env):
    return rp.admit_runtime_provision(
        workspace=env.workspace,
        profile_id=env.payload.profile_id,
        approved_inventory=env.inventory,
        source_package_root=str(env.source),
    )


# ---------------------------------------------------------------------------
# The probe: pass-through spies + independent OS observation
# ---------------------------------------------------------------------------


_DIR_INFO_CLASS = 19  # FileIdExtdDirectoryInfo -- the class the candidate enumerates with


class _CountingK32:
    """Pass-through proxy over the candidate's ``kernel32`` object: every call is
    forwarded unchanged; directory-enumeration fetches are merely counted."""

    def __init__(self, real, probe):
        self._real = real
        self._probe = probe

    def __getattr__(self, name):
        return getattr(self._real, name)

    def GetFileInformationByHandleEx(self, handle, info_class, buffer, size):  # noqa: N802
        if info_class == _DIR_INFO_CLASS:
            self._probe.dir_fetches += 1
        return self._real.GetFileInformationByHandleEx(handle, info_class, buffer, size)


class _Rec:
    __slots__ = ("serial", "kind", "parent", "name", "path", "entry", "children", "attempted", "close_ok")

    def __init__(self, serial, kind, parent, name, path, entry):
        self.serial, self.kind, self.parent, self.name, self.path = serial, kind, parent, name, path
        self.entry = entry
        self.children: list[_Rec] = []
        self.attempted = False
        self.close_ok: bool | None = None


class _Probe:
    """Wraps the candidate's own functions with recorders that call the REAL
    function and return its result unchanged (``fail_close_at`` is the single
    injected seam: the named object's close reports failure and is not issued).

    Everything recorded is what the candidate actually did, in the order it did
    it. The expected values the tests compare against come from the committed
    inventory or from independent code -- never from this recorder alone."""

    def __init__(self, monkeypatch, *, fail_close_at: str | None = None, before_gate=None):
        self.fail_close_at = fail_close_at
        self.before_gate = before_gate
        self.recs: dict[int, _Rec] = {}
        self.by_raw: dict[int, _Rec] = {}
        self.live: set[_Rec] = set()
        self.open_files: collections.Counter = collections.Counter()
        self.serial = 0
        self.samples: list[tuple[int, int, int]] = []  # (os_handles, ledger_open, ledger_peak) after each create
        self.order_violations: list[str] = []
        self.foreign_open_file_violations: list[str] = []
        self.write_before_gate: list[str] = []
        self.gates: list[dict] = []
        self.gated: set[int] = set()
        self.membership_gates = 0
        self.writes: list[str] = []
        self.written_digest_mismatch: list[str] = []
        self.readbacks = 0
        self.enumerations = 0
        self.dir_fetches = 0
        self.last_enumeration: tuple[int, int] = (0, 0)  # (kernel fetches, entries returned)
        self.unknown_closes = 0
        self.close_attempts = 0
        self.leaked_raw: int | None = None
        self.fail_attempts = 0
        self.root: _Rec | None = None
        self._real = {
            name: getattr(rp, name)
            for name in (
                "_native_relative_create",
                "_create_child",
                "_pin_run_root",
                "_close_raw_handle",
                "_gate_exact_set",
                "_gate_membership",
                "_write_verified_content",
                "_raw_read_from_start",
                "_raw_enumerate_once",
            )
        }
        for name in self._real:
            monkeypatch.setattr(rp, name, getattr(self, "_spy" + name))
        monkeypatch.setattr(rp, "_K32", _CountingK32(rp._K32, self))

    # -- creation ----------------------------------------------------------

    def _spy_pin_run_root(self, handles, run_root, expected):
        entry = self._real["_pin_run_root"](handles, run_root, expected)
        rec = _Rec(0, "directory", None, "<R>", "<R>", entry)
        self.root = rec
        self.recs[id(entry)] = rec
        self.by_raw[entry.raw] = rec
        self.live.add(rec)
        return entry

    def _spy_native_relative_create(self, handles, native, parent_raw, name, kind):
        result = self._real["_native_relative_create"](handles, native, parent_raw, name, kind)
        if result[1] is not None:
            self.samples.append((_os_handles(), handles.open_count, handles.peak_open))
        return result

    def _spy_create_child(self, handles, native, parent, name, kind):
        parent_rec = self.recs[id(parent)]
        # Files held at the moment of a create must all be children of THIS
        # parent: a file of any other directory still open here would mean a file
        # handle survived into a descent ("files closed before recursion").
        stray = [serial for serial, count in self.open_files.items() if count and serial != parent_rec.serial]
        if stray:
            self.foreign_open_file_violations.append(f"{parent_rec.path}/{name}")
        entry = self._real["_create_child"](handles, native, parent, name, kind)
        if parent_rec.path == "<R>":
            path = "<RT>"
        elif parent_rec.path == "<RT>":
            path = ""
        elif parent_rec.path == "":
            path = name
        else:
            path = parent_rec.path + "/" + name
        self.serial += 1
        rec = _Rec(self.serial, kind, parent_rec, name, path, entry)
        parent_rec.children.append(rec)
        self.recs[id(entry)] = rec
        self.by_raw[entry.raw] = rec
        self.live.add(rec)
        if kind == "file":
            self.open_files[parent_rec.serial] += 1
        return entry

    # -- gates, content, enumeration ----------------------------------------

    def _spy_raw_enumerate_once(self, raw):
        self.enumerations += 1
        before = self.dir_fetches
        result = self._real["_raw_enumerate_once"](raw)
        self.last_enumeration = (self.dir_fetches - before, len(result))
        return result

    def _spy_gate_membership(self, handles, root, child):
        self._real["_gate_membership"](handles, root, child)
        self.membership_gates += 1

    def _spy_gate_exact_set(self, handles, directory, children):
        rec = self.recs[id(directory)]
        record = {
            "path": rec.path,
            "names": sorted(child.name for child in children),
            "created_before_gate": len(rec.children),
            "ledger_open": handles.open_count,
            "os_open": _os_handles(),
            "writes_before_gate": sum(1 for path in self.writes if self._parent_path(path) == rec.path),
        }

        if self.before_gate is not None:
            self.before_gate(rec)
        self._real["_gate_exact_set"](handles, directory, children)
        record["fetches"], record["entries_seen"] = self.last_enumeration
        record["passed"] = True
        self.gated.add(rec.serial)
        self.gates.append(record)

    @staticmethod
    def _parent_path(path: str) -> str:
        return path.rpartition("/")[0]

    def _spy_write_verified_content(self, handles, child, data, sha256):
        rec = self.recs[id(child)]
        if rec.parent.serial not in self.gated:
            self.write_before_gate.append(rec.path)
        if hashlib.sha256(data).hexdigest() != sha256:
            self.written_digest_mismatch.append(rec.path)
        self._real["_write_verified_content"](handles, child, data, sha256)
        self.writes.append(rec.path)

    def _spy_raw_read_from_start(self, raw, limit):
        self.readbacks += 1
        return self._real["_raw_read_from_start"](raw, limit)

    # -- closing -------------------------------------------------------------

    def _spy_close_raw_handle(self, raw):
        self.close_attempts += 1
        rec = self.by_raw.pop(raw, None)
        if rec is None:
            self.unknown_closes += 1  # a final pin: acquired outside construction
            return self._real["_close_raw_handle"](raw)
        # Every child must have had its close ATTEMPTED before its parent's.
        if any(not child.attempted for child in rec.children):
            self.order_violations.append(rec.path)
        rec.attempted = True
        self.live.discard(rec)
        if rec.kind == "file":
            self.open_files[rec.parent.serial] -= 1
        if self.fail_close_at is not None and rec.path == self.fail_close_at:
            self.leaked_raw = raw
            self.fail_attempts += 1
            rec.close_ok = False
            return False
        rec.close_ok = self._real["_close_raw_handle"](raw)
        return rec.close_ok

    # -- derived views -------------------------------------------------------

    def rec_for_path(self, path: str) -> _Rec | None:
        return next((rec for rec in self.recs.values() if rec.path == path), None)

    def created_children_by_directory(self) -> dict[str, set[str]]:
        return {rec.path: {child.name for child in rec.children} for rec in self.recs.values() if rec.kind == "directory"}

    def os_peak_delta(self, baseline: int) -> int:
        return max(os_count for os_count, _open, _peak in self.samples) - baseline


def _settle() -> int:
    gc.collect()
    return _os_handles()


def _destination(env, rec: _Rec) -> Path:
    if rec.path == "<RT>":
        return env.run_root / rp.RUNTIME_DIR_NAME
    return env.package_root.joinpath(*rec.path.split("/")) if rec.path else env.package_root


def _assert_os_matches_ledger_at_every_create(probe: _Probe, baseline: int) -> None:
    """The OS handle count minus the pre-run baseline equals the ledger's open
    count after EVERY real create. The ledger's peak is thereby compared with an
    observation it did not produce."""
    assert probe.samples, "no create was observed"
    bad = [
        (index, os_count - baseline, ledger_open)
        for index, (os_count, ledger_open, _peak) in enumerate(probe.samples)
        if os_count - baseline != ledger_open
    ]
    assert not bad, f"OS handle count disagrees with the ledger at {len(bad)} creates, first {bad[:3]}"


# ---------------------------------------------------------------------------
# Full committed-shape construction through the public path
# ---------------------------------------------------------------------------


@windows_only
def test_committed_shape_construction_end_to_end_at_full_scale(committed_shape, make_env, monkeypatch):
    """Properties 1-7 on the committed geometry (1436 directories, 15046 files,
    depth 11, 360 + 80 fan-out, 362-entry directory): measured, not asserted
    from the fixture."""
    env = make_env(committed_shape.payload, committed_shape.source, committed_shape.inventory)
    probe = _Probe(monkeypatch)
    provision = _admit(env)
    baseline = _settle()
    rp.run_runtime_provision(provision)
    after_run = _settle()
    try:
        assert provision.state == rp.STATE_PROVEN
        # -- 1. exclusive handle-relative creation of directories and files ----
        created_dirs = [rec for rec in probe.recs.values() if rec.kind == "directory" and rec.serial != 0]
        created_files = [rec for rec in probe.recs.values() if rec.kind == "file"]
        assert len(created_files) == _COMMITTED_FILES
        assert len(created_dirs) == _COMMITTED_DIRS + 2  # + RT + C
        assert provision._construction.entry_count == 1 + len(created_dirs) + len(created_files)  # + R pin
        # -- 2. returned-handle identity vs. the filesystem, per object --------
        mismatched = []
        for rec in [*created_dirs, *created_files]:
            stat = os.stat(_destination(env, rec))
            if (stat.st_dev, stat.st_ino) != rec.entry.identity:
                mismatched.append(rec.path)
        assert not mismatched, mismatched[:3]
        # creation really was per-directory exact: what was created under each
        # directory is exactly what the COMMITTED inventory lists there
        committed = _geometry(_committed_entries())
        observed = probe.created_children_by_directory()
        for directory, (n_files, n_dirs) in committed["per_dir"].items():
            assert len(observed[directory]) == n_files + n_dirs, directory
        assert len(observed[""]) == committed["per_dir"][""][0] + committed["per_dir"][""][1]
        # -- 3. one complete exact-set gate before any content write ----------
        exact_gates = [gate for gate in probe.gates]
        # C + the 1436 inventory directories, plus RT's gate over {C}
        assert len(exact_gates) == 1 + _COMMITTED_DIRS + 1
        assert probe.membership_gates == 1
        assert probe.enumerations == len(exact_gates) + probe.membership_gates  # each gate ran its own enumeration
        by_dir = {gate["path"]: gate for gate in exact_gates}
        assert len(by_dir) == len(exact_gates)  # at most one gate per directory
        for directory, (n_files, n_dirs) in committed["per_dir"].items():
            gate = by_dir[directory]
            assert gate["passed"] and gate["writes_before_gate"] == 0
            assert gate["created_before_gate"] == len(gate["names"]) == n_files + n_dirs, directory
        # each gate's ONE enumeration returned exactly "." + ".." + the created children.
        # Measured, not assumed: the committed geometry's widest directory (364 entries)
        # fits ONE 64 KiB enumeration buffer (a data fetch plus the terminating call), so
        # the multi-buffer continuation is NOT reached at committed scale; the long-name
        # case below forces it.
        for directory, (n_files, n_dirs) in committed["per_dir"].items():
            assert by_dir[directory]["entries_seen"] == n_files + n_dirs + 2, directory
        assert by_dir[_WIDEST]["entries_seen"] == _FROZEN_MAX_ENTRIES + 2
        assert by_dir[_WIDEST]["fetches"] == 2  # one data buffer + the terminating call
        assert by_dir["<RT>"]["names"] == [rp.PACKAGE_DIR_NAME]
        assert not probe.write_before_gate
        assert len(probe.writes) == _COMMITTED_FILES == probe.readbacks
        assert not probe.written_digest_mismatch
        # -- 4. byte identity and digest read-back, checked against the dict ---
        seen_files = 0
        seen_dirs = 0
        for top, dirnames, filenames in os.walk(env.package_root, onerror=lambda exc: (_ for _ in ()).throw(exc)):
            relative_top = os.path.relpath(top, env.package_root).replace("\\", "/")
            relative_top = "" if relative_top == "." else relative_top
            seen_dirs += len(dirnames)
            for filename in filenames:
                relative = (relative_top + "/" + filename) if relative_top else filename
                expected = committed_shape.files[relative]
                actual = Path(top, filename).read_bytes()
                assert actual == expected, relative
                seen_files += 1
        assert (seen_files, seen_dirs) == (_COMMITTED_FILES, _COMMITTED_DIRS)
        copied = pi_payload.observe_payload(str(env.package_root), leaves=pi_payload.genuine_payload_leaves())
        assert copied.complete and copied.inventory.payload_fingerprint == committed_shape.inventory.payload_fingerprint
        # -- 5. bounded actual peak: ledger AND OS, vs. committed and frozen ---
        independent = _independent_peak(committed_shape.entries)
        assert independent == 449
        ledger_peak = provision.construction_peak_open
        os_peak = probe.os_peak_delta(baseline)
        assert ledger_peak == independent == rp.construction_handle_peak(committed_shape.inventory) == os_peak
        assert ledger_peak <= _FROZEN_HANDLE_BOUND
        _assert_os_matches_ledger_at_every_create(probe, baseline)
        # -- 6. children before parents; files closed before any descent -------
        assert not probe.order_violations
        assert not probe.foreign_open_file_violations
        assert all(rec.close_ok is True for rec in probe.recs.values())
        assert probe.unknown_closes == 0  # the four final pins are still held
        # -- 7. complete release (construction handles, observed by the OS) ----
        assert provision.construction_open_count == 0
        assert provision.final_pins_held == 4
        assert after_run - baseline == 4  # exactly the four final pins remain open in the process
        assert probe.live == set()
        print(
            "SCALE_MEASUREMENT "
            + json.dumps(
                {
                    "case": "committed_shape_full",
                    "dirs_created": len(created_dirs),
                    "files_created": len(created_files),
                    "exact_set_gates": len(exact_gates),
                    "ledger_entries": provision._construction.entry_count,
                    "ledger_peak": ledger_peak,
                    "os_peak_delta": os_peak,
                    "independent_peak": independent,
                    "frozen_bound": _FROZEN_HANDLE_BOUND,
                    "widest_gate_ledger_open": by_dir["node_modules/@earendil-works/pi-ai/dist/providers"]["ledger_open"],
                    "os_samples": len(probe.samples),
                    "widest_enumeration_kernel_fetches": by_dir[_WIDEST]["fetches"],
                    "widest_enumeration_entries": by_dir[_WIDEST]["entries_seen"],
                    "longest_destination_path_chars": max(
                        len(str(_destination(env, rec))) for rec in created_files
                    ),
                    "run_root_chars": len(str(env.run_root)),
                }
            )
        )
    finally:
        rp.release_at_l27_entry(provision)
    assert provision.final_pins_held == 0
    assert provision.live_references_released is True
    assert rp.provision_live_references_proven_released(provision) is True
    assert probe.unknown_closes == 4
    assert _settle() == baseline  # the OS agrees: every handle this run opened is closed
    result = run_workspace.remove_cfg1_run_workspace(env.workspace)  # STRICT, inside the test body
    assert not env.run_root.exists()
    assert result is not None


# ---------------------------------------------------------------------------
# Partial failure at the pit of the fan-out
# ---------------------------------------------------------------------------

@windows_only
def test_a_foreign_name_in_the_widest_directory_refuses_with_everything_released(committed_shape, make_env, monkeypatch):
    """A foreign name is planted into the 362-entry directory while 3 + ancestry
    + 362 handles are held. The exact-set gate must REFUSE (it really runs, at
    scale), no content byte reaches that directory, the planted name is not
    deleted, and every handle -- observed by the OS, not only the ledger -- is
    closed, children before parents."""
    env = make_env(committed_shape.payload, committed_shape.source, committed_shape.inventory)
    planted = env.package_root.joinpath(*_WIDEST.split("/"), "foreign.js")
    at_plant = {}

    def plant(rec):
        if rec.path == _WIDEST:
            at_plant["children"] = len(rec.children)
            at_plant["os_open"] = _os_handles()
            planted.write_bytes(b"planted")

    probe = _Probe(monkeypatch, before_gate=plant)
    provision = _admit(env)
    baseline = _settle()
    with pytest.raises(rp.Cfg1RuntimeProvisionError) as refused:
        rp.run_runtime_provision(provision)
    assert refused.value.reason_code == "PARENTAGE_GATE_FAILED"
    assert at_plant["children"] == _FROZEN_MAX_ENTRIES  # the gate was refusing a REAL 362-entry directory
    assert provision.state == rp.STATE_REFUSED and provision.refusal_reason == "PARENTAGE_GATE_FAILED"
    assert provision.construction_open_count == 0
    assert provision._construction.all_proven_closed()
    assert provision.live_references_released is True  # nothing left open; the final-pin ledger never opened
    assert _settle() == baseline  # OS-observed: complete release after a mid-construction refusal
    assert not probe.order_violations and not probe.foreign_open_file_violations
    assert all(rec.close_ok is True for rec in probe.recs.values())
    assert at_plant["os_open"] - baseline >= at_plant["children"] + 3  # the refusal happened at the pit
    # no content in the refused directory; the planted name survives (nothing deleted)
    widest_dir = planted.parent
    assert sorted(path.name for path in widest_dir.iterdir()).count("foreign.js") == 1
    assert all(path.stat().st_size == 0 for path in widest_dir.iterdir() if path.is_file() and path.name != "foreign.js")
    assert planted.read_bytes() == b"planted"
    assert _WIDEST not in {gate["path"] for gate in probe.gates}  # its gate never PASSED
    assert not any(path.startswith(_WIDEST + "/") or path.rpartition("/")[0] == _WIDEST for path in probe.writes)
    rp.release_at_l27_entry(provision)
    assert provision.live_references_released is True
    assert rp.provision_live_references_proven_released(provision) is True
    assert _settle() == baseline


@windows_only
@pytest.mark.parametrize("victim_kind", ["file_in_widest_directory", "deepest_directory"])
def test_a_close_failure_at_scale_latches_and_every_other_handle_is_released(committed_shape, make_env, monkeypatch, victim_kind):
    """An injected close failure on ONE object, in the widest directory (a file
    with hundreds of sibling pins held) and on the deepest directory (with the
    longest ancestry held). The run refuses; the failed entry is never retried;
    every OTHER handle is closed (OS-observed: exactly one leaked handle); the
    derived release fact is False and stays False after L27 release."""
    deepest = max(
        (path for kind, path in committed_shape.entries if kind == "dir"), key=lambda p: (p.count("/"), p)
    )
    victim_path = (_WIDEST + "/" + "anthropic.js") if victim_kind == "file_in_widest_directory" else deepest
    assert victim_kind != "file_in_widest_directory" or ("file", victim_path) in committed_shape.entries
    env = make_env(committed_shape.payload, committed_shape.source, committed_shape.inventory)
    probe = _Probe(monkeypatch, fail_close_at=victim_path)
    provision = _admit(env)
    baseline = _settle()
    try:
        with pytest.raises(rp.Cfg1RuntimeProvisionError) as refused:
            rp.run_runtime_provision(provision)
        assert refused.value.reason_code == "CONSTRUCTION_HANDLE_NOT_CLOSED"
        assert provision.state == rp.STATE_REFUSED
        assert probe.fail_attempts == 1  # never retried
        assert probe.leaked_raw is not None
        failed = [rec for rec in probe.recs.values() if rec.close_ok is False]
        assert [rec.path for rec in failed] == [victim_path]
        assert provision.live_references_released is False
        assert provision._construction.any_close_failed()
        assert provision.construction_open_count == 0  # nothing OPEN; one entry CLOSE_FAILED
        assert not probe.order_violations and not probe.foreign_open_file_violations
        assert all(rec.close_ok is True for rec in probe.recs.values() if rec is not failed[0])
        # the LEDGER's own account, not the injected seam's: one CLOSE_FAILED, none OPEN
        states = collections.Counter(entry.state for entry in provision._construction._entries)
        assert states[rp.HANDLE_CLOSE_FAILED] == 1 and states[rp.HANDLE_OPEN] == 0
        assert states[rp.HANDLE_CLOSED] == provision._construction.entry_count - 1
        assert _settle() - baseline == 1  # OS-observed: exactly the one injected leak remains
        rp.release_at_l27_entry(provision)
        assert probe.fail_attempts == 1  # release did not retry it either
        assert provision.live_references_released is False
        assert rp.provision_live_references_proven_released(provision) is False
        with pytest.raises(rp.Cfg1RuntimeProvisionError) as again:
            rp.release_at_l27_entry(provision)
        assert again.value.reason_code == "PROVISION_ALREADY_RELEASED"
    finally:
        if probe.leaked_raw is not None:  # the harness, not the candidate, frees the real handle
            _K32.CloseHandle(probe.leaked_raw)
    assert _settle() == baseline


# ---------------------------------------------------------------------------
# Sibling pins and nesting, on shaped payloads with hand-derived peaks
# ---------------------------------------------------------------------------


def _shaped_payload(extra: dict[str, bytes]) -> tuple[dict[str, bytes], tuple]:
    files, empty = synthetic_payload_files()
    files = dict(files)
    files["dist/config.js"] = b"export const x = 1;\n"
    files.update(extra)
    return files, tuple(empty)


def _build_small(make_env, tmp_path, extra):
    """A small approvable payload (the PE-2a synthetic tree plus ``extra``) written
    to ``tmp_path`` and approved through a genuine PE-2b load."""
    files, empty = _shaped_payload(extra)
    source = tmp_path / "src" / "pkg"
    for relative, data in files.items():
        target = source.joinpath(*relative.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    for relative in empty:
        source.joinpath(*relative.split("/")).mkdir(parents=True, exist_ok=True)
    observation = pi_payload.observe_payload(str(source), leaves=pi_payload.genuine_payload_leaves())
    assert observation.complete
    payload = Payload(files, empty)
    assert payload.fingerprint == observation.inventory.payload_fingerprint
    return make_env(payload, source, observation.inventory), files, empty, observation


def _run_shape(make_env, monkeypatch, tmp_path, extra):
    env, files, empty, observation = _build_small(make_env, tmp_path, extra)
    probe = _Probe(monkeypatch)
    provision = _admit(env)
    baseline = _settle()
    rp.run_runtime_provision(provision)
    entries = [(entry[0], entry[1]) for entry in observation.inventory.entries]
    try:
        assert provision.state == rp.STATE_PROVEN
        independent = _independent_peak(entries)
        assert provision.construction_peak_open == independent == rp.construction_handle_peak(observation.inventory)
        assert probe.os_peak_delta(baseline) == independent
        _assert_os_matches_ledger_at_every_create(probe, baseline)
        assert not probe.order_violations and not probe.foreign_open_file_violations and not probe.write_before_gate
        assert len(probe.writes) == probe.readbacks == len(files)
        for relative, data in files.items():
            assert env.package_root.joinpath(*relative.split("/")).read_bytes() == data
        assert independent <= _FROZEN_HANDLE_BOUND
        base_only = _shaped_payload({})[0]
        base_entries = _base_entries(base_only, empty)
        return independent, _independent_peak(base_entries), probe
    finally:
        rp.release_at_l27_entry(provision)
        assert provision.live_references_released is True
        assert _settle() == baseline


def _base_entries(files: dict[str, bytes], empty) -> list[tuple[str, str]]:
    """``(kind, path)`` in inventory order for a file mapping (sorted like PI-PC1)."""
    paths = {}
    for relative in files:
        parts = relative.split("/")
        for index in range(1, len(parts)):
            paths["/".join(parts[:index])] = "dir"
        paths[relative] = "file"
    for relative in empty:
        paths[relative] = "dir"
    return [(kind, path) for path, kind in sorted(paths.items(), key=lambda item: item[0].encode("utf-8"))]


@windows_only
def test_simultaneous_360_files_and_80_directories_in_one_directory(make_env, monkeypatch, tmp_path):
    """The largest fan-out the frozen limits allow IN ONE DIRECTORY at once
    (360 file pins + 80 directory pins -- more than the committed inventory has
    in any single directory). Hand-derived peak, with ``zz_wide`` last in
    ``node_modules`` so no other directory pin of ``node_modules`` is pending:
    R, RT, C (3) + the ``node_modules`` pin (1, the directory being built) + the
    ``zz_wide`` pin (1) + 440 children = 445. (A first draft of this derivation
    said 444: it omitted the pin of the directory currently being built. The
    ledger, the OS count and the independent recomputation all said 445.)"""
    extra = {f"node_modules/zz_wide/f{index:03d}.txt": b"f%d" % index for index in range(_FROZEN_MAX_FILES)}
    extra.update({f"node_modules/zz_wide/d{index:02d}/leaf.txt": b"d%d" % index for index in range(_FROZEN_MAX_DIRS)})
    peak, base_peak, _probe = _run_shape(make_env, monkeypatch, tmp_path, extra)
    assert 3 + 1 + 1 + _FROZEN_MAX_FILES + _FROZEN_MAX_DIRS == 445
    assert peak == max(base_peak, 445) == 445


@windows_only
def test_depth_11_with_pending_sibling_pins_at_every_level(make_env, monkeypatch, tmp_path):
    """A file at depth 11 below ``C`` (``node_modules/zz_deep/c1/.../c8/leaf.txt``)
    where each of 8 levels also holds two SIBLING directory pins (``s1``, ``s2``,
    sorted after the chain directory so they are still pending during the
    descent). Hand-derived: R, RT, C (3) + the ``node_modules`` pin (1) + the
    ``zz_deep`` pin (1) + 8 levels (``zz_deep``, ``c1``..``c7``) x 3 pins (the
    chain child and two siblings) + the one leaf file = 30. (A first draft said
    29, omitting the pin of ``node_modules`` itself; the ledger, the OS count and
    the independent recomputation all said 30.)"""
    chain = "node_modules/zz_deep" + "".join(f"/c{level}" for level in range(1, 9))
    extra = {f"{chain}/leaf.txt": b"leaf"}
    parent = "node_modules/zz_deep"
    for level in range(0, 8):
        for sibling in ("s1", "s2"):
            extra[f"{parent}/{sibling}/x.txt"] = b"x"
        parent = f"{parent}/c{level + 1}"
    assert max(path.count("/") + 1 for path in extra) == _FROZEN_DEPTH
    peak, base_peak, _probe = _run_shape(make_env, monkeypatch, tmp_path, extra)
    assert 3 + 1 + 1 + 8 * 3 + 1 == 30
    assert peak == max(base_peak, 30) == 30
    assert peak < _FROZEN_HANDLE_BOUND


@windows_only
def test_the_probe_would_notice_a_gate_that_never_enumerates(make_env, monkeypatch, tmp_path):
    """Non-vacuity of the gate accounting. A stand-in "gate" that merely marks
    its children passed -- exactly what a no-op gate would do -- lets the run
    complete, but the independent enumeration count then disagrees with the
    gate count. The full-scale test asserts the two are EQUAL, so it would fail
    for such a candidate; the foreign-name test shows the real gate refusing."""
    env, _files, _empty, _observation = _build_small(make_env, tmp_path, {})

    def marks_without_looking(handles, directory, children):
        for child in children:
            child.gate_passed = True

    monkeypatch.setattr(rp, "_gate_exact_set", marks_without_looking)
    probe = _Probe(monkeypatch)  # wraps the stand-in, as it wraps the real gate
    provision = _admit(env)
    baseline = _settle()
    rp.run_runtime_provision(provision)
    try:
        assert provision.state == rp.STATE_PROVEN
        assert len(probe.gates) > 1
        assert probe.enumerations == probe.membership_gates  # not one exact-set enumeration happened
        assert probe.enumerations != len(probe.gates) + probe.membership_gates
    finally:
        rp.release_at_l27_entry(provision)
    assert _settle() == baseline


@windows_only
def test_an_enumeration_spanning_several_kernel_buffers_still_gates_exactly(make_env, monkeypatch, tmp_path):
    """The committed geometry never needs a second enumeration buffer (measured
    above), so the continuation inside the single pass is forced here: 300 files
    with 100-character names in one directory (about 90 KiB of directory-info
    records against the candidate's 64 KiB buffer). The gate must still see
    exactly "." + ".." + every created name, once, and pass."""
    names = [f"n{index:03d}_" + "x" * 92 + ".js" for index in range(300)]
    assert all(len(name) == 100 for name in names)
    env, files, _empty, _observation = _build_small(make_env, tmp_path, {f"node_modules/zz_long/{n}": b"c" + n.encode() for n in names})
    probe = _Probe(monkeypatch)
    provision = _admit(env)
    baseline = _settle()
    rp.run_runtime_provision(provision)
    try:
        assert provision.state == rp.STATE_PROVEN
        gate = next(g for g in probe.gates if g["path"] == "node_modules/zz_long")
        assert gate["entries_seen"] == 300 + 2
        assert gate["fetches"] >= 3  # >= 2 data buffers + the terminating call: the continuation ran
        assert gate["created_before_gate"] == len(gate["names"]) == 300
        assert gate["passed"] and gate["writes_before_gate"] == 0
        _assert_os_matches_ledger_at_every_create(probe, baseline)
        for relative, data in files.items():
            assert env.package_root.joinpath(*relative.split("/")).read_bytes() == data
    finally:
        rp.release_at_l27_entry(provision)
    assert _settle() == baseline
