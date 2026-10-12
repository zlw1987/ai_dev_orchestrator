"""F5-A A2 OFFLINE CANDIDATE -- regression tests for ``pi_runtime_provision``.

What these tests are, stated exactly. They are ordinary offline regressions of
the candidate's OWN logic: name validation, topology admission, the ledger's
state machine, provenance non-transferability, the exact-set gate, the
verify-before-persist ordering, fail-closed refusals, the handle lifecycle and
a byte-identical synthetic copy built by REAL handle-relative creates under
pytest ``tmp_path``.

What they are NOT. They are not Windows authority qualification. None of them
creates a reparse point, converts a directory, or races a conversion against a
create: the containment of a handle-relative create beneath a CONVERTED parent
(FU4-A2's A2-3, still INCOMPLETE) is deliberately not exercised here and is
listed as an open qualification obligation in
``docs/PHASE_5F3B_CFG1_F5A_A2_OFFLINE_IMPLEMENTATION_CANDIDATE.md``. Several
refusals are reached through monkeypatched seams (named in each test); those
show the candidate's own branches refuse, not that a real native anomaly
occurs. A green run here does not clear the A2-3 hard bar.

Every object lives under ``tmp_path``. No Node, Pi, npm, network, model or
credential is touched; the approved-inventory test reads only the committed
policy file.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import os
import pickle
import sys
from pathlib import Path

import pytest

from pi_harness_cfg1 import pi_fs_leaves, pi_payload
from pi_harness_cfg1 import pi_runtime_provision as rp

_MODULE_PATH = Path(rp.__file__)
_PROFILE_ID = "56651d0b2b6995e05b6de3aa012f5a82f276b2ac817dcce00844d1db2a9ffd67"
_COMMITTED_INVENTORY = (
    Path(__file__).resolve().parent.parent
    / "pi_profile_policy"
    / "inventories"
    / "66cf8a815d91aeaf3eb920763c6a4f3b98c17625dbaa93c540fb424c451664dc.json"
)

windows_only = pytest.mark.skipif(
    sys.platform != "win32", reason="Win32/NTFS semantics; a skip is not a pass"
)

#: A synthetic payload: the four LDT files, nested directories, an empty
#: directory, the payload's OWN ``node_modules`` descendant (allowed: T-NM only
#: walks upward from ``C``), and a supplementary-plane file name.
_PAYLOAD = {
    "package.json": b'{"name":"synthetic"}\n',
    "dist/cli.js": b"import './main.js';\n",
    "dist/main.js": b"import './config.js';\n" * 40,
    "dist/config.js": b"export const x = 1;\n",
    "dist/core/extensions/loader.js": b"// loader\n",
    "docs/readme.md": b"# synthetic\n",
    "docs/\U0001F600.md": b"astral name\n",
    "node_modules/dep/index.js": b"module.exports = 1;\n",
    "empty.bin": b"",
}
_EMPTY_DIRS = ("examples/empty",)


def _write_source(root: Path) -> None:
    for relative, data in _PAYLOAD.items():
        target = root.joinpath(*relative.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    for relative in _EMPTY_DIRS:
        root.joinpath(*relative.split("/")).mkdir(parents=True, exist_ok=True)


def _identity(path: Path) -> tuple[int, int]:
    result = os.stat(path)
    return (result.st_dev, result.st_ino)


@pytest.fixture
def scenario(tmp_path):
    """A source package, its observed inventory, and a non-empty run root."""
    source = tmp_path / "src" / "pkg"
    _write_source(source)
    observation = pi_payload.observe_payload(str(source), leaves=pi_payload.genuine_payload_leaves())
    assert observation.complete
    run_root = tmp_path / "run"
    (run_root / "workspace").mkdir(parents=True)
    (run_root / "workspace" / "keep.txt").write_bytes(b"workspace bytes")
    return {
        "tmp": tmp_path,
        "source": source,
        "inventory": observation.inventory,
        "run_root": run_root,
        "package_root": run_root / rp.RUNTIME_DIR_NAME / rp.PACKAGE_DIR_NAME,
    }


def _admit(scenario, **overrides):
    arguments = {
        "run_root": str(scenario["run_root"]),
        "run_root_identity": _identity(scenario["run_root"]),
        "profile_id": _PROFILE_ID,
        "approved_inventory": scenario["inventory"],
        "source_package_root": str(scenario["source"]),
    }
    arguments.update(overrides)
    return rp.admit_runtime_provision(**arguments)


def _all_bytes_under(root: Path) -> list[bytes]:
    return [path.read_bytes() for path in root.rglob("*") if path.is_file()]


# ---------------------------------------------------------------------------
# Pure: names, topology, inventory bounds, static audit
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    ["a\\b", "a/b", "..", ".", "", "a:b", "a:stream", "con", "NUL.txt", "x.", "x ", "a\x00b", "a*b", "a?b",
     "\\abs", "C:\\abs", "x" * 256, "\ud800"],
)
def test_names_that_are_not_one_safe_component_are_refused(name):
    with pytest.raises(rp.Cfg1RuntimeProvisionError) as refused:
        rp.require_single_component(name)
    assert refused.value.reason_code == "NAME_NOT_A_SINGLE_COMPONENT"
    assert refused.value.refusal_code == rp.RUNTIME_PROVISIONING_FAILED


@pytest.mark.parametrize("name", ["pi_runtime", "pi-coding-agent", "a b", "\U0001F600.md", ".hidden", "x" * 255])
def test_single_safe_components_are_accepted(name):
    assert rp.require_single_component(name) == name


@pytest.mark.parametrize("bad", [1, None, b"name", ["a"]])
def test_non_string_names_are_refused(bad):
    with pytest.raises(rp.Cfg1RuntimeProvisionError):
        rp.require_single_component(bad)


_BASE = "C:\\Users\\u\\AppData\\Local\\Temp\\scratch\\run\\pi_runtime\\pi-coding-agent\\dist\\config.js"


@pytest.mark.parametrize(
    ("path", "reason"),
    [
        (_BASE, None),
        ("C:\\node_modules\\run\\pi_runtime\\pi-coding-agent\\dist\\config.js", "TOPOLOGY_NODE_MODULES_ANCESTOR"),
        (_BASE.replace("AppData", "Node_Modules"), "TOPOLOGY_NODE_MODULES_ANCESTOR"),
        (_BASE.replace("scratch", "NODE_MODULES"), "TOPOLOGY_NODE_MODULES_ANCESTOR"),
        (_BASE.replace("\\run\\", "\\node_modules\\"), "TOPOLOGY_NODE_MODULES_ANCESTOR"),
        (_BASE.replace("scratch", "$bunfs"), "TOPOLOGY_BUN_MARKER"),
        (_BASE.replace("scratch", "x~BUN"), "TOPOLOGY_BUN_MARKER"),
        (_BASE.replace("scratch", "%7EBun"), "TOPOLOGY_BUN_MARKER"),
        ("\\\\server\\share\\run\\dist\\config.js", "TOPOLOGY_NOT_CANONICAL"),
        ("\\\\?\\C:\\run\\dist\\config.js", "TOPOLOGY_NOT_CANONICAL"),
        ("run\\dist\\config.js", "TOPOLOGY_NOT_CANONICAL"),
        (_BASE.replace("\\run\\", "\\.\\"), "TOPOLOGY_NOT_CANONICAL"),
        (_BASE.replace("\\run\\", "\\..\\"), "TOPOLOGY_NOT_CANONICAL"),
        (_BASE.replace("\\run\\", "\\run.\\"), "TOPOLOGY_NOT_CANONICAL"),
        (_BASE.replace("\\run\\", "\\run \\"), "TOPOLOGY_NOT_CANONICAL"),
        (_BASE.replace("\\", "/"), "TOPOLOGY_NOT_CANONICAL"),
        (_BASE.replace("\\run\\", "\\\\"), "TOPOLOGY_NOT_CANONICAL"),
    ],
)
def test_lexical_topology_t_canon_t_nm_t_bun(path, reason):
    assert rp.lexical_topology_refusal(path) == reason


def test_committed_inventory_ldt_paths_and_construction_bounds():
    """T-F5A-15 / T-F5A-32 (partial, repo-local): the LDT paths are file entries
    of the COMMITTED approved inventory, and the candidate's construction order
    peaks at 449 OPEN handles on it -- within Sec. 7.4A.6's 462 bound."""
    record = json.loads(_COMMITTED_INVENTORY.read_text(encoding="utf-8"))
    inventory = pi_payload.inventory_from_record(record)
    assert inventory.payload_fingerprint == _COMMITTED_INVENTORY.stem
    ldt = rp.LAUNCH_DERIVATION_TABLE[_PROFILE_ID]
    assert ldt["quarantine_rule"] == "NO_NODE_MODULES_ANCESTOR_MEANS_NO_TARGET"
    for relative in (ldt["package_manifest"], *ldt["derivation_chain"]):
        assert inventory.is_file(relative), relative
    assert inventory.entry("dist/package.json") is None
    tree = rp._payload_tree(inventory)
    assert len(tree) - 1 == 1436
    assert max(len(files) for files, _ in tree.values()) == 360
    assert max(len(dirs) for _, dirs in tree.values()) == 80
    assert max(len(files) + len(dirs) for files, dirs in tree.values()) == 362
    assert max(entry[1].count("/") + 1 for entry in inventory.entries) == 11
    assert rp.construction_handle_peak(inventory) == 449 <= 462
    assert max(entry[3] for entry in inventory.entries if entry[0] == "file") == 11694592


