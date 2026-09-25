"""FU1 AMEND2 (Y6): the retained exact-object authority and the handle-bound
CONTENT scrub -- the primitive re-proofs and Tests Y-1 ... Y-25.

Scope statement, exact. Every test here proves that AIDO's L24 / writer paths
scrub the default data stream of the exact file object AIDO created, through a
handle descended from its creating handle, whatever the object's names are. **No
test here asserts, or is named as proving, secure or forensic erasure**, and a
``True``-outstanding row asserts the durable/local FACT only, never that bytes
are gone.

Everything runs the GENUINE writers and the GENUINE Win32 primitives against
synthetic workspaces under pytest's temporary directories (an "outside the root"
location is a sibling ``tmp_path`` directory on the same volume), with a
synthetic ``.invalid`` endpoint and a synthetic token. Faults are injected only
through module seams (retain, identity read, inheritance read, registration,
truncate, flush, ``EndOfFile`` query, H_s/H_r close), never by monkeypatching
``kernel32``. No Node, no Pi, no socket, no credential.
"""

from __future__ import annotations

import builtins
import copy
import ctypes
import ctypes.wintypes as wt
import inspect
import msvcrt
import os
import pickle
import re
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
from cfg1_issuance_cleanup import discard_config_for_test, discard_extension_for_test
from cfg1_doubles import FakeSupervisor, build_doubled_ports, seam_digests_all_match
from cfg1_fu1_support import HandleLog, make_admission

from pi_harness_cfg1 import (
    cfg1_extension,
    cfg1_pi_config,
    config_issuance,
    extension_issuance,
    run_executor,
    run_workspace,
    stage_runner,
)
from pi_harness_cfg1 import win_config_authority as win
from pi_harness_cfg1.cfg1_extension import Cfg1ExtensionError, write_cfg1_extension
from pi_harness_cfg1.cfg1_pi_config import (
    CFG1_CONFIG_DIR_NAME,
    Cfg1PiConfigError,
    write_cfg1_pi_config,
)
from pi_harness_cfg1.halt import _resolve_halt_reason_code
from pi_harness_cfg1.records import _require_valid_cfg1_run_payload_v2, build_cfg1_run_payload
from pi_harness_cfg1.run_executor import execute_cfg1_run

SYNTHETIC_BASE_URL = "https://cfg1-fu1-y6.invalid/v1"
SYNTHETIC_PIPE = "\\\\.\\pipe\\cfg1-fu1-y6-pipe"
SYNTHETIC_CAPABILITY = "cfg1-fu1-y6-capability"
SYNTHETIC_TOKEN = "cfg1-fu1-y6-synthetic-token-not-a-secret"

_ALL_SHARE = win.FILE_SHARE_READ | win.FILE_SHARE_WRITE | win.FILE_SHARE_DELETE
_NOFOLLOW = win.FILE_FLAG_OPEN_REPARSE_POINT

pytestmark = pytest.mark.skipif(not win.PLATFORM_SUPPORTED, reason="Win32 only")


# ---------------------------------------------------------------------------
# Scaffolding
# ---------------------------------------------------------------------------

_K = ctypes.WinDLL("kernel32", use_last_error=True)
_K.CreateFileMappingW.restype = ctypes.c_void_p
_K.CreateFileMappingW.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, wt.DWORD, wt.DWORD, wt.DWORD, wt.LPCWSTR,
]
_K.MapViewOfFile.restype = ctypes.c_void_p
_K.MapViewOfFile.argtypes = [ctypes.c_void_p, wt.DWORD, wt.DWORD, wt.DWORD, ctypes.c_size_t]
_K.UnmapViewOfFile.restype = wt.BOOL
_K.UnmapViewOfFile.argtypes = [ctypes.c_void_p]
_K.ReadFile.restype = wt.BOOL
_K.ReadFile.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, wt.DWORD, ctypes.POINTER(wt.DWORD), ctypes.c_void_p,
]
_PAGE_READONLY = 2
_FILE_MAP_READ = 4


@pytest.fixture()
def workspace(git_executable):
    handle, _built = run_workspace.mint_cfg1_run_workspace(git_executable=git_executable)
    root = handle.experiment_root
    try:
        yield handle
    finally:
        run_workspace.discard_cfg1_run_workspace(handle)
        shutil.rmtree(root, ignore_errors=True)


def _write_extension(handle, **kwargs):
    values = dict(pipe_name=SYNTHETIC_PIPE, capability_id=SYNTHETIC_CAPABILITY, token=SYNTHETIC_TOKEN)
    values.update(kwargs)
    return write_cfg1_extension(handle, **values)


class _Target:
    """One of the two sensitive objects, driven through its genuine writer."""

    def __init__(self, which: str, workspace) -> None:
        self.which = which
        self.workspace = workspace
        self.config = which == "models.json"
        folder = CFG1_CONFIG_DIR_NAME if self.config else "pi_extension"
        self.path = Path(workspace.experiment_root) / folder / which
        self.error_type = Cfg1PiConfigError if self.config else Cfg1ExtensionError

    def generate(self) -> str:
        if self.config:
            return write_cfg1_pi_config(
                self.workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL
            ).issuance_token
        return _write_extension(self.workspace).issuance_token

    def call_writer(self):
        return self.generate()

    def scrub(self, token) -> bool:
        module = config_issuance if self.config else extension_issuance
        fn = module.scrub_config_issuance if self.config else module.scrub_extension_issuance
        return fn(token=token, workspace=self.workspace)

    def discard(self, token) -> None:
        if self.config:
            discard_config_for_test(token)
        else:
            discard_extension_for_test(token)

    def issued(self) -> int:
        return (
            config_issuance.issued_token_count()
            if self.config
            else extension_issuance.issued_extension_token_count()
        )

    def outstanding(self, error) -> object:
        return getattr(
            error, "endpoint_material_outstanding" if self.config else "token_material_outstanding"
        )

    def identity(self) -> tuple[int, int]:
        st = os.stat(self.path)
        return st.st_dev, st.st_ino

    @property
    def fact(self) -> str:
        return "generated_config_scrub_verified" if self.config else "extension_binding_scrub_verified"


@pytest.fixture(params=["models.json", "ar2_config.ts"])
def target(request, workspace):
    return _Target(request.param, workspace)


def _open_foreign(path, access=win.GENERIC_READ):
    """A foreign (same-user) handle to ``path`` with every sharing right."""
    return win._create_file(str(path), access, _ALL_SHARE, win.OPEN_EXISTING, _NOFOLLOW)


def _map_view(path):
    """A foreign user-mapped view of ``path``, its file and section handles closed."""
    handle = _open_foreign(path)
    assert handle is not None
    section = _K.CreateFileMappingW(handle, None, _PAGE_READONLY, 0, 0, None)
    assert section, "the mapping could not be created"
    view = _K.MapViewOfFile(section, _FILE_MAP_READ, 0, 0, 0)
    assert view, "the view could not be mapped"
    win._K32.CloseHandle(section)
    win._K32.CloseHandle(handle)
    return view


