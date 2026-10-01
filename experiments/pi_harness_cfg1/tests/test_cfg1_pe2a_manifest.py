"""PE-2a: manifest bundle, strict parser, B5 names, containment and approvability.

Acceptance rows A-8, A-9, A-10 and A-14 of
``docs/PHASE_5F3B_PI_HARNESS_PROFILE_EVOLUTION_PE1_AMENDMENT.md`` Sec. 26.1,
plus bundle (Sec. 6.1) regressions. All inputs are synthetic bytes or
in-memory trees; the exposure observer runs against recording doubles. No
Node, no Pi, no npm, no installed Pi, no socket, no credential.
"""

from __future__ import annotations

import ast
import base64
import json
import ntpath
from pathlib import Path

import pytest
from pe2a_support import (
    PI_AGENT_CORE,
    PI_AI,
    FakeTree,
    RecordingInspect,
    expected_entries,
    facts_for,
    manifest_bytes,
    pi_agent_core_manifest,
    pi_ai_manifest,
    root_manifest,
    synthetic_payload_files,
)

from pi_harness_cfg1 import pi_manifest, pi_profile_floor
from pi_harness_cfg1.pi_manifest import (
    EXPOSURE_PRESENT_OR_UNOBSERVABLE,
    EXPOSURES_PROVEN_ABSENT,
    Cfg1ManifestError,
    DependencyMaps,
    build_manifest_bundle,
    bundle_from_record,
    bundle_manifest_paths,
    compute_profile_id,
    compute_resolution_exposures,
    observe_exposure_absence,
    package_roots,
    parse_manifest_strict,
    parse_package_name,
    validate_dependency_maps,
)
from pi_harness_cfg1.pi_payload import inventory_from_entries

_PACKAGE_DIR = Path(__file__).resolve().parents[1]


def _refuses(data: bytes, reason: str) -> None:
    with pytest.raises(Cfg1ManifestError) as caught:
        parse_manifest_strict(data)
    assert caught.value.reason_code == reason


# ---------------------------------------------------------------------------
# A-8 -- the strict manifest parser's negative corpus
# ---------------------------------------------------------------------------


def test_a8_the_manifest_bound_literals_are_pinned():
    assert pi_manifest.MAX_MANIFEST_BYTES == 1048576
    assert pi_manifest.MAX_MANIFEST_COUNT == 20000
    assert pi_manifest.MAX_MANIFEST_TOTAL_BYTES == 67108864
    assert pi_manifest.MAX_MANIFEST_JSON_DEPTH == 64
    assert pi_manifest.MAX_MANIFEST_NUMBER_TOKEN_CHARS == 256
    assert pi_manifest.MAX_DEPENDENCY_MAP_KEYS == 4096
    assert pi_manifest.MAX_DEPENDENCY_KEY_CHARS == 214
    assert pi_manifest.MAX_DEPENDENCY_VALUE_CHARS == 1024
    assert pi_manifest.MAX_DECLARED_VERSION_CHARS == 128
    assert pi_profile_floor.MAX_INVENTORY_FILE_BYTES == 100663296
    assert pi_profile_floor.MAX_MANIFEST_BUNDLE_FILE_BYTES == 100663296


def test_a8_a_bom_refuses():
    _refuses(b"\xef\xbb\xbf{}", "MANIFEST_BOM")


@pytest.mark.parametrize("data", [b'{"a":"\xff"}', b'{"a":"\xc0\xaf"}', b'{"a":"\xed\xa0\x80"}'])
def test_a8_invalid_utf8_refuses(data):
    _refuses(data, "MANIFEST_NOT_UTF8")


@pytest.mark.parametrize(
    "data",
    [
        b'{"a":1,"a":1}',
        b'{"a":{"b":1,"b":2}}',
        b'{"a":[{"x":1},{"y":1,"y":2}]}',
        b'{"a":"x","\\u0061":"y"}',
        b'{"dependencies":{"left-pad":"1","left-pad":"2"}}',
    ],
)
def test_a8_duplicate_keys_at_any_depth_refuse(data):
    _refuses(data, "MANIFEST_DUPLICATE_KEY")


@pytest.mark.parametrize("token", [b"NaN", b"Infinity", b"-Infinity"])
def test_a8_non_finite_constants_refuse(token):
    _refuses(b'{"a":' + token + b"}", "MANIFEST_NON_FINITE_NUMBER")


@pytest.mark.parametrize("token", [b"1e400", b"-1e400", b"1E999"])
def test_a8_non_finite_float_results_refuse(token):
    _refuses(b'{"a":' + token + b"}", "MANIFEST_NON_FINITE_NUMBER")