def _calls(tree: ast.AST) -> list[ast.Call]:
    return [node for node in ast.walk(tree) if isinstance(node, ast.Call)]


def _call_name(node: ast.Call) -> str:
    func = node.func
    return func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")


def test_static_audit_no_pathname_creation_no_deletion_no_fallback():
    """The candidate's no-fallback / no-delete properties, as AST facts.

    The ONLY creating call is the handle-relative native create; every
    ``CreateFileW`` is ``OPEN_EXISTING``; no pathname create, delete, rename,
    truncate or disposition exists; the native disposition is ``FILE_CREATE``.
    """
    source = _MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden = {
        "CreateDirectoryW", "CreateDirectoryExW", "CreateDirectoryA", "mkdir", "makedirs", "open", "write_bytes",
        "write_text", "unlink", "remove", "rmdir", "rmtree", "rename", "truncate", "DeleteFileW",
        "RemoveDirectoryW", "MoveFileExW", "MoveFileW", "SetFileInformationByHandle", "ReOpenFile",
        "CreateHardLinkW", "DeviceIoControl", "copyfile", "copy2", "system", "Popen", "run",
    }
    names = [_call_name(node) for node in _calls(tree)]
    assert not forbidden.intersection(names), sorted(forbidden.intersection(names))
    create_file_calls = [node for node in _calls(tree) if _call_name(node) == "CreateFileW"]
    assert len(create_file_calls) == 2
    for node in create_file_calls:
        assert isinstance(node.args[4], ast.Name) and node.args[4].id == "_OPEN_EXISTING"
    native_calls = [node for node in _calls(tree) if _call_name(node) == "native"]
    assert len(native_calls) == 1
    assert isinstance(native_calls[0].args[7], ast.Name) and native_calls[0].args[7].id == "_FILE_CREATE"
    identifiers = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)} | {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    for token in ("FILE_OPEN_IF", "FILE_OVERWRITE", "FILE_SUPERSEDE", "CREATE_ALWAYS", "OPEN_ALWAYS",
                  "TRUNCATE_EXISTING", "CREATE_NEW", "FileDispositionInfo", "DELETE_ON_CLOSE"):
        assert not any(token in identifier for identifier in identifiers), token
    imported = {
        alias.name if isinstance(node, ast.Import) else f"{node.module}.{alias.name}"
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    for module in ("win_config_authority", "config_issuance", "extension_issuance", "run_executor",
                   "cfg1_pi_config", "subprocess", "shutil", "socket"):
        assert not any(module in name for name in imported), (module, imported)
    # No module that can delete, rename or create by pathname is even imported.
    assert {name.split(".")[0] for name in imported} <= {
        "__future__", "hashlib", "ntpath", "secrets", "sys", "ctypes", "pi_harness_cfg1"
    }, imported


def test_provision_types_are_not_mint_backed_cfg1_authority():
    from pi_harness_cfg1 import win_config_authority as wca

    for cls in (rp.RuntimeProvision, rp._HandleLedger, rp._LedgerEntry):
        assert not issubclass(cls, wca._MintBacked)


# ---------------------------------------------------------------------------
# Ledger state machine (no real handle: the close seam is replaced)
# ---------------------------------------------------------------------------


def test_ledger_closes_each_entry_once_latches_failure_and_refuses_injection(monkeypatch):
    closes: list[int] = []

    def fake_close(raw):
        closes.append(raw)
        return raw != 2

    monkeypatch.setattr(rp, "_close_raw_handle", fake_close)
    kinds = frozenset({rp._KIND_DIRECTORY, rp._KIND_FILE})
    ledger = rp._HandleLedger(rp._LEDGER_KEY, kinds)
    other = rp._HandleLedger(rp._LEDGER_KEY, kinds)
    root = ledger.enter(1, rp._KIND_DIRECTORY)
    child = ledger.enter(2, rp._KIND_FILE)
    sibling = ledger.enter(3, rp._KIND_FILE)
    foreign = other.enter(4, rp._KIND_DIRECTORY)
    assert ledger.peak_open == 3

    for bad, kind in ((1, rp._KIND_DIRECTORY), (foreign, rp._KIND_DIRECTORY), (child, rp._KIND_DIRECTORY)):
        with pytest.raises(rp.Cfg1RuntimeProvisionError) as refused:
            ledger.raw_handle(bad, kind)
        assert refused.value.reason_code == "PARENT_HANDLE_NOT_AUTHORITATIVE"
    assert ledger.raw_handle(root, rp._KIND_DIRECTORY) == 1

    ledger.close_all()
    assert closes == [3, 2, 1]  # most recent first: children before directories
    assert (root.state, child.state, sibling.state) == ("CLOSED", "CLOSE_FAILED", "CLOSED")
    with pytest.raises(rp.Cfg1RuntimeProvisionError):
        ledger.raw_handle(root, rp._KIND_DIRECTORY)  # closed entries are not authoritative
    ledger.close_all()
    assert ledger.close(child) is False
    assert closes == [3, 2, 1]  # never retried, never re-closed
    assert ledger.all_proven_closed() is False and ledger.any_close_failed() is True
    assert other.close(child) is False  # a foreign ledger cannot close it either
    for bad in (0, None, "1", 1.0):
        with pytest.raises(rp.Cfg1RuntimeProvisionError):
            ledger.enter(bad, rp._KIND_FILE)
    with pytest.raises(rp.Cfg1RuntimeProvisionError):
        ledger.enter(9, rp._KIND_FINAL_PIN)  # a kind this ledger does not hold
    with pytest.raises(rp.Cfg1RuntimeProvisionError):
        rp._HandleLedger(object(), kinds)
    assert repr(root) == "_LedgerEntry('directory', 'CLOSED')"


def test_a_raising_close_is_recorded_as_close_failed(monkeypatch):
    def raising(raw):
        raise OSError("boom")

    monkeypatch.setattr(rp, "_close_raw_handle", raising)
    ledger = rp._HandleLedger(rp._LEDGER_KEY, frozenset({rp._KIND_FILE}))
    entry = ledger.enter(7, rp._KIND_FILE)
    assert ledger.close(entry) is False
    assert entry.state == rp.HANDLE_CLOSE_FAILED


# ---------------------------------------------------------------------------
# Windows: real handle-relative construction under tmp_path
# ---------------------------------------------------------------------------


@windows_only
def test_successful_provision_is_byte_identical_contained_and_released(scenario):
    """T-F5A-01/08/10/11 (synthetic): exact copy; topology; ledger closed; peak
    equals the simulation; four final pins held until L27; derived release fact."""
    before_tmp = sorted(path.name for path in scenario["tmp"].iterdir())
    provision = _admit(scenario)
    assert provision.state == rp.STATE_ADMITTED
    assert not (scenario["run_root"] / rp.RUNTIME_DIR_NAME).exists()  # admission writes nothing
    rp.run_runtime_provision(provision)
    try:
        assert provision.state == rp.STATE_PROVEN
        package_root = scenario["package_root"]
        assert provision.package_root == str(package_root)
        copied = pi_payload.observe_payload(str(package_root), leaves=pi_payload.genuine_payload_leaves())
        assert copied.complete
        assert copied.inventory.payload_fingerprint == scenario["inventory"].payload_fingerprint
        for relative, data in _PAYLOAD.items():
            assert package_root.joinpath(*relative.split("/")).read_bytes() == data
        assert sorted(path.name for path in (scenario["run_root"] / rp.RUNTIME_DIR_NAME).iterdir()) == [
            rp.PACKAGE_DIR_NAME
        ]
        assert sorted(path.name for path in scenario["run_root"].iterdir()) == [rp.RUNTIME_DIR_NAME, "workspace"]
        assert (scenario["run_root"] / "workspace" / "keep.txt").read_bytes() == b"workspace bytes"
        assert sorted(path.name for path in scenario["tmp"].iterdir()) == before_tmp
        assert provision.package_root_identity == _identity(package_root)
        assert provision.construction_open_count == 0
        assert provision.construction_peak_open == rp.construction_handle_peak(scenario["inventory"])
        assert provision.final_pins_held == 4
        assert provision.live_references_released is False  # pins still OPEN: not proven released
        assert repr(provision) == "RuntimeProvision('PROVEN')"
    finally:
        rp.release_at_l27_entry(provision)
    assert provision.final_pins_held == 0
    assert provision.live_references_released is True
    rp.release_at_l27_entry(provision)  # idempotent: nothing is closed twice
    assert provision.live_references_released is True


@windows_only
def test_a_provision_runs_once_and_cannot_be_forged_copied_or_transferred(scenario):
    from pi_harness_cfg1 import win_config_authority as wca

    with pytest.raises(rp.Cfg1RuntimeProvisionError):
        rp.RuntimeProvision(object())
    forged = object.__new__(rp.RuntimeProvision)
    with pytest.raises(rp.Cfg1RuntimeProvisionError) as refused:
        rp.run_runtime_provision(forged)
    assert refused.value.reason_code == "PROVISION_NOT_ADMITTED"

    provision = _admit(scenario)
    for transfer in (copy.copy, copy.deepcopy, pickle.dumps):
        with pytest.raises(TypeError):
            transfer(provision)
    with pytest.raises(AttributeError):
        provision._state = rp.STATE_PROVEN
    with pytest.raises(rp.Cfg1RuntimeProvisionError):
        provision.package_root_identity  # noqa: B018 - not proven yet
    for consumer in (wca.require_production_issuance_provenance, wca.require_extension_issuance_provenance):
        with pytest.raises(wca.Cfg1DirectoryAuthorityError):
            consumer(provision, ())
    rp.run_runtime_provision(provision)
    try:
        with pytest.raises(rp.Cfg1RuntimeProvisionError) as again:
            rp.run_runtime_provision(provision)
        assert again.value.reason_code == "PROVISION_NOT_ADMITTED"
        with pytest.raises(rp.Cfg1RuntimeProvisionError) as readmit:
            _admit(scenario)
        assert readmit.value.reason_code == "RUNTIME_ROOT_ALREADY_PRESENT"
    finally:
        rp.release_at_l27_entry(provision)


@windows_only
@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"profile_id": "0" * 64}, "NO_LDT_ENTRY"),
        ({"run_root": 7}, "MALFORMED_INPUT"),
        ({"run_root_identity": (1,)}, "MALFORMED_INPUT"),
        ({"run_root_identity": (1, True)}, "MALFORMED_INPUT"),
        ({"approved_inventory": object()}, "MALFORMED_INPUT"),
    ],
)
def test_admission_refuses_malformed_inputs_and_unlisted_profiles(scenario, overrides, reason):
    with pytest.raises(rp.Cfg1RuntimeProvisionError) as refused:
        _admit(scenario, **overrides)
    assert refused.value.reason_code == reason
    assert not (scenario["run_root"] / rp.RUNTIME_DIR_NAME).exists()