class _PathnameOpenSpy:
    """Counts every pathname-based open reachable from the CFG1 code."""

    def __init__(self, monkeypatch) -> None:
        self.calls: list[str] = []
        real_create, real_os_open, real_open = win._create_file, os.open, builtins.open

        def _create(path, *a, **k):
            self.calls.append(f"CreateFileW:{path}")
            return real_create(path, *a, **k)

        def _os_open(path, *a, **k):
            self.calls.append(f"os.open:{path}")
            return real_os_open(path, *a, **k)

        def _open(file, *a, **k):
            self.calls.append(f"open:{file}")
            return real_open(file, *a, **k)

        monkeypatch.setattr(win, "_create_file", _create)
        monkeypatch.setattr(os, "open", _os_open)
        monkeypatch.setattr(builtins, "open", _open)


def _alias_on_write(monkeypatch, target: _Target, alias: Path) -> None:
    """Create a hard link to the sensitive object while the writer's H_c is held."""
    real = win.write_child_text

    def _write(child, text):
        if win.child_name(child) == target.which and not alias.exists():
            os.link(target.path, alias)  # the accepted Y-6 behavior: it SUCCEEDS
        return real(child, text)

    monkeypatch.setattr(win, "write_child_text", _write)


def _run_l21_hook(monkeypatch, git_executable, hook, *, at_removal=None):
    seam_digests_all_match(monkeypatch)
    holder: dict = {}

    class _Hooked(FakeSupervisor):
        def shutdown(self):
            hook(holder["made"]["workspace"])
            return super().shutdown()

    supervisor = _Hooked()
    ports, made = build_doubled_ports(
        git_executable=git_executable, overrides={"build_supervisor": lambda **_k: supervisor}
    )
    holder["made"] = made
    removals: list[set] = []
    real_remove = run_workspace.remove_cfg1_run_workspace

    def _remove(handle):
        root = Path(handle.experiment_root)
        removals.append({str(p.relative_to(root)) for p in root.rglob("*")})
        if at_removal is not None:
            at_removal(handle)
        return real_remove(handle)

    monkeypatch.setattr(run_workspace, "remove_cfg1_run_workspace", _remove)
    return execute_cfg1_run(make_admission(), ports=ports), made, removals


def _assert_lifecycle_unproven(outcome) -> None:
    observations = outcome.observations
    assert "L24" in observations["lifecycle_failure_steps"]
    assert observations["lifecycle_all_closed"] is False
    assert observations["verification_attempted"] is False
    assert observations["verification_skip_reason"] == "LIFECYCLE_UNPROVEN"
    payload = build_cfg1_run_payload(
        stage_id="S1", stage_execution_id="S1-X1", run_ordinal=1, observations=observations
    )
    _require_valid_cfg1_run_payload_v2(payload)
    assert payload["run_classification"] == "INDETERMINATE_LIFECYCLE"
    assert _resolve_halt_reason_code(
        emission_status="RECORD_EMITTED",
        halt_triggered_by_this_run=False,
        lifecycle_all_closed=False,
        run_classification=payload["run_classification"],
        registries_empty=True,
    ) == "LIFECYCLE_CLOSURE_UNPROVEN"


# ---------------------------------------------------------------------------
# Platform primitives (AMEND2 §3), re-proved on THIS host under tmp_path.
# Raw handles only: nothing here touches the repository's issuance machinery.
# ---------------------------------------------------------------------------


class _Raw:
    """A CREATE_NEW share-0 creating handle H_c on a synthetic file."""

    def __init__(self, path: Path, data: bytes = b'{"sensitive": "synthetic"}\n') -> None:
        self.path = path
        handle = win._create_file(
            str(path),
            win.GENERIC_READ | win.GENERIC_WRITE | win.DELETE,
            0,
            win.CREATE_NEW,
            _NOFOLLOW,
        )
        assert handle is not None
        self.fd = msvcrt.open_osfhandle(handle, os.O_RDWR)
        self.hc = msvcrt.get_osfhandle(self.fd)
        os.write(self.fd, data)
        self.closed = False

    def close_creating(self) -> None:
        if not self.closed:
            os.close(self.fd)
            self.closed = True


@pytest.fixture()
def raw(tmp_path):
    made: list[_Raw] = []
    held: list[int] = []

    def _make(name="sensitive.json", **kw):
        item = _Raw(tmp_path / name, **kw)
        made.append(item)
        return item

    _make.held = held
    yield _make
    for item in made:
        item.close_creating()
    for handle in held:
        win._K32.CloseHandle(handle)


def _retain_raw(item: _Raw, raw_factory) -> int:
    handle = win._reopen_file(item.hc, 0, _ALL_SHARE, _NOFOLLOW)
    assert handle is not None
    raw_factory.held.append(handle)
    return handle


def test_p1_p2_p3_retain_from_the_creating_handle_proves_identity_and_no_inheritance(raw):
    item = raw()
    # CREATE_NEW / share 0: a data open of the name while held is refused, and a
    # second CREATE_NEW is refused.
    assert _open_foreign(item.path) is None
    assert win._create_file(str(item.path), win.GENERIC_READ, 0, win.CREATE_NEW, _NOFOLLOW) is None
    retained = _retain_raw(item, raw)
    assert win._handle_identity(retained) == win._handle_identity(item.hc)
    stat = os.stat(item.path)
    assert win._handle_identity(retained) == (stat.st_dev, stat.st_ino)
    assert win._handle_inheritable(retained) is False
    # Zero access: H_r can neither read nor write nor truncate.
    buffer = ctypes.create_string_buffer(8)
    read = wt.DWORD(0)
    assert not _K.ReadFile(retained, buffer, 8, ctypes.byref(read), None)
    assert ctypes.get_last_error() == 5  # ERROR_ACCESS_DENIED
    assert win._truncate_handle(retained) is False


def test_p4_ordinary_runtime_reads_work_while_the_retained_handle_is_held(raw):
    item = raw()
    retained = _retain_raw(item, raw)
    item.close_creating()
    assert item.path.read_bytes().startswith(b'{"sensitive"')
    reader = win._create_file(
        str(item.path), win.GENERIC_READ, win.FILE_SHARE_READ, win.OPEN_EXISTING, _NOFOLLOW
    )
    assert reader is not None
    win._K32.CloseHandle(reader)
    # Even an exclusive share-0 read/write open succeeds: H_r takes no part.
    exclusive = win._create_file(
        str(item.path), win.GENERIC_READ | win.GENERIC_WRITE, 0, win.OPEN_EXISTING, _NOFOLLOW
    )
    assert exclusive is not None
    win._K32.CloseHandle(exclusive)
    assert win._handle_identity(retained) == (os.stat(item.path).st_dev, os.stat(item.path).st_ino)


