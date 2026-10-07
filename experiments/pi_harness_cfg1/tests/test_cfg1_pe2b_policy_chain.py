"""PE-2b: the policy directory, the strict canonical parser, the append-only
chain, complete recomputation, policy bounds, the committed genesis, the
``-text`` attribute rule and the loader's use of the accepted PE-2a parsers.

Acceptance rows B-1, B-2, B-3, B-4, B-12, B-13 and B-14 of
``docs/PHASE_5F3B_PI_HARNESS_PROFILE_EVOLUTION_PE1_AMENDMENT.md`` Sec. 26.2.
Every chain is SYNTHETIC under ``tmp_path`` except B-4, which loads the REAL
committed genesis bytes through the real loader -- alone, in an isolated tree, as
history -- and, separately, the REAL current committed chain (pytest, no Git). Reparse points are
leaf doubles, never real links. Nothing here runs Pi, Node or npm.
"""

from __future__ import annotations

import ast
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from pe2a_support import expected_entries, manifest_bytes, root_manifest, synthetic_payload_files
from pe2b_support import (
    SYNTHETIC_REF,
    Chain,
    Payload,
    PolicyWorld,
    approval,
    base_payload,
    genesis_like_chain,
    pmd_for,
    profile_record,
    rechain,
    retirement,
    seam_evidence,
    two_profile_chain,
    version_bump_payload,
    with_id,
)
from test_cfg1_pe2a_manifest import _B5_KEYS

from pi_harness_cfg1 import pi_fs_leaves, pi_manifest, pi_payload, pi_profile_floor
from pi_harness_cfg1 import pi_profile_policy_loader as loader
from pi_harness_cfg1.pi_fs_leaves import (
    CLASSIFICATION_OTHER,
    CLASSIFICATION_REGULAR_FILE,
    CLASSIFICATION_REPARSE_POINT,
    ENTRY_KIND_REPARSE,
    DirectoryListing,
    PayloadFileRead,
)
from pi_harness_cfg1.pi_manifest import build_manifest_bundle, bundle_manifest_paths
from pi_harness_cfg1.pi_payload import canonical_json_bytes, inventory_from_entries
from pi_harness_cfg1.pi_profile_floor import policy_file_bytes
from pi_harness_cfg1.pi_profile_policy_loader import Cfg1PolicyError
from pi_harness_cfg1.preflight import PINNED_PI_SEAM_DIGESTS

_PACKAGE_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = _PACKAGE_DIR.parents[1]


def _refuses(world: PolicyWorld, code: str | None = None, **leaves) -> str:
    with pytest.raises(Cfg1PolicyError) as caught:
        world.load(**leaves)
    if code is not None:
        assert caught.value.reason_code == code
    return caught.value.reason_code


def _world_with(tmp_path, chain: Chain, revision_bytes=None) -> PolicyWorld:
    world = PolicyWorld(tmp_path)
    world.write_chain(chain, revision_bytes)
    return world


class LeafDouble:
    """Genuine no-follow leaves plus targeted overrides; records every call."""

    def __init__(self) -> None:
        self.enumerated: list[str] = []
        self.read: list[str] = []
        self.listing_overrides: dict[str, DirectoryListing] = {}
        self.kind_overrides: dict[tuple[str, str], str] = {}
        self.read_overrides: dict[str, PayloadFileRead] = {}

    def enumerate_directory(self, path: str, max_entries: int) -> DirectoryListing:
        self.enumerated.append(path)
        if path in self.listing_overrides:
            return self.listing_overrides[path]
        listing = pi_fs_leaves.enumerate_directory_no_follow(path, max_entries)
        if listing.complete:
            entries = tuple(
                (name, self.kind_overrides.get((path, name), kind)) for name, kind in listing.entries
            )
            listing = DirectoryListing(listing.classification, True, False, entries)
        return listing

    def read_file(self, path: str, max_bytes: int) -> PayloadFileRead:
        self.read.append(path)
        if path in self.read_overrides:
            return self.read_overrides[path]
        return pi_fs_leaves.read_payload_file_bytes(path, max_bytes)

    def leaves(self) -> dict:
        return {"enumerate_directory": self.enumerate_directory, "read_file": self.read_file}


# ---------------------------------------------------------------------------
# B-1 -- layout
# ---------------------------------------------------------------------------


def test_b1_a_genesis_shaped_chain_loads_with_absent_payload_directories(tmp_path):
    world = _world_with(tmp_path, genesis_like_chain())
    assert not world.inventories.exists() and not world.bundles.exists()
    load = world.load()
    assert load.snapshot.eligible_profile_ids == frozenset()
    assert load.snapshot.aps_revision == 1


def test_b1_empty_present_payload_directories_are_accepted_when_unreferenced(tmp_path):
    world = _world_with(tmp_path, genesis_like_chain())
    world.inventories.mkdir()
    world.bundles.mkdir()
    assert world.load().snapshot.eligible_profile_ids == frozenset()


def test_b1_a_two_profile_chain_loads(tmp_path):
    chain, a, b = two_profile_chain()
    load = _world_with(tmp_path, chain).load()
    assert load.snapshot.eligible_profile_ids == frozenset({a.profile_id, b.profile_id})


@pytest.mark.parametrize("name", ["README.md", "notes.txt", ".gitkeep", "aps.r0001.json", "pi_profile_candidates"])
def test_b1_a_stray_file_at_the_top_level_refuses(tmp_path, name):
    world = _world_with(tmp_path, genesis_like_chain())
    (world.dir / name).write_bytes(b"stray")
    _refuses(world, "POLICY_STRAY_ENTRY")


@pytest.mark.parametrize("name", ["__pycache__", "profiles", "APS", "extra"])
def test_b1_a_stray_directory_at_the_top_level_refuses(tmp_path, name):
    world = _world_with(tmp_path, genesis_like_chain())
    if name == "APS":
        # Case-insensitive volumes cannot hold both; rename the real one.
        world.aps.rename(world.dir / "APS")
        _refuses(world)
        return
    (world.dir / name).mkdir()
    _refuses(world, "POLICY_STRAY_ENTRY")


@pytest.mark.parametrize(
    "name",
    [
        "README.md",
        "aps.r1.json",
        "aps.r00001.json",
        "aps.r0002.JSON",
        "APS.r0002.json",
        "aps.r0002.json.bak",
        "aps.r0002.json~",
        "~aps.r0002.json",
        ".aps.r0002.json.swp",
        "aps.r000a.json",
        "aps.r\u0661\u0662\u0663\u0664.json",
        "aps.r0002.json.tmp",
    ],
)
def test_b1_a_stray_or_misnamed_revision_file_refuses(tmp_path, name):
    world = _world_with(tmp_path, genesis_like_chain())
    (world.aps / name).write_bytes(policy_file_bytes({"x": 1}))
    _refuses(world, "POLICY_STRAY_ENTRY")


def test_b1_a_pycache_directory_inside_aps_refuses(tmp_path):
    world = _world_with(tmp_path, genesis_like_chain())
    (world.aps / "__pycache__").mkdir()
    _refuses(world, "POLICY_STRAY_ENTRY")


def test_b1_a_directory_named_like_a_revision_refuses(tmp_path):
    chain = genesis_like_chain()
    world = _world_with(tmp_path, chain)
    (world.aps / "aps.r0002.json").mkdir()
    _refuses(world, "POLICY_FILE_NOT_REGULAR")


def test_b1_aps_missing_or_empty_refuses(tmp_path):
    world = PolicyWorld(tmp_path)
    world.dir.mkdir()
    _refuses(world, "POLICY_APS_DIRECTORY_MISSING")
    world.aps.mkdir()
    _refuses(world, "POLICY_APS_EMPTY")


def test_b1_aps_as_a_file_refuses(tmp_path):
    world = PolicyWorld(tmp_path)
    world.dir.mkdir()
    (world.dir / "aps").write_bytes(b"not a directory")
    _refuses(world, "POLICY_DIRECTORY_NOT_PLAIN")


def test_b1_an_absent_policy_directory_refuses(tmp_path):
    _refuses(PolicyWorld(tmp_path), "POLICY_DIRECTORY_NOT_PLAIN")


def test_b1_a_relative_policy_directory_refuses():
    with pytest.raises(Cfg1PolicyError) as caught:
        loader._load_policy_directory("pi_profile_policy")
    assert caught.value.reason_code == "POLICY_DIRECTORY_MALFORMED"


def test_b1_an_unreferenced_inventory_or_bundle_refuses(tmp_path):
    chain, _a, _b = two_profile_chain()
    world = _world_with(tmp_path, chain)
    other = version_bump_payload("9.9.9")
    (world.inventories / (other.fingerprint + ".json")).write_bytes(other.inventory_bytes)
    _refuses(world, "POLICY_UNREFERENCED_FILE")
    (world.inventories / (other.fingerprint + ".json")).unlink()
    (world.bundles / (other.fingerprint + ".json")).write_bytes(other.bundle_bytes)
    _refuses(world, "POLICY_UNREFERENCED_FILE")