def test_a8_long_number_tokens_refuse_at_257_and_pass_at_256():
    assert parse_manifest_strict(b'{"a":' + b"1" * 256 + b"}")["a"] == int("1" * 256)
    _refuses(b'{"a":' + b"1" * 257 + b"}", "MANIFEST_NUMBER_TOKEN_TOO_LONG")
    assert type(parse_manifest_strict(b'{"a":0.' + b"1" * 254 + b"}")["a"]) is float
    _refuses(b'{"a":0.' + b"1" * 255 + b"}", "MANIFEST_NUMBER_TOKEN_TOO_LONG")
    _refuses(b'{"a":-' + b"1" * 256 + b"}", "MANIFEST_NUMBER_TOKEN_TOO_LONG")


def _nested(depth: int) -> bytes:
    # The top-level object is depth 1; each list adds one.
    inner = depth - 1
    return b'{"a":' + b"[" * inner + b"]" * inner + b"}"


def test_a8_depth_64_is_accepted_and_65_refuses():
    assert type(parse_manifest_strict(_nested(64))) is dict
    _refuses(_nested(65), "MANIFEST_DEPTH_EXCEEDED")


def test_a8_pathological_depth_refuses_without_crashing():
    _refuses(b'{"a":' + b"[" * 200000 + b"]" * 200000 + b"}", "MANIFEST_DEPTH_EXCEEDED")


def test_a8_more_than_one_mib_refuses():
    body = b'{"a":"' + b"x" * (pi_manifest.MAX_MANIFEST_BYTES - 8) + b'"}'
    assert len(body) == pi_manifest.MAX_MANIFEST_BYTES
    assert type(parse_manifest_strict(body)) is dict
    _refuses(body + b" ", "MANIFEST_TOO_LARGE")


@pytest.mark.parametrize("data", [b"[]", b'"s"', b"1", b"null", b"true"])
def test_a8_a_non_object_top_level_refuses(data):
    _refuses(data, "MANIFEST_TOP_LEVEL_NOT_OBJECT")


@pytest.mark.parametrize("data", [b'{"a":"x\x01y"}', b'{"a":"x\ty"}', b'{"a":"x\ny"}', b'{"a\x1f":1}'])
def test_a8_a_raw_control_character_refuses(data):
    _refuses(data, "MANIFEST_JSON_INVALID")


@pytest.mark.parametrize("data", [b"", b"{", b'{"a":1,}', b"{'a':1}", b'{"a":1} x', b"\x00"])
def test_a8_malformed_json_refuses(data):
    _refuses(data, "MANIFEST_JSON_INVALID")


def test_a8_non_bytes_input_refuses():
    for value in ("{}", bytearray(b"{}"), memoryview(b"{}"), None):
        with pytest.raises(Cfg1ManifestError):
            parse_manifest_strict(value)


def test_a8_results_are_exact_typed_and_order_preserving():
    value = parse_manifest_strict(b'{"z":1,"a":true,"m":1.5,"n":null,"l":[false],"s":"t"}')
    assert list(value) == ["z", "a", "m", "n", "l", "s"]
    assert type(value["z"]) is int and type(value["a"]) is bool
    assert type(value["m"]) is float and value["n"] is None


def test_a8_a_refusal_never_carries_manifest_text():
    needle = "needle-7f3a"
    try:
        parse_manifest_strict(b'{"' + needle.encode() + b'":1,"' + needle.encode() + b'":2}')
    except Cfg1ManifestError as refusal:
        assert needle not in str(refusal) and needle not in repr(refusal.args)
        assert refusal.__cause__ is None
    else:  # pragma: no cover
        pytest.fail("duplicate key accepted")


# ---------------------------------------------------------------------------
# A-9 -- the PE-0 Sec. 14.4 B5 malicious-name corpus
# ---------------------------------------------------------------------------


class _StrSubclass(str):
    pass


_B5_KEYS = [
    "..",
    "../x",
    "..\\x",
    "C:\\x",
    "/x",
    "\\\\server\\share",
    "@scope/../x",
    "@scope/x/y",
    "@/x",
    "@scope/",
    "a\x00b",
    "a\nb",
    "a\x1fb",
    "x.",
    "nul",
    "con.js",
    "node_modules",
    ".x",
    "_x",
    "-x",
    "X",
    "@Scope/x",
    "@scope/X",
    "@scope",
    "@@scope/x",
    "scope@x",
    "a b",
    "a%2e",
    "lpt1",
    "@scope/com3.x",
    "@node_modules/x",
    "x" * 215,
    "",
]


@pytest.mark.parametrize("key", _B5_KEYS)
def test_a9_the_package_name_parser_refuses_every_b5_key(key):
    with pytest.raises(Cfg1ManifestError) as caught:
        parse_package_name(key)
    assert caught.value.reason_code == "PACKAGE_NAME_OUTSIDE_HPP1_GRAMMAR"
    if len(key) >= 3:
        assert key not in str(caught.value)


def test_a9_a_str_subclass_key_refuses():
    with pytest.raises(Cfg1ManifestError):
        parse_package_name(_StrSubclass("left-pad"))
    with pytest.raises(Cfg1ManifestError):
        validate_dependency_maps({"dependencies": {_StrSubclass("left-pad"): "1"}})


