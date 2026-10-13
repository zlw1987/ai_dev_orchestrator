"""F5-A A2 OFFLINE CANDIDATE -- ORDINARY (non-reparse) handle-semantics evidence.

What this module measures. How the handles the ACTUAL A2 candidate
(``pi_runtime_provision``) creates and pins behave against an ordinary second actor
of the same user on this host's NTFS volume. Every handle under test is produced by
the candidate's own primitives -- ``_pin_run_root``, ``_create_child`` (one
``NtCreateFile(FILE_CREATE)`` relative to a held parent) and the four final read-only
pins taken by ``run_runtime_provision`` -> ``_acquire_final_pins`` -- never by a
test-local look-alike. The "second actor" is a plain Win32 call
(``ordinary_handle_actor``), issued in-process and, for one case, from a SEPARATE
process of the same user.

Three groups.

* **A  Final read-only pins** (``GENERIC_READ`` / share ``READ`` / ``OPEN_EXISTING``,
  a REOPENED handle on an object the construction creating handle already closed):
  can a second actor delete, rename, replace or overwrite/truncate the held file; and
  can the ancestors ``dist``, ``C``, ``RT``, ``R`` be renamed (the P-R1-2 shape).
* **B  Native construction directory pins** (the directory shape of ``_create_child``,
  and the run-root pin of ``_pin_run_root``): ordinary rename and delete of pinned
  directories, held children, nested parents -- as a staged matrix over WHICH handles
  are held.
* **C  Share-zero file children** (the creating handle of ``_create_child``): incompatible
  opens, exclusive creation of an occupied name, replace/overwrite, and that the
  creating handle keeps referring to the original object.

Evidence standard. Nothing is assumed to refuse: each case records the REAL
``GetLastError`` / ``NTSTATUS``, the object's identity and content before and after,
and a MATCHED CONTROL -- the identical call on the identical object after the held
handle is released through the candidate's own ledger. A refusal only counts when the
control shows the call otherwise succeeds, so a fixture or a typo cannot pass as a
sharing guarantee. Fixture teardown is strict: a leaked workspace, a surviving fixture tree,
an unclosed handle or a process handle count that does not return to its baseline fails the test.
Each case prints one ``ORDINARY_HANDLE_MEASUREMENT {json}`` line (run with ``-rP``).

What this module does NOT do (and must not be read as). It creates no junction,
symlink, hard link, or other reparse point; converts no directory; opens nothing with
``FILE_WRITE_ATTRIBUTES``; races no conversion against a create; attempts no
escape outside its owned fixtures; and launches no Pi, Node, model, backend or
credential-bearing process. It is NOT proof of containment beneath a converted
parent (A2-3, INCOMPLETE), says nothing about R-ALIAS, and does not qualify A2 for
live use. A green run is ordinary regression evidence about sharing semantics, for
this one host and build.
"""

from __future__ import annotations

import ast
import errno
import gc
import hashlib
import inspect
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Win32/NTFS semantics; a skip is not a pass")

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    import ordinary_handle_actor as actor
    from pe2a_support import synthetic_payload_files
    from pe2b_support import Payload
    from pe2c_support import install_synthetic_policy

    from pi_harness_cfg1 import pi_payload
    from pi_harness_cfg1 import pi_runtime_provision as rp
    from pi_harness_cfg1 import run_workspace

    _K32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _K32.GetCurrentProcess.restype = wintypes.HANDLE
    _K32.GetCurrentProcess.argtypes = []
    _K32.GetProcessHandleCount.restype = wintypes.BOOL
    _K32.GetProcessHandleCount.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    _NT = ctypes.WinDLL("ntdll")
    _NT.NtQueryInformationFile.restype = ctypes.c_long
    _NT.NtQueryInformationFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong]

# Computed ONCE, at import: the first call of ``sys.getwindowsversion()`` allocates a process-lifetime
# handle (traced), which must not be read as a leak by the handle-count checks below.
_PLATFORM = (
    f"Windows build {sys.getwindowsversion().build} / Python {sys.version.split()[0]}" if sys.platform == "win32" else sys.platform
)
_ACTOR_SCRIPT = Path(__file__).resolve().parent / "ordinary_handle_actor.py"

#: Observed on this host for every refusal that is a SHARING refusal.
ERROR_SHARING_VIOLATION = 32
#: Observed when a rename/delete is refused because an object BENEATH the target is open.
ERROR_ACCESS_DENIED = 5
#: Observed for ``CREATE_NEW`` on a name that already exists.
ERROR_FILE_EXISTS = 80
#: ``STATUS_OBJECT_NAME_COLLISION``: the NT status of ``FILE_CREATE`` on an occupied name.
STATUS_OBJECT_NAME_COLLISION = 0xC0000035

_FILE_GENERIC_READ = 0x120089
_DELETE = 0x00010000
_WRITE_ACCESS_BITS = 0x2 | 0x4 | 0x10 | 0x100 | 0x40000 | 0x80000  # WRITE_DATA|APPEND|WRITE_EA|WRITE_ATTR|WRITE_DAC|WRITE_OWNER


# ---------------------------------------------------------------------------
# Observation helpers
# ---------------------------------------------------------------------------


def _os_handles() -> int:
    """The PROCESS's open handle count, from the OS -- not from any ledger. A collection runs
    first so a not-yet-finalised Python object (a pipe, a file) is not read as a leak."""
    gc.collect()
    count = wintypes.DWORD(0)
    assert _K32.GetProcessHandleCount(_K32.GetCurrentProcess(), ctypes.byref(count))
    return int(count.value)


def _identity(path) -> tuple[int, int]:
    result = os.stat(path)
    return (result.st_dev, result.st_ino)