def test_b1_payload_files_present_for_a_genesis_shaped_chain_are_unreferenced(tmp_path):
    world = _world_with(tmp_path, genesis_like_chain())
    world.write_payload(base_payload())
    _refuses(world, "POLICY_UNREFERENCED_FILE")


@pytest.mark.parametrize("which", ["inventories", "manifest_bundles"])
def test_b1_a_missing_referenced_file_or_directory_refuses(tmp_path, which):
    chain, a, _b = two_profile_chain()
    world = _world_with(tmp_path, chain)
    (world.dir / which / (a.fingerprint + ".json")).unlink()
    _refuses(world, "POLICY_REFERENCED_FILE_MISSING")
    shutil.rmtree(world.dir / which)
    _refuses(world, "POLICY_REFERENCED_FILE_MISSING")


@pytest.mark.parametrize(
    "rename",
    [
        lambda fp: fp.upper() + ".json",
        lambda fp: fp[:63] + ".json",
        lambda fp: fp + ".JSON",
        lambda fp: fp + ".json.bak",
        lambda fp: fp,
    ],
)
def test_b1_a_badly_named_payload_file_refuses(tmp_path, rename):
    chain, a, _b = two_profile_chain()
    world = _world_with(tmp_path, chain)
    source = world.inventories / (a.fingerprint + ".json")
    source.rename(world.inventories / rename(a.fingerprint))
    _refuses(world, "POLICY_UNREFERENCED_FILE")


def test_b1_a_directory_in_place_of_a_referenced_file_refuses(tmp_path):
    chain, a, _b = two_profile_chain()
    world = _world_with(tmp_path, chain)
    target = world.bundles / (a.fingerprint + ".json")
    target.unlink()
    target.mkdir()
    _refuses(world, "POLICY_FILE_NOT_REGULAR")


def test_b1_a_stray_in_a_payload_directory_refuses(tmp_path):
    chain, _a, _b = two_profile_chain()
    world = _world_with(tmp_path, chain)
    (world.inventories / "__pycache__").mkdir()
    _refuses(world, "POLICY_UNREFERENCED_FILE")


@pytest.mark.parametrize("where", ["policy", "aps", "inventories", "manifest_bundles"])
def test_b1_a_reparse_directory_refuses_and_is_never_listed(tmp_path, where):
    chain, _a, _b = two_profile_chain()
    world = _world_with(tmp_path, chain)
    double = LeafDouble()
    target = str(world.dir) if where == "policy" else str(world.dir / where)
    double.listing_overrides[target] = DirectoryListing(CLASSIFICATION_REPARSE_POINT, False, False, None)
    _refuses(world, "POLICY_DIRECTORY_NOT_PLAIN", **double.leaves())
    assert not any(path.startswith(target + "\\") for path in double.read)


@pytest.mark.parametrize("where", ["aps", "inventories", "manifest_bundles"])
def test_b1_a_reparse_entry_at_the_top_level_refuses(tmp_path, where):
    chain, _a, _b = two_profile_chain()
    world = _world_with(tmp_path, chain)
    double = LeafDouble()
    double.kind_overrides[(str(world.dir), where)] = ENTRY_KIND_REPARSE
    _refuses(world, "POLICY_DIRECTORY_NOT_PLAIN", **double.leaves())


def test_b1_a_reparse_revision_entry_refuses(tmp_path):
    world = _world_with(tmp_path, genesis_like_chain())
    double = LeafDouble()
    double.kind_overrides[(str(world.aps), "aps.r0001.json")] = ENTRY_KIND_REPARSE
    _refuses(world, "POLICY_FILE_NOT_REGULAR", **double.leaves())
    assert double.read == []


@pytest.mark.parametrize("which", ["inventories", "manifest_bundles"])
def test_b1_a_reparse_payload_entry_refuses_before_any_payload_read(tmp_path, which):
    chain, a, _b = two_profile_chain()
    world = _world_with(tmp_path, chain)
    double = LeafDouble()
    double.kind_overrides[(str(world.dir / which), a.fingerprint + ".json")] = ENTRY_KIND_REPARSE
    _refuses(world, "POLICY_FILE_NOT_REGULAR", **double.leaves())
    assert all("\\aps\\" in path for path in double.read)


@pytest.mark.parametrize("classification", [CLASSIFICATION_REPARSE_POINT, CLASSIFICATION_OTHER, "directory", "missing"])
def test_b1_a_file_that_is_not_regular_at_open_refuses(tmp_path, classification):
    chain, a, _b = two_profile_chain()
    world = _world_with(tmp_path, chain)
    double = LeafDouble()
    double.read_overrides[str(world.inventories / (a.fingerprint + ".json"))] = PayloadFileRead(
        classification, False, False, None, None, None
    )
    _refuses(world, "POLICY_FILE_NOT_REGULAR", **double.leaves())


def test_b1_an_unstable_or_malformed_leaf_read_refuses(tmp_path):
    world = _world_with(tmp_path, genesis_like_chain())
    path = str(world.aps / "aps.r0001.json")
    double = LeafDouble()
    double.read_overrides[path] = PayloadFileRead(CLASSIFICATION_REGULAR_FILE, True, False, None, None, None)
    _refuses(world, "POLICY_FILE_UNSTABLE", **double.leaves())
    data = (world.aps / "aps.r0001.json").read_bytes()
    double.read_overrides[path] = PayloadFileRead(
        CLASSIFICATION_REGULAR_FILE, True, True, len(data), "0" * 64, data
    )
    _refuses(world, "POLICY_LEAF_MALFORMED", **double.leaves())
    double.read_overrides[path] = "not a read"
    _refuses(world, "POLICY_LEAF_MALFORMED", **double.leaves())


def test_b1_an_incomplete_or_malformed_listing_refuses(tmp_path):
    world = _world_with(tmp_path, genesis_like_chain())
    double = LeafDouble()
    double.listing_overrides[str(world.aps)] = DirectoryListing("directory", False, False, None)
    _refuses(world, "POLICY_DIRECTORY_UNREADABLE", **double.leaves())
    double.listing_overrides[str(world.aps)] = DirectoryListing("directory", False, True, None)
    _refuses(world, "POLICY_DIRECTORY_ENTRY_BOUND_EXCEEDED", **double.leaves())
    double.listing_overrides[str(world.aps)] = DirectoryListing(
        "directory", True, False, (("aps.r0001.json", "file"), ("aps.r0001.json", "file"))
    )
    _refuses(world, "POLICY_DIRECTORY_DUPLICATE_ENTRY", **double.leaves())
    double.listing_overrides[str(world.aps)] = ("aps.r0001.json",)
    _refuses(world, "POLICY_LEAF_MALFORMED", **double.leaves())


# ---------------------------------------------------------------------------
# B-2 -- chain, canonical bytes and type strictness
# ---------------------------------------------------------------------------


def _three_revision_chain() -> Chain:
    chain = genesis_like_chain()
    base = base_payload()
    other_digests = dict(base.facts.seam_digests_dict())
    other_digests["dist/main.js"] = "11" * 32
    chain.revision(seam_evidence=[seam_evidence(other_digests)])
    third = dict(other_digests)
    third["dist/cli.js"] = "22" * 32
    chain.revision(seam_evidence=[seam_evidence(third)])
    return chain


def test_b2_a_three_revision_chain_loads_with_contiguous_heads(tmp_path):
    chain = _three_revision_chain()
    load = _world_with(tmp_path, chain).load()
    data = chain.file_bytes()
    assert [entry[0] for entry in load.revisions] == [1, 2, 3]
    assert [entry[1] for entry in load.revisions] == [hashlib.sha256(item).hexdigest() for item in data]
    assert load.snapshot.aps_head_sha256 == hashlib.sha256(data[-1]).hexdigest()
    assert load.snapshot.aps_revision == 3


def test_b2_a_gap_refuses(tmp_path):
    world = _world_with(tmp_path, _three_revision_chain())
    (world.aps / "aps.r0002.json").unlink()
    _refuses(world, "POLICY_APS_NOT_CONTIGUOUS")


def test_b2_a_missing_first_revision_refuses(tmp_path):
    world = _world_with(tmp_path, _three_revision_chain())
    (world.aps / "aps.r0001.json").unlink()
    _refuses(world, "POLICY_APS_NOT_CONTIGUOUS")


def test_b2_r0000_refuses(tmp_path):
    world = _world_with(tmp_path, genesis_like_chain())
    (world.aps / "aps.r0000.json").write_bytes((world.aps / "aps.r0001.json").read_bytes())
    _refuses(world, "POLICY_APS_NOT_CONTIGUOUS")


def test_b2_a_revision_field_that_disagrees_with_its_file_name_refuses(tmp_path):
    chain = _three_revision_chain()
    records = [dict(record) for record in chain.records]
    records[1]["revision"] = 1
    _refuses(_world_with(tmp_path, chain, rechain(records)), "POLICY_APS_REVISION_MISMATCH")