@pytest.mark.parametrize("field", ["dependencies", "optionalDependencies", "peerDependencies"])
@pytest.mark.parametrize("key", _B5_KEYS)
def test_a9_the_strict_parser_plus_schema_refuses_every_b5_key_in_every_field(field, key):
    data = json.dumps({"name": "x", field: {key: "1.0.0"}}).encode("ascii")
    document = parse_manifest_strict(data)
    with pytest.raises(Cfg1ManifestError) as caught:
        validate_dependency_maps(document, "node_modules/x/package.json")
    assert caught.value.reason_code in (
        "PACKAGE_NAME_OUTSIDE_HPP1_GRAMMAR",
        "DEPENDENCY_KEY_LENGTH_OUT_OF_BOUNDS",
    )
    assert caught.value.manifest_path == "node_modules/x/package.json"
    if len(key) >= 3:
        assert key not in str(caught.value) and key not in repr(caught.value.args)


class _DictSubclass(dict):
    pass


@pytest.mark.parametrize("mapping", [[], "x", True, False, None, 0, 1.5, _DictSubclass(a="1")])
def test_a9_a_malformed_dependency_map_type_refuses(mapping):
    with pytest.raises(Cfg1ManifestError) as caught:
        validate_dependency_maps({"dependencies": mapping})
    assert caught.value.reason_code == "DEPENDENCY_MAP_NOT_OBJECT"


@pytest.mark.parametrize("value", [[], 1, True, None, 1.0, {}, _StrSubclass("1")])
def test_a9_a_malformed_dependency_value_type_refuses(value):
    with pytest.raises(Cfg1ManifestError) as caught:
        validate_dependency_maps({"peerDependencies": {"left-pad": value}})
    assert caught.value.reason_code == "DEPENDENCY_VALUE_NOT_STR"


def test_a9_bounds_key_value_and_map_size():
    validate_dependency_maps({"dependencies": {"a" * 214: "x" * 1024}})
    with pytest.raises(Cfg1ManifestError) as caught:
        validate_dependency_maps({"dependencies": {"a" * 215: "1"}})
    assert caught.value.reason_code == "DEPENDENCY_KEY_LENGTH_OUT_OF_BOUNDS"
    with pytest.raises(Cfg1ManifestError) as caught:
        validate_dependency_maps({"dependencies": {"a": "x" * 1025}})
    assert caught.value.reason_code == "DEPENDENCY_VALUE_TOO_LONG"
    full = {f"p{index}": "" for index in range(4096)}
    validate_dependency_maps({"dependencies": full})
    full["p4096"] = ""
    with pytest.raises(Cfg1ManifestError) as caught:
        validate_dependency_maps({"dependencies": full})
    assert caught.value.reason_code == "DEPENDENCY_MAP_TOO_LARGE"


def test_a9_empty_map_is_not_treated_as_absent_and_absent_is_fine():
    assert validate_dependency_maps({}).maps == ()
    assert validate_dependency_maps({"dependencies": {}}).maps == (("dependencies", ()),)


def test_a9_positive_round_trips_and_exact_path_construction():
    assert parse_package_name("left-pad") == ("left-pad",)
    assert parse_package_name(PI_AI) == ("@earendil-works", "pi-ai")
    for key in ("left-pad", PI_AI, "a", "a.b_c-d", "@s/n", "x" * 214):
        components = parse_package_name(key)
        assert pi_manifest.package_name_text(components) == key
        assert pi_manifest._join_relative("", components) == "node_modules/" + key
    ancestor = "C:\\prefix\\npm"
    assert ntpath.join(ancestor, "node_modules", *parse_package_name(PI_AI)) == (
        "C:\\prefix\\npm\\node_modules\\@earendil-works\\pi-ai"
    )


def test_a9_a_dependency_maps_object_cannot_be_forged():
    with pytest.raises(Cfg1ManifestError):
        DependencyMaps(object(), (("dependencies", ((("..",), "1"),)),))


@pytest.mark.parametrize("key", _B5_KEYS)
def test_a9_the_exposure_observer_refuses_a_malicious_exposure_before_any_observation(key):
    inspect = RecordingInspect()
    with pytest.raises(Cfg1ManifestError):
        observe_exposure_absence("C:\\x\\npm\\node_modules\\@e\\pi", [key], inspect=inspect)
    assert inspect.calls == []


def test_a9_a_malicious_key_makes_the_candidate_c5_with_no_profile_or_exposure():
    files, empty_dirs = synthetic_payload_files()
    for key in ("../x", "@scope/../x", "C:\\x"):
        broken = dict(files)
        broken["package.json"] = manifest_bytes(root_manifest(peerDependencies={key: "1"}))
        facts = facts_for(broken, empty_dirs)
        assert facts.c5_reason == "PACKAGE_NAME_OUTSIDE_HPP1_GRAMMAR"
        assert facts.c5_manifest_path == "package.json"
        assert facts.resolution_exposures is None and facts.profile_id is None