def _snap(path, *, content: bool = True) -> dict:
    """What is at ``path`` right now: existence, identity, size and (optionally) content hash."""
    path = str(path)
    if not os.path.lexists(path):
        return {"exists": False}
    stat = os.stat(path)
    snapshot = {"exists": True, "identity": (stat.st_dev, stat.st_ino), "size": stat.st_size, "sha": None}
    if content and os.path.isfile(path):
        snapshot["sha"] = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    return snapshot


def _granted_access(raw: int) -> int:
    """The access mask the OS actually granted to a handle (``FileAccessInformation``)."""
    iosb = ctypes.create_string_buffer(16)
    value = ctypes.c_ulong(0)
    status = _NT.NtQueryInformationFile(raw, iosb, ctypes.byref(value), 4, 8)
    assert status == 0, hex(status & 0xFFFFFFFF)
    return int(value.value)


def _emit(record: dict) -> None:
    record = {"platform": _PLATFORM, **record}
    print("ORDINARY_HANDLE_MEASUREMENT " + json.dumps(record, sort_keys=True, default=str))


def _codes(op: str) -> tuple[int, ...]:
    """The refusal codes OBSERVED for ``op`` against a held object on this build. Replacing an
    existing file by ``MoveFileExW(REPLACE_EXISTING)`` is reported as ACCESS_DENIED (5) rather
    than SHARING_VIOLATION (32); every other operation here is 32. The safety-relevant fact is
    "refused, no effect, and the released control succeeds"; the code is recorded, not trusted."""
    return (ERROR_ACCESS_DENIED, ERROR_SHARING_VIOLATION) if op == "replace_by_other" else (ERROR_SHARING_VIOLATION,)


def _python_refusal(attempt) -> dict:
    """An ordinary Python file call that is expected to be refused: it must raise
    ``PermissionError`` (errno EACCES); ``winerror`` is present for ``os.*`` calls and absent
    for ``open()``, whose C runtime maps the sharing violation to EACCES."""
    with pytest.raises(PermissionError) as refused:
        attempt()
    assert refused.value.errno == errno.EACCES
    assert getattr(refused.value, "winerror", None) in (None, ERROR_ACCESS_DENIED, ERROR_SHARING_VIOLATION)
    return {"errno": refused.value.errno, "winerror": getattr(refused.value, "winerror", None)}


def _positive(call, attempts: int = 5) -> dict:
    """A POSITIVE operation (a control, or restoring a rename), retried a bounded number of times.

    A directory rename is refused while ANY handle is open beneath or on it, and a handle opened by something
    outside this test (an indexer or scanner reading the fresh temporary tree) refused such an operation
    about once in ten runs. That would invalidate a CONTROL, never a held-phase refusal -- those are attempted
    exactly once and never pass through here. The attempt count is recorded in the result."""
    for attempt in range(1, attempts + 1):
        result = call()
        if result["ok"]:
            break
        time.sleep(0.2)
    return {**result, "attempts": attempt}


def _refused(result: dict, *codes: int) -> None:
    assert result["ok"] is False, f"UNEXPECTED SUCCESS: {result}"
    assert result["winerror"] in codes, result


def _assert_control_effect(op: str, path: str, pre: dict, original: bytes, other_path: str | None, other_bytes: bytes | None) -> None:
    """After a SUCCESSFUL control, the object really was affected as the op says."""
    if op == "delete":
        assert not os.path.lexists(path)
    elif op == "rename_away":
        assert not os.path.lexists(path)
        moved = _snap(path + ".moved")
        assert moved["exists"] and moved["identity"] == pre["identity"] and moved["sha"] == pre["sha"]
    elif op == "replace_by_other":
        assert Path(path).read_bytes() == other_bytes
        assert _identity(path) != pre["identity"]  # a DIFFERENT object now owns the name
        assert not os.path.lexists(other_path)
    elif op == "open_write_existing":
        assert _identity(path) == pre["identity"]
        assert Path(path).read_bytes() == actor.PAYLOAD + original[len(actor.PAYLOAD):]
    elif op in ("truncate_existing", "create_always"):
        assert _identity(path) == pre["identity"]
        assert Path(path).read_bytes() == actor.PAYLOAD
    else:  # pragma: no cover
        raise AssertionError(op)


# ---------------------------------------------------------------------------
# Provenance: the access/share shapes under test ARE the candidate's shapes
# ---------------------------------------------------------------------------