def test_b2_a_duplicate_revision_copy_refuses(tmp_path):
    """r0002 a byte copy of r0001: its revision field and previous digest lie."""
    world = _world_with(tmp_path, genesis_like_chain())
    (world.aps / "aps.r0002.json").write_bytes((world.aps / "aps.r0001.json").read_bytes())
    _refuses(world, "POLICY_APS_REVISION_MISMATCH")


def test_b2_previous_digest_mismatch_refuses(tmp_path):
    chain = _three_revision_chain()
    records = [dict(record) for record in chain.records]
    data = rechain(records)
    tampered = dict(records[2])
    tampered["previous_revision_sha256"] = "0" * 64
    data[2] = policy_file_bytes(tampered)
    _refuses(_world_with(tmp_path, chain, data), "POLICY_APS_PREVIOUS_DIGEST_MISMATCH")
    tampered["previous_revision_sha256"] = None
    data[2] = policy_file_bytes(tampered)
    _refuses(_world_with(tmp_path, chain, data), "POLICY_APS_PREVIOUS_DIGEST_MISMATCH")


def test_b2_a_genesis_with_a_previous_digest_refuses(tmp_path):
    chain = genesis_like_chain()
    record = dict(chain.records[0])
    record["previous_revision_sha256"] = "0" * 64
    _refuses(_world_with(tmp_path, chain, [policy_file_bytes(record)]), "POLICY_APS_PREVIOUS_DIGEST_MISMATCH")


def test_b2_an_edited_historical_revision_refuses(tmp_path):
    """Editing r0001 in place (even canonically) breaks r0002's digest."""
    chain = _three_revision_chain()
    data = chain.file_bytes()
    record = json.loads(data[0])
    record["seam_evidence"][0]["evidence"] = [dict(SYNTHETIC_REF, repo_path="docs/edited.md")]
    record["seam_evidence"][0] = with_id(record["seam_evidence"][0], "evidence_id")
    data[0] = policy_file_bytes(record)
    _refuses(_world_with(tmp_path, chain, data), "POLICY_APS_PREVIOUS_DIGEST_MISMATCH")


@pytest.mark.parametrize("edit", ["edit", "remove", "reorder", "replace"])
def test_b2_an_edited_removed_reordered_or_replaced_record_refuses(tmp_path, edit):
    chain = _three_revision_chain()
    records = [json.loads(item) for item in chain.file_bytes()]
    later = records[2]["seam_evidence"]
    if edit == "edit":
        later[0]["evidence"] = [dict(SYNTHETIC_REF, repo_path="docs/edited.md")]
        later[0] = with_id(later[0], "evidence_id")
    elif edit == "remove":
        del later[1]
    elif edit == "reorder":
        later[0], later[1] = later[1], later[0]
    else:
        later[1] = with_id(dict(later[1], evidence=[dict(SYNTHETIC_REF, sha256="cd" * 32)]), "evidence_id")
    _refuses(_world_with(tmp_path, chain, rechain(records)), "POLICY_APS_NOT_APPEND_ONLY")


def test_b2_a_removed_profile_approval_or_retirement_refuses(tmp_path):
    chain, a, _b = two_profile_chain()
    chain.revision(retirements=[retirement(a.profile_id)])
    for list_name in ("profiles", "approvals", "retirements"):
        records = [json.loads(item) for item in chain.file_bytes()]
        records.append(dict(records[-1], revision=4))
        records[3][list_name] = records[3][list_name][:-1]
        _refuses(_world_with(tmp_path / list_name, chain, rechain(records)), "POLICY_APS_NOT_APPEND_ONLY")


def test_b2_a_duplicate_seam_evidence_record_refuses(tmp_path):
    chain = genesis_like_chain()
    chain.revision(seam_evidence=[chain.lists["seam_evidence"][0]])
    _refuses(_world_with(tmp_path, chain), "POLICY_DUPLICATE_EVIDENCE_ID")


def _genesis_bytes() -> bytes:
    return genesis_like_chain().file_bytes()[0]


@pytest.mark.parametrize(
    "mutate, code",
    [
        (lambda b: b.replace(b"\n", b"\r\n"), "POLICY_FILE_CONTAINS_CR"),
        (lambda b: b[:-1] + b"\r\n", "POLICY_FILE_CONTAINS_CR"),
        (lambda b: b.replace(b'"revision":1', b'"revision":1\r'), "POLICY_FILE_CONTAINS_CR"),
        (lambda b: b[:-1], "POLICY_FILE_LINE_ENDING"),
        (lambda b: b + b"\n", "POLICY_FILE_LINE_ENDING"),
        (lambda b: b.replace(b",", b",\n", 1), "POLICY_FILE_LINE_ENDING"),
        (lambda b: b.replace(b'"revision":1', b'"revision": 1'), "POLICY_NOT_CANONICAL"),
        (lambda b: b" " + b, "POLICY_NOT_CANONICAL"),
        (lambda b: b[:-1] + b" \n", "POLICY_NOT_CANONICAL"),
        (lambda b: b.replace(b"aido-pi-approved", b"aido-pi-appr\\u006fved"), "POLICY_NOT_CANONICAL"),
        (lambda b: b.replace(b"HPP-1", "HPP\u20111".encode("utf-8")), "POLICY_FILE_NOT_ASCII"),
        (lambda b: b"\xef\xbb\xbf" + b, "POLICY_FILE_NOT_ASCII"),
        (lambda b: b.replace(b'"revision":1', b'"revision":1.0'), "POLICY_FLOAT"),
        (lambda b: b.replace(b'"revision":1', b'"revision":1e0'), "POLICY_FLOAT"),
        (lambda b: b.replace(b'"revision":1', b'"revision":NaN'), "POLICY_NON_FINITE_NUMBER"),
        (lambda b: b.replace(b'"revision":1', b'"revision":Infinity'), "POLICY_NON_FINITE_NUMBER"),
        (lambda b: b.replace(b'"revision":1', b'"revision":-Infinity'), "POLICY_NON_FINITE_NUMBER"),
        (lambda b: b.replace(b'"revision":1', b'"revision":-1'), "POLICY_INT_OUT_OF_RANGE"),
        (lambda b: b.replace(b'"revision":1', b'"revision":01'), "POLICY_JSON_INVALID"),
        (lambda b: b.replace(b'"revision":1', b'"revision":1,"revision":1'), "POLICY_DUPLICATE_KEY"),
        (lambda b: b"[" + b[:-1] + b"]\n", "POLICY_TOP_LEVEL_NOT_OBJECT"),
        (lambda b: b[:-2] + b"\n", "POLICY_JSON_INVALID"),
        (lambda b: b.replace(b"HPP-1", b"HPP\\x2d1"), "POLICY_JSON_INVALID"),
    ],
)
def test_b2_non_canonical_or_malformed_bytes_refuse(tmp_path, mutate, code):
    data = mutate(_genesis_bytes())
    world = PolicyWorld(tmp_path)
    world.write_revisions([data])
    _refuses(world, code)


@pytest.mark.parametrize(
    "data, code",
    [
        (b'{"a":"\\ud800"}\n', "POLICY_NOT_CANONICAL"),
        (b'{"a":"\\u00e9"}\n', None),
        (b'{"a":"\\u00E9"}\n', "POLICY_NOT_CANONICAL"),
        (b'{"a":"\\/"}\n', "POLICY_NOT_CANONICAL"),
        (b'{"a":"\x01"}\n', "POLICY_JSON_INVALID"),
        (b'{"a":true}\n', None),
        (b'{"a":True}\n', "POLICY_JSON_INVALID"),
        (b"{}\n", None),
        (b"\n", "POLICY_JSON_INVALID"),
        (b"", "POLICY_FILE_LINE_ENDING"),
        ("text", "POLICY_FILE_MALFORMED"),
        (bytearray(b"{}\n"), "POLICY_FILE_MALFORMED"),
    ],
)
def test_b2_the_strict_policy_parser_admits_exactly_one_encoding(data, code):
    if code is None:
        assert type(loader._parse_policy_bytes(data)) is dict
        return
    with pytest.raises(Cfg1PolicyError) as caught:
        loader._parse_policy_bytes(data)
    assert caught.value.reason_code == code


def test_b2_key_order_is_part_of_canonical_bytes(tmp_path):
    record = genesis_like_chain().records[0]
    reordered = json.dumps(record, separators=(",", ":"), ensure_ascii=True).encode("ascii") + b"\n"
    assert reordered != policy_file_bytes(record)
    world = PolicyWorld(tmp_path)
    world.write_revisions([reordered])
    _refuses(world, "POLICY_NOT_CANONICAL")


@pytest.mark.parametrize("value", [True, False, None, "1", [1]])
def test_b2_bool_or_other_types_never_satisfy_the_revision_integer(tmp_path, value):
    record = dict(genesis_like_chain().records[0])
    record["revision"] = value
    world = PolicyWorld(tmp_path)
    world.write_revisions([policy_file_bytes(record)])
    _refuses(world, "POLICY_APS_REVISION_MISMATCH")