def test_a9_ast_audit_no_raw_dependency_key_reaches_a_path_or_format_operation():
    """Raw keys are only ever bound to ``key`` in the two key-handling functions;
    ``key`` never reaches a join, a format, an f-string, ``%`` or ``+``; and the
    only path-forming joins in the module consume parser output."""
    source = (_PACKAGE_DIR / "pi_manifest.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {node.name: node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}

    def _names_in(node) -> set[str]:
        return {sub.id for sub in ast.walk(node) if isinstance(sub, ast.Name)}

    for function in functions.values():
        for node in ast.walk(function):
            if isinstance(node, ast.JoinedStr):
                assert "key" not in _names_in(node), function.name
            if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod)):
                assert "key" not in _names_in(node), (function.name, node.lineno)
            if isinstance(node, ast.Call):
                func = node.func
                name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
                if name in ("join", "format", "normpath", "abspath", "realpath"):
                    for argument in list(node.args) + [k.value for k in node.keywords]:
                        assert "key" not in _names_in(argument), (function.name, node.lineno)
    # Path-forming joins live only in the two parser-output helpers (plus the
    # text-of-components helper and the manifest-path helper of a validated
    # inventory path).
    join_sites = set()
    for function in functions.values():
        for node in ast.walk(function):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "join"
            ):
                join_sites.add(function.name)
    assert join_sites <= {"_absent_under", "_join_relative", "package_name_text", "_proper_ancestors_for_containment"}
    # ``key`` is bound only in the parser, the schema, and the duplicate-key
    # object hook (which only tests membership and stores the pair).
    binders = set()
    for function in functions.values():
        for node in ast.walk(function):
            if isinstance(node, ast.Name) and node.id == "key" and isinstance(node.ctx, ast.Store):
                binders.add(function.name)
            if isinstance(node, ast.arg) and node.arg == "key":
                binders.add(function.name)
    assert binders <= {"parse_package_name", "validate_dependency_maps", "_exact_object", "__init__"}


def test_a9_no_other_pe2a_module_touches_dependency_keys():
    for module in ("pi_payload.py", "pi_profile_discovery.py"):
        source = (_PACKAGE_DIR / module).read_text(encoding="utf-8")
        assert "Dependencies" not in source and '"dependencies"' not in source, module


# ---------------------------------------------------------------------------
# A-10 -- containment, exposures and the no-follow exposure observer
# ---------------------------------------------------------------------------


def _exposures(files: dict[str, bytes], empty_dirs=()) -> tuple[str, ...]:
    facts = facts_for(files, empty_dirs)
    assert facts.resolution_exposures is not None, facts.c5_reason
    return facts.resolution_exposures


def test_a10_the_default_synthetic_payload_has_every_dependency_contained():
    files, empty_dirs = synthetic_payload_files()
    assert _exposures(files, empty_dirs) == ()


def test_a10_a_dependency_contained_only_in_a_nested_node_modules():
    files, empty_dirs = synthetic_payload_files()
    files = dict(files)
    files["node_modules/left-pad/package.json"] = manifest_bytes(
        {"name": "left-pad", "version": "1.3.0", "dependencies": {"nested-dep": "0.1.0"}}
    )
    assert _exposures(files, empty_dirs) == ()
    # ...but the ROOT asking for nested-dep is NOT contained (it is nested).
    files["package.json"] = manifest_bytes(root_manifest(peerDependencies={"nested-dep": "0.1.0"}))
    assert _exposures(files, empty_dirs) == ("nested-dep",)


def test_a10_a_directory_without_package_json_is_an_exposure():
    files, empty_dirs = synthetic_payload_files()
    files = dict(files)
    del files["node_modules/fsevents/package.json"]
    files["node_modules/fsevents/index.js"] = b"x"
    assert _exposures(files, empty_dirs) == ("fsevents",)


def test_a10_scoped_dependencies_and_optional_peer_maps_all_count():
    files, empty_dirs = synthetic_payload_files()
    files = dict(files)
    files["package.json"] = manifest_bytes(
        root_manifest(
            optionalDependencies={"@opt/one": "1", "fsevents": "2"},
            peerDependencies={"@peer/two": "1", "left-pad": "1"},
        )
    )
    assert _exposures(files, empty_dirs) == ("@opt/one", "@peer/two")