def test_the_shapes_measured_here_are_the_production_shapes():
    """The measured handles come from the candidate's own functions, and the access,
    share and option words those functions pass are the ones the evidence is labelled
    with. A future edit to a shape changes this test, not just the report."""
    assert rp._GENERIC_READ == 0x80000000 and rp._FILE_SHARE_READ == 1 and rp._FILE_SHARE_WRITE == 2
    assert rp._DIRECTORY_SHAPE == (0x1 | 0x80 | 0x100000, 0x1, 0x1 | 0x20 | 0x200000)
    assert rp._FILE_SHAPE == (0x80000000 | 0x40000000 | 0x10000 | 0x100000, 0x0, 0x40 | 0x20 | 0x200000)

    def create_file_args(function) -> list[str]:
        tree = ast.parse(inspect.getsource(function))
        calls = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "CreateFileW"
        ]
        assert len(calls) == 1
        return [ast.unparse(argument) for argument in calls[0].args]

    # CreateFileW(path, access, share, security, disposition, flags, template)
    assert create_file_args(rp._acquire_final_pins)[1:] == [
        "_GENERIC_READ", "_FILE_SHARE_READ", "None", "_OPEN_EXISTING", "_FILE_FLAG_OPEN_REPARSE_POINT", "None",
    ]
    assert create_file_args(rp._pin_run_root)[1:] == [
        "_FILE_LIST_DIRECTORY | _FILE_READ_ATTRIBUTES",
        "_FILE_SHARE_READ | _FILE_SHARE_WRITE",
        "None",
        "_OPEN_EXISTING",
        "_FILE_FLAG_BACKUP_SEMANTICS | _FILE_FLAG_OPEN_REPARSE_POINT",
        "None",
    ]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def provisioned(tmp_path, monkeypatch, git_executable):
    """A REAL minted workspace and a REAL run of the candidate over a small synthetic
    approved payload; the four final read-only pins are held when the test starts.
    Teardown releases anything still held, removes the workspace through the frozen
    remover and FAILS on any residue or any handle-count drift."""
    files, empty_dirs = synthetic_payload_files()
    files = dict(files)
    source = tmp_path / "src" / "pkg"
    for relative, data in files.items():
        target = source.joinpath(*relative.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    for relative in empty_dirs:
        source.joinpath(*relative.split("/")).mkdir(parents=True, exist_ok=True)
    observation = pi_payload.observe_payload(str(source), leaves=pi_payload.genuine_payload_leaves())
    assert observation.complete
    payload = Payload(dict(files), tuple(empty_dirs))
    assert payload.fingerprint == observation.inventory.payload_fingerprint
    install_synthetic_policy(monkeypatch, payload)
    workspace, _built = run_workspace.mint_cfg1_run_workspace(git_executable=git_executable)
    baseline = _os_handles()
    provision = rp.admit_runtime_provision(
        workspace=workspace,
        profile_id=payload.profile_id,
        approved_inventory=observation.inventory,
        source_package_root=str(source),
    )
    rp.run_runtime_provision(provision)
    assert provision.state == rp.STATE_PROVEN and provision.final_pins_held == 4
    package_root = provision.package_root
    ldt = rp.LAUNCH_DERIVATION_TABLE[payload.profile_id]
    relatives = (ldt["package_manifest"], *ldt["derivation_chain"])
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    counter = iter(range(10_000))

    def fresh_other() -> tuple[str, bytes]:
        n = next(counter)
        path, data = scratch / f"other{n}.bin", f"OTHER-{n}".encode()
        path.write_bytes(data)
        return str(path), data

    ctx = SimpleNamespace(
        provision=provision,
        workspace=workspace,
        run_root=str(Path(workspace.experiment_root)),
        package_root=package_root,
        runtime_dir=os.path.dirname(package_root),
        pinned={relative: os.path.join(package_root, *relative.split("/")) for relative in relatives},
        original={relative: files[relative] for relative in relatives},
        fresh_other=fresh_other,
        baseline=baseline,
    )
    yield ctx
    problems = []
    if not provision._released:
        rp.release_at_l27_entry(provision)
    if not provision.live_references_released:
        problems.append("handles not proven released")
    if run_workspace.workspace_is_registered(workspace):
        try:
            run_workspace.remove_cfg1_run_workspace(workspace)
        except Exception as exc:  # noqa: BLE001 - reported, never swallowed
            problems.append(f"workspace removal: {type(exc).__name__}")
        finally:
            run_workspace.discard_cfg1_run_workspace(workspace)
    if os.path.exists(workspace.experiment_root):
        problems.append("workspace tree still present")
    for owned in (source.parent, scratch):  # the test-owned source copy and scratch files: removed, then proven gone
        shutil.rmtree(owned, ignore_errors=False)
        if owned.exists():
            problems.append(f"{owned.name} still present")
    if _os_handles() != baseline:
        problems.append(f"process handle count {_os_handles()} != baseline {baseline}")
    assert not problems, problems


def _assert_pins_live(ctx) -> dict:
    """The tested objects are STILL held, by the candidate's own ledger, right now --
    each OPEN final-pin entry's handle identity equals the identity found at its path."""
    provision = ctx.provision
    assert provision.final_pins_held == 4 and provision.live_references_released is False
    entries = list(provision._final_pins._entries)
    assert len(entries) == 4
    seen = {}
    for entry in entries:
        assert entry.state == rp.HANDLE_OPEN and entry.kind == rp._KIND_FINAL_PIN
        assert rp._raw_identity(entry.raw) == entry.identity == _identity(ctx.pinned[entry.name])
        seen[entry.name] = _granted_access(entry.raw)
    assert set(seen) == set(ctx.pinned)
    return seen


def _release(ctx) -> None:
    rp.release_at_l27_entry(ctx.provision)
    assert ctx.provision.final_pins_held == 0
    assert ctx.provision.live_references_released is True
    assert _os_handles() == ctx.baseline


# ---------------------------------------------------------------------------
# A. Final read-only pins
# ---------------------------------------------------------------------------

A_OPS = ["delete", "rename_away", "replace_by_other", "open_write_existing", "truncate_existing", "create_always"]


def test_a_the_final_pin_handles_hold_read_only_access(provisioned):
    """The access the OS GRANTED the real final pins: read-only, no DELETE, no write bit
    of any kind. (Share mode cannot be queried from a handle; its effect is what the
    refusals and matched controls below measure.)"""
    for relative, mask in _assert_pins_live(provisioned).items():
        assert mask == _FILE_GENERIC_READ, (relative, hex(mask))
        assert not mask & _DELETE and not mask & _WRITE_ACCESS_BITS


@pytest.mark.parametrize("op", A_OPS)
def test_a_final_pin_refuses_delete_rename_replace_and_overwrite_and_a_released_control_succeeds(provisioned, op):
    ctx = provisioned
    pre = {relative: _snap(path) for relative, path in ctx.pinned.items()}
    _assert_pins_live(ctx)
    held, others = {}, {}
    for relative, path in ctx.pinned.items():
        other = None
        if op == "replace_by_other":
            other = ctx.fresh_other()
            others[relative] = other
        held[relative] = actor.run(op, path, other[0] if other else None)
        _refused(held[relative], *_codes(op))
        # no effect: same object, same bytes, nothing moved, the replacement untouched
        assert _snap(path) == pre[relative], relative
        assert not os.path.lexists(path + ".moved")
        if other:
            assert Path(other[0]).read_bytes() == other[1]
        # the fixture is valid: the very same path is readable by the second actor
        assert actor.run("open_read", path)["ok"] is True
    _assert_pins_live(ctx)  # still the same live handles to the same objects
    _release(ctx)
    control = {}
    for relative, path in ctx.pinned.items():
        other = ctx.fresh_other() if op == "replace_by_other" else None
        control[relative] = actor.run(op, path, other[0] if other else None)
        assert control[relative]["ok"] is True, (relative, control[relative])
        _assert_control_effect(op, path, pre[relative], ctx.original[relative], other[0] if other else None, other[1] if other else None)
    _emit({
        "case": f"A final pin / {op}", "filesystem": actor.filesystem_name(ctx.run_root),
        "handle": "REOPENED (OPEN_EXISTING) by _acquire_final_pins after the creating handle was closed",
        "access_share": "GENERIC_READ (granted 0x120089) / FILE_SHARE_READ / OPEN_REPARSE_POINT",
        "held_during_attempt": True, "os_result_held": held, "os_result_control_after_release": control,
        "identity_and_content_unchanged_while_held": True, "handles_released": True,
    })


def test_a_final_pin_open_matrix_read_is_shared_every_other_access_is_refused(provisioned):
    ctx = provisioned
    matrix = {
        "open_read": True, "open_read_data": True, "open_read_attributes": True,
        "open_write": False, "open_read_write": False, "open_delete_access": False,
    }
    held, control = {}, {}
    for relative, path in ctx.pinned.items():
        for op, allowed in matrix.items():
            held[f"{relative}:{op}"] = actor.run(op, path)
            if allowed:
                assert held[f"{relative}:{op}"]["ok"] is True
            else:
                _refused(held[f"{relative}:{op}"], ERROR_SHARING_VIOLATION)
        # CREATE_NEW of an occupied name is refused with the NAME error, not a sharing one
        _refused(actor.run("create_new", path), ERROR_FILE_EXISTS)
        assert _snap(path)["sha"] == hashlib.sha256(ctx.original[relative]).hexdigest()
    _assert_pins_live(ctx)
    _release(ctx)
    for relative, path in ctx.pinned.items():
        for op in matrix:
            control[f"{relative}:{op}"] = actor.run(op, path)
            assert control[f"{relative}:{op}"]["ok"] is True, (relative, op)
    _emit({"case": "A final pin / open matrix", "held": held, "control_after_release": control})


def test_a_high_level_python_calls_agree_with_the_win32_results(provisioned):
    """``open(..., 'wb')``, ``os.remove``, ``os.rename``, ``os.replace``: the calls an
    ordinary program actually makes, mapped to the same refusal, then the control."""
    ctx = provisioned
    results = {}
    for relative, path in ctx.pinned.items():
        other, _ = ctx.fresh_other()
        attempts = {
            "open_wb": lambda: open(path, "wb"),
            "open_r+b": lambda: open(path, "r+b"),
            "os.remove": lambda: os.remove(path),
            "os.rename": lambda: os.rename(path, path + ".moved"),
            "os.replace": lambda: os.replace(other, path),
        }
        for name, attempt in attempts.items():
            results[f"{relative}:{name}"] = _python_refusal(attempt)
        assert _snap(path)["sha"] == hashlib.sha256(ctx.original[relative]).hexdigest()
        assert not os.path.lexists(path + ".moved")
    _assert_pins_live(ctx)
    _release(ctx)
    for relative, path in ctx.pinned.items():
        with open(path, "r+b"):  # the SAME call that was refused now opens
            pass
        os.rename(path, path + ".moved")
        os.replace(path + ".moved", path)
        os.remove(path)
        assert not os.path.lexists(path)
    _emit({"case": "A final pin / high-level python", "python_errors_while_held": results, "control": "all succeeded after release"})


def test_a_ancestors_of_held_final_pins_cannot_be_renamed_and_a_released_control_can(provisioned):
    """The P-R1-2 shape for A2: ``dist``, ``C``, ``RT`` and ``R`` while the four read-only
    pins are held. (Only ``rename`` is tested -- ``rmdir`` of a non-empty directory is
    refused for emptiness regardless of any pin and would prove nothing.)"""
    ctx = provisioned
    ancestors = {
        "dist": os.path.join(ctx.package_root, "dist"),
        "C": ctx.package_root,
        "RT": ctx.runtime_dir,
        "R": ctx.run_root,
    }
    pre = {name: _snap(path, content=False) for name, path in ancestors.items()}
    held = {}
    for name, path in ancestors.items():
        held[name] = actor.run("rename_away", path)
        _refused(held[name], ERROR_ACCESS_DENIED, ERROR_SHARING_VIOLATION)
        assert _snap(path, content=False) == pre[name] and not os.path.lexists(path + ".moved")
    _assert_pins_live(ctx)
    _release(ctx)
    control = {}
    for name, path in ancestors.items():
        control[name] = _positive(lambda: actor.run("rename_away", path))
        assert control[name]["ok"] is True, (name, control[name])
        moved = path + ".moved"
        try:
            assert _snap(moved, content=False)["identity"] == pre[name]["identity"]
        finally:
            restored = _positive(lambda: actor.rename(moved, path))  # restore, always
            assert restored["ok"] is True, f"could not restore {name}: {restored}"
        assert _snap(path, content=False) == pre[name]
    _emit({"case": "A ancestors of final pins (P-R1-2 shape)", "os_result_held": held, "control_after_release": control})


def test_a_a_second_process_of_the_same_user_gets_the_same_results(provisioned):
    ctx = provisioned

    def separate_process(requests) -> list[dict]:
        done = subprocess.run(
            [sys.executable, str(_ACTOR_SCRIPT), json.dumps(requests)],
            capture_output=True, text=True, timeout=120, check=True, stdin=subprocess.DEVNULL,
        )
        return json.loads(done.stdout)

    pre = {relative: _snap(path) for relative, path in ctx.pinned.items()}
    requests = []
    for op in A_OPS:
        for path in ctx.pinned.values():
            requests.append([op, path, ctx.fresh_other()[0] if op == "replace_by_other" else None])
    requests.append(["open_read", next(iter(ctx.pinned.values())), None])
    _assert_pins_live(ctx)
    held = separate_process(requests)
    for entry in held:
        if entry["op"] == "open_read":
            assert entry["ok"] is True
        else:
            _refused(entry, *_codes(entry["op"]))
    assert {relative: _snap(path) for relative, path in ctx.pinned.items()} == pre
    _release(ctx)
    path = ctx.pinned["package.json"]
    control = separate_process([["open_write_existing", path, None], ["rename_away", ctx.pinned["dist/cli.js"], None]])
    assert [entry["ok"] for entry in control] == [True, True]
    _emit({"case": "A final pin / separate process", "attempts_refused_while_held": len(held) - 1, "control": control})


# ---------------------------------------------------------------------------
# B. Native construction directory pins
# ---------------------------------------------------------------------------


@pytest.fixture
def construction(tmp_path):
    """``build()`` makes ``<tmp>/parent`` and, with the candidate's own primitives,
    ``P`` (``_pin_run_root`` of ``parent``) > ``d`` > ``e`` (native directories) > ``f``
    (a native share-0 file). Every handle is in one candidate ledger; teardown closes
    them through it and fails on a handle-count drift."""
    if sys.platform != "win32":
        pytest.skip("Win32/NTFS semantics; a skip is not a pass")
    native = rp._resolve_native_create()
    assert native is not None
    baseline = _os_handles()
    ledgers = []
    tops = []
    counter = iter(range(1000))

    def build(content: bytes | None = None) -> SimpleNamespace:
        top = tmp_path / f"fx{next(counter)}"
        parent = top / "parent"
        parent.mkdir(parents=True)
        tops.append(top)
        ledger = rp._HandleLedger(rp._LEDGER_KEY, frozenset({rp._KIND_DIRECTORY, rp._KIND_FILE}))
        ledgers.append(ledger)
        root = rp._pin_run_root(ledger, str(parent), _identity(parent))
        d = rp._create_child(ledger, native, root, "d", rp._KIND_DIRECTORY)
        e = rp._create_child(ledger, native, d, "e", rp._KIND_DIRECTORY)
        f = rp._create_child(ledger, native, e, "f", rp._KIND_FILE)
        if content is not None:  # the production ordering: gate first, then content through the creating handle
            rp._gate_exact_set(ledger, e, [f])
            rp._write_verified_content(ledger, f, content, hashlib.sha256(content).hexdigest())
        return SimpleNamespace(
            top=top, parent=str(parent), ledger=ledger, native=native, entries={"P": root, "d": d, "e": e, "f": f},
            path={
                "P": str(parent), "d": str(parent / "d"), "e": str(parent / "d" / "e"), "f": str(parent / "d" / "e" / "f"),
            },
        )

    yield build
    for ledger in ledgers:
        ledger.close_all()
        assert ledger.all_proven_closed() and ledger.open_count == 0
    assert _os_handles() == baseline, "process handle count drifted"
    for top in tops:  # test-owned fixture trees: removed strictly (a surviving tree is a teardown error)
        shutil.rmtree(top, ignore_errors=False)
        assert not top.exists()


def test_b_the_native_construction_handles_hold_the_expected_access(construction):
    fx = construction()
    # P: _pin_run_root (LIST_DIRECTORY | READ_ATTRIBUTES + SYNCHRONIZE from the I/O manager);
    # d, e: the directory shape; f: the file shape (it alone carries DELETE and write access).
    expected = {"d": 0x1 | 0x80 | 0x100000, "e": 0x1 | 0x80 | 0x100000}
    for name, mask in expected.items():
        assert _granted_access(fx.entries[name].raw) == mask, name
    p_mask = _granted_access(fx.entries["P"].raw)
    assert not p_mask & _DELETE and not p_mask & _WRITE_ACCESS_BITS
    f_mask = _granted_access(fx.entries["f"].raw)
    assert f_mask & _DELETE and f_mask & 0x2  # DELETE and WRITE_DATA: the creating handle itself
    _emit({"case": "B granted access", "P": hex(p_mask), "d": hex(_granted_access(fx.entries["d"].raw)), "f": hex(f_mask)})


def test_b_an_empty_pinned_directory_cannot_be_renamed_or_deleted_and_a_released_control_can(construction):
    fx = construction()
    s_entry = rp._create_child(fx.ledger, fx.native, fx.entries["P"], "s", rp._KIND_DIRECTORY)
    s = os.path.join(fx.parent, "s")
    pre = _snap(s, content=False)
    assert rp._raw_identity(s_entry.raw) == s_entry.identity == pre["identity"]
    held = {"rename": actor.run("rename_away", s), "rmdir": actor.run("remove_dir", s)}
    for result in held.values():
        _refused(result, ERROR_SHARING_VIOLATION)
    assert _snap(s, content=False) == pre and not os.path.lexists(s + ".moved")
    assert fx.ledger.close(s_entry) and s_entry.state == rp.HANDLE_CLOSED
    control = {"rename": actor.run("rename_away", s)}
    assert control["rename"]["ok"] and _snap(s + ".moved", content=False)["identity"] == pre["identity"]
    assert actor.rename(s + ".moved", s)["ok"]
    control["rmdir"] = actor.run("remove_dir", s)
    assert control["rmdir"]["ok"] and not os.path.lexists(s)
    _emit({
        "case": "B empty construction directory pin", "filesystem": actor.filesystem_name(fx.parent),
        "handle": "CREATING handle of _create_child (the pin itself)", "access_share": "LIST_DIRECTORY|READ_ATTRIBUTES|SYNCHRONIZE / FILE_SHARE_READ",
        "os_result_held": held, "control_after_release": control, "released_state": s_entry.state,
    })


#: (held handles, operation, target, expected). ``expected`` is the OBSERVED outcome on this
#: build: ``0`` = the call succeeds; otherwise the ``GetLastError`` it fails with. Every row
#: that fails is followed, in the same fixture, by its MATCHED CONTROL: the identical call
#: after every handle was released through the ledger.
#:
#: P, d, e = directory pins (P: _pin_run_root, share READ|WRITE; d, e: native, share READ);
#: f = a native share-0 file. A handle NOT in the held set is CLOSED through the ledger first.
_B_ROWS = [
    # rename a pinned directory: its own pin refuses (sharing), whatever else is or is not held
    ("Pdef", "rename_away", "d", 32), ("Pde", "rename_away", "d", 32), ("Pd", "rename_away", "d", 32),
    ("Pdef", "rename_away", "e", 32), ("e", "rename_away", "e", 32),
    # the OBSERVED side effect: a held share-READ directory pin also refuses rename of its UNHELD children
    ("Pd", "rename_away", "e", 32), ("d", "rename_away", "e", 32), ("Pde", "rename_away", "f", 32),
    # the run-root pin (share READ|WRITE) does NOT refuse rename of a child it parents
    ("P", "rename_away", "d", 0), ("P", "rename_away", "e", 0), ("P", "rename_away", "f", 0), ("", "rename_away", "d", 0),
    # a held file child refuses rename and delete
    ("Pdef", "rename_away", "f", 32), ("Pdef", "delete", "f", 32),
    # nested parent: the pinned directory itself is refused (32); an UNHELD ancestor of any held
    # descendant is refused (5, access denied); with nothing beneath held it is renamable
    ("P", "rename_away", "P", 32), ("Pdef", "rename_away", "P", 32), ("Pf", "rename_away", "P", 32),
    ("d", "rename_away", "P", 5), ("e", "rename_away", "P", 5), ("f", "rename_away", "P", 5),
    ("f", "rename_away", "d", 5), ("e", "rename_away", "d", 5), ("d", "rename_away", "d", 32),
    ("", "rename_away", "P", 0),
    # RELEASED child of a HELD parent: the parent pin does not protect a closed file's name or bytes
    ("Pde", "delete", "f", 0), ("Pde", "open_write_existing", "f", 0), ("Pde", "truncate_existing", "f", 0),
    ("Pde", "replace_by_other", "f", 32),  # refused by the held parent's share mode, not by f
    ("P", "replace_by_other", "f", 0),
    # a HELD file child refuses every overwrite
    ("Pdef", "open_write_existing", "f", 32), ("Pdef", "truncate_existing", "f", 32), ("Pdef", "replace_by_other", "f", 32),
]


@pytest.mark.parametrize("held,op,target,expected", _B_ROWS, ids=[f"{h or 'none'}-{o}-{t}" for h, o, t, _ in _B_ROWS])
def test_b_staged_matrix_over_which_handles_are_held(construction, held, op, target, expected):
    content = b"approved-bytes-for-f"
    fx = construction(content)
    for name in "fed":  # children before parents, as the candidate itself releases
        if name not in held:
            assert fx.ledger.close(fx.entries[name]), name
    if "P" not in held:
        assert fx.ledger.close(fx.entries["P"])
    path = fx.path[target]
    other = None
    if op == "replace_by_other":
        other = (str(fx.top / "other.bin"), b"OTHER-BYTES")
        Path(other[0]).write_bytes(other[1])
    pre = _snap(path, content=False)
    # f's content can be hashed only when no handle on it excludes a reader
    pre_full = _snap(path) if target == "f" and "f" not in held else pre
    result = actor.run(op, path, other[0] if other else None)
    if expected == 0:
        assert result["ok"] is True, f"UNEXPECTED REFUSAL: {result}"
        if op == "rename_away":
            assert _snap(path + ".moved", content=False)["identity"] == pre["identity"]
        _emit({"case": f"B matrix held={held or 'none'} {op} {target}", "result": result, "role": "success (itself a control)"})
        return
    _refused(result, expected)
    assert _snap(path, content=False) == pre and not os.path.lexists(path + ".moved")
    if other:
        assert Path(other[0]).read_bytes() == other[1]
    # the tested handles were still live at the moment of the call
    for name in held:
        assert fx.entries[name].state == rp.HANDLE_OPEN
        assert rp._raw_identity(fx.entries[name].raw) == fx.entries[name].identity
    # MATCHED CONTROL: release everything through the ledger, repeat the identical call
    fx.ledger.close_all()
    assert fx.ledger.all_proven_closed()
    control = actor.run(op, path, other[0] if other else None)
    assert control["ok"] is True, f"control also refused ({control}); the refusal is not attributable to the held handle"
    if op == "rename_away":
        assert _snap(path + ".moved", content=False)["identity"] == pre["identity"]
    elif op == "delete" or op == "remove_dir":
        assert not os.path.lexists(path)
    elif op == "replace_by_other":
        assert Path(path).read_bytes() == other[1]
    else:
        assert Path(path).read_bytes().startswith(actor.PAYLOAD)
    _emit({
        "case": f"B matrix held={held} {op} {target}", "os_result_held": result, "control_after_full_release": control,
        "object_unchanged_while_held": True, "handles_released": True, "pre": pre_full,
    })


def test_b_a_pinned_directory_does_not_stop_a_new_name_being_added_inside_it(construction):
    """Not a refusal -- a LIMIT, recorded so the report cannot overstate it: a share-READ
    directory pin does not prevent an ordinary create of a new name beneath it. That is why the
    exact-set gate is load-bearing. The directory handle's enumeration cursor is single-pass, so the
    gate is the ONLY enumeration of each fixture (the listing below uses a fresh pathname handle).
    A matched fixture without the intruder shows the same gate otherwise passes."""
    clean = construction()
    rp._gate_exact_set(clean.ledger, clean.entries["e"], [clean.entries["f"]])  # control: passes
    assert clean.entries["f"].gate_passed

    fx = construction()
    intruder = os.path.join(fx.path["e"], "intruder.bin")
    result = actor.open_close(intruder, actor.GENERIC_WRITE, actor.CREATE_NEW)
    assert result["ok"] is True
    assert sorted(os.listdir(fx.path["e"])) == ["f", "intruder.bin"]
    with pytest.raises(rp.Cfg1RuntimeProvisionError) as gate:
        rp._gate_exact_set(fx.ledger, fx.entries["e"], [fx.entries["f"]])
    assert gate.value.reason_code == "PARENTAGE_GATE_FAILED" and not fx.entries["f"].gate_passed
    _emit({"case": "B new name inside a pinned directory", "os_result": result, "gate": "PARENTAGE_GATE_FAILED", "control_without_intruder": "gate passed"})


# ---------------------------------------------------------------------------
# C. Share-zero file children
# ---------------------------------------------------------------------------

C_CONTENT = b"approved runtime bytes held through the creating handle"


def _creating_handle_still_refers_to_the_original(child, path, identity) -> None:
    """The creating handle is OPEN, its handle-derived identity is the one recorded when it
    was created and the one found at the path, and its bytes (read through ITSELF, since
    no other handle may read a share-0 file) are the bytes that were written."""
    assert child.state == rp.HANDLE_OPEN
    assert rp._raw_identity(child.raw) == child.identity == identity == _identity(path)
    assert rp._raw_end_of_file(child.raw) == len(C_CONTENT)
    assert rp._raw_read_from_start(child.raw, len(C_CONTENT) + 1) == C_CONTENT


def _share_zero_child(construction, *, parents_held: bool):
    """A native share-0 child ``child.bin`` created in ``e`` by the candidate's own primitive, passed
    through the production gate and given its content through its creating handle.

    ``parents_held=True`` is the construction-time reality: the directory pins ``P``, ``d``, ``e`` (and the
    sibling ``f``) are all still held. ``parents_held=False`` releases every one of them (through the
    ledger, children first) so that the ONLY handle in the system is the child's creating handle: a
    refusal there cannot be a side effect of a held directory pin."""
    fx = construction()
    child = rp._create_child(fx.ledger, fx.native, fx.entries["e"], "child.bin", rp._KIND_FILE)
    rp._gate_exact_set(fx.ledger, fx.entries["e"], [fx.entries["f"], child])  # the production gate, then content
    rp._write_verified_content(fx.ledger, child, C_CONTENT, hashlib.sha256(C_CONTENT).hexdigest())
    if not parents_held:
        for name in ("f", "e", "d", "P"):
            assert fx.ledger.close(fx.entries[name])
        assert fx.ledger.open_count == 1 and child.state == rp.HANDLE_OPEN
    return fx, child, os.path.join(fx.path["e"], "child.bin")


@pytest.mark.parametrize("parents_held", [True, False], ids=["parents-held", "child-alone"])
@pytest.mark.parametrize("op", A_OPS)
def test_c_a_share_zero_child_cannot_be_replaced_or_overwritten_and_a_released_control_can(construction, op, parents_held):
    fx, child, path = _share_zero_child(construction, parents_held=parents_held)
    identity = child.identity
    pre = _snap(path, content=False)
    other = None
    if op == "replace_by_other":
        other = (str(fx.top / "other.bin"), b"OTHER-BYTES")
        Path(other[0]).write_bytes(other[1])
    result = actor.run(op, path, other[0] if other else None)
    _refused(result, *_codes(op))
    assert _snap(path, content=False) == pre and not os.path.lexists(path + ".moved")
    if other:
        assert Path(other[0]).read_bytes() == other[1]
    _creating_handle_still_refers_to_the_original(child, path, identity)  # AFTER the attempt
    assert actor.PAYLOAD not in rp._raw_read_from_start(child.raw, 1 << 16)
    # MATCHED CONTROL: same call, same object, every handle released through the candidate's ledger
    fx.ledger.close_all()
    assert fx.ledger.all_proven_closed() and child.state == rp.HANDLE_CLOSED
    pre_released = _snap(path)
    assert pre_released["identity"] == identity and Path(path).read_bytes() == C_CONTENT  # original bytes survived
    control = actor.run(op, path, other[0] if other else None)
    assert control["ok"] is True, f"control also refused: {control}"
    _assert_control_effect(op, path, pre_released, C_CONTENT, other[0] if other else None, other[1] if other else None)
    _emit({
        "case": f"C share-zero child / {op} / {'parents held' if parents_held else 'child alone'}",
        "filesystem": actor.filesystem_name(fx.parent),
        "handle": "CREATING handle of _create_child, held (never reopened)",
        "access_share": "GENERIC_READ|GENERIC_WRITE|DELETE|SYNCHRONIZE / share 0 / FILE_CREATE|OPEN_REPARSE_POINT",
        "os_result_held": result, "control_after_release": control, "identity_before_after_equal": True,
        "original_bytes_intact_via_creating_handle": True, "released_state": child.state,
    })


def test_c_a_share_zero_child_refuses_every_data_or_delete_open_and_attribute_only_open_is_the_recorded_exception(construction):
    fx, child, path = _share_zero_child(construction, parents_held=False)  # the child's own handle is the only one
    identity = child.identity
    held, control = {}, {}
    for op in ("open_read", "open_read_data", "open_write", "open_read_write", "open_delete_access"):
        held[op] = actor.run(op, path)
        _refused(held[op], ERROR_SHARING_VIOLATION)
    # RECORDED, not asserted away: an open that requests only FILE_READ_ATTRIBUTES is not subject to the
    # share check on this build. It grants no data or delete access, and it is a limit of what "share 0" means.
    held["open_read_attributes"] = actor.run("open_read_attributes", path)
    assert held["open_read_attributes"]["ok"] is True
    held["create_new"] = actor.run("create_new", path)
    _refused(held["create_new"], ERROR_FILE_EXISTS)
    for name, attempt in {  # the calls an ordinary program makes
        "open_rb": lambda: open(path, "rb"), "open_wb": lambda: open(path, "wb"), "open_r+b": lambda: open(path, "r+b"),
        "os.remove": lambda: os.remove(path), "os.rename": lambda: os.rename(path, path + ".moved"),
    }.items():
        held["python:" + name] = _python_refusal(attempt)
    assert not os.path.lexists(path + ".moved")
    _creating_handle_still_refers_to_the_original(child, path, identity)
    fx.ledger.close_all()
    for op in ("open_read", "open_read_data", "open_write", "open_read_write", "open_delete_access", "open_read_attributes"):
        control[op] = actor.run(op, path)
        assert control[op]["ok"] is True, op  # the SAME opens succeed once the creating handle is released
    _emit({"case": "C share-zero child / opens", "os_result_held": held, "control_after_release": control})


def test_c_exclusive_creation_refuses_an_occupied_name_with_the_real_nt_status(construction):
    fx, child, path = _share_zero_child(construction, parents_held=True)  # a create needs the parent handle
    identity = child.identity
    parent_raw = fx.ledger.raw_handle(fx.entries["e"], rp._KIND_DIRECTORY)
    observed = {}
    for name, kind in (("child.bin", rp._KIND_FILE), ("CHILD.BIN", rp._KIND_FILE), ("child.bin", rp._KIND_DIRECTORY), ("f", rp._KIND_FILE)):
        before = fx.ledger.entry_count
        status, entry, information = rp._native_relative_create(fx.ledger, fx.native, parent_raw, name, kind)
        assert status == STATUS_OBJECT_NAME_COLLISION, hex(status)  # the OS's own status, not ours
        assert entry is None and information != rp._FILE_CREATED
        assert fx.ledger.entry_count == before  # no handle came back, nothing to leak
        observed[f"{name}/{kind}"] = hex(status)
        with pytest.raises(rp.Cfg1RuntimeProvisionError) as refused:  # and through the production wrapper
            rp._create_child(fx.ledger, fx.native, fx.entries["e"], name, kind)
        assert refused.value.reason_code == "NATIVE_CREATE_REFUSED"
    # nothing was created, replaced or truncated by the refused attempts (a fresh pathname listing:
    # the directory handle's own enumeration cursor was already consumed by the production gate)
    assert sorted(os.listdir(fx.path["e"])) == ["child.bin", "f"]
    _creating_handle_still_refers_to_the_original(child, path, identity)
    # MATCHED CONTROL: the collision is about the NAME, so it persists once the child's handle is released
    assert fx.ledger.close(child)
    status, entry, _ = rp._native_relative_create(fx.ledger, fx.native, parent_raw, "child.bin", rp._KIND_FILE)
    assert status == STATUS_OBJECT_NAME_COLLISION and entry is None
    assert Path(path).read_bytes() == C_CONTENT and _identity(path) == identity
    assert sorted(os.listdir(fx.path["e"])) == ["child.bin", "f"]
    _emit({"case": "C exclusive creation of an occupied name", "nt_status": observed, "control_after_child_released": hex(status)})


def test_c_the_creating_handle_keeps_the_original_object_across_every_refused_attempt(construction):
    """Every refused operation in one sequence against ONE held child with nothing else held."""
    fx, child, path = _share_zero_child(construction, parents_held=False)
    identity = child.identity
    other = str(fx.top / "other.bin")
    Path(other).write_bytes(b"OTHER-BYTES")
    for op in A_OPS:
        _refused(actor.run(op, path, other if op == "replace_by_other" else None), *_codes(op))
        _creating_handle_still_refers_to_the_original(child, path, identity)
    assert child.gate_passed and rp._raw_is_plain(child.raw, rp._KIND_FILE)
    assert Path(other).read_bytes() == b"OTHER-BYTES" and sorted(os.listdir(fx.path["e"])) == ["child.bin", "f"]
    _emit({"case": "C creating handle identity across all attempts", "identity_unchanged": True, "attempts": len(A_OPS)})