@pytest.mark.parametrize("field", ["seam_evidence", "profiles", "approvals", "retirements"])
@pytest.mark.parametrize("value", [None, {}, "x", 0, True])
def test_b2_a_list_field_of_the_wrong_type_refuses(tmp_path, field, value):
    record = dict(genesis_like_chain().records[0])
    record[field] = value
    world = PolicyWorld(tmp_path)
    world.write_revisions([policy_file_bytes(record)])
    _refuses(world, "POLICY_APS_LIST_MALFORMED")


@pytest.mark.parametrize(
    "field, value, code",
    [
        ("record_kind", "aido-pi-approved-profile-set.v2", "POLICY_APS_KIND"),
        ("consumer_contract", "CFG1-CC2", "POLICY_CONSUMER_CONTRACT"),
        ("policy_revision", "HPP-2", "POLICY_POLICY_REVISION"),
        ("payload_contract", "PI-PC2", "POLICY_PAYLOAD_CONTRACT"),
        ("seam_contract", "pi-sc1", "POLICY_SEAM_CONTRACT"),
    ],
)
def test_b2_every_literal_is_exact(tmp_path, field, value, code):
    record = dict(genesis_like_chain().records[0])
    record[field] = value
    world = PolicyWorld(tmp_path)
    world.write_revisions([policy_file_bytes(record)])
    _refuses(world, code)


@pytest.mark.parametrize("extra", ["eligible", "approved", "active", "latest", "head"])
def test_b2_no_mutable_authority_bit_can_be_added(tmp_path, extra):
    chain, a, _b = two_profile_chain()
    records = [json.loads(item) for item in chain.file_bytes()]
    records[0][extra] = True
    _refuses(_world_with(tmp_path / "aps", chain, rechain(records)), "POLICY_APS_KEYS")
    records = [json.loads(item) for item in chain.file_bytes()]
    records[0]["approvals"][0][extra] = True
    records[1]["approvals"][0][extra] = True
    _refuses(_world_with(tmp_path / "approval", chain, rechain(records)), "POLICY_APPROVAL_KEYS")
    records = [json.loads(item) for item in chain.file_bytes()]
    records[0]["profiles"][0][extra] = True
    records[1]["profiles"][0][extra] = True
    _refuses(_world_with(tmp_path / "profile", chain, rechain(records)), "POLICY_PROFILE_KEYS")


@pytest.mark.parametrize("extra", ["inventory_ref", "manifest_bundle_ref", "path", "approved"])
def test_b2_a_profile_record_carrying_a_path_or_flag_key_refuses(tmp_path, extra):
    a = base_payload()
    chain = Chain()
    chain.revision(profiles=[a.profile(**{extra: "inventories/" + a.fingerprint + ".json"})], payloads=[a])
    _refuses(_world_with(tmp_path, chain), "POLICY_PROFILE_KEYS")


# ---------------------------------------------------------------------------
# B-3 -- every derivable field is recomputed; forged ids refuse
# ---------------------------------------------------------------------------


def _single_profile_chain(profile: dict | None = None, payload: Payload | None = None) -> Chain:
    a = payload or base_payload()
    chain = Chain()
    record = a.profile() if profile is None else profile
    chain.revision(
        profiles=[record],
        approvals=[approval(record["profile_id"], "C3_SEAM_CHANGED")],
        payloads=[a],
    )
    return chain


def test_b3_the_untampered_single_profile_chain_loads(tmp_path):
    a = base_payload()
    load = _world_with(tmp_path, _single_profile_chain(payload=a)).load()
    assert load.snapshot.eligible_profile_ids == frozenset({a.profile_id})


def _tamper_profile(tmp_path, mutate, code):
    a = base_payload()
    record = a.profile()
    mutate(record)
    _refuses(_world_with(tmp_path, _single_profile_chain(record, a)), code)


def test_b3_a_forged_payload_fingerprint_never_redirects_the_loader(tmp_path):
    """A forged fingerprint names no committed file; the genuine files become
    unreferenced -> refused before any payload file is read."""
    a = base_payload()
    record = a.profile(payload_fingerprint="ab" * 32)
    world = _world_with(tmp_path, _single_profile_chain(record, a))
    double = LeafDouble()
    _refuses(world, "POLICY_UNREFERENCED_FILE", **double.leaves())
    assert all("\\aps\\" in path for path in double.read)
    for directory in (world.inventories, world.bundles):
        (directory / (a.fingerprint + ".json")).unlink()
    _refuses(world, "POLICY_REFERENCED_FILE_MISSING")


def test_b3_a_forged_fingerprint_with_renamed_files_refuses_on_recomputation(tmp_path):
    a = base_payload()
    forged = "cd" * 32
    record = a.profile(payload_fingerprint=forged)
    world = PolicyWorld(tmp_path)
    chain = _single_profile_chain(record, a)
    world.write_revisions(chain.file_bytes())
    world.inventories.mkdir()
    world.bundles.mkdir()
    (world.inventories / (forged + ".json")).write_bytes(a.inventory_bytes)
    (world.bundles / (forged + ".json")).write_bytes(a.bundle_bytes)
    _refuses(world, "POLICY_INVENTORY_FINGERPRINT_MISMATCH")


@pytest.mark.parametrize("value", ["AB" * 32, "ab" * 31, "../" + "a" * 61, None, 7, "ab" * 32 + "\n"])
def test_b3_a_malformed_fingerprint_never_forms_a_file_name(tmp_path, value):
    double = LeafDouble()
    a = base_payload()
    record = a.profile(payload_fingerprint=value)
    world = _world_with(tmp_path, _single_profile_chain(record, a))
    _refuses(world, "POLICY_PAYLOAD_FINGERPRINT_MALFORMED", **double.leaves())
    assert all("\\aps\\" in path for path in double.read)


def test_b3_a_tampered_seam_digest_refuses(tmp_path):
    def _mutate(record):
        record["seam_digests"]["dist/main.js"] = "ee" * 32

    _tamper_profile(tmp_path, _mutate, "POLICY_SEAM_DIGESTS_MISMATCH")


def test_b3_a_tampered_seam_fingerprint_refuses(tmp_path):
    _tamper_profile(tmp_path, lambda r: r.update(seam_fingerprint="ee" * 32), "POLICY_SEAM_FINGERPRINT_MISMATCH")


@pytest.mark.parametrize("field", ["package_name", "package_version", "pi_ai_version", "pi_agent_core_version"])
def test_b3_tampered_declared_provenance_refuses(tmp_path, field):
    """Counterexample 12: false declared metadata with correct hashes."""

    def _mutate(record):
        record["declared"][field] = "9.9.9"

    _tamper_profile(tmp_path, _mutate, "POLICY_DECLARED_MISMATCH")


@pytest.mark.parametrize(
    "exposures, code",
    [
        (["left-pad"], "POLICY_EXPOSURES_MISMATCH"),
        (["zzz-not-a-dependency"], "POLICY_EXPOSURES_MISMATCH"),
        (["b", "a"], "POLICY_EXPOSURES_MALFORMED"),
        (["a", "a"], "POLICY_EXPOSURES_MALFORMED"),
        (["../x"], "POLICY_EXPOSURES_MALFORMED"),
        (["Left-Pad"], "POLICY_EXPOSURES_MALFORMED"),
        ([1], "POLICY_EXPOSURES_MALFORMED"),
    ],
)
def test_b3_tampered_exposures_refuse(tmp_path, exposures, code):
    _tamper_profile(tmp_path, lambda r: r.update(resolution_exposures=exposures), code)


def test_b3_exposures_are_recomputed_for_an_exposed_payload(tmp_path):
    from pe2b_support import exposed_payload

    exposed = exposed_payload()
    assert exposed.facts.resolution_exposures == ("@ghost/pkg", "missing-dep")
    load = _world_with(tmp_path, _single_profile_chain(payload=exposed)).load()
    (view,) = load.snapshot.eligible_profiles
    assert view.resolution_exposures == (("@ghost", "pkg"), ("missing-dep",))
    record = exposed.profile(resolution_exposures=["missing-dep"])
    _refuses(_world_with(tmp_path / "t", _single_profile_chain(record, exposed)), "POLICY_EXPOSURES_MISMATCH")


def test_b3_a_forged_profile_id_refuses_even_with_a_matching_approval(tmp_path):
    _tamper_profile(tmp_path, lambda r: r.update(profile_id="ab" * 32), "POLICY_PROFILE_ID_MISMATCH")


@pytest.mark.parametrize(
    "field, value, code",
    [
        ("payload_contract", "PI-PC2", "POLICY_PAYLOAD_CONTRACT"),
        ("seam_contract", "PI-SC2", "POLICY_SEAM_CONTRACT"),
        ("record_kind", "aido-pi-profile.v2", "POLICY_PROFILE_KIND"),
        ("discovery", {"aido_commit": "A" * 40, "discovery_tool_revision": "PE-2a"}, "POLICY_DISCOVERY_MALFORMED"),
        ("discovery", {"aido_commit": "0" * 40, "discovery_tool_revision": "PE 2a"}, "POLICY_DISCOVERY_MALFORMED"),
        ("discovery", {"aido_commit": "0" * 40}, "POLICY_DISCOVERY_KEYS"),
        ("declared", {"package_name": "x"}, "POLICY_DECLARED_KEYS"),
        ("seam_digests", {}, "POLICY_SEAM_DIGESTS_MALFORMED"),
    ],
)
def test_b3_profile_schema_violations_refuse(tmp_path, field, value, code):
    _tamper_profile(tmp_path, lambda r: r.update({field: value}), code)


