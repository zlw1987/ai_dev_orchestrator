"""PE-2a: the PI-PC1 walk, canonical inventory, fingerprints and PI-SC1.

Acceptance rows A-1 .. A-7 of
``docs/PHASE_5F3B_PI_HARNESS_PROFILE_EVOLUTION_PE1_AMENDMENT.md`` Sec. 26.1,
plus adversarial regressions derived from the implementation.

Every payload is SYNTHETIC: real files under pytest ``tmp_path`` walked by the
GENUINE no-follow leaves, or an in-memory tree served by leaf doubles. Reparse
points are exercised through doubles only (a real reparse point under
``tmp_path`` needs its own explicit authorization, PE-1 Sec. 26). No Node, no
Pi, no npm, no installed Pi, no socket, no credential.
"""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pytest
from pe2a_support import (
    FakeTree,
    expected_entries,
    facts_for,
    synthetic_payload_files,
    write_tree,
)

from pi_harness_cfg1 import pi_fs_leaves, pi_payload, preflight
from pi_harness_cfg1.pi_fs_leaves import (
    CLASSIFICATION_REGULAR_FILE,
    DirectoryListing,
    PayloadFileRead,
)
from pi_harness_cfg1.pi_manifest import compute_profile_id
from pi_harness_cfg1.pi_payload import (
    PI_SC1_PATHS,
    Cfg1PayloadError,
    PayloadInventory,
    PayloadLeaves,
    canonical_json_bytes,
    compute_seam_fingerprint,
    genuine_payload_leaves,
    inventory_from_entries,
    inventory_from_record,
    observe_payload,
    project_seam_digests,
    relative_path_is_valid,
)

_PACKAGE_DIR = Path(__file__).resolve().parents[1]


def _observe_real(root: Path):
    return observe_payload(str(root), leaves=genuine_payload_leaves())


def _fingerprint_and_profile(root: Path) -> tuple[str, str]:
    observation = _observe_real(root)
    assert observation.complete, observation.refusal_code
    fingerprint = observation.inventory.payload_fingerprint
    return fingerprint, compute_profile_id(fingerprint, ["fsevents"])


def _assert_refused(observation, code: str) -> None:
    assert observation.complete is False
    assert observation.refusal_code == code
    assert observation.inventory is None
    assert observation.payload_fingerprint is None


# ---------------------------------------------------------------------------
# A-1 -- every dir (incl. empty) and every file of every extension
# ---------------------------------------------------------------------------


def test_a1_the_walk_records_every_directory_and_file_of_every_kind(tmp_path):
    files, empty_dirs = synthetic_payload_files()
    root = tmp_path / "payload"
    write_tree(root, files, empty_dirs)
    observation = _observe_real(root)
    assert observation.complete is True and observation.refusal_code is None
    assert observation.inventory.entries == expected_entries(files, empty_dirs)
    paths = {entry[1] for entry in observation.inventory.entries}
    for must in (
        "empty_dir",
        "dist/empty_nested/deeper",
        ".npmignore",
        "dist/native/addon.node",
        "dist/wasm/module.wasm",
        "dist/cli.js.map",
        "README.md",
        "LICENSE",
        "node_modules/.bin/pi",
        "node_modules/left-pad/node_modules/nested-dep/data.bin",
        "node_modules/@scope/util/lib/x.cjs",
        "node_modules/zod/index.mjs",
        "dist/fixtures/broken/package.json",
    ):
        assert must in paths, must
    assert observation.inventory.is_dir("empty_dir")
    assert observation.inventory.is_dir("node_modules/left-pad/node_modules")


def test_a1_the_payload_root_itself_is_not_an_entry_and_order_is_code_point(tmp_path):
    files, empty_dirs = synthetic_payload_files()
    root = tmp_path / "payload"
    write_tree(root, files, empty_dirs)
    entries = _observe_real(root).inventory.entries
    paths = [entry[1] for entry in entries]
    assert "" not in paths
    assert paths == sorted(paths)
    assert [p.encode("utf-8") for p in paths] == sorted(p.encode("utf-8") for p in paths)


# ---------------------------------------------------------------------------
# A-2 -- any byte / tree change changes the fingerprint and the profile id
# ---------------------------------------------------------------------------


_MUTATION_TARGETS = (
    "dist/core/sdk.js",  # a PI-SC1 seam file
    "dist/cli/setup.js",  # counterexample 1
    "dist/other.js",  # counterexample 2: another non-seam JS
    "node_modules/left-pad/node_modules/nested-dep/data.bin",  # counterexample 3
    "dist/native/addon.node",
    "dist/wasm/module.wasm",
    "README.md",
)


@pytest.mark.parametrize("target", _MUTATION_TARGETS)
def test_a2_a_one_byte_change_anywhere_changes_fingerprint_and_profile_id(tmp_path, target):
    files, empty_dirs = synthetic_payload_files()
    root = tmp_path / "payload"
    write_tree(root, files, empty_dirs)
    before = _fingerprint_and_profile(root)
    path = root.joinpath(*target.split("/"))
    data = bytearray(path.read_bytes())
    data[0] ^= 0x01
    path.write_bytes(bytes(data))
    after = _fingerprint_and_profile(root)
    assert after[0] != before[0]
    assert after[1] != before[1]