def test_p5_rename_and_hard_links_do_not_invalidate_the_retained_identity(raw, tmp_path):
    item = raw()
    pre_alias = tmp_path / "pre_alias.json"
    os.link(item.path, pre_alias)  # created while H_c is held
    retained = _retain_raw(item, raw)
    identity = win._handle_identity(retained)
    item.close_creating()
    inside, outside = tmp_path / "post_inside.json", tmp_path / "outside" / "post_outside.json"
    outside.parent.mkdir()
    os.link(pre_alias, inside)
    os.link(pre_alias, outside)
    renamed = tmp_path / "outside" / "renamed_away.json"
    os.rename(item.path, renamed)
    item.path.write_bytes(b"foreign occupant")
    assert win._handle_identity(retained) == identity
    for name in (pre_alias, inside, outside, renamed):
        stat = os.stat(name)
        assert (stat.st_dev, stat.st_ino) == identity
    foreign = os.stat(item.path)
    assert (foreign.st_dev, foreign.st_ino) != identity


def test_p6_p7_p8_the_scrub_handle_reaches_the_same_object_and_every_name(raw, tmp_path):
    item = raw()
    pre_alias = tmp_path / "pre_alias.json"
    os.link(item.path, pre_alias)
    retained = _retain_raw(item, raw)
    identity = win._handle_identity(retained)
    item.close_creating()
    renamed = tmp_path / "outside"
    renamed.mkdir()
    renamed = renamed / "renamed.json"
    os.rename(item.path, renamed)
    item.path.write_bytes(b"foreign occupant")
    foreign_id = os.stat(item.path).st_ino
    scrub_handle = win._reopen_file(
        retained, win.GENERIC_WRITE | win.FILE_READ_ATTRIBUTES, 0, _NOFOLLOW
    )
    assert scrub_handle is not None
    assert win._handle_identity(scrub_handle) == identity
    assert win._handle_inheritable(scrub_handle) is False
    # share-0: no other data-access handle can be opened through ANY link (X1).
    assert _open_foreign(pre_alias) is None and _open_foreign(renamed) is None
    # ...but a link CAN still be created, and it is the same object (X1, P7).
    during = tmp_path / "created_during_scrub.json"
    os.link(renamed, during)
    assert win._scrub_open_handle(scrub_handle) is True
    assert win._end_of_file_is_exactly_zero(scrub_handle) is True
    win._K32.CloseHandle(scrub_handle)
    for name in (pre_alias, renamed, during):
        assert os.stat(name).st_size == 0 and name.read_bytes() == b""
    assert item.path.read_bytes() == b"foreign occupant"  # untouched
    assert os.stat(item.path).st_ino == foreign_id


def test_p9_each_handle_release_is_separately_observable(raw):
    item = raw()
    retained = win._reopen_file(item.hc, 0, _ALL_SHARE, _NOFOLLOW)
    item.close_creating()
    scrub_handle = win._reopen_file(
        retained, win.GENERIC_WRITE | win.FILE_READ_ATTRIBUTES, 0, _NOFOLLOW
    )
    assert win._close_handle(scrub_handle, "scrub_handle") is True
    flags = wt.DWORD(0)
    assert win._K32.GetHandleInformation(retained, ctypes.byref(flags))  # H_r still valid
    assert win._close_handle(retained, "retained") is True
    assert not win._K32.GetHandleInformation(retained, ctypes.byref(flags))
    assert ctypes.get_last_error() == 6  # ERROR_INVALID_HANDLE


def test_x2_a_foreign_data_handle_refuses_the_scrub_reopen(raw, tmp_path):
    item = raw()
    alias = tmp_path / "alias.json"
    os.link(item.path, alias)
    retained = _retain_raw(item, raw)
    item.close_creating()
    foreign = _open_foreign(alias)
    assert foreign is not None
    try:
        assert (
            win._reopen_file(retained, win.GENERIC_WRITE | win.FILE_READ_ATTRIBUTES, 0, _NOFOLLOW)
            is None
        )
    finally:
        win._K32.CloseHandle(foreign)


def test_x3_a_user_mapped_view_refuses_truncation(raw, tmp_path):
    item = raw()
    alias = tmp_path / "alias.json"
    os.link(item.path, alias)
    retained = _retain_raw(item, raw)
    item.close_creating()
    view = _map_view(alias)
    try:
        scrub_handle = win._reopen_file(
            retained, win.GENERIC_WRITE | win.FILE_READ_ATTRIBUTES, 0, _NOFOLLOW
        )
        assert scrub_handle is not None  # share access is released at last cleanup
        assert win._truncate_handle(scrub_handle) is False  # ERROR_USER_MAPPED_FILE
        win._K32.CloseHandle(scrub_handle)
    finally:
        _K.UnmapViewOfFile(view)


def test_x4_an_object_whose_every_name_was_deleted_is_still_reached(raw):
    item = raw()
    retained = _retain_raw(item, raw)
    item.close_creating()
    os.unlink(item.path)
    scrub_handle = win._reopen_file(
        retained, win.GENERIC_WRITE | win.FILE_READ_ATTRIBUTES, 0, _NOFOLLOW
    )
    assert scrub_handle is not None
    assert win._scrub_open_handle(scrub_handle) is True
    win._K32.CloseHandle(scrub_handle)


# ---------------------------------------------------------------------------
# Y-1 ... Y-9': the retained handle bridges writer -> runtime -> L24
# ---------------------------------------------------------------------------


def test_y1_the_retained_handle_bridges_writer_runtime_and_l24(target, monkeypatch):
    token = target.generate()
    identity = target.identity()
    failures = win.close_failure_count()
    assert win.held_retained_count() == 1
    # During the ACTIVE issuance, pathname reads succeed.
    assert target.path.read_bytes() != b""
    reader = win._create_file(
        str(target.path), win.GENERIC_READ, win.FILE_SHARE_READ, win.OPEN_EXISTING, _NOFOLLOW
    )
    assert reader is not None
    win._K32.CloseHandle(reader)
    seen: list = []
    real = win._handle_identity
    monkeypatch.setattr(win, "_handle_identity", lambda h: (seen.append(real(h)), seen[-1])[1])
    assert target.scrub(token) is True
    assert target.path.stat().st_size == 0
    assert seen and seen[-1] == identity  # H_s's identity == the identity at creation
    assert win.held_retained_count() == 0
    assert target.issued() == 0
    assert win.close_failure_count() == failures


def test_y2_an_alias_created_before_issuance_is_scrubbed(target, monkeypatch, tmp_path):
    alias = tmp_path / "alias_before_issuance.json"
    real = win.retain_child

    def _retain(child, **kw):
        os.link(target.path, alias)  # H_c is held: the link is created (Y-6 behavior)
        return real(child, **kw)

    monkeypatch.setattr(win, "retain_child", _retain)
    token = target.generate()
    assert alias.exists() and alias.read_bytes() == target.path.read_bytes() != b""
    assert target.scrub(token) is True
    assert alias.read_bytes() == b"" and target.path.read_bytes() == b""