def test_b3_seam_evidence_fingerprint_and_id_are_recomputed(tmp_path):
    record = seam_evidence(base_payload().facts.seam_digests_dict())
    forged_fp = dict(record, seam_fingerprint="ee" * 32)
    chain = Chain()
    chain.revision(seam_evidence=[with_id(forged_fp, "evidence_id")])
    _refuses(_world_with(tmp_path / "fp", chain), "POLICY_SEAM_FINGERPRINT_MISMATCH")
    edited = dict(record)
    edited["seam_digests"] = dict(record["seam_digests"], **{"dist/main.js": "ee" * 32})
    chain = Chain()
    chain.revision(seam_evidence=[with_id(edited, "evidence_id")])
    _refuses(_world_with(tmp_path / "digests", chain), "POLICY_SEAM_FINGERPRINT_MISMATCH")
    chain = Chain()
    chain.revision(seam_evidence=[dict(record, evidence_id="ab" * 32)])
    _refuses(_world_with(tmp_path / "id", chain), "POLICY_EVIDENCE_ID_MISMATCH")
    chain = Chain()
    chain.revision(seam_evidence=[dict(record, evidence=[dict(SYNTHETIC_REF, repo_path="docs/other.md")])])
    _refuses(_world_with(tmp_path / "content", chain), "POLICY_EVIDENCE_ID_MISMATCH")


def test_b3_approval_and_retirement_ids_are_recomputed(tmp_path):
    a = base_payload()
    good = approval(a.profile_id, "C3_SEAM_CHANGED")
    chain = Chain()
    chain.revision(profiles=[a.profile()], approvals=[dict(good, approval_id="ab" * 32)], payloads=[a])
    _refuses(_world_with(tmp_path / "approval_id", chain), "POLICY_APPROVAL_ID_MISMATCH")
    chain = Chain()
    chain.revision(
        profiles=[a.profile()], approvals=[dict(good, acceptance_reference="EDITED")], payloads=[a]
    )
    _refuses(_world_with(tmp_path / "approval_content", chain), "POLICY_APPROVAL_ID_MISMATCH")
    chain = _single_profile_chain(payload=a)
    good_retirement = retirement(a.profile_id)
    chain.revision(retirements=[dict(good_retirement, retirement_id="ab" * 32)])
    _refuses(_world_with(tmp_path / "retirement_id", chain), "POLICY_RETIREMENT_ID_MISMATCH")
    chain = _single_profile_chain(payload=a)
    chain.revision(retirements=[dict(good_retirement, reason_code="SECURITY_ADVISORY")])
    _refuses(_world_with(tmp_path / "retirement_content", chain), "POLICY_RETIREMENT_ID_MISMATCH")


def test_b3_a_valid_profile_paired_with_another_payloads_inventory_refuses(tmp_path):
    a = base_payload()
    other = version_bump_payload()
    world = _world_with(tmp_path, _single_profile_chain(payload=a))
    (world.inventories / (a.fingerprint + ".json")).write_bytes(other.inventory_bytes)
    _refuses(world, "POLICY_INVENTORY_FINGERPRINT_MISMATCH")


def test_b3_a_valid_inventory_paired_with_another_payloads_bundle_refuses(tmp_path):
    a = base_payload()
    other = version_bump_payload()
    world = _world_with(tmp_path, _single_profile_chain(payload=a))
    (world.bundles / (a.fingerprint + ".json")).write_bytes(other.bundle_bytes)
    _refuses(world, "POLICY_MANIFEST_BUNDLE_INVALID")


def test_b3_a_bundle_with_the_right_fingerprint_but_unbound_manifest_bytes_refuses(tmp_path):
    a = base_payload()
    other = version_bump_payload()
    record = json.loads(a.bundle_bytes)
    record["manifests"]["package.json"] = json.loads(other.bundle_bytes)["manifests"]["package.json"]
    world = _world_with(tmp_path, _single_profile_chain(payload=a))
    (world.bundles / (a.fingerprint + ".json")).write_bytes(policy_file_bytes(record))
    _refuses(world, "POLICY_MANIFEST_BUNDLE_INVALID")


def test_b3_a_non_canonical_inventory_or_bundle_file_refuses(tmp_path):
    a = base_payload()
    world = _world_with(tmp_path, _single_profile_chain(payload=a))
    path = world.inventories / (a.fingerprint + ".json")
    path.write_bytes(a.inventory_bytes.replace(b'"dir"', b'"dir" ', 1))
    _refuses(world, "POLICY_NOT_CANONICAL")
    path.write_bytes(a.inventory_bytes.replace(b"\n", b"\r\n"))
    _refuses(world, "POLICY_FILE_CONTAINS_CR")


# ---------------------------------------------------------------------------
# B-4 -- the REAL committed genesis r0001 (exact bytes, isolated) and the REAL
# current committed chain it heads (pytest, no Git)
# ---------------------------------------------------------------------------

_GENESIS_EVIDENCE = (
    (
        "docs/PHASE_5F3B_HARNESS_CFG1_LAUNCH_CONFIGURATION_ISOLATION_DESIGN.md",
        "dee474f01e928f7bf56349fbfcf19b0bdb5f82b196d531121fabff1a4e5f51f8",
    ),
    (
        "docs/PHASE_5F3B_HARNESS_CFG1_L16_FU2_RUNTIME_CAPABILITY_OBSERVATION_DESIGN.md",
        "d224e4c644c0bcac3605d2b9e8fc54295fcfdb967001bfe332236899dbb5aef5",
    ),
    (
        "docs/PHASE_5F3B_HARNESS_CFG1_L1_BOUNDARY_FU1_OC3_AMEND1_DESIGN.md",
        "bd8569e460e5e2ffccb33d63f3d70e41ea3007246207a43ee27a754ba055c14e",
    ),
)
_GENESIS_HEAD_SHA256 = "69922eb557e783b9a4bb6e504092a5de4c82812fa477a8bd59b28bf30a53c373"
#: PE-5 appended r0002 (HPP-1 approval of the PE-3 candidate). Genesis r0001 is
#: HISTORY from then on: its own properties are proved against its exact bytes in
#: an isolated tree, never by assuming the genuine head IS genesis.
_PE5_PROFILE_ID = "56651d0b2b6995e05b6de3aa012f5a82f276b2ac817dcce00844d1db2a9ffd67"
_PE5_PAYLOAD_FINGERPRINT = "66cf8a815d91aeaf3eb920763c6a4f3b98c17625dbaa93c540fb424c451664dc"


def _load_exact_genesis(tmp_path) -> object:
    """The EXACT committed r0001 bytes, alone in an isolated tree, through the real loader."""
    data = (_PACKAGE_DIR / "pi_profile_policy" / "aps" / "aps.r0001.json").read_bytes()
    assert hashlib.sha256(data).hexdigest() == _GENESIS_HEAD_SHA256
    aps = tmp_path / "exact_genesis" / "pi_profile_policy" / "aps"
    aps.mkdir(parents=True)
    (aps / "aps.r0001.json").write_bytes(data)
    return loader._load_policy_directory(str(aps.parent))


def test_b4_the_exact_historical_genesis_r0001_loads_through_the_real_loader(tmp_path):
    load = _load_exact_genesis(tmp_path)
    snapshot = load.snapshot
    assert snapshot.aps_revision == 1
    assert snapshot.eligible_profile_ids == frozenset()
    assert snapshot.eligible_profiles == ()
    assert snapshot.aps_head_sha256 == _GENESIS_HEAD_SHA256
    assert snapshot.policy_directory == str(tmp_path / "exact_genesis" / "pi_profile_policy")
    assert (snapshot.policy_revision, snapshot.payload_contract, snapshot.seam_contract, snapshot.consumer_contract) == (
        "HPP-1",
        "PI-PC1",
        "PI-SC1",
        "CFG1-CC1",
    )
    assert load.revisions == ((1, _GENESIS_HEAD_SHA256, frozenset()),)
    # zero profiles of any status (retired ones included), so zero approvals and retirements took effect
    assert load.profile_declared_versions == ()
    assert load.head_reference.eligible_payloads == ()
    assert load.head_reference.present_ineligible_profile_ids == frozenset()
    assert load.head_reference.seam_fingerprints == frozenset(
        {pi_payload.compute_seam_fingerprint(dict(PINNED_PI_SEAM_DIGESTS))}
    )
    record = loader._parse_policy_bytes(
        (tmp_path / "exact_genesis" / "pi_profile_policy" / "aps" / "aps.r0001.json").read_bytes()
    )
    assert record["profiles"] == [] and record["approvals"] == [] and record["retirements"] == []
    assert [evidence["evidence_id"] for evidence in record["seam_evidence"]] == [
        "37ba281569b1ca52b497a1e1a504e57f53be4c39ce39796033ccfd406ea4cd08"
    ]