@pytest.mark.parametrize("mutation", ["add_file", "remove_file", "rename_file", "add_empty_dir"])
def test_a2_tree_changes_change_fingerprint_and_profile_id(tmp_path, mutation):
    files, empty_dirs = synthetic_payload_files()
    root = tmp_path / "payload"
    write_tree(root, files, empty_dirs)
    before = _fingerprint_and_profile(root)
    if mutation == "add_file":
        (root / "dist" / "new.js").write_bytes(b"")
    elif mutation == "remove_file":
        (root / "dist" / "other.js").unlink()
    elif mutation == "rename_file":
        (root / "dist" / "other.js").rename(root / "dist" / "other2.js")
    else:
        (root / "dist" / "brand_new_empty").mkdir()
    after = _fingerprint_and_profile(root)
    assert after[0] != before[0]
    assert after[1] != before[1]


def test_a2_same_seams_different_payload_are_distinct_profiles(tmp_path):
    """Counterexample 1 at the identity layer: the 20 seams are unchanged."""
    files, empty_dirs = synthetic_payload_files()
    base = facts_for(files, empty_dirs)
    changed = dict(files)
    changed["dist/cli/setup.js"] = b"export const setup = 2;\n"
    other = facts_for(changed, empty_dirs)
    assert base.seam_fingerprint == other.seam_fingerprint
    assert base.payload_fingerprint != other.payload_fingerprint
    assert base.profile_id != other.profile_id


# ---------------------------------------------------------------------------
# A-3 -- reparse anywhere refuses and is never entered (doubles)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "where, directory",
    [
        ("dist/link.js", False),  # file symlink
        ("dist/linked_dir", True),  # directory symlink
        ("node_modules/junction", True),  # junction
        ("node_modules/left-pad/node_modules/mount", True),  # nested mount point
    ],
)
def test_a3_a_reparse_point_anywhere_refuses_and_is_never_traversed(where, directory):
    files, empty_dirs = synthetic_payload_files()
    tree = FakeTree().populate(files, empty_dirs)
    tree.add_reparse(where, directory=directory)
    observation = tree.observe()
    _assert_refused(observation, pi_payload.PAYLOAD_REPARSE_POINT)
    reparse_path = tree.abs(where)
    assert ("enumerate", reparse_path) not in tree.log
    assert ("read", reparse_path) not in tree.log
    assert not any(path.startswith(reparse_path + "\\") for _kind, path in tree.log)


def test_a3_a_reparse_payload_root_refuses():
    tree = FakeTree()
    tree.nodes[tree.root] = ("reparse", True)
    _assert_refused(tree.observe(), pi_payload.PAYLOAD_REPARSE_POINT)


def test_a3_an_entry_that_becomes_a_reparse_point_at_open_refuses():
    """Enumerated as a plain dir, but the no-follow open classifies reparse."""
    files, empty_dirs = synthetic_payload_files()
    tree = FakeTree().populate(files, empty_dirs)
    target = tree.abs("node_modules/zod")

    def _hook(kind, path):
        if kind == "enumerate" and path == target:
            tree.nodes[target] = ("reparse", True)

    tree.hook = _hook
    _assert_refused(tree.observe(), pi_payload.PAYLOAD_REPARSE_POINT)


def test_a3_a_file_that_is_a_reparse_point_at_read_refuses():
    files, empty_dirs = synthetic_payload_files()
    tree = FakeTree().populate(files, empty_dirs)
    target = tree.abs("dist/other.js")

    def _hook(kind, path):
        if kind == "read" and path == target:
            tree.nodes[target] = ("reparse", False)

    tree.hook = _hook
    _assert_refused(tree.observe(), pi_payload.PAYLOAD_REPARSE_POINT)


# ---------------------------------------------------------------------------
# A-4 -- other / failure / instability refuse; nothing skipped, nothing partial
# ---------------------------------------------------------------------------


def _tree():
    files, empty_dirs = synthetic_payload_files()
    return FakeTree().populate(files, empty_dirs)


def test_a4_an_other_classified_entry_refuses():
    tree = _tree()
    tree.add_other("dist/device")
    _assert_refused(tree.observe(), pi_payload.PAYLOAD_ENTRY_UNOBSERVABLE)


def test_a4_an_enumeration_failure_refuses():
    tree = _tree()
    tree.enum_fail.add(tree.abs("node_modules/left-pad"))
    _assert_refused(tree.observe(), pi_payload.PAYLOAD_ENUMERATION_FAILED)


def test_a4_an_open_or_read_failure_refuses():
    tree = _tree()
    tree.read_fail.add(tree.abs("node_modules/zod/index.mjs"))
    _assert_refused(tree.observe(), pi_payload.PAYLOAD_ENTRY_UNOBSERVABLE)


def test_a4_size_instability_refuses():
    tree = _tree()
    tree.unstable.add(tree.abs("dist/native/addon.node"))
    _assert_refused(tree.observe(), pi_payload.PAYLOAD_FILE_UNSTABLE)


def test_a4_an_entry_vanishing_between_enumeration_and_read_refuses():
    tree = _tree()
    tree.vanish_on_read.add(tree.abs("README.md"))
    _assert_refused(tree.observe(), pi_payload.PAYLOAD_ENTRY_MISSING)


def test_a4_a_file_swapped_for_a_directory_before_its_read_refuses():
    tree = _tree()
    tree.kind_swap_on_read.add(tree.abs("LICENSE"))
    _assert_refused(tree.observe(), pi_payload.PAYLOAD_ENTRY_KIND_CHANGED)