@windows_only
def test_admission_refuses_an_inventory_missing_an_ldt_file(scenario):
    entries = tuple(entry for entry in scenario["inventory"].entries if entry[1] != "dist/main.js")
    with pytest.raises(rp.Cfg1RuntimeProvisionError) as refused:
        _admit(scenario, approved_inventory=pi_payload.inventory_from_entries(entries))
    assert refused.value.reason_code == "LDT_PATH_NOT_IN_INVENTORY"


@windows_only
def test_admission_refuses_a_node_modules_ancestor_before_any_write(tmp_path, scenario):
    run_root = tmp_path / "node_modules" / "run"
    run_root.mkdir(parents=True)
    with pytest.raises(rp.Cfg1RuntimeProvisionError) as refused:
        _admit(scenario, run_root=str(run_root), run_root_identity=_identity(run_root))
    assert refused.value.reason_code == "TOPOLOGY_NODE_MODULES_ANCESTOR"
    assert list(run_root.iterdir()) == []


@windows_only
def test_admission_refuses_a_non_plain_chain_component(scenario, monkeypatch):
    """T-PLAIN, reached through a monkeypatched no-follow leaf (no real reparse
    point is created by this suite)."""
    real = pi_fs_leaves.inspect_no_follow
    target = str(scenario["run_root"])

    def reports_reparse(path):
        if path == target:
            return pi_fs_leaves.NoFollowObservation(pi_fs_leaves.CLASSIFICATION_REPARSE_POINT, None)
        return real(path)

    monkeypatch.setattr(pi_fs_leaves, "inspect_no_follow", reports_reparse)
    with pytest.raises(rp.Cfg1RuntimeProvisionError) as refused:
        _admit(scenario)
    assert refused.value.reason_code == "TOPOLOGY_NOT_PLAIN"


