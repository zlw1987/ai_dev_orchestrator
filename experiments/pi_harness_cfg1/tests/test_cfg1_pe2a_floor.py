"""PE-2a: the mechanical floor classifier, the C2 projection and PMD deltas.

Acceptance rows A-11, A-12 and A-13 of
``docs/PHASE_5F3B_PI_HARNESS_PROFILE_EVOLUTION_PE1_AMENDMENT.md`` Sec. 26.1
(with PE-0 Sec. 14.3 counterexamples 5, 6, 13, 14 and the Sec. 14.5 B9
table). Pure functions over SUPPLIED synthetic reference sets: no APS, no
policy, no approval, no filesystem.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from pe2a_support import (
    PI_AGENT_CORE,
    PI_AI,
    facts_for,
    manifest_bytes,
    pi_agent_core_manifest,
    pi_ai_manifest,
    root_manifest,
    synthetic_payload_files,
)

from pi_harness_cfg1 import pi_profile_floor
from pi_harness_cfg1.pi_profile_floor import (
    FLOOR_C1,
    FLOOR_C1R,
    FLOOR_C2,
    FLOOR_C3_SEAM_CHANGED,
    FLOOR_C3_SEAM_EQUAL,
    FLOOR_C5,
    Cfg1FloorError,
    ReferenceView,
    c2_relation,
    classify_floor,
    compute_pmd_deltas,
    project_permitted_value_slots,
)

_PACKAGE_DIR = Path(__file__).resolve().parents[1]
_ROOT_M = "package.json"
_AI_M = "node_modules/@earendil-works/pi-ai/package.json"
_CORE_M = "node_modules/@earendil-works/pi-agent-core/package.json"


def _base():
    files, empty_dirs = synthetic_payload_files()
    return dict(files), empty_dirs


def _variant(**changes):
    files, empty_dirs = _base()
    files.update(changes)
    return facts_for(files, empty_dirs)


def _reference():
    files, empty_dirs = _base()
    return facts_for(files, empty_dirs)


def _view(*eligible, ineligible=(), seams=()):
    return ReferenceView(
        eligible=eligible, present_ineligible_profile_ids=ineligible, seam_fingerprints=seams
    )


# ---------------------------------------------------------------------------
# A-11 -- the classifier
# ---------------------------------------------------------------------------


def test_a11_counterexample_5_version_only_change_is_c2():
    reference = _reference()
    candidate = _variant(**{_ROOT_M: manifest_bytes(root_manifest(version="1.0.1"))})
    assert candidate.profile_id != reference.profile_id
    assert c2_relation(candidate, reference) is True
    assert classify_floor(candidate, _view(reference)) == FLOOR_C2


@pytest.mark.parametrize(
    "change",
    [
        {"dependencies": {PI_AI: "^1.0.0", PI_AGENT_CORE: "^1.0.0", "left-pad": "1.3.1", "@scope/util": "2.0.0"}},
        {"exports": {".": "./dist/main.js"}},
        {"type": "commonjs"},
        {"bin": {"pi": "dist/main.js"}},
    ],
)
def test_a11_counterexample_6_non_permitted_manifest_field_change_is_not_c2(change):
    reference = _reference()
    candidate = _variant(**{_ROOT_M: manifest_bytes(root_manifest(**change))})
    assert c2_relation(candidate, reference) is False
    assert classify_floor(candidate, _view(reference)) in (FLOOR_C3_SEAM_EQUAL, FLOOR_C3_SEAM_CHANGED)


def test_a11_counterexample_13_same_seams_different_payload():
    reference = _reference()
    candidate = _variant(**{"dist/cli/setup.js": b"export const setup = 'changed';\n"})
    assert candidate.seam_fingerprint == reference.seam_fingerprint
    assert candidate.payload_fingerprint != reference.payload_fingerprint
    assert candidate.profile_id != reference.profile_id
    assert c2_relation(candidate, reference) is False
    assert classify_floor(candidate, _view(reference)) == FLOOR_C3_SEAM_EQUAL
    # Never C1: the seam match grants nothing.
    assert classify_floor(candidate, _view(reference)) != FLOOR_C1


def test_a11_counterexample_14_different_versions_identical_runtime_bytes_are_distinct_c2_profiles():
    reference = _reference()
    candidate = _variant(
        **{
            _ROOT_M: manifest_bytes(root_manifest(version="2.0.0")),
            _AI_M: manifest_bytes(pi_ai_manifest(version="2.0.0")),
            _CORE_M: manifest_bytes(pi_agent_core_manifest(version="2.0.0")),
        }
    )
    assert candidate.profile_id != reference.profile_id
    assert c2_relation(candidate, reference) is True
    assert c2_relation(reference, candidate) is True


def test_a11_b9_same_internal_key_different_value_may_be_c2():
    reference = _reference()
    deps = {PI_AI: "^1.1.0", PI_AGENT_CORE: "^1.0.0", "left-pad": "1.3.0", "@scope/util": "2.0.0"}
    candidate = _variant(**{_ROOT_M: manifest_bytes(root_manifest(dependencies=deps))})
    assert classify_floor(candidate, _view(reference)) == FLOOR_C2
    assert [d["delta"] for d in compute_pmd_deltas(candidate, reference)] == [
        "RAW_BYTES",
        "INTERNAL_DEPENDENCY:@earendil-works/pi-ai",
    ]


def test_a11_b9_formatting_only_change_is_c2_with_exactly_one_raw_bytes_delta():
    reference = _reference()
    candidate = _variant(**{_ROOT_M: manifest_bytes(root_manifest(), indent=None)})
    assert classify_floor(candidate, _view(reference)) == FLOOR_C2
    deltas = compute_pmd_deltas(candidate, reference)
    assert [d["delta"] for d in deltas] == ["RAW_BYTES"]


def test_a11_b9_reference_has_key_candidate_omits_it_is_not_c2():
    reference = _reference()
    deps = {PI_AGENT_CORE: "^1.0.0", "left-pad": "1.3.0", "@scope/util": "2.0.0"}
    candidate = _variant(
        **{_ROOT_M: manifest_bytes(root_manifest(dependencies=deps, peerDependencies={PI_AI: "^1.0.0"}))}
    )
    assert c2_relation(candidate, reference) is False


def test_a11_b9_reference_omits_key_candidate_adds_it_is_not_c2():
    files, empty_dirs = _base()
    deps = {PI_AGENT_CORE: "^1.0.0", "left-pad": "1.3.0", "@scope/util": "2.0.0"}
    files[_ROOT_M] = manifest_bytes(root_manifest(dependencies=deps))
    reference = facts_for(files, empty_dirs)
    assert reference.c5_reason is None
    candidate = _reference()
    assert c2_relation(candidate, reference) is False


def test_a11_b9_internal_key_reordered_is_not_c2():
    reference = _reference()
    deps = {PI_AGENT_CORE: "^1.0.0", PI_AI: "^1.0.0", "left-pad": "1.3.0", "@scope/util": "2.0.0"}
    candidate = _variant(**{_ROOT_M: manifest_bytes(root_manifest(dependencies=deps))})
    assert c2_relation(candidate, reference) is False


def test_a11_top_level_key_reorder_is_not_c2():
    reference = _reference()
    document = root_manifest()
    reordered = {"version": document["version"], **{k: v for k, v in document.items() if k != "version"}}
    candidate = _variant(**{_ROOT_M: manifest_bytes(reordered)})
    assert c2_relation(candidate, reference) is False


def test_a11_b9_a_non_str_internal_value_is_refused_by_the_schema_first():
    deps = {PI_AI: None, PI_AGENT_CORE: "^1.0.0", "left-pad": "1.3.0", "@scope/util": "2.0.0"}
    candidate = _variant(**{_ROOT_M: manifest_bytes(root_manifest(dependencies=deps))})
    assert candidate.c5_reason == "DEPENDENCY_VALUE_NOT_STR"
    assert classify_floor(candidate, _view(_reference())) == FLOOR_C5
    with pytest.raises(Cfg1FloorError):
        c2_relation(candidate, _reference())


def test_a11_a_peer_dependency_internal_value_change_is_not_a_permitted_slot():
    reference = _reference()
    candidate = _variant(
        **{_CORE_M: manifest_bytes(pi_agent_core_manifest(peerDependencies={PI_AI: "^2.0.0"}))}
    )
    assert c2_relation(candidate, reference) is False


def test_a11_a_non_permitted_manifest_only_change_is_not_c2():
    reference = _reference()
    candidate = _variant(**{"node_modules/zod/package.json": manifest_bytes({"name": "zod", "version": "3.0.1"})})
    assert c2_relation(candidate, reference) is False
    assert classify_floor(candidate, _view(reference)) == FLOOR_C3_SEAM_EQUAL


def test_a11_a_permitted_manifest_plus_any_other_byte_is_not_c2():
    reference = _reference()
    candidate = _variant(
        **{_ROOT_M: manifest_bytes(root_manifest(version="1.0.1")), "README.md": b"# changed\n"}
    )
    assert c2_relation(candidate, reference) is False


def test_a11_a_tree_difference_is_not_c2_even_with_a_permitted_value_change():
    files, empty_dirs = _base()
    files[_ROOT_M] = manifest_bytes(root_manifest(version="1.0.1"))
    candidate = facts_for(files, empty_dirs + ("another_empty",))
    assert c2_relation(candidate, _reference()) is False


@pytest.mark.parametrize(
    "left, right, expected",
    [
        ({"x": 1}, {"x": 1.0}, False),
        ({"x": 1}, {"x": True}, False),
        ({"x": 0.0}, {"x": -0.0}, True),
        ({"x": "a"}, {"x": "a"}, True),
        ({"x": [1, 2]}, {"x": [2, 1]}, False),
        ({"x": {"a": 1, "b": 2}}, {"x": {"b": 2, "a": 1}}, False),
        ({"x": None}, {"x": False}, False),
    ],
)
def test_a11_exact_type_ordered_equality_outside_the_permitted_slots(left, right, expected):
    reference_files, empty_dirs = _base()
    reference_files[_ROOT_M] = manifest_bytes(root_manifest(**left))
    reference = facts_for(reference_files, empty_dirs)
    candidate_files = dict(reference_files)
    candidate_files[_ROOT_M] = manifest_bytes(root_manifest(**right))
    if right == {"x": "a"}:
        # Same parsed value, different escape spelling in the raw bytes.
        candidate_files[_ROOT_M] = candidate_files[_ROOT_M].replace(b'"x": "a"', b'"x": "\\u0061"')
    candidate = facts_for(candidate_files, empty_dirs)
    assert candidate.payload_fingerprint != reference.payload_fingerprint
    assert c2_relation(candidate, reference) is expected


def test_a11_floor_order_c5_c1_c1r_c2_c3():
    reference = _reference()
    assert classify_floor(reference, _view(reference)) == FLOOR_C1
    assert classify_floor(reference, _view(ineligible=(reference.profile_id,))) == FLOOR_C1R
    c5 = _variant(**{_ROOT_M: b"[]"})
    assert classify_floor(c5, _view(reference)) == FLOOR_C5
    seam_changed = _variant(**{"dist/core/sdk.js": b"changed seam\n"})
    assert classify_floor(seam_changed, _view(reference)) == FLOOR_C3_SEAM_CHANGED
    assert (
        classify_floor(seam_changed, _view(reference, seams=(seam_changed.seam_fingerprint,)))
        == FLOOR_C3_SEAM_EQUAL
    )
    assert classify_floor(seam_changed, _view()) == FLOOR_C3_SEAM_CHANGED
    assert classify_floor(reference, _view()) == FLOOR_C3_SEAM_CHANGED


def test_a11_a_retired_reference_never_supports_c2():
    reference = _reference()
    candidate = _variant(**{_ROOT_M: manifest_bytes(root_manifest(version="1.0.1"))})
    assert classify_floor(candidate, _view(ineligible=(reference.profile_id,))) == FLOOR_C3_SEAM_CHANGED


def test_a11_reference_view_refuses_malformed_inputs():
    reference = _reference()
    with pytest.raises(Cfg1FloorError):
        _view(_variant(**{_ROOT_M: b"[]"}))
    with pytest.raises(Cfg1FloorError):
        _view(ineligible=("NOT-HEX",))
    with pytest.raises(Cfg1FloorError):
        _view(reference, ineligible=(reference.profile_id,))


def test_a11_the_classifier_decides_nothing_from_version_text():
    """A version change alone yields C2 -- never C1 -- whatever the values."""
    reference = _reference()
    for version in ("0.0.1", "1.0.0-rc", "999.999.999", "1.0.0+build"):
        candidate = _variant(**{_ROOT_M: manifest_bytes(root_manifest(version=version))})
        assert classify_floor(candidate, _view(reference)) == FLOOR_C2


# ---------------------------------------------------------------------------
# A-12 -- the structure-preserving projection
# ---------------------------------------------------------------------------


def test_a12_the_projection_is_never_invoked_on_presence_differing_input(monkeypatch):
    calls = []
    real = pi_profile_floor.project_permitted_value_slots

    def _spy(document, on_both):
        calls.append(on_both)
        return real(document, on_both)

    monkeypatch.setattr(pi_profile_floor, "project_permitted_value_slots", _spy)
    reference = _reference()
    deps = {PI_AGENT_CORE: "^1.0.0", "left-pad": "1.3.0", "@scope/util": "2.0.0"}
    candidate = _variant(**{_ROOT_M: manifest_bytes(root_manifest(dependencies=deps))})
    assert c2_relation(candidate, reference) is False
    assert calls == []
    # ...and IS invoked when presence agrees.
    same_presence = _variant(**{_ROOT_M: manifest_bytes(root_manifest(version="9"))})
    assert c2_relation(same_presence, reference) is True
    assert calls and all(on_both == (PI_AI, PI_AGENT_CORE) for on_both in calls)


def test_a12_the_projection_retains_every_key_and_position():
    document = {
        "a": 1,
        "version": "1.0.0",
        "dependencies": {"x": "1", PI_AI: "2", "y": "3", PI_AGENT_CORE: "4"},
        "z": {"version": "nested-not-replaced"},
    }
    projected = project_permitted_value_slots(document, (PI_AI, PI_AGENT_CORE))
    assert list(projected) == list(document)
    assert list(projected["dependencies"]) == list(document["dependencies"])
    assert projected["dependencies"]["x"] == "1" and projected["dependencies"]["y"] == "3"
    assert projected["z"] == {"version": "nested-not-replaced"}
    assert projected["version"] is pi_profile_floor._MARKER
    assert projected["dependencies"][PI_AI] is pi_profile_floor._MARKER
    # The input is untouched.
    assert document["version"] == "1.0.0" and document["dependencies"][PI_AI] == "2"
    # Only names present on BOTH sides are masked.
    only_ai = project_permitted_value_slots(document, (PI_AI,))
    assert only_ai["dependencies"][PI_AGENT_CORE] == "4"


def test_a12_ast_audit_the_projection_never_deletes_filters_or_builds_key_sets():
    tree = ast.parse((_PACKAGE_DIR / "pi_profile_floor.py").read_text(encoding="utf-8"))
    function = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "project_permitted_value_slots"
    )
    forbidden_attrs = {"pop", "popitem", "clear", "remove", "discard", "keys", "difference", "intersection"}
    for node in ast.walk(function):
        assert not isinstance(node, ast.Delete), node.lineno
        assert not isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)), node.lineno
        if isinstance(node, ast.Attribute):
            assert node.attr not in forbidden_attrs, node.attr
        if isinstance(node, ast.Name):
            assert node.id not in ("filter", "set", "frozenset", "sorted"), node.id
        if isinstance(node, ast.Set):
            pytest.fail("set literal in the projector")


def test_a12_no_parsed_json_value_aliases_the_marker():
    marker = pi_profile_floor._MARKER
    for value in (repr(marker), str(marker), "<permitted value slot>", "MARKER", None, 0, False, [], {}):
        assert (value == marker) is False
        assert pi_profile_floor._ordered_equal({"version": value}, {"version": marker}) is False
        assert pi_profile_floor._ordered_equal({"version": marker}, {"version": value}) is False
    assert pi_profile_floor._ordered_equal({"version": marker}, {"version": marker}) is True


def test_a12_a_manifest_spelling_the_marker_repr_cannot_fake_a_masked_slot():
    reference = _reference()
    candidate = _variant(
        **{_ROOT_M: manifest_bytes(root_manifest(description=repr(pi_profile_floor._MARKER)))}
    )
    assert c2_relation(candidate, reference) is False


# ---------------------------------------------------------------------------
# A-13 -- the mechanical PMD delta list
# ---------------------------------------------------------------------------


def test_a13_delta_order_completeness_and_orientation():
    reference = _reference()
    root_deps = {PI_AI: "^2.0.0", PI_AGENT_CORE: "^2.0.0", "left-pad": "1.3.0", "@scope/util": "2.0.0"}
    candidate = _variant(
        **{
            _ROOT_M: manifest_bytes(root_manifest(version="2.0.0", dependencies=root_deps)),
            _AI_M: manifest_bytes(pi_ai_manifest(version="2.0.0")),
            _CORE_M: manifest_bytes(pi_agent_core_manifest(), indent=None),
        }
    )
    deltas = compute_pmd_deltas(candidate, reference)
    projection = [(d["delta"], d["manifest_path"], d["old"], d["new"]) for d in deltas]
    root_old = reference.inventory.entry(_ROOT_M)[2]
    root_new = candidate.inventory.entry(_ROOT_M)[2]
    # Inventory (code-point) order: node_modules/.../pi-agent-core/... <
    # node_modules/.../pi-ai/... < package.json
    assert projection == [
        ("RAW_BYTES", _CORE_M, reference.inventory.entry(_CORE_M)[2], candidate.inventory.entry(_CORE_M)[2]),
        ("RAW_BYTES", _AI_M, reference.inventory.entry(_AI_M)[2], candidate.inventory.entry(_AI_M)[2]),
        ("VERSION", _AI_M, "1.0.0", "2.0.0"),
        ("RAW_BYTES", _ROOT_M, root_old, root_new),
        ("VERSION", _ROOT_M, "1.0.0", "2.0.0"),
        ("INTERNAL_DEPENDENCY:@earendil-works/pi-ai", _ROOT_M, "^1.0.0", "^2.0.0"),
        ("INTERNAL_DEPENDENCY:@earendil-works/pi-agent-core", _ROOT_M, "^1.0.0", "^2.0.0"),
    ]
    assert set(deltas[0]) == {"delta", "manifest_path", "old", "new"}


def test_a13_raw_bytes_is_always_present_for_every_differing_manifest():
    reference = _reference()
    candidate = _variant(**{_AI_M: manifest_bytes(pi_ai_manifest(), indent=4)})
    assert [d["delta"] for d in compute_pmd_deltas(candidate, reference)] == ["RAW_BYTES"]


def test_a13_no_delta_list_exists_for_a_presence_differing_pair():
    reference = _reference()
    deps = {PI_AGENT_CORE: "^1.0.0", "left-pad": "1.3.0", "@scope/util": "2.0.0"}
    candidate = _variant(**{_ROOT_M: manifest_bytes(root_manifest(dependencies=deps))})
    with pytest.raises(Cfg1FloorError) as caught:
        compute_pmd_deltas(candidate, reference)
    assert caught.value.reason_code == "PMD_REQUIRES_C2"


def test_a13_no_delta_list_exists_for_identical_or_non_c2_pairs():
    reference = _reference()
    with pytest.raises(Cfg1FloorError):
        compute_pmd_deltas(reference, reference)
    with pytest.raises(Cfg1FloorError):
        compute_pmd_deltas(_variant(**{"README.md": b"x"}), reference)


def test_a13_a_value_unchanged_internal_key_yields_no_internal_delta():
    reference = _reference()
    candidate = _variant(**{_ROOT_M: manifest_bytes(root_manifest(version="1.0.1"))})
    assert [d["delta"] for d in compute_pmd_deltas(candidate, reference)] == ["RAW_BYTES", "VERSION"]