def test_y3_an_alias_created_after_issuance_is_scrubbed(target, tmp_path):
    token = target.generate()
    alias = tmp_path / "alias_after_issuance.json"
    os.link(target.path, alias)
    assert target.scrub(token) is True
    assert alias.read_bytes() == b"" and target.path.read_bytes() == b""


@pytest.mark.parametrize("where", ["same_directory", "elsewhere_in_root", "outside_root"])
def test_y4_a_renamed_object_is_scrubbed_and_no_pathname_is_opened(
    where, target, monkeypatch, tmp_path
):
    token = target.generate()
    root = Path(target.workspace.experiment_root)
    if where == "same_directory":
        destination = target.path.parent / "leak.bin"
    elif where == "elsewhere_in_root":
        (root / "elsewhere").mkdir()
        destination = root / "elsewhere" / "leak.bin"
    else:
        (tmp_path / "outside").mkdir()
        destination = tmp_path / "outside" / "leak.bin"
    os.rename(target.path, destination)
    spy = _PathnameOpenSpy(monkeypatch)
    assert target.scrub(token) is True
    assert spy.calls == []  # L24 opened no pathname at all
    monkeypatch.undo()
    assert destination.read_bytes() == b"" and destination.stat().st_size == 0
    assert not target.path.exists()


def test_y5_a_foreign_same_name_replacement_after_a_rename_is_untouched(target, tmp_path):
    token = target.generate()
    renamed = target.path.parent / "leak.bin"
    os.rename(target.path, renamed)
    target.path.write_bytes(b"foreign occupant, not created by CFG1")
    before = (target.path.read_bytes(), os.stat(target.path).st_ino)
    assert target.scrub(token) is True
    assert (target.path.read_bytes(), os.stat(target.path).st_ino) == before
    assert renamed.read_bytes() == b""