@windows_only
def test_existing_runtime_dir_or_run_root_node_modules_refuses_admission(scenario):
    (scenario["run_root"] / "node_modules").mkdir()
    with pytest.raises(rp.Cfg1RuntimeProvisionError) as refused:
        _admit(scenario)
    assert refused.value.reason_code == "RUN_ROOT_NODE_MODULES_PRESENT"
    (scenario["run_root"] / "node_modules").rmdir()
    (scenario["run_root"] / rp.RUNTIME_DIR_NAME).mkdir()
    with pytest.raises(rp.Cfg1RuntimeProvisionError) as refused:
        _admit(scenario)
    assert refused.value.reason_code == "RUNTIME_ROOT_ALREADY_PRESENT"


def _assert_refused_cleanly(provision, reason):
    assert provision.state == rp.STATE_REFUSED
    assert provision.refusal_reason == reason
    assert provision.construction_open_count == 0


@windows_only
def test_run_root_identity_mismatch_refuses_before_any_create(scenario):
    provision = _admit(scenario, run_root_identity=_identity(scenario["source"]))
    with pytest.raises(rp.Cfg1RuntimeProvisionError) as refused:
        rp.run_runtime_provision(provision)
    assert refused.value.reason_code == "RUN_ROOT_IDENTITY_MISMATCH"
    _assert_refused_cleanly(provision, "RUN_ROOT_IDENTITY_MISMATCH")
    assert not (scenario["run_root"] / rp.RUNTIME_DIR_NAME).exists()
    assert provision.live_references_released is True