def test_b4_the_current_genuine_chain_appends_r0002_to_the_unchanged_genesis():
    genuine = _PACKAGE_DIR / "pi_profile_policy"
    fingerprint_file = _PE5_PAYLOAD_FINGERPRINT + ".json"
    assert sorted(path.relative_to(genuine).as_posix() for path in genuine.rglob("*")) == [
        "aps",
        "aps/aps.r0001.json",
        "aps/aps.r0002.json",
        "inventories",
        "inventories/" + fingerprint_file,
        "manifest_bundles",
        "manifest_bundles/" + fingerprint_file,
    ]
    r0001 = (genuine / "aps" / "aps.r0001.json").read_bytes()
    r0002 = (genuine / "aps" / "aps.r0002.json").read_bytes()
    assert hashlib.sha256(r0001).hexdigest() == _GENESIS_HEAD_SHA256
    head = hashlib.sha256(r0002).hexdigest()
    record = loader._parse_policy_bytes(r0002)
    assert record["revision"] == 2 and record["previous_revision_sha256"] == _GENESIS_HEAD_SHA256
    fresh = loader._load_policy_directory(loader._POLICY_DIR)
    for snapshot in (fresh.snapshot, loader.SEALED_POLICY_SNAPSHOT):
        assert snapshot.aps_revision == 2
        assert snapshot.aps_head_sha256 == head
        assert snapshot.eligible_profile_ids == frozenset({_PE5_PROFILE_ID})
        (view,) = snapshot.eligible_profiles
        assert view.profile_id == _PE5_PROFILE_ID
        assert view.payload_fingerprint == _PE5_PAYLOAD_FINGERPRINT
        assert snapshot.policy_directory == str(genuine)
        assert (snapshot.policy_revision, snapshot.payload_contract, snapshot.seam_contract, snapshot.consumer_contract) == (
            "HPP-1",
            "PI-PC1",
            "PI-SC1",
            "CFG1-CC1",
        )
    # r0001 stays historical revision 1 with an EMPTY eligible set; r0002 is revision 2.
    assert fresh.revisions == (
        (1, _GENESIS_HEAD_SHA256, frozenset()),
        (2, head, frozenset({_PE5_PROFILE_ID})),
    )
    assert loader._GENUINE_POLICY_LOAD.revisions == fresh.revisions


def test_b4_genesis_holds_exactly_one_historical_seam_evidence_and_nothing_else():
    data = (_PACKAGE_DIR / "pi_profile_policy" / "aps" / "aps.r0001.json").read_bytes()
    assert hashlib.sha256(data).hexdigest() == _GENESIS_HEAD_SHA256
    assert b"\r" not in data and data.endswith(b"\n")
    record = loader._parse_policy_bytes(data)
    assert record["revision"] == 1 and record["previous_revision_sha256"] is None
    assert record["profiles"] == [] and record["approvals"] == [] and record["retirements"] == []
    (evidence,) = record["seam_evidence"]
    assert evidence["seam_digests"] == PINNED_PI_SEAM_DIGESTS
    assert list(evidence["seam_digests"]) == sorted(PINNED_PI_SEAM_DIGESTS)
    assert evidence["seam_fingerprint"] == pi_payload.compute_seam_fingerprint(dict(PINNED_PI_SEAM_DIGESTS))
    assert evidence["evidence_id"] == loader._record_id(evidence, "evidence_id")
    assert [(ref["repo_path"], ref["sha256"]) for ref in evidence["evidence"]] == list(_GENESIS_EVIDENCE)


def test_b4_genesis_evidence_digests_name_the_committed_lf_bytes_of_the_cited_documents():
    """No Git: the committed blobs hold no CR, so stripping a checkout's CRs
    recovers them. (The OFFLINE verifier itself never normalizes -- B-10.)"""
    for repo_path, digest in _GENESIS_EVIDENCE:
        data = (_REPO_ROOT / repo_path).read_bytes().replace(b"\r\n", b"\n")
        assert hashlib.sha256(data).hexdigest() == digest, repo_path


def test_b4_the_exact_genesis_r0001_reference_view_admits_no_profile(tmp_path):
    view = loader._reference_view_from_material(_load_exact_genesis(tmp_path).head_reference)
    assert view.eligible == ()
    assert view.present_ineligible_profile_ids == frozenset()
    assert view.seam_fingerprints == frozenset(
        {pi_payload.compute_seam_fingerprint(dict(PINNED_PI_SEAM_DIGESTS))}
    )


def test_b4_the_current_genuine_head_reference_view_reflects_the_adopted_profile():
    """Derived by the real loader from the committed r0002 chain; never hand-built."""
    view = loader.head_reference_view()
    (facts,) = view.eligible
    assert facts.profile_id == _PE5_PROFILE_ID
    assert facts.payload_fingerprint == _PE5_PAYLOAD_FINGERPRINT
    assert facts.c5_reason is None
    (profile,) = loader._parse_policy_bytes(
        (_PACKAGE_DIR / "pi_profile_policy" / "aps" / "aps.r0002.json").read_bytes()
    )["profiles"]
    assert facts.seam_fingerprint == profile["seam_fingerprint"]
    assert facts.seam_digests_dict() == profile["seam_digests"]
    assert view.present_ineligible_profile_ids == frozenset()
    # r0002 added no seam evidence: S is still exactly the genesis seam fingerprint.
    assert view.seam_fingerprints == frozenset(
        {pi_payload.compute_seam_fingerprint(dict(PINNED_PI_SEAM_DIGESTS))}
    )


# ---------------------------------------------------------------------------
# B-12 -- every policy bound: at-bound accepted, over refused
# ---------------------------------------------------------------------------


def test_b12_the_frozen_bound_values():
    assert loader.MAX_APS_REVISION_FILE_BYTES == 16777216
    assert loader.MAX_INVENTORY_FILE_BYTES == 100663296
    assert loader.MAX_MANIFEST_BUNDLE_FILE_BYTES == 100663296
    assert loader.MAX_INVENTORY_FILE_BYTES is pi_profile_floor.MAX_INVENTORY_FILE_BYTES
    assert loader.MAX_APS_REVISIONS == 9999
    assert loader.MAX_PROFILES == 256
    assert loader.MAX_POLICY_TOTAL_BYTES == 1073741824
    assert loader.MAX_POLICY_JSON_DEPTH == 24
    assert loader.MAX_POLICY_INT == 9007199254740991
    assert loader.MAX_EVIDENCE_REFS == 256
    assert loader.MAX_FINDING_REFS == 64
    assert loader.MAX_REPO_PATH_CHARS == 512
    assert loader.MAX_ACCEPTANCE_REFERENCE_CHARS == 1024


def test_b12_aps_revision_file_bound(tmp_path, monkeypatch):
    world = _world_with(tmp_path, genesis_like_chain())
    size = len((world.aps / "aps.r0001.json").read_bytes())
    monkeypatch.setattr(loader, "MAX_APS_REVISION_FILE_BYTES", size)
    world.load()
    monkeypatch.setattr(loader, "MAX_APS_REVISION_FILE_BYTES", size - 1)
    _refuses(world, "POLICY_FILE_BOUND_EXCEEDED")


@pytest.mark.parametrize("name, which", [("MAX_INVENTORY_FILE_BYTES", "inventory"), ("MAX_MANIFEST_BUNDLE_FILE_BYTES", "bundle")])
def test_b12_inventory_and_bundle_file_bounds(tmp_path, monkeypatch, name, which):
    a = base_payload()
    world = _world_with(tmp_path, _single_profile_chain(payload=a))
    size = len(a.inventory_bytes if which == "inventory" else a.bundle_bytes)
    monkeypatch.setattr(loader, name, size)
    world.load()
    monkeypatch.setattr(loader, name, size - 1)
    _refuses(world, "POLICY_FILE_BOUND_EXCEEDED")


def test_b12_total_policy_bytes_bound(tmp_path, monkeypatch):
    chain, _a, _b = two_profile_chain()
    world = _world_with(tmp_path, chain)
    total = sum(path.stat().st_size for path in world.dir.rglob("*") if path.is_file())
    monkeypatch.setattr(loader, "MAX_POLICY_TOTAL_BYTES", total)
    world.load()
    monkeypatch.setattr(loader, "MAX_POLICY_TOTAL_BYTES", total - 1)
    _refuses(world, "POLICY_TOTAL_BYTES_EXCEEDED")


def test_b12_aps_revision_count_bound(tmp_path, monkeypatch):
    chain = _three_revision_chain()
    world = _world_with(tmp_path, chain)
    monkeypatch.setattr(loader, "MAX_APS_REVISIONS", 3)
    world.load()
    monkeypatch.setattr(loader, "MAX_APS_REVISIONS", 2)
    _refuses(world, "POLICY_APS_REVISION_BOUND_EXCEEDED")