def test_y6p_aliases_inside_and_outside_the_root_at_once(monkeypatch, git_executable, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    inside_names: list[str] = []
    seen: dict = {}

    def _hook(handle):
        root = Path(handle.experiment_root)
        for index, (folder, name) in enumerate(
            ((CFG1_CONFIG_DIR_NAME, "models.json"), ("pi_extension", "ar2_config.ts"))
        ):
            target = root / folder / name
            os.link(target, root / f"alias_in_root_{index}.bin")
            os.link(target, outside / f"alias_outside_{index}.bin")
            inside_names.append(f"alias_in_root_{index}.bin")

    def _at_removal(handle):
        root = Path(handle.experiment_root)
        seen["inside"] = [(root / name).stat().st_size for name in inside_names]

    outcome, _made, removals = _run_l21_hook(
        monkeypatch, git_executable, _hook, at_removal=_at_removal
    )
    observations = outcome.observations
    assert observations["generated_config_scrub_verified"] is True
    assert observations["extension_binding_scrub_verified"] is True
    assert seen["inside"] == [0, 0]  # every in-root alias reads zero at L27 time
    # L24 deleted no alias: they were all still there when L27 took the root.
    assert removals and all(name in removals[0] for name in inside_names)
    # L27 removed only in-root names; the outside aliases persist at length 0.
    assert observations["workspace_removed_verified"] is True
    for index in (0, 1):
        alias = outside / f"alias_outside_{index}.bin"
        assert alias.exists() and alias.stat().st_size == 0 and alias.read_bytes() == b""


def test_y7p_an_alias_created_during_l24_is_scrubbed_and_data_opens_are_refused(
    target, monkeypatch, tmp_path
):
    token = target.generate()
    alias = tmp_path / "created_during_l24.json"
    observed: dict = {}
    real = win._truncate_handle

    def _truncate(handle):
        # Between the H_s reopen and the truncate.
        os.link(target.path, alias)  # link creation succeeds
        try:
            builtins.open(alias, "rb").close()
            observed["data_open"] = "SUCCEEDED"
        except OSError:
            observed["data_open"] = "REFUSED"
        return real(handle)

    monkeypatch.setattr(win, "_truncate_handle", _truncate)
    assert target.scrub(token) is True
    assert observed == {"data_open": "REFUSED"}  # a sharing violation
    assert alias.read_bytes() == b""


def test_y8p_every_name_observes_endoffile_zero_by_metadata_and_by_read(target, tmp_path):
    root = Path(target.workspace.experiment_root)
    token = target.generate()
    names = [target.path]
    for label, folder in (("a", target.path.parent), ("b", root), ("c", tmp_path)):
        alias = folder / f"alias_{label}.bin"
        os.link(target.path, alias)
        names.append(alias)
    (tmp_path / "outside").mkdir()
    moved = tmp_path / "outside" / "moved.bin"
    os.rename(names[1], moved)
    names[1] = moved
    assert target.scrub(token) is True
    for name in names:
        assert os.stat(name).st_size == 0
        assert name.read_bytes() == b""


@pytest.mark.parametrize("swap", ["rename_and_plant", "delete_and_plant"])
def test_y9p_a_foreign_replacement_is_byte_identical_and_keeps_its_file_id(
    swap, target, tmp_path
):
    token = target.generate()
    if swap == "rename_and_plant":
        os.rename(target.path, target.path.parent / "moved_away.bin")
    else:
        os.unlink(target.path)
    target.path.write_bytes(b"foreign bytes 3f1a")
    stat = os.stat(target.path)
    assert target.scrub(token) is True
    assert target.path.read_bytes() == b"foreign bytes 3f1a"
    assert os.stat(target.path).st_ino == stat.st_ino


# ---------------------------------------------------------------------------
# Y-10 ... Y-13: writer failure paths, each with an alias made while H_c is held
# ---------------------------------------------------------------------------


def _fail_reopen_on_call(monkeypatch, index: int) -> None:
    real = win._reopen_file
    calls: list[int] = []

    def _reopen(handle, access, share, flags):
        calls.append(1)
        if len(calls) == index:
            return None
        return real(handle, access, share, flags)

    monkeypatch.setattr(win, "_reopen_file", _reopen)


def _arm_identity_fault(monkeypatch, *, inheritable: bool) -> None:
    if inheritable:
        monkeypatch.setattr(win, "_handle_inheritable", lambda handle: True)
        return
    real_retain, real_identity = win.retain_child, win._handle_identity
    state = {"on": False, "n": 0}

    def _retain(child, **kw):
        state.update(on=True, n=0)
        try:
            return real_retain(child, **kw)
        finally:
            state["on"] = False

    def _identity(handle):
        result = real_identity(handle)
        if state["on"]:
            state["n"] += 1
            if state["n"] == 2:  # the retained handle's own reading
                return (result[0], result[1] + 1)
        return result

    monkeypatch.setattr(win, "retain_child", _retain)
    monkeypatch.setattr(win, "_handle_identity", _identity)


def _inject_point(point: str, target: _Target, monkeypatch, log: HandleLog) -> None:
    if point == "partial_write":
        real = win.write_child_text

        def _write(child, text):
            if win.child_name(child) == target.which:
                real(child, text[:20])
                raise win.Cfg1DirectoryAuthorityError("CONFIG_FILES_NOT_WRITTEN")
            return real(child, text)

        monkeypatch.setattr(win, "write_child_text", _write)
    elif point == "readback":
        monkeypatch.setattr(
            win, "read_child_bytes",
            lambda child: (_ for _ in ()).throw(win.Cfg1DirectoryAuthorityError("X")),
        )
    elif point == "shape_mismatch":
        if target.config:
            from pi_harness_cfg1.arms import ARM_REDACTED_DIGEST

            monkeypatch.setitem(ARM_REDACTED_DIGEST, "Q", "0" * 64)
        else:
            real = win.read_child_bytes
            monkeypatch.setattr(win, "read_child_bytes", lambda child: real(child) + b" ")
    elif point == "retain_fails":
        _fail_reopen_on_call(monkeypatch, 1)
    elif point == "identity_mismatch":
        _arm_identity_fault(monkeypatch, inheritable=False)
    elif point == "inheritable":
        _arm_identity_fault(monkeypatch, inheritable=True)
    elif point == "register_before_insert":
        if target.config:
            monkeypatch.setattr(
                config_issuance, "register_config_issuance",
                lambda **k: (_ for _ in ()).throw(config_issuance.ConfigIssuanceError("X")),
            )
        else:
            monkeypatch.setattr(
                extension_issuance, "register_extension_issuance",
                lambda **k: (_ for _ in ()).throw(extension_issuance.ExtensionIssuanceError("X")),
            )
    elif point == "raise_after_insert":
        if target.config:
            monkeypatch.setattr(
                cfg1_pi_config, "settings_digest",
                lambda: (_ for _ in ()).throw(RuntimeError("after insert")),
            )
        else:
            monkeypatch.setattr(
                cfg1_extension, "GeneratedCfg1Extension",
                lambda token: (_ for _ in ()).throw(RuntimeError("after insert")),
            )
    else:
        raise AssertionError(point)


#: (point, injected handle fault, ``*_material_outstanding`` expected).
_Y10_ROWS = [
    ("partial_write", "none", False),
    ("readback", "none", False),
    ("shape_mismatch", "none", False),
    ("retain_fails", "none", False),
    ("identity_mismatch", "none", False),
    ("inheritable", "none", False),
    ("register_before_insert", "none", False),
    ("raise_after_insert", "none", False),
    ("partial_write", "dispose_fails", False),
    ("raise_after_insert", "dispose_fails", False),
    ("partial_write", "scrub_fails", True),
    ("raise_after_insert", "scrub_fails", True),
    ("partial_write", "creating_close_fails", True),
    ("raise_after_insert", "creating_close_fails", True),
    ("identity_mismatch", "retained_release_fails", True),
    ("register_before_insert", "retained_release_fails", True),
    ("raise_after_insert", "retained_release_fails", True),
]


@pytest.mark.parametrize("point,fault,expected", _Y10_ROWS)
def test_y10_every_writer_failure_row_scrubs_an_alias_made_while_h_c_was_held(
    point, fault, expected, target, monkeypatch, tmp_path
):
    log = HandleLog(monkeypatch)
    if fault == "dispose_fails":
        log.dispose_result[target.which] = False
    elif fault == "scrub_fails":
        log.scrub_result[target.which] = False
    elif fault == "creating_close_fails":
        log.close_fails.add(target.which)
    elif fault == "retained_release_fails":
        log.retained_close_fails = True
    alias = tmp_path / "alias_during_writer.bin"
    _alias_on_write(monkeypatch, target, alias)
    _inject_point(point, target, monkeypatch, log)
    issued_before = target.issued()
    try:
        # The extension writer propagates an UNANTICIPATED exception untyped
        # (R6 Sec. 9.2a): it is released exactly like a known failure but
        # carries no outstanding bool, so the executor never credits it (G6).
        untyped = not target.config and point == "raise_after_insert"
        with pytest.raises(RuntimeError if untyped else target.error_type) as excinfo:
            target.call_writer()
        if not untyped:
            assert target.outstanding(excinfo.value) is expected
        assert target.issued() == issued_before
        assert win.held_retained_count() == 0
        if expected is False:
            assert alias.exists(), "the alias was created while H_c was held"
            assert alias.read_bytes() == b"" and alias.stat().st_size == 0
        # In a True row the test asserts the FACT only: nothing about the bytes.
    finally:
        log.release_leaks()


@pytest.mark.parametrize("where", ["config", "extension"])
def test_y11_a_retain_failure_scrubs_through_h_c_registers_nothing_and_is_proven(
    where, monkeypatch, git_executable
):
    _fail_reopen_on_call(monkeypatch, 1 if where == "config" else 2)
    seam_digests_all_match(monkeypatch)
    ports, _made = build_doubled_ports(git_executable=git_executable)
    outcome = execute_cfg1_run(make_admission(), ports=ports)
    observations = outcome.observations
    failed_step = "L9" if where == "config" else "L11"
    assert observations["refused_at_step"] == failed_step
    key = "generated_config_scrub_verified" if where == "config" else "extension_binding_scrub_verified"
    assert observations[key] is True  # an exact typed False, scrub and closes proven
    assert config_issuance.issued_token_count() == 0
    assert extension_issuance.issued_extension_token_count() == 0
    assert win.held_retained_count() == 0


@pytest.mark.parametrize("defect", ["identity_mismatch", "inheritable"])
@pytest.mark.parametrize("release", ["ok", "fails"])
def test_y12_an_unproven_retained_handle_is_never_written_through(
    defect, release, target, monkeypatch
):
    log = HandleLog(monkeypatch)
    log.retained_close_fails = release == "fails"
    _arm_identity_fault(monkeypatch, inheritable=defect == "inheritable")
    reopened: list[tuple[int, object]] = []
    truncated: list[int] = []
    real_reopen, real_truncate = win._reopen_file, win._truncate_handle
    monkeypatch.setattr(
        win, "_reopen_file",
        lambda h, a, s, f: (reopened.append((a, real_reopen(h, a, s, f))), reopened[-1][1])[1],
    )
    monkeypatch.setattr(
        win, "_truncate_handle", lambda h: (truncated.append(h), real_truncate(h))[1]
    )
    try:
        with pytest.raises(target.error_type) as excinfo:
            target.call_writer()
        assert target.outstanding(excinfo.value) is (release == "fails")
        # Exactly one reopen (the RETAIN, access 0) and no write through it: no
        # H_s exists, and the one truncation is SCRUB-C through H_c.
        assert [access for access, _handle in reopened] == [0]
        retained_handle = reopened[0][1]
        assert retained_handle not in truncated
        assert len(truncated) == 1
        if release == "fails":
            assert "retained" in win._CLOSE_FAILURES
    finally:
        log.release_leaks()


@pytest.mark.parametrize("phase", ["before_insert", "after_insert_exception", "after_insert_interrupt"])
def test_y13_no_active_issuance_survives_a_registration_failure(phase, target, monkeypatch):
    issued_before = target.issued()
    reclaimed: list[bool] = []
    module = config_issuance if target.config else extension_issuance
    reclaim_name = "reclaim_config_issuance" if target.config else "reclaim_extension_issuance"
    real_reclaim = getattr(module, reclaim_name)
    monkeypatch.setattr(
        module, reclaim_name,
        lambda retained: (reclaimed.append(real_reclaim(retained)), reclaimed[-1])[1],
    )
    if phase == "before_insert":
        _inject_point("register_before_insert", target, monkeypatch, None)
    else:
        boom = KeyboardInterrupt if phase.endswith("interrupt") else RuntimeError
        if target.config:
            monkeypatch.setattr(
                cfg1_pi_config, "settings_digest", lambda: (_ for _ in ()).throw(boom("x"))
            )
        else:
            monkeypatch.setattr(
                cfg1_extension, "GeneratedCfg1Extension", lambda token: (_ for _ in ()).throw(boom("x"))
            )
    if phase.endswith("interrupt"):
        expected_exception = KeyboardInterrupt
    elif target.config or phase == "before_insert":
        expected_exception = target.error_type
    else:
        expected_exception = RuntimeError  # the extension writer's untyped propagation
    with pytest.raises(expected_exception) as excinfo:
        target.call_writer()
    assert target.issued() == issued_before
    assert win.held_retained_count() == 0
    if phase == "before_insert":
        assert reclaimed == [] or reclaimed == [False]
    else:
        assert reclaimed == [True]  # found by the retained authority, not by a token
    if expected_exception is target.error_type:
        assert target.outstanding(excinfo.value) is False


# ---------------------------------------------------------------------------
# Y-14 ... Y-18: every L24 failure boundary is fail-closed
# ---------------------------------------------------------------------------


def _both_facts_false(monkeypatch, git_executable, install) -> object:
    install()
    outcome, _made, _removals = _run_l21_hook(monkeypatch, git_executable, lambda handle: None)
    observations = outcome.observations
    assert observations["generated_config_scrub_verified"] is False
    assert observations["extension_binding_scrub_verified"] is False
    _assert_lifecycle_unproven(outcome)
    # L27's independent whole-root success upgrades neither fact (Y-20).
    assert observations["workspace_removed_verified"] is True
    assert win.held_retained_count() == 0  # every handle released
    assert config_issuance.issued_token_count() == 0
    assert extension_issuance.issued_extension_token_count() == 0
    return outcome


def test_y14_a_truncate_failure_is_false_and_skips_l26(monkeypatch, git_executable):
    failures = win.close_failure_count()
    _both_facts_false(
        monkeypatch, git_executable,
        lambda: monkeypatch.setattr(win, "_truncate_handle", lambda handle: False),
    )
    assert win.close_failure_count() == failures


def test_y14_a_real_user_mapped_view_is_false_for_that_object_only(monkeypatch, git_executable):
    views: list[int] = []

    def _hook(handle):
        root = Path(handle.experiment_root)
        alias = root / "mapped_alias.bin"
        os.link(root / CFG1_CONFIG_DIR_NAME / "models.json", alias)
        views.append(_map_view(alias))

    outcome, made, _removals = _run_l21_hook(monkeypatch, git_executable, _hook)
    root = made["workspace"].experiment_root
    try:
        observations = outcome.observations
        assert observations["generated_config_scrub_verified"] is False
        assert observations["extension_binding_scrub_verified"] is True  # independent
        _assert_lifecycle_unproven(outcome)
        assert win.held_retained_count() == 0
    finally:
        for view in views:
            _K.UnmapViewOfFile(view)
        shutil.rmtree(root, ignore_errors=True)


def test_y15_a_flush_failure_is_false(monkeypatch, git_executable):
    _both_facts_false(
        monkeypatch, git_executable,
        lambda: monkeypatch.setattr(win, "_flush_handle", lambda handle: False),
    )


@pytest.mark.parametrize("value", [None, False, True, 1, -1, "0", 0.0, b"0"])
def test_y16_every_malformed_or_nonzero_endoffile_is_false(value, target, monkeypatch):
    token = target.generate()
    monkeypatch.setattr(win, "_handle_end_of_file", lambda handle: value)
    assert target.scrub(token) is False
    assert win.held_retained_count() == 0


def test_y16_a_failing_endoffile_query_is_false(target, monkeypatch):
    token = target.generate()
    monkeypatch.setattr(
        win, "_handle_end_of_file", lambda handle: (_ for _ in ()).throw(OSError("query"))
    )
    assert target.scrub(token) is False
    assert win.held_retained_count() == 0


def _failing_close(monkeypatch, kind: str):
    leaked: list[int] = []
    order: list[str] = []
    real = win._close_handle

    def _close(handle, k):
        order.append(k)
        if k == kind:
            leaked.append(handle)
            return False
        return real(handle, k)

    monkeypatch.setattr(win, "_close_handle", _close)
    return leaked, order


@pytest.mark.parametrize("kind", ["scrub_handle", "retained"])
def test_y17_y18_a_failed_close_is_false_counted_and_never_retried(kind, target, monkeypatch):
    token = target.generate()
    leaked, order = _failing_close(monkeypatch, kind)
    try:
        assert target.scrub(token) is False
        assert order == ["scrub_handle", "retained"]  # H_r's close is still attempted
        assert win._CLOSE_FAILURES == [kind]
        assert order.count(kind) == 1  # never retried
    finally:
        for handle in leaked:
            win._K32.CloseHandle(handle)
        win._CLOSE_FAILURES.clear()
        win._RETAINED.clear()


# ---------------------------------------------------------------------------
# Y-19 ... Y-25
# ---------------------------------------------------------------------------


def test_y19_repeated_cleanup_is_false_with_zero_io(target, monkeypatch):
    token = target.generate()
    assert target.scrub(token) is True
    reopens: list[int] = []
    real = win._reopen_file
    monkeypatch.setattr(
        win, "_reopen_file", lambda *a: (reopens.append(1), real(*a))[1]
    )
    assert target.scrub(token) is False
    assert reopens == []
    if target.config:
        assert discard_config_for_test(token) is False
    else:
        assert discard_extension_for_test(token) is False
    module = config_issuance if target.config else extension_issuance
    reclaim = module.reclaim_config_issuance if target.config else module.reclaim_extension_issuance
    assert reclaim(object()) is False


def test_y19_the_executor_retires_each_issuance_exactly_once(monkeypatch, git_executable):
    retired: list[bool] = []
    real = win.scrub_retire_retained
    monkeypatch.setattr(
        win, "scrub_retire_retained", lambda retained: (retired.append(1), real(retained))[1]
    )
    seam_digests_all_match(monkeypatch)
    ports, _made = build_doubled_ports(git_executable=git_executable)
    outcome = execute_cfg1_run(make_admission(), ports=ports)
    assert outcome.observations["generated_config_scrub_verified"] is True
    assert outcome.observations["extension_binding_scrub_verified"] is True
    assert retired == [1, 1]


def test_y21_no_public_object_or_output_carries_the_retained_handle(target, monkeypatch):
    if target.config:
        generated = write_cfg1_pi_config(target.workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
        token = generated.issuance_token
        record = config_issuance._ISSUED[token]
    else:
        generated = _write_extension(target.workspace)
        token = generated.issuance_token
        record = extension_issuance._ISSUED_EXTENSIONS[token]
    raw_handle = win._RETAINED[record.retained.nonce][0]
    assert type(raw_handle) is int

    def _scan(obj) -> None:
        texts = [repr(obj), str(obj)]
        slots = [
            name for klass in type(obj).__mro__ for name in getattr(klass, "__slots__", ())
        ]
        values = [getattr(obj, name, None) for name in slots]
        values += list(getattr(obj, "__dict__", {}).values())
        assert raw_handle not in values
        assert not any(type(value) is win.RetainedAuthority for value in values)
        for text in texts:
            assert str(raw_handle) not in text and hex(raw_handle) not in text
            assert "RetainedAuthority" not in text
        for operation in (
            lambda o: pickle.dumps(o),
            lambda o: copy.copy(o),
            lambda o: copy.deepcopy(o),
        ):
            try:
                out = operation(obj)
            except Exception:  # noqa: BLE001 - refusing to copy is also fine
                continue
            blob = out if type(out) is bytes else repr(out) + repr(getattr(out, "__dict__", ""))
            assert str(raw_handle).encode() not in (blob if type(blob) is bytes else blob.encode())

    _scan(generated)
    # The retained authority itself is a nonce: no raw handle, and not copyable.
    retained = record.retained
    assert raw_handle not in (retained.nonce,) and str(raw_handle) not in repr(retained)
    for operation in (copy.copy, copy.deepcopy, pickle.dumps):
        with pytest.raises(Exception):
            out = operation(retained)
            if operation is pickle.dumps:
                pickle.loads(out)  # loading would have to rebind the frozen slot
    target.discard(token)


def test_y21_records_and_console_never_carry_a_retained_handle(monkeypatch, git_executable):
    seam_digests_all_match(monkeypatch)
    raw_handles: list[int] = []
    real = win.retain_child

    def _retain(child, **kw):
        authority = real(child, **kw)
        raw_handles.append(win._RETAINED[authority.nonce][0])
        return authority

    monkeypatch.setattr(win, "retain_child", _retain)
    ports, _made = build_doubled_ports(git_executable=git_executable)
    outcome = execute_cfg1_run(make_admission(), ports=ports)
    blob = repr(outcome.observations) + repr(outcome.console_codes)
    payload = build_cfg1_run_payload(
        stage_id="S1", stage_execution_id="S1-X1", run_ordinal=1, observations=outcome.observations
    )
    blob += repr(payload)
    assert len(raw_handles) == 2
    for handle in raw_handles:
        assert not re.search(rf"(?<!\d){handle}(?!\d)", blob)


def test_y22_static_discipline_of_the_scrub_primitives(monkeypatch, target):
    source = inspect.getsource(win)
    # Every ReOpenFile call site passes FILE_FLAG_OPEN_REPARSE_POINT.
    sites = [m.start() for m in re.finditer(r"_reopen_file\(", source)]
    call_sites = [pos for pos in sites if not source[max(0, pos - 4):pos] == "def "]
    assert len(call_sites) == 2  # RETAIN and SCRUB-R's H_s -- and nothing else
    for position in call_sites:
        depth, index = 0, position + len("_reopen_file")
        while True:
            depth += source[index] == "("
            depth -= source[index] == ")"
            index += 1
            if depth == 0:
                break
        assert "FILE_FLAG_OPEN_REPARSE_POINT" in source[position:index]
    assert source.count("_K32.ReOpenFile(") == 1  # only inside the seam
    # NumberOfLinks is never a decision input: it appears only in the struct.
    assert re.findall(r"\.NumberOfLinks", source) == []  # never read as an attribute
    assert source.count('("NumberOfLinks"') == 1  # the ctypes struct field only
    assert not hasattr(win, "identity_bound_unlink")
    assert not hasattr(win, "_unlink_handle_link_count")
    package = Path(win.__file__).parent
    for module in package.glob("*.py"):
        assert "identity_bound_unlink(" not in module.read_text(encoding="utf-8"), module.name
    # Behavior: a link count of 1, 2 or 5 makes no difference to the result.
    token = target.generate()
    for index in range(4):
        os.link(target.path, target.path.parent / f"link_{index}.bin")
    assert os.stat(target.path).st_nlink == 5
    assert target.scrub(token) is True


def test_y23_a_stranded_retained_entry_trips_the_registries_halt(workspace):
    target = _Target("models.json", workspace)
    token = target.generate()
    retained = config_issuance._ISSUED[token].retained
    run_workspace.discard_cfg1_run_workspace(workspace)
    outcome = SimpleNamespace(live_references_released=True)
    config_issuance._ISSUED.pop(token)  # a stranded retained handle: no owner
    try:
        assert config_issuance.issued_token_count() == 0
        assert win.held_retained_count() == 1
        assert stage_runner._run_scoped_registries_empty(outcome) is False
    finally:
        assert win.release_retained(retained) is True
    assert stage_runner._run_scoped_registries_empty(outcome) is True


def test_y24_a_foreign_data_handle_open_during_l24_is_false(target, tmp_path):
    token = target.generate()
    alias = tmp_path / "foreign_reader_alias.bin"
    os.link(target.path, alias)
    foreign = _open_foreign(alias)
    assert foreign is not None
    failures = win.close_failure_count()
    try:
        assert target.scrub(token) is False  # the share-0 reopen is refused
        assert win.held_retained_count() == 0  # H_r is closed regardless
        assert win.close_failure_count() == failures
    finally:
        win._K32.CloseHandle(foreign)


def test_y25_a_fully_unnamed_object_is_true_only_from_an_endoffile_zero_reading(
    target, monkeypatch
):
    token = target.generate()
    os.unlink(target.path)  # every name deleted by a same-user actor while ACTIVE
    readings: list[object] = []
    real = win._handle_end_of_file
    monkeypatch.setattr(win, "_handle_end_of_file", lambda h: (readings.append(real(h)), readings[-1])[1])
    result = target.scrub(token)
    if result is True:
        assert readings and readings[-1] == 0 and type(readings[-1]) is int
    else:
        assert result is False  # a host that refuses the reopen: fail-closed
    assert win.held_retained_count() == 0


# ---------------------------------------------------------------------------
# Ownership boundary at L24 (AMEND2 §12 step 1)
# ---------------------------------------------------------------------------


def test_the_l24_ownership_check_never_touches_another_runs_entry(target, git_executable):
    token = target.generate()
    other, _built = run_workspace.mint_cfg1_run_workspace(git_executable=git_executable)
    try:
        failures = win.close_failure_count()
        module = config_issuance if target.config else extension_issuance
        fn = module.scrub_config_issuance if target.config else module.scrub_extension_issuance
        assert fn(token=token, workspace=other) is False  # another run's workspace
        assert fn(token=object(), workspace=target.workspace) is False
        assert fn(token=token, workspace=object()) is False
        assert fn(token="", workspace=target.workspace) is False
        assert fn(token=token + "0", workspace=target.workspace) is False
        # The entry is intact, untouched, and still owns its retained handle.
        assert target.issued() == 1 and win.held_retained_count() == 1
        assert target.path.read_bytes() != b""
        assert win.close_failure_count() == failures
        # A config token is never an extension token, and vice versa.
        other_fn = (
            extension_issuance.scrub_extension_issuance
            if target.config
            else config_issuance.scrub_config_issuance
        )
        assert other_fn(token=token, workspace=target.workspace) is False
        assert target.scrub(token) is True
    finally:
        run_workspace.discard_cfg1_run_workspace(other)
        shutil.rmtree(other.experiment_root, ignore_errors=True)


@pytest.mark.parametrize("bad", [None, 0, 1, "x", b"x", object(), True])
def test_malformed_values_at_every_new_boundary_are_refused(bad, target):
    token = target.generate()
    try:
        # retain / release / scrub of anything that is not a retained authority.
        assert win.scrub_retire_retained(bad) is False
        assert win.release_retained(bad) is False
        assert win.scrub_child_through_creating_handle(bad) is False
        assert config_issuance.reclaim_config_issuance(bad) is False
        assert extension_issuance.reclaim_extension_issuance(bad) is False
        assert discard_config_for_test(bad) is False
        assert discard_extension_for_test(bad) is False
        with pytest.raises(win.Cfg1DirectoryAuthorityError):
            win.retained_identity(bad)
        assert win.retained_kind_is_valid(bad) is False
        # A malformed kind or interval refuses before any handle is obtained.
        with pytest.raises(win.Cfg1DirectoryAuthorityError):
            win.retain_child(bad, kind="config_models", interval=bad)
        assert target.scrub(bad) is False
        assert target.issued() == 1  # the genuine entry is undisturbed
    finally:
        target.discard(token)


def test_a_retained_authority_cannot_be_constructed_or_rebound():
    with pytest.raises(win.Cfg1DirectoryAuthorityError):
        win.RetainedAuthority("0" * 32)
    with pytest.raises(win.Cfg1DirectoryAuthorityError):
        win.RetainedAuthority(None)


def test_registration_refuses_a_missing_or_wrong_typed_retained_authority(workspace, monkeypatch):
    """The retained-authority binding at the issuance boundary (RA-3)."""
    real_register = config_issuance.register_config_issuance
    outcomes: list[str] = []
    state: dict = {}

    def _register(**kwargs):
        kwargs = dict(kwargs)
        kwargs["retained"] = None if state["mode"] == "missing" else object()
        try:
            return real_register(**kwargs)
        except config_issuance.ConfigIssuanceError as exc:
            outcomes.append(exc.reason_code)
            raise

    monkeypatch.setattr(config_issuance, "register_config_issuance", _register)
    for mode in ("missing", "wrong_type"):
        state["mode"] = mode
        with pytest.raises(Cfg1PiConfigError) as excinfo:
            write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
        assert excinfo.value.endpoint_material_outstanding is False
        assert outcomes[-1] == "RETAINED_AUTHORITY_NOT_BOUND"
        shutil.rmtree(Path(workspace.experiment_root) / CFG1_CONFIG_DIR_NAME, ignore_errors=True)
    assert win.held_retained_count() == 0
    assert config_issuance.issued_token_count() == 0


# ---------------------------------------------------------------------------
# Post-implementation adversarial review additions
# ---------------------------------------------------------------------------


def test_y26_a_genuine_but_mismatched_retained_authority_is_refused(workspace, monkeypatch):
    """Adversarial construction 1: a GENUINE retained authority, right kind, right
    interval, minted for the WRONG object (``settings.json``), offered at
    registration -- and a retained authority of the OTHER kind offered at mint.
    """
    holder: dict = {}
    real_pin, real_register = win.acquire_root_pin, config_issuance.register_config_issuance

    def _pin(path, **kw):
        holder["interval"] = kw["interval"]
        return real_pin(path, **kw)

    codes: list[str] = []

    def _register(**kw):
        kw = dict(kw)
        with pytest.raises(win.Cfg1DirectoryAuthorityError) as wrong_kind:
            win.retain_child(
                kw["models_child"], kind=win.RETAINED_KIND_EXTENSION_TOKEN,
                interval=holder["interval"],
            )
        codes.append(wrong_kind.value.reason_code)
        extra = win.retain_child(
            kw["settings_child"], kind=win.RETAINED_KIND_CONFIG_MODELS,
            interval=holder["interval"],
        )
        holder["extra"] = extra
        kw["retained"] = extra  # genuine, but bound to another object
        try:
            return real_register(**kw)
        except config_issuance.ConfigIssuanceError as exc:
            codes.append(exc.reason_code)
            raise

    monkeypatch.setattr(win, "acquire_root_pin", _pin)
    monkeypatch.setattr(config_issuance, "register_config_issuance", _register)
    try:
        with pytest.raises(Cfg1PiConfigError) as excinfo:
            write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
        assert codes == ["GENERATION_INTERVAL_KIND_MISMATCH", "RETAINED_AUTHORITY_NOT_BOUND"]
        assert excinfo.value.endpoint_material_outstanding is False
        assert config_issuance.issued_token_count() == 0
    finally:
        # The mismatched authority was never owned by anything; releasing it is
        # the test's job, and it is the ONLY retained handle left.
        assert win.held_retained_count() == 1
        assert win.release_retained(holder["extra"]) is True


@pytest.mark.parametrize("seam", ["_truncate_handle", "_flush_handle"])
@pytest.mark.parametrize("value", [1, "yes", [0], object()])
def test_y27_a_truthy_non_bool_seam_result_is_not_a_success(seam, value, target, monkeypatch):
    token = target.generate()
    monkeypatch.setattr(win, seam, lambda handle: value)
    assert target.scrub(token) is False
    assert win.held_retained_count() == 0