@windows_only
def test_unavailable_native_create_fails_closed_with_no_fallback(scenario, monkeypatch):
    """Injected: the resolver reports the export missing. Nothing is created by
    any other route (there is none), and no handle is left open."""
    monkeypatch.setattr(rp, "_resolve_native_create", lambda: None)
    provision = _admit(scenario)
    with pytest.raises(rp.Cfg1RuntimeProvisionError) as refused:
        rp.run_runtime_provision(provision)
    assert refused.value.reason_code == "NATIVE_RELATIVE_CREATE_UNAVAILABLE"
    _assert_refused_cleanly(provision, "NATIVE_RELATIVE_CREATE_UNAVAILABLE")
    assert sorted(path.name for path in scenario["run_root"].iterdir()) == ["workspace"]
    assert provision.live_references_released is True


@windows_only
def test_a_runtime_dir_planted_after_admission_is_never_adopted(scenario):
    """A same-user actor creates ``RT`` between admission and construction: the
    exclusive native create collides, nothing is created inside the planted
    directory, and nothing is deleted."""
    provision = _admit(scenario)
    planted = scenario["run_root"] / rp.RUNTIME_DIR_NAME
    planted.mkdir()
    (planted / "foreign.txt").write_bytes(b"foreign")
    with pytest.raises(rp.Cfg1RuntimeProvisionError) as refused:
        rp.run_runtime_provision(provision)
    assert refused.value.reason_code == "NATIVE_CREATE_REFUSED"
    _assert_refused_cleanly(provision, "NATIVE_CREATE_REFUSED")
    assert sorted(path.name for path in planted.iterdir()) == ["foreign.txt"]
    assert provision.live_references_released is True