def test_a4_a_directory_swapped_for_a_file_before_its_enumeration_refuses():
    tree = _tree()
    target = tree.abs("dist/cli")

    def _hook(kind, path):
        if kind == "enumerate" and path == target:
            tree.nodes[target] = ("file", b"now a file")

    tree.hook = _hook
    _assert_refused(tree.observe(), pi_payload.PAYLOAD_ENTRY_KIND_CHANGED)


def test_a4_a_missing_payload_root_refuses():
    tree = FakeTree()
    del tree.nodes[tree.root]
    _assert_refused(tree.observe(), pi_payload.PAYLOAD_ENTRY_MISSING)


def test_a4_nothing_is_skipped_every_entry_is_read_or_enumerated():
    tree = _tree()
    observation = tree.observe()
    assert observation.complete
    enumerated = {path for kind, path in tree.log if kind == "enumerate"}
    read = {path for kind, path in tree.log if kind == "read"}
    for entry in observation.inventory.entries:
        absolute = tree.abs(entry[1])
        if entry[0] == "dir":
            assert absolute in enumerated
        else:
            assert absolute in read


@pytest.mark.parametrize(
    "listing",
    [
        "not a listing",
        DirectoryListing("directory", True, False, None),
        DirectoryListing("directory", True, False, (("a", "weird-kind"),)),
        DirectoryListing("directory", True, True, ()),
        DirectoryListing("bogus", False, False, None),
        DirectoryListing("directory", 1, False, ()),
        DirectoryListing("directory", False, False, (("a", "file"),)),
    ],
)
def test_a4_a_malformed_listing_raises_and_returns_nothing(listing):
    leaves = PayloadLeaves(
        enumerate_directory=lambda path, budget: listing,
        read_file=lambda path, cap: None,
    )
    with pytest.raises(Cfg1PayloadError):
        observe_payload("C:\\fake\\root", leaves=leaves)


@pytest.mark.parametrize(
    "read",
    [
        None,
        PayloadFileRead("regular_file", True, True, -1, "0" * 64, None),
        PayloadFileRead("regular_file", True, True, True, "0" * 64, None),
        PayloadFileRead("regular_file", True, True, 1, "A" * 64, None),
        PayloadFileRead("directory", True, True, 1, "0" * 64, None),
        PayloadFileRead("regular_file", 1, True, 1, "0" * 64, None),
    ],
)
def test_a4_a_malformed_file_read_raises_and_returns_nothing(read):
    leaves = PayloadLeaves(
        enumerate_directory=lambda path, budget: DirectoryListing(
            "directory", True, False, (("a.js", "file"),)
        ),
        read_file=lambda path, cap: read,
    )
    with pytest.raises(Cfg1PayloadError):
        observe_payload("C:\\fake\\root", leaves=leaves)


def test_a4_a_leaf_reporting_more_bytes_than_its_cap_is_malformed():
    leaves = PayloadLeaves(
        enumerate_directory=lambda path, budget: DirectoryListing(
            "directory", True, False, (("a.js", "file"),)
        ),
        read_file=lambda path, cap: PayloadFileRead("regular_file", True, True, cap + 1, "0" * 64, None),
    )
    with pytest.raises(Cfg1PayloadError):
        observe_payload("C:\\fake\\root", leaves=leaves)


# ---------------------------------------------------------------------------
# A-5 -- every Sec. 4.2 grammar rule and case-fold collision refuses
# ---------------------------------------------------------------------------


_BAD_NAMES = [
    ".",
    "..",
    "a\x00b",
    "a\x1fb",
    "a\x7fb",
    "a\x85b",
    "a\x9fb",
    "a\\b",
    "a/b",
    "a:b",
    "C:",
    "a*b",
    "a?b",
    'a"b',
    "a<b",
    "a>b",
    "a|b",
    "lone\ud800surrogate",
    "trailing.",
    "trailing ",
    "con",
    "CON",
    "Con.js",
    "nul.txt",
    "aux",
    "prn.json",
    "com0",
    "COM9.dll",
    "lpt0",
    "lpt9.x",
    "",
]


@pytest.mark.parametrize("name", _BAD_NAMES)
def test_a5_a_grammar_invalid_name_refuses_before_it_becomes_a_path(name):
    tree = FakeTree()
    tree.add_file("ok.js", b"ok")
    tree.add_raw_name("", name, ("file", b"x"))
    observation = tree.observe()
    _assert_refused(observation, pi_payload.PAYLOAD_PATH_GRAMMAR)
    # The invalid name was never handed to a leaf as (part of) a path.
    for _kind, path in tree.log:
        assert path in (tree.root, tree.abs("ok.js"))


@pytest.mark.parametrize("name", ["com10", "lpt", "con_", "conx.js", "a.con", "é", "日本.js", ".dot", "-x"])
def test_a5_grammar_valid_unusual_names_are_accepted(name):
    tree = FakeTree()
    tree.add_raw_name("", name, ("file", b"x"))
    observation = tree.observe()
    assert observation.complete, observation.refusal_code
    assert observation.inventory.entries[0][1] == name