def test_b12_profile_count_bound(tmp_path, monkeypatch):
    chain, a, b = two_profile_chain()
    world = _world_with(tmp_path, chain)
    monkeypatch.setattr(loader, "MAX_PROFILES", 2)
    world.load()
    monkeypatch.setattr(loader, "MAX_PROFILES", 1)
    _refuses(world, "POLICY_PROFILE_BOUND_EXCEEDED")


def _nested(depth: int) -> dict:
    value: dict = {}
    for _ in range(depth - 1):
        value = {"a": value}
    return value


def test_b12_policy_json_depth_bound():
    assert loader._policy_depth(_nested(24)) == 24
    loader._parse_policy_bytes(policy_file_bytes(_nested(24)))
    with pytest.raises(Cfg1PolicyError) as caught:
        loader._parse_policy_bytes(policy_file_bytes(_nested(25)))
    assert caught.value.reason_code == "POLICY_DEPTH_EXCEEDED"
    deep = b'{"a":' * 200000 + b"1" + b"}" * 200000 + b"\n"
    with pytest.raises(Cfg1PolicyError) as caught:
        loader._parse_policy_bytes(deep)
    assert caught.value.reason_code == "POLICY_DEPTH_EXCEEDED"


def test_b12_policy_integer_bound():
    loader._parse_policy_bytes(b'{"n":9007199254740991}\n')
    for token in (b"9007199254740992", b"99999999999999999999", b"-1"):
        with pytest.raises(Cfg1PolicyError) as caught:
            loader._parse_policy_bytes(b'{"n":' + token + b"}\n")
        assert caught.value.reason_code == "POLICY_INT_OUT_OF_RANGE"


def _genesis_with_refs(ref_list) -> Chain:
    chain = Chain()
    chain.revision(seam_evidence=[seam_evidence(base_payload().facts.seam_digests_dict(), ref_list)])
    return chain


def test_b12_evidence_ref_count_bound(tmp_path):
    many = [dict(SYNTHETIC_REF, repo_path=f"docs/r{index}.md") for index in range(256)]
    _world_with(tmp_path / "ok", _genesis_with_refs(many)).load()
    _refuses(_world_with(tmp_path / "over", _genesis_with_refs(many + [dict(SYNTHETIC_REF)])), "POLICY_REFS_MALFORMED")
    _refuses(_world_with(tmp_path / "empty", _genesis_with_refs([])), "POLICY_REFS_EMPTY")


def test_b12_repo_path_length_and_grammar(tmp_path):
    at_bound = "d/" + "a" * 510
    assert len(at_bound) == 512 and loader.repo_path_is_valid(at_bound)
    _world_with(tmp_path / "ok", _genesis_with_refs([dict(SYNTHETIC_REF, repo_path=at_bound)])).load()
    over = "d/" + "a" * 511
    assert not loader.repo_path_is_valid(over)
    _refuses(
        _world_with(tmp_path / "over", _genesis_with_refs([dict(SYNTHETIC_REF, repo_path=over)])),
        "POLICY_REF_REPO_PATH_GRAMMAR",
    )
    for bad in ("", "/docs/x.md", "docs/x.md/", "docs//x.md", "docs/../x.md", "./x", "C:/x", "docs\\x.md", "a b", "docs/\u00e9.md", "\\\\server\\x", "docs/x:y"):
        assert not loader.repo_path_is_valid(bad), bad
    for good in ("docs/x.md", "a", "a.b-c_d/E9", "x."):
        assert loader.repo_path_is_valid(good), good


def test_b12_ref_digest_and_key_shape(tmp_path):
    for index, bad in enumerate(
        [
            dict(SYNTHETIC_REF, sha256="AB" * 32),
            dict(SYNTHETIC_REF, extra=1),
            {"repo_path": "docs/x.md"},
            "docs/x.md",
        ]
    ):
        _refuses(_world_with(tmp_path / str(index), _genesis_with_refs([bad])))


def test_b12_finding_ref_count_bound(tmp_path):
    a = base_payload()
    b = version_bump_payload()

    def _chain(count):
        pmd = pmd_for(b, a)
        pmd["deltas"][0]["read_as_raw_manifest"]["refs"] = [
            dict(SYNTHETIC_REF, repo_path=f"docs/f{index}.md") for index in range(count)
        ]
        for delta in pmd["deltas"]:
            delta["read_as_raw_manifest"] = dict(pmd["deltas"][0]["read_as_raw_manifest"])
        chain = Chain()
        chain.revision(profiles=[a.profile()], approvals=[approval(a.profile_id, "C3_SEAM_CHANGED")], payloads=[a])
        chain.revision(profiles=[b.profile()], approvals=[approval(b.profile_id, "C2_MANIFEST_ONLY", pmd=pmd)], payloads=[b])
        return chain

    _world_with(tmp_path / "ok", _chain(64)).load()
    _refuses(_world_with(tmp_path / "over", _chain(65)), "POLICY_REFS_MALFORMED")


def test_b12_acceptance_reference_bound_and_characters(tmp_path):
    a = base_payload()

    def _chain(text):
        chain = Chain()
        chain.revision(
            profiles=[a.profile()], approvals=[approval(a.profile_id, "C3_SEAM_CHANGED", acceptance=text)], payloads=[a]
        )
        return chain

    _world_with(tmp_path / "ok", _chain("A" * 1024)).load()
    _world_with(tmp_path / "printable", _chain(" !~ ")).load()
    for index, bad in enumerate(["A" * 1025, "", "tab\there", "del\x7f", "nl\n", "\u00e9"]):
        _refuses(_world_with(tmp_path / f"bad{index}", _chain(bad)), "POLICY_ACCEPTANCE_REFERENCE_MALFORMED")


# ---------------------------------------------------------------------------
# B-13 -- the -text attribute rule, scoped to the policy directory only
# ---------------------------------------------------------------------------

_ATTRIBUTE_RULE = "experiments/pi_harness_cfg1/pi_profile_policy/** -text"


def test_b13_the_attribute_file_holds_exactly_the_one_scoped_rule():
    data = (_REPO_ROOT / ".gitattributes").read_bytes()
    assert data == (_ATTRIBUTE_RULE + "\n").encode("ascii")


def test_b13_the_rule_unsets_text_only_inside_the_policy_directory(tmp_path):
    """A SYNTHETIC repository under tmp_path; the real checkout's Git is not used."""
    git = shutil.which("git")
    if git is None:
        pytest.skip("git is not available")
    repo = tmp_path / "synthetic_repo"
    repo.mkdir()
    subprocess.run([git, "init", "-q", str(repo)], check=True, capture_output=True)  # noqa: S603
    shutil.copyfile(_REPO_ROOT / ".gitattributes", repo / ".gitattributes")
    probes = {
        "experiments/pi_harness_cfg1/pi_profile_policy/aps/aps.r0001.json": "unset",
        "experiments/pi_harness_cfg1/pi_profile_policy/inventories/" + "a" * 64 + ".json": "unset",
        "experiments/pi_harness_cfg1/pi_profile_policy/manifest_bundles/" + "a" * 64 + ".json": "unset",
        "experiments/pi_harness_cfg1/pi_profile_candidates/x.candidate.json": "unspecified",
        "experiments/pi_harness_cfg1/pi_profile_policy_loader.py": "unspecified",
        "experiments/pi_harness_cfg1/pi_profile_policy.json": "unspecified",
        "experiments/pi_harness_cfg1/results/x.json": "unspecified",
        "docs/PHASE_5F3B_PI_HARNESS_PROFILE_EVOLUTION_PE1_AMENDMENT.md": "unspecified",
        "x/experiments/pi_harness_cfg1/pi_profile_policy/aps/a.json": "unspecified",
    }
    completed = subprocess.run(  # noqa: S603 - fixed argv, synthetic repository
        [git, "-C", str(repo), "check-attr", "text", "--", *probes],
        check=True,
        capture_output=True,
        text=True,
    )
    observed = dict(line.rsplit(": text: ", 1) for line in completed.stdout.splitlines())
    assert observed == probes


# ---------------------------------------------------------------------------
# B-14 -- the loader calls the ACCEPTED PE-2a parsers by identity; the B5
# malicious corpus in committed synthetic bundle data refuses before any path
# ---------------------------------------------------------------------------