@windows_only
def test_a_foreign_name_planted_before_the_gate_refuses_with_zero_content(scenario, monkeypatch):
    """T-F5A-26 (synthetic): a foreign file planted into ``C\\dist`` after its
    children were created and before its gate. The exact-set gate refuses; no
    content byte reaches any file of ``dist`` or below; nothing is deleted."""
    real_gate = rp._gate_exact_set
    dist = scenario["package_root"] / "dist"

    def plant_then_gate(ledger, directory, children):
        if {child.name for child in children} >= {"cli.js", "main.js", "config.js"}:
            (dist / "foreign.js").write_bytes(b"planted")
        return real_gate(ledger, directory, children)

    monkeypatch.setattr(rp, "_gate_exact_set", plant_then_gate)
    provision = _admit(scenario)
    with pytest.raises(rp.Cfg1RuntimeProvisionError) as refused:
        rp.run_runtime_provision(provision)
    assert refused.value.reason_code == "PARENTAGE_GATE_FAILED"
    _assert_refused_cleanly(provision, "PARENTAGE_GATE_FAILED")
    for name in ("cli.js", "main.js", "config.js"):
        assert (dist / name).stat().st_size == 0
    assert (dist / "core").is_dir() and list((dist / "core").iterdir()) == []
    assert (dist / "foreign.js").read_bytes() == b"planted"
    assert provision.live_references_released is True


@windows_only
def test_source_mutated_after_observation_persists_no_foreign_byte(scenario, monkeypatch):
    """T-F5A-28 (synthetic): after the source observation, a source file is
    replaced by same-size foreign bytes carrying a SECRET marker. The digest
    refuses; no SECRET byte exists anywhere under the run root; the diagnostic
    names only the approved path and a closed reason."""
    real_observe = pi_payload.observe_payload
    source = scenario["source"]
    main = source / "dist" / "main.js"
    original = main.read_bytes()
    foreign = (b"SECRET" * len(original))[: len(original)]

    def observe_then_mutate(root, *, leaves):
        observation = real_observe(root, leaves=leaves)
        if root == str(source):
            main.write_bytes(foreign)
        return observation

    monkeypatch.setattr(pi_payload, "observe_payload", observe_then_mutate)
    provision = _admit(scenario)
    with pytest.raises(rp.Cfg1RuntimeProvisionError) as refused:
        rp.run_runtime_provision(provision)
    assert refused.value.reason_code == "SOURCE_BYTES_NOT_APPROVED"
    assert refused.value.entry_path == "dist/main.js"
    assert "SECRET" not in str(refused.value)
    assert hashlib.sha256(foreign).hexdigest() not in str(refused.value)
    _assert_refused_cleanly(provision, "SOURCE_BYTES_NOT_APPROVED")
    assert not any(b"SECRET" in data for data in _all_bytes_under(scenario["run_root"]))
    assert (scenario["package_root"] / "dist" / "main.js").stat().st_size == 0
    assert provision.live_references_released is True


@windows_only
def test_unexpected_native_result_refuses_and_closes_its_handle(scenario, monkeypatch):
    """Injected: a success whose ``Information`` is not ``FILE_CREATED``. The
    candidate refuses, closes the returned handle through the ledger, and
    leaves the object in place for L27."""
    real = rp._native_relative_create

    def opened_not_created(ledger, native, parent_raw, name, kind):
        status, entry, information = real(ledger, native, parent_raw, name, kind)
        return status, entry, (1 if name == "main.js" else information)

    monkeypatch.setattr(rp, "_native_relative_create", opened_not_created)
    provision = _admit(scenario)
    with pytest.raises(rp.Cfg1RuntimeProvisionError) as refused:
        rp.run_runtime_provision(provision)
    assert refused.value.reason_code == "NATIVE_CREATE_UNEXPECTED_RESULT"
    _assert_refused_cleanly(provision, "NATIVE_CREATE_UNEXPECTED_RESULT")
    assert (scenario["package_root"] / "dist" / "main.js").stat().st_size == 0
    assert provision.live_references_released is True