def test_a5_a_case_fold_collision_refuses():
    tree = FakeTree()
    tree.add_file("Readme.md", b"a")
    tree.add_file("README.md", b"b")
    _assert_refused(tree.observe(), pi_payload.PAYLOAD_CASE_FOLD_COLLISION)


def test_a5_a_nested_case_fold_collision_refuses():
    tree = FakeTree()
    tree.add_file("dist/A/x.js", b"a")
    tree.add_file("dist/a/y.js", b"b")
    _assert_refused(tree.observe(), pi_payload.PAYLOAD_CASE_FOLD_COLLISION)


def test_a5_a_unicode_case_fold_collision_refuses():
    tree = FakeTree()
    tree.add_file("stra\u00dfe.js", b"a")  # straße
    tree.add_file("strasse.js", b"b")  # casefold-equal
    _assert_refused(tree.observe(), pi_payload.PAYLOAD_CASE_FOLD_COLLISION)


@pytest.mark.parametrize(
    "path",
    ["", "/a", "a/", "a//b", "C:/a", "a/../b", "a/./b", "a\\b", "con/x", "x/aux.js", "a/b.", "a/b "],
)
def test_a5_relative_path_grammar_refuses(path):
    assert relative_path_is_valid(path) is False
    with pytest.raises(Cfg1PayloadError):
        inventory_from_entries((("file", path, "0" * 64, 0),))


def test_a5_a_str_subclass_path_or_name_is_refused():
    class Sneaky(str):
        pass

    assert relative_path_is_valid(Sneaky("a.js")) is False
    tree = FakeTree()
    tree.add_raw_name("", Sneaky("a.js"), ("file", b"x"))
    _assert_refused(tree.observe(), pi_payload.PAYLOAD_PATH_GRAMMAR)


# ---------------------------------------------------------------------------
# A-6 -- every Sec. 4.4 walk bound: at bound accepted, +1 refused, nothing partial
# ---------------------------------------------------------------------------


def test_a6_the_frozen_bound_literals_are_pinned():
    assert pi_payload.MAX_PAYLOAD_ENTRIES == 250000
    assert pi_payload.MAX_PAYLOAD_FILE_BYTES == 536870912
    assert pi_payload.MAX_PAYLOAD_TOTAL_BYTES == 4294967296
    assert pi_payload.MAX_RELATIVE_PATH_CHARS == 1024
    assert pi_payload.MAX_PATH_SEGMENTS == 128
    assert pi_payload.MAX_SEGMENT_CHARS == 255
    for name in (
        "MAX_PAYLOAD_ENTRIES",
        "MAX_PAYLOAD_FILE_BYTES",
        "MAX_PAYLOAD_TOTAL_BYTES",
        "MAX_RELATIVE_PATH_CHARS",
        "MAX_PATH_SEGMENTS",
        "MAX_SEGMENT_CHARS",
    ):
        assert type(getattr(pi_payload, name)) is int


def test_a6_the_frozen_bound_literals_are_source_literals():
    """Statically: each bound is assigned exactly once, to a plain int literal."""
    tree = ast.parse((_PACKAGE_DIR / "pi_payload.py").read_text(encoding="utf-8"))
    expected = {
        "MAX_PAYLOAD_ENTRIES": 250000,
        "MAX_PAYLOAD_FILE_BYTES": 536870912,
        "MAX_PAYLOAD_TOTAL_BYTES": 4294967296,
        "MAX_RELATIVE_PATH_CHARS": 1024,
        "MAX_PATH_SEGMENTS": 128,
        "MAX_SEGMENT_CHARS": 255,
    }
    found: dict[str, list] = {name: [] for name in expected}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in expected:
                    found[target.id].append(node.value)
    for name, value in expected.items():
        assert len(found[name]) == 1, name
        assert isinstance(found[name][0], ast.Constant) and found[name][0].value == value


def _flat_tree(count: int) -> FakeTree:
    tree = FakeTree()
    for index in range(count):
        tree.add_file(f"f{index:04d}", b"")
    return tree


def test_a6_entry_bound_at_bound_accepted_plus_one_refused(monkeypatch):
    monkeypatch.setattr(pi_payload, "MAX_PAYLOAD_ENTRIES", 5)
    assert _flat_tree(5).observe().complete
    _assert_refused(_flat_tree(6).observe(), pi_payload.PAYLOAD_ENTRY_BOUND_EXCEEDED)


def test_a6_entry_bound_counts_directories_and_files_across_levels(monkeypatch):
    monkeypatch.setattr(pi_payload, "MAX_PAYLOAD_ENTRIES", 4)
    tree = FakeTree()
    tree.add_file("a/b/c.js", b"")  # a, a/b, a/b/c.js = 3
    tree.add_dir("d")  # 4
    assert tree.observe().complete
    tree.add_dir("a/e")  # 5
    _assert_refused(tree.observe(), pi_payload.PAYLOAD_ENTRY_BOUND_EXCEEDED)


def test_a6_file_bound_at_bound_accepted_plus_one_refused(monkeypatch):
    monkeypatch.setattr(pi_payload, "MAX_PAYLOAD_FILE_BYTES", 10)
    tree = FakeTree()
    tree.add_file("a", b"x" * 10)
    assert tree.observe().complete
    tree.add_file("b", b"x" * 11)
    _assert_refused(tree.observe(), pi_payload.PAYLOAD_FILE_BYTES_EXCEEDED)