def test_a10_node_modules_named_ancestors_are_skipped():
    files, empty_dirs = synthetic_payload_files()
    files = dict(files)
    files["node_modules/a/package.json"] = manifest_bytes({"name": "a", "version": "1"})
    files["node_modules/a/node_modules/b/package.json"] = manifest_bytes(
        {"name": "b", "version": "1", "dependencies": {"c": "1"}}
    )
    # A candidate under a node_modules-named ANCESTOR would be
    # node_modules/a/node_modules/node_modules/c -- never consulted.
    files["node_modules/a/node_modules/node_modules/c/package.json"] = manifest_bytes(
        {"name": "c", "version": "1"}
    )
    assert _exposures(files, empty_dirs) == ("c",)
    files["node_modules/a/node_modules/c/package.json"] = manifest_bytes({"name": "c", "version": "1"})
    assert _exposures(files, empty_dirs) == ()


def test_a10_the_scope_directory_is_an_ancestor_candidate():
    files, empty_dirs = synthetic_payload_files()
    files = dict(files)
    files["node_modules/@scope/util/package.json"] = manifest_bytes(
        {"name": "@scope/util", "version": "2.0.0", "dependencies": {"y": "1"}}
    )
    assert _exposures(files, empty_dirs) == ("y",)
    files["node_modules/@scope/node_modules/y/package.json"] = manifest_bytes({"name": "y", "version": "1"})
    assert _exposures(files, empty_dirs) == ()


def test_a10_package_roots_follow_inventory_structure_only():
    files, empty_dirs = synthetic_payload_files()
    inventory = inventory_from_entries(expected_entries(files, empty_dirs))
    roots = package_roots(inventory)
    assert roots[0] == ""
    assert "node_modules/@earendil-works/pi-ai" in roots
    assert "node_modules/left-pad/node_modules/nested-dep" in roots
    assert "node_modules/.bin" not in roots  # no package.json of its own
    assert "dist/fixtures/broken" not in roots  # not a node_modules child
    assert "node_modules/@scope" not in roots
    assert list(roots[1:]) == sorted(roots[1:])


@pytest.mark.parametrize(
    "bad_root",
    ["node_modules/Bad", "node_modules/@Other/x", "node_modules/@s/X", "node_modules/@scope", "node_modules/.hidden"],
)
def test_a10_a_package_root_name_outside_the_grammar_is_c5(bad_root):
    files, empty_dirs = synthetic_payload_files()
    files = dict(files)
    files[bad_root + "/package.json"] = manifest_bytes({"name": "x", "version": "1"})
    facts = facts_for(files, empty_dirs)
    assert facts.c5_reason == "PACKAGE_ROOT_NAME_OUTSIDE_HPP1_GRAMMAR"
    assert facts.c5_manifest_path == bad_root + "/package.json"


def test_a10_compute_exposures_refuses_a_root_set_mismatch():
    files, empty_dirs = synthetic_payload_files()
    inventory = inventory_from_entries(expected_entries(files, empty_dirs))
    with pytest.raises(Cfg1ManifestError):
        compute_resolution_exposures(inventory, {"": validate_dependency_maps({})})


_ROOT = "C:\\pre\\npm\\node_modules\\@earendil-works\\pi-coding-agent"
_ANCESTORS = (
    "C:\\pre\\npm\\node_modules\\@earendil-works",
    "C:\\pre\\npm",
    "C:\\pre",
    "C:\\",
)


def test_a10_observer_checks_every_non_node_modules_ancestor_nearest_first():
    inspect = RecordingInspect()
    result = observe_exposure_absence(_ROOT, ["fsevents"], inspect=inspect)
    assert result.status == EXPOSURES_PROVEN_ABSENT and result.exposure is None
    assert inspect.calls == [ntpath.join(ancestor, "node_modules") for ancestor in _ANCESTORS]
    assert not any("node_modules\\node_modules" in call for call in inspect.calls)


def test_a10_observer_plain_directory_then_missing_is_absent():
    inspect = RecordingInspect(
        {"C:\\pre\\npm\\node_modules": "directory", "C:\\pre\\npm\\node_modules\\@s": "directory"}
    )
    result = observe_exposure_absence(_ROOT, ["@s/n"], inspect=inspect)
    assert result.status == EXPOSURES_PROVEN_ABSENT
    assert "C:\\pre\\npm\\node_modules\\@s\\n" in inspect.calls


@pytest.mark.parametrize("final", ["directory", "regular_file", "reparse_point", "other"])
def test_a10_observer_a_present_or_odd_final_entry_is_exposed(final):
    inspect = RecordingInspect(
        {"C:\\pre\\npm\\node_modules": "directory", "C:\\pre\\npm\\node_modules\\fsevents": final}
    )
    result = observe_exposure_absence(_ROOT, ["fsevents"], inspect=inspect)
    assert result.status == EXPOSURE_PRESENT_OR_UNOBSERVABLE and result.exposure == "fsevents"


@pytest.mark.parametrize("intermediate", ["reparse_point", "regular_file", "other"])
def test_a10_observer_an_odd_intermediate_is_unobservable_and_never_followed(intermediate):
    inspect = RecordingInspect({"C:\\pre\\npm\\node_modules": intermediate})
    result = observe_exposure_absence(_ROOT, ["@s/n"], inspect=inspect)
    assert result.status == EXPOSURE_PRESENT_OR_UNOBSERVABLE
    assert not any(call.startswith("C:\\pre\\npm\\node_modules\\@s") for call in inspect.calls)