@windows_only
@pytest.mark.parametrize("victim", ["cli.js", "dist"])
def test_construction_close_failure_latches_and_is_never_retried(scenario, monkeypatch, victim):
    """T-F5A-30 (synthetic, injected close failure): for a child file handle and,
    separately, a directory pin. L3R refuses; the failed entry is never retried;
    the release fact is ``False`` and stays ``False`` after L27 entry."""
    from ctypes import WinDLL

    kernel32 = WinDLL("kernel32", use_last_error=True)
    real_create = rp._native_relative_create
    real_close = rp._close_raw_handle
    targets: list[int] = []
    attempts: list[int] = []

    def capture(ledger, native, parent_raw, name, kind):
        result = real_create(ledger, native, parent_raw, name, kind)
        if name == victim and result[1] is not None:
            targets.append(result[1].raw)
        return result

    def failing_close(raw):
        if raw in targets:
            attempts.append(raw)
            return False
        return real_close(raw)

    monkeypatch.setattr(rp, "_native_relative_create", capture)
    monkeypatch.setattr(rp, "_close_raw_handle", failing_close)
    provision = _admit(scenario)
    try:
        with pytest.raises(rp.Cfg1RuntimeProvisionError) as refused:
            rp.run_runtime_provision(provision)
        assert refused.value.reason_code == "CONSTRUCTION_HANDLE_NOT_CLOSED"
        assert provision.state == rp.STATE_REFUSED
        assert provision.live_references_released is False
        rp.release_at_l27_entry(provision)
        rp.release_at_l27_entry(provision)
        assert attempts == targets and len(targets) == 1
        assert provision.live_references_released is False
    finally:
        for raw in targets:  # the harness, not the candidate, frees the real handle
            kernel32.CloseHandle(raw)


@windows_only
def test_final_pin_close_failure_latches_false(scenario, monkeypatch):
    """T-F5A-33(d) for this provision's own fact: a final read-only pin fails to
    close at L27 entry; no retry; the fact stays ``False``."""
    from ctypes import WinDLL

    kernel32 = WinDLL("kernel32", use_last_error=True)
    provision = _admit(scenario)
    rp.run_runtime_provision(provision)
    victim = provision._final_pins._entries[0].raw
    attempts: list[int] = []
    real_close = rp._close_raw_handle

    def failing_close(raw):
        if raw == victim:
            attempts.append(raw)
            return False
        return real_close(raw)

    monkeypatch.setattr(rp, "_close_raw_handle", failing_close)
    try:
        rp.release_at_l27_entry(provision)
        rp.release_at_l27_entry(provision)
        assert attempts == [victim]
        assert provision.final_pins_held == 0
        assert provision.live_references_released is False
    finally:
        kernel32.CloseHandle(victim)


@windows_only
def test_a_substitute_in_the_creator_to_pin_gap_is_refused(scenario, monkeypatch):
    """T-F5A-11 (synthetic): after population, ``main.js`` is replaced by an
    ordinary file with identical bytes (a different object). The final pin's
    id check refuses; construction handles are already closed; the pins taken
    so far stay held for L27 and release cleanly."""
    real_pins = rp._acquire_final_pins
    main = scenario["package_root"] / "dist" / "main.js"

    def substitute_then_pin(provision, pins):
        data = main.read_bytes()
        main.unlink()
        main.write_bytes(data)
        return real_pins(provision, pins)

    monkeypatch.setattr(rp, "_acquire_final_pins", substitute_then_pin)
    provision = _admit(scenario)
    with pytest.raises(rp.Cfg1RuntimeProvisionError) as refused:
        rp.run_runtime_provision(provision)
    assert refused.value.reason_code == "FINAL_PIN_REFUSED"
    _assert_refused_cleanly(provision, "FINAL_PIN_REFUSED")
    with pytest.raises(rp.Cfg1RuntimeProvisionError):
        provision.package_root_identity  # noqa: B018 - a refused provision proves nothing
    rp.release_at_l27_entry(provision)
    assert provision.live_references_released is True


# ---------------------------------------------------------------------------
# Windows: the creation primitive itself (authority of the parent, names,
# content ordering) against a real directory under tmp_path
# ---------------------------------------------------------------------------


@pytest.fixture
def primitive(tmp_path):
    """A real proven parent pin in an isolated ledger, closed at teardown."""
    if sys.platform != "win32":
        pytest.skip("Win32/NTFS semantics; a skip is not a pass")
    parent = tmp_path / "parent"
    parent.mkdir()
    ledger = rp._HandleLedger(rp._LEDGER_KEY, frozenset({rp._KIND_DIRECTORY, rp._KIND_FILE}))
    native = rp._resolve_native_create()
    assert native is not None
    pin = rp._pin_run_root(ledger, str(parent), _identity(parent))
    yield {"parent": parent, "ledger": ledger, "native": native, "pin": pin}
    ledger.close_all()
    assert ledger.all_proven_closed()


def test_native_create_returns_identity_bearing_handles_and_refuses_collision(primitive):
    ledger, native, pin, parent = primitive["ledger"], primitive["native"], primitive["pin"], primitive["parent"]
    directory = rp._create_child(ledger, native, pin, "d", rp._KIND_DIRECTORY)
    child = rp._create_child(ledger, native, pin, "\U0001F600.bin", rp._KIND_FILE)
    assert directory.identity == _identity(parent / "d")
    assert child.identity == _identity(parent / "\U0001F600.bin")  # the full name, not a truncation
    nested = rp._create_child(ledger, native, directory, "inner", rp._KIND_FILE)
    assert nested.identity == _identity(parent / "d" / "inner")
    for name, kind in (("d", rp._KIND_FILE), ("D", rp._KIND_DIRECTORY), ("\U0001F600.BIN", rp._KIND_FILE)):
        with pytest.raises(rp.Cfg1RuntimeProvisionError) as refused:
            rp._create_child(ledger, native, pin, name, kind)
        assert refused.value.reason_code == "NATIVE_CREATE_REFUSED"
    assert ledger.open_count == 4  # pin, d, the file, inner -- no refused handle left open
    rp._gate_exact_set(ledger, pin, [directory, child])
    assert directory.gate_passed and child.gate_passed