def test_a6_total_bound_at_bound_accepted_plus_one_refused(monkeypatch):
    monkeypatch.setattr(pi_payload, "MAX_PAYLOAD_TOTAL_BYTES", 20)
    tree = FakeTree()
    tree.add_file("a", b"x" * 10)
    tree.add_file("b", b"x" * 10)
    assert tree.observe().complete
    tree.add_file("c", b"x")
    _assert_refused(tree.observe(), pi_payload.PAYLOAD_TOTAL_BYTES_EXCEEDED)


def test_a6_file_bound_on_real_files_through_the_genuine_leaf(tmp_path, monkeypatch):
    monkeypatch.setattr(pi_payload, "MAX_PAYLOAD_FILE_BYTES", 64)
    root = tmp_path / "payload"
    write_tree(root, {"a.bin": b"x" * 64})
    assert _observe_real(root).complete
    write_tree(root, {"b.bin": b"x" * 65})
    _assert_refused(_observe_real(root), pi_payload.PAYLOAD_FILE_BYTES_EXCEEDED)


def test_a6_segment_chars_at_bound_accepted_plus_one_refused(monkeypatch):
    monkeypatch.setattr(pi_payload, "MAX_SEGMENT_CHARS", 8)
    tree = FakeTree()
    tree.add_file("a" * 8, b"")
    assert tree.observe().complete
    tree.add_file("b" * 9, b"")
    _assert_refused(tree.observe(), pi_payload.PAYLOAD_PATH_BOUND_EXCEEDED)


def test_a6_the_real_segment_bound_is_255(tmp_path):
    tree = FakeTree()
    tree.add_raw_name("", "a" * 255, ("file", b""))
    assert tree.observe().complete
    tree = FakeTree()
    tree.add_raw_name("", "a" * 256, ("file", b""))
    _assert_refused(tree.observe(), pi_payload.PAYLOAD_PATH_BOUND_EXCEEDED)


def test_a6_path_segments_at_bound_accepted_plus_one_refused(monkeypatch):
    monkeypatch.setattr(pi_payload, "MAX_PATH_SEGMENTS", 4)
    tree = FakeTree()
    tree.add_file("a/b/c/d", b"")
    assert tree.observe().complete
    tree.add_file("a/b/c/e/f", b"")
    _assert_refused(tree.observe(), pi_payload.PAYLOAD_PATH_BOUND_EXCEEDED)


def test_a6_relative_path_chars_at_bound_accepted_plus_one_refused(monkeypatch):
    monkeypatch.setattr(pi_payload, "MAX_RELATIVE_PATH_CHARS", 9)
    tree = FakeTree()
    tree.add_file("abcd/efgh", b"")  # exactly 9
    assert tree.observe().complete
    tree.add_file("abcd/efghi", b"")  # 10
    _assert_refused(tree.observe(), pi_payload.PAYLOAD_PATH_BOUND_EXCEEDED)


def test_a6_inventory_validation_enforces_the_same_bounds(monkeypatch):
    monkeypatch.setattr(pi_payload, "MAX_PAYLOAD_ENTRIES", 2)
    with pytest.raises(Cfg1PayloadError):
        inventory_from_entries((("dir", "a"), ("dir", "b"), ("dir", "c")))
    monkeypatch.setattr(pi_payload, "MAX_PAYLOAD_ENTRIES", 250000)
    monkeypatch.setattr(pi_payload, "MAX_PAYLOAD_TOTAL_BYTES", 3)
    with pytest.raises(Cfg1PayloadError):
        inventory_from_entries((("file", "a", "0" * 64, 2), ("file", "b", "0" * 64, 2)))
    monkeypatch.setattr(pi_payload, "MAX_PAYLOAD_FILE_BYTES", 1)
    with pytest.raises(Cfg1PayloadError):
        inventory_from_entries((("file", "a", "0" * 64, 2),))


# ---------------------------------------------------------------------------
# A-7 -- order independence; golden vectors computed from the spec
# ---------------------------------------------------------------------------


def test_a7_enumeration_order_permutations_give_identical_bytes():
    files, empty_dirs = synthetic_payload_files()
    forward = FakeTree().populate(files, empty_dirs)
    reverse = FakeTree().populate(dict(reversed(list(files.items()))), tuple(reversed(empty_dirs)))
    reverse.order = "reverse"
    first = forward.observe().inventory
    second = reverse.observe().inventory
    assert first.canonical_bytes == second.canonical_bytes
    assert first.payload_fingerprint == second.payload_fingerprint
    assert compute_profile_id(first.payload_fingerprint, []) == compute_profile_id(
        second.payload_fingerprint, []
    )


def test_a7_the_fake_and_the_genuine_walk_agree_byte_for_byte(tmp_path):
    files, empty_dirs = synthetic_payload_files()
    root = tmp_path / "payload"
    write_tree(root, files, empty_dirs)
    genuine = _observe_real(root).inventory
    fake = FakeTree().populate(files, empty_dirs).observe().inventory
    assert genuine.canonical_bytes == fake.canonical_bytes