def test_a10_observer_an_observation_failure_is_unobservable():
    inspect = RecordingInspect(raise_on={"C:\\pre\\node_modules"})
    assert observe_exposure_absence(_ROOT, ["x"], inspect=inspect).status == EXPOSURE_PRESENT_OR_UNOBSERVABLE
    malformed = lambda path: "not an observation"  # noqa: E731
    assert observe_exposure_absence(_ROOT, ["x"], inspect=malformed).status == EXPOSURE_PRESENT_OR_UNOBSERVABLE


def test_a10_observer_never_skips_a_differently_cased_node_modules_ancestor():
    """Node skips only an exact ``node_modules`` segment; so does the observer."""
    root = "C:\\pre\\Node_Modules\\x\\node_modules\\@e\\pi"
    inspect = RecordingInspect()
    observe_exposure_absence(root, ["y"], inspect=inspect)
    assert "C:\\pre\\Node_Modules\\node_modules" in inspect.calls
    assert "C:\\pre\\Node_Modules\\x\\node_modules\\node_modules" not in inspect.calls


def test_a10_observer_refuses_a_relative_root():
    with pytest.raises(Cfg1ManifestError):
        observe_exposure_absence("relative\\root", [], inspect=RecordingInspect())


def test_a10_empty_exposures_observe_nothing():
    inspect = RecordingInspect()
    assert observe_exposure_absence(_ROOT, [], inspect=inspect).status == EXPOSURES_PROVEN_ABSENT
    assert inspect.calls == []


@pytest.mark.parametrize("exposures", [["b", "a"], ["a", "a"], ("a", 1), "abc"])
def test_profile_id_refuses_non_canonical_exposure_lists(exposures):
    with pytest.raises(Cfg1ManifestError):
        compute_profile_id("0" * 64, exposures)


# ---------------------------------------------------------------------------
# A-14 -- approvability failures are C5
# ---------------------------------------------------------------------------


def test_a14_the_synthetic_payload_meets_the_approvability_floor():
    files, empty_dirs = synthetic_payload_files()
    facts = facts_for(files, empty_dirs)
    assert facts.c5_reason is None
    assert facts.declared_dict() == {
        "package_name": "@earendil-works/pi-coding-agent",
        "package_version": "1.0.0",
        "pi_ai_version": "1.0.0",
        "pi_agent_core_version": "1.0.0",
    }


@pytest.mark.parametrize(
    "missing", ["dist/core/sdk.js", "node_modules/@earendil-works/pi-ai/dist/models.js"]
)
def test_a14_a_missing_pi_sc1_path_is_c5(missing):
    files, empty_dirs = synthetic_payload_files()
    files = dict(files)
    del files[missing]
    assert facts_for(files, empty_dirs).c5_reason == "PI_SC1_PATH_NOT_A_FILE"


def test_a14_dist_cli_js_as_a_directory_is_c5():
    files, empty_dirs = synthetic_payload_files()
    files = dict(files)
    del files["dist/cli.js"]
    files["dist/cli.js/inner.js"] = b"x"
    facts = facts_for(files, empty_dirs)
    assert facts.c5_reason == "LAUNCH_TARGET_NOT_A_FILE"
    assert facts.seam_digests is None


@pytest.mark.parametrize(
    "path, document",
    [
        ("package.json", root_manifest(name="@earendil-works/pi-coding-agentx")),
        ("package.json", root_manifest(name="@Earendil-Works/pi-coding-agent")),
        ("node_modules/@earendil-works/pi-ai/package.json", pi_ai_manifest(name="pi-ai")),
        (
            "node_modules/@earendil-works/pi-agent-core/package.json",
            pi_agent_core_manifest(name=["@earendil-works/pi-agent-core"]),
        ),
    ],
)
def test_a14_a_wrong_package_name_is_c5(path, document):
    files, empty_dirs = synthetic_payload_files()
    files = dict(files)
    files[path] = manifest_bytes(document)
    facts = facts_for(files, empty_dirs)
    assert facts.c5_reason == "DECLARED_PACKAGE_NAME_MISMATCH"
    assert facts.c5_manifest_path == path


@pytest.mark.parametrize("version", ["", "x" * 129, "1.0 .0", "1.0.0\u00e9", 1, None, ["1.0.0"], "1.\x7f"])
def test_a14_a_bad_version_grammar_is_c5(version):
    files, empty_dirs = synthetic_payload_files()
    files = dict(files)
    files["node_modules/@earendil-works/pi-ai/package.json"] = manifest_bytes(pi_ai_manifest(version=version))
    facts = facts_for(files, empty_dirs)
    assert facts.c5_reason == "DECLARED_VERSION_INVALID"