def test_b14_the_loader_binds_the_accepted_pe2a_primitives_by_identity():
    assert loader.compute_profile_facts is pi_profile_floor.compute_profile_facts
    assert loader.inventory_from_record is pi_payload.inventory_from_record
    assert loader.bundle_from_record is pi_manifest.bundle_from_record
    assert loader.parse_package_name is pi_manifest.parse_package_name
    assert loader.validate_resolution_exposures is pi_manifest.validate_resolution_exposures
    assert loader.compute_seam_fingerprint is pi_payload.compute_seam_fingerprint
    assert loader.classify_floor is pi_profile_floor.classify_floor
    assert loader.c2_relation is pi_profile_floor.c2_relation
    assert loader.compute_pmd_deltas is pi_profile_floor.compute_pmd_deltas
    assert loader.ReferenceView is pi_profile_floor.ReferenceView
    assert loader.policy_file_bytes is pi_profile_floor.policy_file_bytes
    assert pi_profile_floor.parse_manifest_strict is pi_manifest.parse_manifest_strict
    assert pi_profile_floor.validate_dependency_maps is pi_manifest.validate_dependency_maps
    assert pi_profile_floor.package_roots is pi_manifest.package_roots


def test_b14_ast_audit_no_second_manifest_parser_on_the_loader_path():
    source = (_PACKAGE_DIR / "pi_profile_policy_loader.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for needle in ('"dependencies"', '"optionalDependencies"', '"peerDependencies"', "b64decode", "import base64"):
        assert needle not in source, needle
    defined = {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
    for forbidden in (
        "parse_manifest_strict",
        "validate_dependency_maps",
        "parse_package_name",
        "package_roots",
        "compute_resolution_exposures",
        "compute_profile_id",
        "classify_floor",
        "c2_relation",
        "compute_pmd_deltas",
        "inventory_from_record",
        "bundle_from_record",
    ):
        assert forbidden not in defined, forbidden
    loads_sites = {
        function.name
        for function in ast.walk(tree)
        if isinstance(function, ast.FunctionDef)
        for node in ast.walk(function)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "loads"
    }
    assert loads_sites == {"_parse_policy_bytes"}


def test_b14_loading_runs_the_accepted_parsers(tmp_path, monkeypatch):
    calls = {"parse_manifest_strict": 0, "validate_dependency_maps": 0, "parse_package_name": 0}

    def _spy(module, name):
        real = getattr(module, name)

        def _wrapped(*args, **kwargs):
            calls[name] += 1
            return real(*args, **kwargs)

        monkeypatch.setattr(module, name, _wrapped)

    chain, a, _b = two_profile_chain()
    world = _world_with(tmp_path, chain)
    _spy(pi_profile_floor, "parse_manifest_strict")
    _spy(pi_profile_floor, "validate_dependency_maps")
    _spy(pi_manifest, "parse_package_name")
    world.load()
    roots = len(pi_manifest.package_roots(a.facts.inventory))
    assert calls["parse_manifest_strict"] == 2 * roots
    assert calls["validate_dependency_maps"] == 2 * roots
    assert calls["parse_package_name"] > 0


def _malicious_payload_world(tmp_path, manifest_path: str, manifest: bytes) -> PolicyWorld:
    """A committed profile whose bundle carries ``manifest`` at ``manifest_path``."""
    files, empty_dirs = synthetic_payload_files()
    files[manifest_path] = manifest
    inventory = inventory_from_entries(expected_entries(files, empty_dirs))
    bundle = build_manifest_bundle(inventory, {path: files[path] for path in bundle_manifest_paths(inventory)})
    good = base_payload()
    record = profile_record(good.facts)
    record["payload_fingerprint"] = inventory.payload_fingerprint
    chain = Chain()
    chain.revision(profiles=[record], approvals=[approval(record["profile_id"], "C3_SEAM_CHANGED")])
    world = PolicyWorld(tmp_path)
    world.write_revisions(chain.file_bytes())
    world.inventories.mkdir()
    world.bundles.mkdir()
    name = inventory.payload_fingerprint + ".json"
    (world.inventories / name).write_bytes(policy_file_bytes(inventory.to_record()))
    (world.bundles / name).write_bytes(policy_file_bytes(bundle.to_record()))
    return world


class _PathFormationTripwire:
    def __init__(self, monkeypatch) -> None:
        self.calls: list = []
        real = pi_manifest._join_relative

        def _join_relative(prefix, components):
            self.calls.append(components)
            return real(prefix, components)

        monkeypatch.setattr(pi_manifest, "_join_relative", _join_relative)


@pytest.mark.parametrize("field", ["dependencies", "optionalDependencies", "peerDependencies"])
@pytest.mark.parametrize("key", _B5_KEYS)
@pytest.mark.parametrize("manifest_path", ["package.json", "node_modules/left-pad/package.json"])
def test_b14_the_b5_corpus_in_committed_bundle_data_refuses_before_any_path(
    tmp_path, monkeypatch, field, key, manifest_path
):
    if manifest_path == "package.json":
        document = root_manifest(**{field: {key: "1.0.0"}})
    else:
        document = {"name": "left-pad", "version": "1.3.0", field: {key: "1.0.0"}}
    world = _malicious_payload_world(tmp_path, manifest_path, json.dumps(document).encode("ascii"))
    tripwire = _PathFormationTripwire(monkeypatch)
    double = LeafDouble()
    code = _refuses(world, "POLICY_PROFILE_NOT_APPROVABLE", **double.leaves())
    assert tripwire.calls == [], "a key-derived in-memory path was formed"
    allowed = {str(world.aps / "aps.r0001.json")} | {
        str(path) for path in world.inventories.iterdir()
    } | {str(path) for path in world.bundles.iterdir()}
    assert set(double.read) <= allowed
    if len(key) >= 3:
        assert key not in code


@pytest.mark.parametrize(
    "manifest",
    [
        b"\xef\xbb\xbf" + manifest_bytes(root_manifest()),
        b'{"name":"x","name":"y"}',
        b'{"name":"@earendil-works/pi-coding-agent","version":"1.0.0","dependencies":{"a":"1","a":"2"}}',
        b"\xff\xfe not utf-8",
        b'{"name":"@earendil-works/pi-coding-agent","version":NaN}',
        b'{"name":"@earendil-works/pi-coding-agent","version":"1.0.0","n":1e400}',
        b"[1,2,3]",
        manifest_bytes(root_manifest(dependencies=["left-pad"])),
        manifest_bytes(root_manifest(dependencies=None)),
        manifest_bytes(root_manifest(dependencies={"left-pad": 1})),
    ],
)
def test_b14_malformed_committed_manifest_data_refuses_before_any_path(tmp_path, monkeypatch, manifest):
    world = _malicious_payload_world(tmp_path, "package.json", manifest)
    tripwire = _PathFormationTripwire(monkeypatch)
    _refuses(world, "POLICY_PROFILE_NOT_APPROVABLE")
    assert tripwire.calls == []


@pytest.mark.parametrize(
    "manifest",
    [
        manifest_bytes(root_manifest(version=1)),
        manifest_bytes(root_manifest(version="")),
        manifest_bytes(root_manifest(version="1.0.0 beta")),
        manifest_bytes(root_manifest(name="@earendil-works/pi-coding-agent-fork")),
    ],
)
def test_b14_a_false_declared_identity_in_committed_bytes_refuses(tmp_path, manifest):
    """Counterexample 12 at the bundle level: the declared projection is
    recomputed from the committed bytes, so a wrong name or a bad version is
    C5 under HPP-1 and refuses the chain."""
    world = _malicious_payload_world(tmp_path, "package.json", manifest)
    _refuses(world, "POLICY_PROFILE_NOT_APPROVABLE")


@pytest.mark.parametrize("key", [key for key in _B5_KEYS if key])
def test_b14_a_malicious_stored_exposure_refuses_before_any_path(tmp_path, monkeypatch, key):
    a = base_payload()
    record = a.profile(resolution_exposures=[key])
    world = _world_with(tmp_path, _single_profile_chain(record, a))
    tripwire = _PathFormationTripwire(monkeypatch)
    _refuses(world, "POLICY_EXPOSURES_MALFORMED")
    assert all(components != (key,) for components in tripwire.calls)


def test_b14_a_canonical_inventory_must_still_satisfy_the_pe2a_inventory_rules(tmp_path):
    """Strict canonical bytes are necessary, not sufficient: PE-2a's inventory
    validator (order, tree closure, case-fold uniqueness, grammar) still runs."""
    a = base_payload()
    world = _world_with(tmp_path, _single_profile_chain(payload=a))
    record = json.loads(a.inventory_bytes)
    record["entries"].append({"kind": "file", "path": "zzz/orphan.js", "sha256": "0" * 64, "size": 1})
    (world.inventories / (a.fingerprint + ".json")).write_bytes(policy_file_bytes(record))
    _refuses(world, "POLICY_INVENTORY_INVALID")
    record = json.loads(a.inventory_bytes)
    record["entries"].append({"kind": "file", "path": "ZZZ_README.md", "sha256": "0" * 64, "size": 1})
    record["entries"].append({"kind": "file", "path": "zzz_readme.md", "sha256": "0" * 64, "size": 1})
    (world.inventories / (a.fingerprint + ".json")).write_bytes(policy_file_bytes(record))
    _refuses(world, "POLICY_INVENTORY_INVALID")


def test_b14_canonical_json_bytes_is_the_shared_primitive():
    assert policy_file_bytes({"b": 1, "a": [None, True]}) == canonical_json_bytes({"b": 1, "a": [None, True]}) + b"\n"