def test_parent_injection_and_bad_names_never_reach_the_native_call(primitive, monkeypatch):
    ledger, native, pin = primitive["ledger"], primitive["native"], primitive["pin"]
    calls: list[str] = []
    real = rp._native_relative_create

    def spy(*args):
        calls.append(args[3])
        return real(*args)

    monkeypatch.setattr(rp, "_native_relative_create", spy)
    other = rp._HandleLedger(rp._LEDGER_KEY, frozenset({rp._KIND_DIRECTORY}))
    file_child = rp._create_child(ledger, native, pin, "f", rp._KIND_FILE)
    calls.clear()
    closed_dir = rp._create_child(ledger, native, pin, "closed", rp._KIND_DIRECTORY)
    ledger.close(closed_dir)
    calls.clear()
    raw_pin = ledger.raw_handle(pin, rp._KIND_DIRECTORY)
    for parent in (raw_pin, None, file_child, closed_dir):
        with pytest.raises(rp.Cfg1RuntimeProvisionError) as refused:
            rp._create_child(ledger, native, parent, "x", rp._KIND_FILE)
        assert refused.value.reason_code == "PARENT_HANDLE_NOT_AUTHORITATIVE"
    with pytest.raises(rp.Cfg1RuntimeProvisionError):
        rp._create_child(other, native, pin, "x", rp._KIND_FILE)  # pin belongs to another ledger
    for name in ("d\\x", "d/x", "..", "a:s", "con"):
        with pytest.raises(rp.Cfg1RuntimeProvisionError) as refused:
            rp._create_child(ledger, native, pin, name, rp._KIND_FILE)
        assert refused.value.reason_code == "NAME_NOT_A_SINGLE_COMPONENT"
    assert calls == []
    assert not (primitive["parent"] / "x").exists()


def test_content_is_refused_before_the_gate_and_written_only_once_after_it(primitive):
    ledger, native, pin, parent = primitive["ledger"], primitive["native"], primitive["pin"], primitive["parent"]
    child = rp._create_child(ledger, native, pin, "content.bin", rp._KIND_FILE)
    data = b"approved bytes\x00\xff" * 1000
    digest = hashlib.sha256(data).hexdigest()
    with pytest.raises(rp.Cfg1RuntimeProvisionError) as refused:
        rp._write_verified_content(ledger, child, data, digest)
    assert refused.value.reason_code == "CONTENT_BEFORE_GATE"
    rp._gate_exact_set(ledger, pin, [child])
    rp._write_verified_content(ledger, child, data, digest)
    with pytest.raises(rp.Cfg1RuntimeProvisionError) as again:
        rp._write_verified_content(ledger, child, data, digest)
    assert again.value.reason_code == "CONTENT_ALREADY_WRITTEN"
    ledger.close(child)
    assert (parent / "content.bin").read_bytes() == data


def test_the_gate_refuses_a_foreign_entry_in_the_parent(primitive):
    ledger, native, pin, parent = primitive["ledger"], primitive["native"], primitive["pin"], primitive["parent"]
    child = rp._create_child(ledger, native, pin, "mine.bin", rp._KIND_FILE)
    (parent / "theirs.bin").write_bytes(b"x")
    with pytest.raises(rp.Cfg1RuntimeProvisionError) as refused:
        rp._gate_exact_set(ledger, pin, [child])
    assert refused.value.reason_code == "PARENTAGE_GATE_FAILED"
    assert child.gate_passed is False


def test_an_unknown_kind_is_refused_before_the_native_call(primitive, monkeypatch):
    """Self-review regression: an unknown ``kind`` used to reach the native create
    (as a file) and be refused only at ledger entry -- a created object plus an
    UNTRACKED handle. It must now refuse before any call, creating nothing."""
    ledger, native, pin, parent = primitive["ledger"], primitive["native"], primitive["pin"], primitive["parent"]
    calls: list[str] = []
    real = rp._native_relative_create

    def spy(*args):
        calls.append(args[3])
        return real(*args)

    monkeypatch.setattr(rp, "_native_relative_create", spy)
    entries_before = ledger.entry_count
    for kind in (rp._KIND_FINAL_PIN, "x", None):
        with pytest.raises(rp.Cfg1RuntimeProvisionError) as refused:
            rp._create_child(ledger, native, pin, "k", kind)
        assert refused.value.reason_code == "MALFORMED_INPUT"
    with pytest.raises(rp.Cfg1RuntimeProvisionError):
        real(ledger, native, ledger.raw_handle(pin, rp._KIND_DIRECTORY), "k", "x")
    assert calls == []
    assert ledger.entry_count == entries_before
    assert not (parent / "k").exists()