def test_a14_a_version_at_its_bounds_is_accepted():
    files, empty_dirs = synthetic_payload_files()
    files = dict(files)
    files["package.json"] = manifest_bytes(root_manifest(version="!" + "~" * 127))
    assert facts_for(files, empty_dirs).c5_reason is None


def test_a14_a_missing_version_is_c5():
    files, empty_dirs = synthetic_payload_files()
    files = dict(files)
    document = root_manifest()
    del document["version"]
    files["package.json"] = manifest_bytes(document)
    assert facts_for(files, empty_dirs).c5_reason == "DECLARED_VERSION_INVALID"


@pytest.mark.parametrize(
    "data, reason",
    [
        (b"\xef\xbb\xbf{}", "MANIFEST_BOM"),
        (b'{"name":1,"name":2}', "MANIFEST_DUPLICATE_KEY"),
        (b"[]", "MANIFEST_TOP_LEVEL_NOT_OBJECT"),
        (b'{"dependencies":[]}', "DEPENDENCY_MAP_NOT_OBJECT"),
    ],
)
def test_a14_a_strictly_unparseable_package_root_manifest_is_c5(data, reason):
    files, empty_dirs = synthetic_payload_files()
    files = dict(files)
    files["node_modules/zod/package.json"] = data
    facts = facts_for(files, empty_dirs)
    assert facts.c5_reason == reason
    assert facts.c5_manifest_path == "node_modules/zod/package.json"


def test_a14_a_malformed_non_root_manifest_is_bytes_only_and_not_c5():
    files, empty_dirs = synthetic_payload_files()
    assert files["dist/fixtures/broken/package.json"] == b"{ not json"
    assert facts_for(files, empty_dirs).c5_reason is None


def test_a14_committed_file_bounds_are_c5(monkeypatch):
    files, empty_dirs = synthetic_payload_files()
    monkeypatch.setattr(pi_profile_floor, "MAX_INVENTORY_FILE_BYTES", 100)
    assert facts_for(files, empty_dirs).c5_reason == "INVENTORY_FILE_BOUND_EXCEEDED"
    monkeypatch.setattr(pi_profile_floor, "MAX_INVENTORY_FILE_BYTES", 100663296)
    monkeypatch.setattr(pi_profile_floor, "MAX_MANIFEST_BUNDLE_FILE_BYTES", 100)
    assert facts_for(files, empty_dirs).c5_reason == "MANIFEST_BUNDLE_FILE_BOUND_EXCEEDED"


def test_a14_approvability_items_are_evaluated_in_sec_4_6_order():
    files, empty_dirs = synthetic_payload_files()
    files = dict(files)
    del files["dist/cli.js"]
    files["package.json"] = manifest_bytes(root_manifest(name="wrong"))
    assert facts_for(files, empty_dirs).c5_reason == "LAUNCH_TARGET_NOT_A_FILE"


# ---------------------------------------------------------------------------
# Sec. 6.1 -- the manifest bundle
# ---------------------------------------------------------------------------


def _inventory_and_bundle():
    files, empty_dirs = synthetic_payload_files()
    inventory = inventory_from_entries(expected_entries(files, empty_dirs))
    bundle = build_manifest_bundle(inventory, {p: files[p] for p in bundle_manifest_paths(inventory)})
    return files, inventory, bundle


def test_bundle_covers_every_package_json_file_and_only_those():
    files, inventory, bundle = _inventory_and_bundle()
    expected = sorted(path for path in files if path.split("/")[-1] == "package.json")
    assert [path for path, _ in bundle.manifests] == expected
    assert "dist/fixtures/broken/package.json" in dict(bundle.manifests)


def test_bundle_a_case_fold_variant_is_not_a_manifest():
    files, empty_dirs = synthetic_payload_files()
    files = dict(files)
    files["dist/Package.json"] = b"{}"
    inventory = inventory_from_entries(expected_entries(files, empty_dirs))
    assert "dist/Package.json" not in bundle_manifest_paths(inventory)


def test_bundle_record_round_trips_exactly():
    files, inventory, bundle = _inventory_and_bundle()
    record = json.loads(json.dumps(bundle.to_record()))
    again = bundle_from_record(record, inventory)
    assert again.manifests == bundle.manifests
    for path, data in again.manifests:
        assert data == files[path]
        assert record["manifests"][path] == base64.b64encode(data).decode("ascii")