_GOLDEN_X_SHA256 = "2d711642b726b04401627ca9fbac32f5c8530fb1903cc4db02258717921a4881"
_GOLDEN_INVENTORY_BYTES = (
    b'{"entries":[{"kind":"dir","path":"a"},{"kind":"file","path":"a/b.js","sha256":"'
    + _GOLDEN_X_SHA256.encode("ascii")
    + b'","size":1},{"kind":"dir","path":"c"},{"kind":"dir","path":"\\u00e9t\\u00e9"}],'
    b'"payload_contract":"PI-PC1","record_kind":"aido-pi-payload-inventory.v1"}'
)
_GOLDEN_PAYLOAD_FINGERPRINT = "f16104268ae217518396898871495281e54c71078c1ca9fdb94f55aa0b63917c"
_GOLDEN_PROFILE_ID = "1425931bea7d32913885f5606a98724aa20afb4f480c16e84cf2f1fed47a239e"
_GOLDEN_PROFILE_ID_NO_EXPOSURES = "d26636bc9f3123c059f297279ce6ee60a889e202bf8234a050240ee5bc92e7a9"


def test_a7_golden_inventory_fingerprint_and_profile_id():
    tree = FakeTree()
    tree.add_file("a/b.js", b"x")
    tree.add_dir("c")
    tree.add_dir("\u00e9t\u00e9")
    tree.order = "reverse"
    inventory = tree.observe().inventory
    assert inventory.canonical_bytes == _GOLDEN_INVENTORY_BYTES
    # The fingerprint, recomputed here from the spec's formula alone.
    assert (
        hashlib.sha256(b"aido.pi-payload.v1\x00" + _GOLDEN_INVENTORY_BYTES).hexdigest()
        == _GOLDEN_PAYLOAD_FINGERPRINT
        == inventory.payload_fingerprint
    )
    assert compute_profile_id(inventory.payload_fingerprint, ["@scope/a", "left-pad"]) == _GOLDEN_PROFILE_ID
    assert compute_profile_id(inventory.payload_fingerprint, []) == _GOLDEN_PROFILE_ID_NO_EXPOSURES
    spec_profile_bytes = json.dumps(
        {
            "payload_contract": "PI-PC1",
            "payload_fingerprint": _GOLDEN_PAYLOAD_FINGERPRINT,
            "resolution_exposures": ["@scope/a", "left-pad"],
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    assert hashlib.sha256(b"aido.pi-profile.v1\x00" + spec_profile_bytes).hexdigest() == _GOLDEN_PROFILE_ID


def test_a7_the_inventory_record_round_trips_and_validates_strictly():
    files, empty_dirs = synthetic_payload_files()
    inventory = FakeTree().populate(files, empty_dirs).observe().inventory
    record = json.loads(inventory.canonical_bytes)
    again = inventory_from_record(record)
    assert again.canonical_bytes == inventory.canonical_bytes
    assert again.payload_fingerprint == inventory.payload_fingerprint


# ---------------------------------------------------------------------------
# Inventory validation adversaries (shared by the PE-2b loader later)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "entries, reason",
    [
        ((("dir", "b"), ("dir", "a")), "INVENTORY_NOT_STRICTLY_ORDERED"),
        ((("dir", "a"), ("dir", "a")), "INVENTORY_NOT_STRICTLY_ORDERED"),
        ((("dir", "A"), ("dir", "a")), "INVENTORY_CASE_FOLD_COLLISION"),
        ((("file", "a/b", "0" * 64, 0),), "INVENTORY_TREE_NOT_CLOSED"),
        ((("file", "a", "0" * 64, 0), ("file", "a/b", "0" * 64, 0)), "INVENTORY_TREE_NOT_CLOSED"),
        ((("file", "a", "0" * 63, 0),), "INVENTORY_DIGEST_MALFORMED"),
        ((("file", "a", "0" * 63 + "A", 0),), "INVENTORY_DIGEST_MALFORMED"),
        ((("file", "a", "0" * 64, True),), "INVENTORY_SIZE_OUT_OF_BOUNDS"),
        ((("file", "a", "0" * 64, -1),), "INVENTORY_SIZE_OUT_OF_BOUNDS"),
        ((("file", "a", "0" * 64, 1.0),), "INVENTORY_SIZE_OUT_OF_BOUNDS"),
        ((("link", "a"),), "INVENTORY_ENTRY_KIND_UNKNOWN"),
        ((("dir", "a", "extra"),), "INVENTORY_ENTRY_MALFORMED"),
        ((["dir", "a"],), "INVENTORY_ENTRY_MALFORMED"),
    ],
)
def test_inventory_validation_refuses_every_malformation(entries, reason):
    with pytest.raises(Cfg1PayloadError) as caught:
        inventory_from_entries(entries)
    assert caught.value.reason_code == reason


@pytest.mark.parametrize(
    "mutate",
    [
        lambda r: r.update(extra=1),
        lambda r: r.pop("payload_contract"),
        lambda r: r.update(record_kind="aido-pi-payload-inventory.v2"),
        lambda r: r.update(payload_contract="PI-PC2"),
        lambda r: r.update(entries=tuple(r["entries"])),
        lambda r: r["entries"][0].update(extra=1),
        lambda r: r["entries"][0].update(kind="file"),
        lambda r: r["entries"].append({"kind": "dir", "path": "zzz", "sha256": "0" * 64}),
    ],
)
def test_inventory_record_validation_is_closed(mutate):
    inventory = inventory_from_entries((("dir", "a"), ("file", "a/b", "0" * 64, 1)))
    record = inventory.to_record()
    mutate(record)
    with pytest.raises(Cfg1PayloadError):
        inventory_from_record(record)


def test_inventory_objects_are_immutable_and_not_constructible_outside():
    inventory = inventory_from_entries((("dir", "a"),))
    with pytest.raises(Cfg1PayloadError):
        inventory.entries = ()
    with pytest.raises(Cfg1PayloadError):
        PayloadInventory(object(), (), b"", {})
    record = inventory.to_record()
    record["entries"].append({"kind": "dir", "path": "b"})
    assert inventory.to_record()["entries"] == [{"kind": "dir", "path": "a"}]


# ---------------------------------------------------------------------------
# canonical_json_bytes (Sec. 7.1)
# ---------------------------------------------------------------------------


def test_canonical_json_bytes_matches_the_spec_formula():
    value = {"b": [1, "é", None, True], "a": {"y": 0, "x": "z"}}
    assert canonical_json_bytes(value) == json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


@pytest.mark.parametrize(
    "value",
    [1.0, -1, 2**53, (1,), {1: "a"}, "\ud800", {"a": float("nan")}, b"x", {"a": {1, 2}}],
)
def test_canonical_json_bytes_refuses_out_of_domain_values(value):
    with pytest.raises(Cfg1PayloadError):
        canonical_json_bytes(value)


def test_canonical_json_bytes_refuses_subclasses():
    class D(dict):
        pass

    class S(str):
        pass

    with pytest.raises(Cfg1PayloadError):
        canonical_json_bytes(D())
    with pytest.raises(Cfg1PayloadError):
        canonical_json_bytes([S("a")])


# ---------------------------------------------------------------------------
# PI-SC1 (Sec. 5) -- 20 paths, derivation evidence only
# ---------------------------------------------------------------------------


def test_pi_sc1_is_exactly_the_frozen_20_paths_of_the_historical_table():
    assert len(PI_SC1_PATHS) == 20 == pi_payload.PI_SC1_ENTRY_COUNT
    assert len(set(PI_SC1_PATHS)) == 20
    assert set(PI_SC1_PATHS) == set(preflight.PINNED_PI_SEAM_DIGESTS)


def test_pi_sc1_does_not_modify_the_historical_pin_table():
    assert len(preflight.PINNED_PI_SEAM_DIGESTS) == 20
    assert preflight.PINNED_PI_SEAM_DIGESTS["dist/cli.js"] == (
        "8189b66abc4f9f431dbb70941dcba690d76d040de1fbfff212886be35a53639d"
    )


def test_seam_projection_and_fingerprint_follow_the_spec():
    files, empty_dirs = synthetic_payload_files()
    inventory = FakeTree().populate(files, empty_dirs).observe().inventory
    digests = project_seam_digests(inventory)
    assert set(digests) == set(PI_SC1_PATHS)
    for path in PI_SC1_PATHS:
        assert digests[path] == hashlib.sha256(files[path]).hexdigest()
    body = json.dumps(
        {"seam_contract": "PI-SC1", "seam_digests": digests},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    assert compute_seam_fingerprint(digests) == hashlib.sha256(b"aido.pi-seam.v1\x00" + body).hexdigest()


def test_seam_fingerprint_of_the_historical_table_is_computable():
    """The genesis seam evidence (PE-2b) will cite exactly these digests."""
    fingerprint = compute_seam_fingerprint(dict(preflight.PINNED_PI_SEAM_DIGESTS))
    assert len(fingerprint) == 64


@pytest.mark.parametrize("missing", ["dist/cli.js", "node_modules/@earendil-works/pi-agent-core/dist/agent-loop.js"])
def test_seam_projection_is_none_unless_all_20_are_files(missing):
    files, empty_dirs = synthetic_payload_files()
    files = dict(files)
    del files[missing]
    tree = FakeTree().populate(files, empty_dirs)
    assert project_seam_digests(tree.observe().inventory) is None
    tree.add_dir(missing)  # present, but as a directory
    assert project_seam_digests(tree.observe().inventory) is None


@pytest.mark.parametrize(
    "digests",
    [
        {},
        {path: "0" * 64 for path in PI_SC1_PATHS[:-1]},
        {**{path: "0" * 64 for path in PI_SC1_PATHS}, "extra": "0" * 64},
        {**{path: "0" * 64 for path in PI_SC1_PATHS}, "dist/cli.js": "Z" * 64},
    ],
)
def test_seam_fingerprint_refuses_malformed_digest_maps(digests):
    with pytest.raises(Cfg1PayloadError):
        compute_seam_fingerprint(digests)


# ---------------------------------------------------------------------------
# Leaf surface (X-1): the genuine leaves stay inside the frozen native surface
# ---------------------------------------------------------------------------


def test_the_genuine_payload_leaves_are_the_pi_fs_leaves_functions():
    leaves = genuine_payload_leaves()
    assert leaves.enumerate_directory is pi_fs_leaves.enumerate_directory_no_follow
    assert leaves.read_file is pi_fs_leaves.read_payload_file_digest
    assert PayloadLeaves.__slots__ == ("enumerate_directory", "read_file")


def test_the_genuine_reader_reports_size_digest_and_stability(tmp_path):
    target = tmp_path / "a.bin"
    target.write_bytes(b"hello")
    read = pi_fs_leaves.read_payload_file_digest(str(target), 100)
    assert read.classification == CLASSIFICATION_REGULAR_FILE
    assert (read.within_bound, read.stable, read.size) == (True, True, 5)
    assert read.sha256 == hashlib.sha256(b"hello").hexdigest()
    assert read.content is None
    assert pi_fs_leaves.read_payload_file_bytes(str(target), 100).content == b"hello"
    assert pi_fs_leaves.read_payload_file_digest(str(target), 4).within_bound is False
    assert pi_fs_leaves.read_payload_file_digest(str(tmp_path), 4).classification == "directory"
    assert pi_fs_leaves.read_payload_file_digest(str(tmp_path / "nope"), 4).classification == "missing"


def test_the_genuine_enumerator_lists_through_one_handle_and_honours_its_budget(tmp_path):
    for index in range(40):
        (tmp_path / f"{index:03d}_{'x' * 200}").write_bytes(b"")
    (tmp_path / "sub").mkdir()
    listing = pi_fs_leaves.enumerate_directory_no_follow(str(tmp_path), 41)
    assert listing.complete and len(listing.entries) == 41
    assert ("sub", "directory") in listing.entries
    over = pi_fs_leaves.enumerate_directory_no_follow(str(tmp_path), 40)
    assert over.complete is False and over.over_budget is True and over.entries is None
    as_file = pi_fs_leaves.enumerate_directory_no_follow(str(tmp_path / ("000_" + "x" * 200)), 5)
    assert as_file.classification == "regular_file" and as_file.entries is None


def test_the_historical_p_leaves_are_unchanged_objects():
    """X-1 adds functions; the historical leaves keep their exact result types.

    PE-2c (PE-1 Sec. 11.2) then rebinds P's ``read_digest`` slot to the
    one-handle PAYLOAD reader (classification, exact byte count, SHA-256,
    within-bound, size stability) and adds the ``enumerate_directory`` slot.
    The historical seam reader and its result type remain unchanged objects
    in ``pi_fs_leaves``; P no longer consumes them.
    """
    from pi_harness_cfg1.pi_identity import genuine_pi_proof_leaves

    leaves = genuine_pi_proof_leaves()
    assert leaves.inspect is pi_fs_leaves.inspect_no_follow
    assert leaves.read_digest is pi_fs_leaves.read_payload_file_digest
    assert leaves.enumerate_directory is pi_fs_leaves.enumerate_directory_no_follow
    assert callable(pi_fs_leaves.read_bounded_digest)
    assert pi_fs_leaves.BoundedSeamRead.__slots__ == ("classification", "within_bound", "sha256")


# ---------------------------------------------------------------------------
# Post-implementation self-review regressions
# ---------------------------------------------------------------------------


def test_review_the_genuine_reader_refuses_a_file_that_grows_past_its_bound(tmp_path, monkeypatch):
    """The handle's reported size said 5, but 10 bytes arrive: the read stops at
    the bound and reports no digest, never a truncated one."""
    target = tmp_path / "grows.bin"
    target.write_bytes(b"x" * 10)
    monkeypatch.setattr(pi_fs_leaves, "_standard_end_of_file", lambda handle: 5)
    read = pi_fs_leaves.read_payload_file_digest(str(target), 8)
    assert read.within_bound is False and read.sha256 is None and read.size is None


def test_review_the_genuine_reader_reports_instability_when_sizes_disagree(tmp_path, monkeypatch):
    target = tmp_path / "changes.bin"
    target.write_bytes(b"x" * 10)
    sizes = iter([10, 11])
    monkeypatch.setattr(pi_fs_leaves, "_standard_end_of_file", lambda handle: next(sizes))
    read = pi_fs_leaves.read_payload_file_digest(str(target), 100)
    assert read.within_bound is True and read.stable is False
    assert read.sha256 is None and read.size is None and read.content is None
    sizes = iter([9, 9])
    monkeypatch.setattr(pi_fs_leaves, "_standard_end_of_file", lambda handle: next(sizes))
    assert pi_fs_leaves.read_payload_file_bytes(str(target), 100).stable is False


def test_review_an_unstable_genuine_read_refuses_the_walk(tmp_path, monkeypatch):
    root = tmp_path / "payload"
    write_tree(root, {"a.bin": b"x" * 10})
    sizes = iter([10, 12])
    monkeypatch.setattr(pi_fs_leaves, "_standard_end_of_file", lambda handle: next(sizes))
    _assert_refused(_observe_real(root), pi_payload.PAYLOAD_FILE_UNSTABLE)


def test_review_the_real_segment_count_bound_is_128():
    tree = FakeTree()
    tree.add_file("/".join(["d"] * 127 + ["f"]), b"")
    assert tree.observe().complete
    tree = FakeTree()
    tree.add_file("/".join(["d"] * 128 + ["f"]), b"")
    _assert_refused(tree.observe(), pi_payload.PAYLOAD_PATH_BOUND_EXCEEDED)


def test_review_a_refusal_never_names_an_entry():
    tree = FakeTree()
    tree.add_file("needle-4d2e.js", b"x")
    tree.add_file("NEEDLE-4D2E.js", b"y")
    observation = tree.observe()
    assert "4d2e" not in repr(observation).lower()
    with pytest.raises(Cfg1PayloadError) as caught:
        inventory_from_entries((("dir", "needle-4d2e"), ("dir", "NEEDLE-4D2E")))
    assert "4d2e" not in str(caught.value).lower()