@pytest.mark.parametrize(
    "mutate, reason",
    [
        (lambda r, i: r.update(extra=1), "BUNDLE_RECORD_KEYS"),
        (lambda r, i: r.update(record_kind="aido-pi-manifest-bundle.v2"), "BUNDLE_RECORD_KIND"),
        (lambda r, i: r.update(payload_fingerprint="0" * 64), "BUNDLE_FINGERPRINT_MISMATCH"),
        (lambda r, i: r.update(payload_fingerprint=r["payload_fingerprint"].upper()), "BUNDLE_FINGERPRINT_MISMATCH"),
        (lambda r, i: r["manifests"].pop("package.json"), "BUNDLE_KEY_SET_MISMATCH"),
        (lambda r, i: r["manifests"].update({"dist/x.json": "e30="}), "BUNDLE_KEY_SET_MISMATCH"),
        (lambda r, i: r["manifests"].update({"package.json": "e30"}), "BUNDLE_VALUE_MALFORMED"),
        (lambda r, i: r["manifests"].update({"package.json": "e3\n0="}), "BUNDLE_VALUE_MALFORMED"),
        (lambda r, i: r["manifests"].update({"package.json": "e30=\n"}), "BUNDLE_VALUE_MALFORMED"),
        (lambda r, i: r["manifests"].update({"package.json": "e30_"}), "BUNDLE_VALUE_MALFORMED"),
        (lambda r, i: r["manifests"].update({"package.json": "e31="}), "BUNDLE_VALUE_NOT_CANONICAL_BASE64"),
        (lambda r, i: r["manifests"].update({"package.json": "e30="}), "BUNDLE_MANIFEST_NOT_BOUND"),
        (lambda r, i: r["manifests"].update({"package.json": 1}), "BUNDLE_MANIFESTS_MALFORMED"),
        (lambda r, i: r.update(manifests=list(r["manifests"].items())), "BUNDLE_MANIFESTS_MALFORMED"),
    ],
)
def test_bundle_record_validation_refuses(mutate, reason):
    _files, inventory, bundle = _inventory_and_bundle()
    record = bundle.to_record()
    mutate(record, inventory)
    with pytest.raises(Cfg1ManifestError) as caught:
        bundle_from_record(record, inventory)
    assert caught.value.reason_code == reason


def test_bundle_binding_refuses_wrong_bytes_or_key_sets():
    files, inventory, _bundle = _inventory_and_bundle()
    supplied = {p: files[p] for p in bundle_manifest_paths(inventory)}
    with pytest.raises(Cfg1ManifestError):
        build_manifest_bundle(inventory, {**supplied, "package.json": files["package.json"] + b" "})
    with pytest.raises(Cfg1ManifestError):
        build_manifest_bundle(inventory, {k: v for k, v in supplied.items() if k != "package.json"})
    with pytest.raises(Cfg1ManifestError):
        build_manifest_bundle(inventory, {**supplied, "package.json": bytearray(files["package.json"])})


def test_bundle_bounds_at_bound_accepted_plus_one_refused(monkeypatch):
    files, inventory, _bundle = _inventory_and_bundle()
    supplied = {p: files[p] for p in bundle_manifest_paths(inventory)}
    count = len(supplied)
    largest = max(len(v) for v in supplied.values())
    total = sum(len(v) for v in supplied.values())
    monkeypatch.setattr(pi_manifest, "MAX_MANIFEST_COUNT", count)
    build_manifest_bundle(inventory, supplied)
    monkeypatch.setattr(pi_manifest, "MAX_MANIFEST_COUNT", count - 1)
    with pytest.raises(Cfg1ManifestError) as caught:
        build_manifest_bundle(inventory, supplied)
    assert caught.value.reason_code == "MANIFEST_COUNT_EXCEEDED"
    monkeypatch.setattr(pi_manifest, "MAX_MANIFEST_COUNT", 20000)
    monkeypatch.setattr(pi_manifest, "MAX_MANIFEST_BYTES", largest)
    build_manifest_bundle(inventory, supplied)
    monkeypatch.setattr(pi_manifest, "MAX_MANIFEST_BYTES", largest - 1)
    with pytest.raises(Cfg1ManifestError) as caught:
        build_manifest_bundle(inventory, supplied)
    assert caught.value.reason_code == "MANIFEST_TOO_LARGE"
    monkeypatch.setattr(pi_manifest, "MAX_MANIFEST_BYTES", 1048576)
    monkeypatch.setattr(pi_manifest, "MAX_MANIFEST_TOTAL_BYTES", total)
    build_manifest_bundle(inventory, supplied)
    monkeypatch.setattr(pi_manifest, "MAX_MANIFEST_TOTAL_BYTES", total - 1)
    with pytest.raises(Cfg1ManifestError) as caught:
        build_manifest_bundle(inventory, supplied)
    assert caught.value.reason_code == "MANIFEST_TOTAL_BYTES_EXCEEDED"


def test_bundle_objects_are_not_constructible_outside():
    with pytest.raises(Cfg1ManifestError):
        pi_manifest.ManifestBundle(object(), "0" * 64, ())


def test_the_internal_dependency_names_are_exact_literals():
    assert PI_AI == pi_manifest.PI_AI_PACKAGE_NAME
    assert PI_AGENT_CORE == pi_manifest.PI_AGENT_CORE_PACKAGE_NAME
    assert pi_manifest.ROOT_PACKAGE_NAME == "@earendil-works/pi-coding-agent"
