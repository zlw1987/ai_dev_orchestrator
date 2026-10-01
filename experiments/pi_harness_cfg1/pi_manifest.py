"""Manifests, the B5 package-name grammar and declared-dependency containment (PE-2a).

Implements ``docs/PHASE_5F3B_PI_HARNESS_PROFILE_EVOLUTION_PE1_AMENDMENT.md``
Sec. 6.1-6.6 and Sec. 4.7 as SHARED PURE PRIMITIVES (plus one injected-leaf
observer). Discovery uses them now; the PE-2b loader will call these same
function objects later. Nothing here loads policy, grants eligibility, or is
consulted by P, the gate, L1, L14 or L21A.

**Untrusted bytes, exact types, no repair.** ``package.json`` bytes are Pi
content. The strict parser refuses a BOM, invalid UTF-8, duplicate keys at any
depth, ``NaN``/``Infinity``, over-long number tokens, non-finite floats, raw
control characters, excessive nesting and any non-object top level; it never
coerces, defaults, strips or repairs anything.

**A raw dependency key never forms a path.** Every key passes the dependency
map schema and :func:`parse_package_name` first; only the parser's returned
components are ever joined -- in memory with ``"/".join`` and on disk with
``ntpath.join(<ancestor>, "node_modules", *components)``. A refused key is
never rendered: every refusal carries a closed reason code and, at most, the
grammar-validated payload path of the manifest it came from.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import ntpath
import re
from collections.abc import Mapping, Sequence
from typing import Callable

from .pi_fs_leaves import (
    CLASSIFICATION_DIRECTORY,
    CLASSIFICATION_MISSING,
    CLASSIFICATIONS,
    NoFollowObservation,
)
from .pi_payload import (
    INVENTORY_KIND_DIR,
    INVENTORY_KIND_FILE,
    PAYLOAD_CONTRACT,
    PayloadInventory,
    canonical_json_bytes,
    is_lowercase_hex64,
    last_segment,
)

# ---------------------------------------------------------------------------
# Frozen literals and bounds (PE-1 Sec. 3, Sec. 4.4)
# ---------------------------------------------------------------------------

MANIFEST_BUNDLE_RECORD_KIND = "aido-pi-manifest-bundle.v1"
PROFILE_ID_DOMAIN_TAG = b"aido.pi-profile.v1\x00"
MANIFEST_NAME = "package.json"

ROOT_PACKAGE_NAME = "@earendil-works/pi-coding-agent"
PI_AI_PACKAGE_NAME = "@earendil-works/pi-ai"
PI_AGENT_CORE_PACKAGE_NAME = "@earendil-works/pi-agent-core"

ROOT_MANIFEST_PATH = "package.json"
PI_AI_MANIFEST_PATH = "node_modules/@earendil-works/pi-ai/package.json"
PI_AGENT_CORE_MANIFEST_PATH = "node_modules/@earendil-works/pi-agent-core/package.json"

MAX_MANIFEST_BYTES = 1048576
MAX_MANIFEST_COUNT = 20000
MAX_MANIFEST_TOTAL_BYTES = 67108864
MAX_MANIFEST_JSON_DEPTH = 64
MAX_MANIFEST_NUMBER_TOKEN_CHARS = 256
MAX_DEPENDENCY_MAP_KEYS = 4096
MAX_DEPENDENCY_KEY_CHARS = 214
MAX_DEPENDENCY_VALUE_CHARS = 1024
MAX_DECLARED_VERSION_CHARS = 128

DEPENDENCY_FIELDS: tuple[str, ...] = (
    "dependencies",
    "optionalDependencies",
    "peerDependencies",
)

_UTF8_BOM = b"\xef\xbb\xbf"

# ---------------------------------------------------------------------------
# Closed refusal vocabulary
# ---------------------------------------------------------------------------

MANIFEST_TOO_LARGE = "MANIFEST_TOO_LARGE"
MANIFEST_BOM = "MANIFEST_BOM"
MANIFEST_NOT_UTF8 = "MANIFEST_NOT_UTF8"
MANIFEST_JSON_INVALID = "MANIFEST_JSON_INVALID"
MANIFEST_DUPLICATE_KEY = "MANIFEST_DUPLICATE_KEY"
MANIFEST_NON_FINITE_NUMBER = "MANIFEST_NON_FINITE_NUMBER"
MANIFEST_NUMBER_TOKEN_TOO_LONG = "MANIFEST_NUMBER_TOKEN_TOO_LONG"
MANIFEST_DEPTH_EXCEEDED = "MANIFEST_DEPTH_EXCEEDED"
MANIFEST_TOP_LEVEL_NOT_OBJECT = "MANIFEST_TOP_LEVEL_NOT_OBJECT"
DEPENDENCY_MAP_NOT_OBJECT = "DEPENDENCY_MAP_NOT_OBJECT"
DEPENDENCY_MAP_TOO_LARGE = "DEPENDENCY_MAP_TOO_LARGE"
DEPENDENCY_KEY_NOT_STR = "DEPENDENCY_KEY_NOT_STR"
DEPENDENCY_KEY_LENGTH_OUT_OF_BOUNDS = "DEPENDENCY_KEY_LENGTH_OUT_OF_BOUNDS"
DEPENDENCY_VALUE_NOT_STR = "DEPENDENCY_VALUE_NOT_STR"
DEPENDENCY_VALUE_TOO_LONG = "DEPENDENCY_VALUE_TOO_LONG"
PACKAGE_NAME_OUTSIDE_HPP1_GRAMMAR = "PACKAGE_NAME_OUTSIDE_HPP1_GRAMMAR"
PACKAGE_ROOT_NAME_OUTSIDE_HPP1_GRAMMAR = "PACKAGE_ROOT_NAME_OUTSIDE_HPP1_GRAMMAR"
DECLARED_MANIFEST_MISSING = "DECLARED_MANIFEST_MISSING"
DECLARED_PACKAGE_NAME_MISMATCH = "DECLARED_PACKAGE_NAME_MISMATCH"
DECLARED_VERSION_INVALID = "DECLARED_VERSION_INVALID"


class Cfg1ManifestError(Exception):
    """A manifest, bundle or name refusal. Closed reason code only.

    ``manifest_path`` is either ``None`` or a payload relative path that has
    already passed the Sec. 4.2 grammar (an inventory path). Neither the
    message nor any attribute ever carries a dependency key, a value, or
    manifest text: a refused raw key must never reach a console or log.
    """

    def __init__(self, reason_code: str, manifest_path: str | None = None) -> None:
        super().__init__(f"cfg1 pi manifest refused: {reason_code}")
        self.reason_code = reason_code
        self.manifest_path = manifest_path


# ---------------------------------------------------------------------------
# Sec. 6.3: the ONE package-name parser (B5, frozen)
# ---------------------------------------------------------------------------

_NAME_CHARACTERS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789._@/-")
_COMPONENT = re.compile(r"[a-z0-9][a-z0-9._-]*")
_RESERVED_STEMS = frozenset(
    {"con", "prn", "aux", "nul"}
    | {f"com{digit}" for digit in range(10)}
    | {f"lpt{digit}" for digit in range(10)}
)


def _component_ok(component: str) -> bool:
    if not component or _COMPONENT.fullmatch(component) is None:
        return False
    if component.endswith(".") or component == "node_modules":
        return False
    return component.split(".", 1)[0] not in _RESERVED_STEMS


def parse_package_name(key: object) -> tuple[str] | tuple[str, str]:
    """``NAME -> (NAME,)`` and ``@SCOPE/NAME -> ("@"+SCOPE, NAME)``; else refuse.

    PE-0 Sec. 5.3.1 / PE-1 Sec. 6.3 exactly. Never normalizes, lowercases,
    strips, percent-decodes or repairs; never consults npm, Node or the
    filesystem. The refusal names no part of ``key``.
    """
    if type(key) is not str:
        raise Cfg1ManifestError(PACKAGE_NAME_OUTSIDE_HPP1_GRAMMAR)
    if not 1 <= len(key) <= MAX_DEPENDENCY_KEY_CHARS:
        raise Cfg1ManifestError(PACKAGE_NAME_OUTSIDE_HPP1_GRAMMAR)
    for character in key:
        if character not in _NAME_CHARACTERS:
            raise Cfg1ManifestError(PACKAGE_NAME_OUTSIDE_HPP1_GRAMMAR)
    slashes = key.count("/")
    ats = key.count("@")
    if slashes == 0 and ats == 0:
        if not _component_ok(key):
            raise Cfg1ManifestError(PACKAGE_NAME_OUTSIDE_HPP1_GRAMMAR)
        components: tuple[str] | tuple[str, str] = (key,)
        canonical = key
    elif key[0] == "@" and slashes == 1 and ats == 1:
        scope, name = key[1:].split("/")
        if not _component_ok(scope) or not _component_ok(name):
            raise Cfg1ManifestError(PACKAGE_NAME_OUTSIDE_HPP1_GRAMMAR)
        components = ("@" + scope, name)
        canonical = "@" + scope + "/" + name
    else:
        raise Cfg1ManifestError(PACKAGE_NAME_OUTSIDE_HPP1_GRAMMAR)
    if canonical != key:
        raise Cfg1ManifestError(PACKAGE_NAME_OUTSIDE_HPP1_GRAMMAR)
    return components


def package_name_text(components: tuple[str, ...]) -> str:
    """The canonical text of parser output (re-parsed to prove the round trip)."""
    if type(components) is not tuple or len(components) not in (1, 2):
        raise Cfg1ManifestError(PACKAGE_NAME_OUTSIDE_HPP1_GRAMMAR)
    text = "/".join(components)
    if parse_package_name(text) != components:
        raise Cfg1ManifestError(PACKAGE_NAME_OUTSIDE_HPP1_GRAMMAR)
    return text


# ---------------------------------------------------------------------------
# Sec. 6.2: the strict manifest parser
# ---------------------------------------------------------------------------


def _refuse_constant(_token: str):
    raise Cfg1ManifestError(MANIFEST_NON_FINITE_NUMBER)


def _parse_int(token: str) -> int:
    if len(token) > MAX_MANIFEST_NUMBER_TOKEN_CHARS:
        raise Cfg1ManifestError(MANIFEST_NUMBER_TOKEN_TOO_LONG)
    return int(token)


def _parse_float(token: str) -> float:
    if len(token) > MAX_MANIFEST_NUMBER_TOKEN_CHARS:
        raise Cfg1ManifestError(MANIFEST_NUMBER_TOKEN_TOO_LONG)
    value = float(token)
    if not math.isfinite(value):
        raise Cfg1ManifestError(MANIFEST_NON_FINITE_NUMBER)
    return value


def _exact_object(pairs: list) -> dict:
    """Duplicate keys refuse at ANY depth; key order is preserved."""
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise Cfg1ManifestError(MANIFEST_DUPLICATE_KEY)
        result[key] = value
    return result


def _nesting_depth(value: object) -> int:
    """Container nesting depth (a top-level object is depth 1), iteratively."""
    deepest = 0
    pending = [(value, 1)]
    while pending:
        current, depth = pending.pop()
        if type(current) is dict:
            deepest = max(deepest, depth)
            pending.extend((item, depth + 1) for item in current.values())
        elif type(current) is list:
            deepest = max(deepest, depth)
            pending.extend((item, depth + 1) for item in current)
    return deepest


def parse_manifest_strict(data: object) -> dict:
    """Parse one package-root manifest from BOUND bytes, strictly (Sec. 6.2).

    The result is order-preserving and exact-typed: ``dict`` (insertion
    ordered), ``list``, ``str``, ``int`` (never ``bool``), finite ``float``,
    ``bool``, ``None``. Any refusal raises :class:`Cfg1ManifestError`; no
    partial value is ever returned.
    """
    if type(data) is not bytes:
        raise Cfg1ManifestError(MANIFEST_JSON_INVALID)
    if len(data) > MAX_MANIFEST_BYTES:
        raise Cfg1ManifestError(MANIFEST_TOO_LARGE)
    if data.startswith(_UTF8_BOM):
        raise Cfg1ManifestError(MANIFEST_BOM)
    try:
        text = data.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise Cfg1ManifestError(MANIFEST_NOT_UTF8) from None
    try:
        value = json.loads(
            text,
            object_pairs_hook=_exact_object,
            parse_constant=_refuse_constant,
            parse_float=_parse_float,
            parse_int=_parse_int,
            strict=True,
        )
    except Cfg1ManifestError as refusal:
        raise Cfg1ManifestError(refusal.reason_code) from None
    except RecursionError:
        raise Cfg1ManifestError(MANIFEST_DEPTH_EXCEEDED) from None
    except ValueError:
        raise Cfg1ManifestError(MANIFEST_JSON_INVALID) from None
    if _nesting_depth(value) > MAX_MANIFEST_JSON_DEPTH:
        raise Cfg1ManifestError(MANIFEST_DEPTH_EXCEEDED)
    if type(value) is not dict:
        raise Cfg1ManifestError(MANIFEST_TOP_LEVEL_NOT_OBJECT)
    return value


# ---------------------------------------------------------------------------
# Sec. 6.3: the dependency-map schema
# ---------------------------------------------------------------------------


class DependencyMaps:
    """The three validated dependency maps of ONE package-root manifest.

    ``maps`` is ``((field, ((components, value), ...)), ...)`` in
    :data:`DEPENDENCY_FIELDS` order, each map in its manifest's key order;
    an absent field is simply not listed. ``components`` is parser output --
    the raw key itself is not retained. Immutable.
    """

    __slots__ = ("maps",)

    def __init__(self, key: object, maps: tuple) -> None:
        if key is not _SCHEMA_KEY:
            raise Cfg1ManifestError(DEPENDENCY_MAP_NOT_OBJECT)
        object.__setattr__(self, "maps", maps)

    def __setattr__(self, name: str, value: object) -> None:  # noqa: D105
        raise AttributeError("DependencyMaps is immutable")


_SCHEMA_KEY = object()


def validate_dependency_maps(manifest: object, manifest_path: str | None = None) -> DependencyMaps:
    """Validate ``dependencies``/``optionalDependencies``/``peerDependencies``.

    Each field is absent or an EXACT ``dict`` (``null``, list, str, number,
    bool or a subclass refuses; "empty means absent" is never applied). Every
    key is an exact ``str`` of 1..214 characters that :func:`parse_package_name`
    accepts; every value is an exact ``str`` of 0..1024 characters; a map
    holds at most 4096 keys. Values are never interpreted. The whole manifest
    refuses on the first violation; nothing is partially validated.
    """
    if type(manifest) is not dict:
        raise Cfg1ManifestError(MANIFEST_TOP_LEVEL_NOT_OBJECT, manifest_path)
    validated = []
    for field in DEPENDENCY_FIELDS:
        if field not in manifest:
            continue
        mapping = manifest[field]
        if type(mapping) is not dict:
            raise Cfg1ManifestError(DEPENDENCY_MAP_NOT_OBJECT, manifest_path)
        if len(mapping) > MAX_DEPENDENCY_MAP_KEYS:
            raise Cfg1ManifestError(DEPENDENCY_MAP_TOO_LARGE, manifest_path)
        entries = []
        for key, value in mapping.items():
            if type(key) is not str:
                raise Cfg1ManifestError(DEPENDENCY_KEY_NOT_STR, manifest_path)
            if not 1 <= len(key) <= MAX_DEPENDENCY_KEY_CHARS:
                raise Cfg1ManifestError(DEPENDENCY_KEY_LENGTH_OUT_OF_BOUNDS, manifest_path)
            try:
                components = parse_package_name(key)
            except Cfg1ManifestError:
                raise Cfg1ManifestError(PACKAGE_NAME_OUTSIDE_HPP1_GRAMMAR, manifest_path) from None
            if type(value) is not str:
                raise Cfg1ManifestError(DEPENDENCY_VALUE_NOT_STR, manifest_path)
            if len(value) > MAX_DEPENDENCY_VALUE_CHARS:
                raise Cfg1ManifestError(DEPENDENCY_VALUE_TOO_LONG, manifest_path)
            entries.append((components, value))
        validated.append((field, tuple(entries)))
    return DependencyMaps(_SCHEMA_KEY, tuple(validated))


# ---------------------------------------------------------------------------
# Sec. 6.1: the manifest bundle
# ---------------------------------------------------------------------------

_BUNDLE_RECORD_KEYS = ("manifests", "payload_fingerprint", "record_kind")
_MAX_MANIFEST_BASE64_CHARS = 4 * ((MAX_MANIFEST_BYTES + 2) // 3)


def bundle_manifest_paths(inventory: PayloadInventory) -> tuple[str, ...]:
    """Every inventory FILE whose last segment is exactly ``package.json`` (case-sensitive)."""
    if type(inventory) is not PayloadInventory:
        raise Cfg1ManifestError("MALFORMED_INVENTORY")
    return tuple(
        entry[1]
        for entry in inventory.entries
        if entry[0] == INVENTORY_KIND_FILE and last_segment(entry[1]) == MANIFEST_NAME
    )


class ManifestBundle:
    """A validated ``aido-pi-manifest-bundle.v1``, bound to one inventory.

    ``manifests`` is ``((path, bytes), ...)`` in inventory order; every path
    is exactly a bundle manifest path of the bound inventory and every byte
    string hashes to that entry's digest with that entry's size. Immutable.
    """

    __slots__ = ("payload_fingerprint", "manifests", "_by_path")

    def __init__(self, key: object, payload_fingerprint: str, manifests: tuple) -> None:
        if key is not _BUNDLE_KEY:
            raise Cfg1ManifestError("BUNDLE_NOT_VALIDATED")
        object.__setattr__(self, "payload_fingerprint", payload_fingerprint)
        object.__setattr__(self, "manifests", manifests)
        object.__setattr__(self, "_by_path", dict(manifests))

    def __setattr__(self, name: str, value: object) -> None:  # noqa: D105
        raise AttributeError("ManifestBundle is immutable")

    def __repr__(self) -> str:  # noqa: D105
        return f"{type(self).__name__}(manifests={len(self.manifests)})"

    def manifest_bytes(self, path: str) -> bytes | None:
        if type(path) is not str:
            return None
        return self._by_path.get(path)

    def to_record(self) -> dict:
        return {
            "record_kind": MANIFEST_BUNDLE_RECORD_KIND,
            "payload_fingerprint": self.payload_fingerprint,
            "manifests": {
                path: base64.b64encode(data).decode("ascii") for path, data in self.manifests
            },
        }


_BUNDLE_KEY = object()


def _bind_manifests(inventory: PayloadInventory, supplied: Mapping[str, bytes]) -> ManifestBundle:
    paths = bundle_manifest_paths(inventory)
    if len(paths) > MAX_MANIFEST_COUNT:
        raise Cfg1ManifestError("MANIFEST_COUNT_EXCEEDED")
    if set(supplied) != set(paths):
        raise Cfg1ManifestError("BUNDLE_KEY_SET_MISMATCH")
    total = 0
    bound = []
    for path in paths:
        data = supplied[path]
        if type(data) is not bytes:
            raise Cfg1ManifestError("BUNDLE_VALUE_MALFORMED", path)
        if len(data) > MAX_MANIFEST_BYTES:
            raise Cfg1ManifestError(MANIFEST_TOO_LARGE, path)
        total += len(data)
        if total > MAX_MANIFEST_TOTAL_BYTES:
            raise Cfg1ManifestError("MANIFEST_TOTAL_BYTES_EXCEEDED")
        entry = inventory.entry(path)
        if entry[3] != len(data) or entry[2] != hashlib.sha256(data).hexdigest():
            raise Cfg1ManifestError("BUNDLE_MANIFEST_NOT_BOUND", path)
        bound.append((path, data))
    return ManifestBundle(_BUNDLE_KEY, inventory.payload_fingerprint, tuple(bound))


def build_manifest_bundle(inventory: PayloadInventory, manifest_bytes: Mapping[str, bytes]) -> ManifestBundle:
    """Bind exactly the inventory's bundle manifests' bytes (size + SHA-256 each)."""
    if not isinstance(manifest_bytes, Mapping):
        raise Cfg1ManifestError("BUNDLE_VALUE_MALFORMED")
    for path in manifest_bytes:
        if type(path) is not str:
            raise Cfg1ManifestError("BUNDLE_KEY_SET_MISMATCH")
    return _bind_manifests(inventory, dict(manifest_bytes))


def bundle_from_record(record: object, inventory: PayloadInventory) -> ManifestBundle:
    """Strictly validate a bundle RECORD against its bound inventory (Sec. 6.1)."""
    if type(inventory) is not PayloadInventory:
        raise Cfg1ManifestError("MALFORMED_INVENTORY")
    if type(record) is not dict or tuple(sorted(record)) != _BUNDLE_RECORD_KEYS:
        raise Cfg1ManifestError("BUNDLE_RECORD_KEYS")
    if type(record["record_kind"]) is not str or record["record_kind"] != MANIFEST_BUNDLE_RECORD_KIND:
        raise Cfg1ManifestError("BUNDLE_RECORD_KIND")
    fingerprint = record["payload_fingerprint"]
    if not is_lowercase_hex64(fingerprint) or fingerprint != inventory.payload_fingerprint:
        raise Cfg1ManifestError("BUNDLE_FINGERPRINT_MISMATCH")
    manifests = record["manifests"]
    if type(manifests) is not dict:
        raise Cfg1ManifestError("BUNDLE_MANIFESTS_MALFORMED")
    if len(manifests) > MAX_MANIFEST_COUNT:
        raise Cfg1ManifestError("MANIFEST_COUNT_EXCEEDED")
    decoded: dict[str, bytes] = {}
    decoded_total = 0
    for path, text in manifests.items():
        if type(path) is not str or type(text) is not str:
            raise Cfg1ManifestError("BUNDLE_MANIFESTS_MALFORMED")
        if len(text) > _MAX_MANIFEST_BASE64_CHARS or not text.isascii():
            raise Cfg1ManifestError("BUNDLE_VALUE_MALFORMED")
        try:
            data = base64.b64decode(text, validate=True)
        except ValueError:
            raise Cfg1ManifestError("BUNDLE_VALUE_MALFORMED") from None
        if base64.b64encode(data).decode("ascii") != text:
            raise Cfg1ManifestError("BUNDLE_VALUE_NOT_CANONICAL_BASE64")
        decoded_total += len(data)
        if decoded_total > MAX_MANIFEST_TOTAL_BYTES:
            raise Cfg1ManifestError("MANIFEST_TOTAL_BYTES_EXCEEDED")
        decoded[path] = data
    return _bind_manifests(inventory, decoded)


# ---------------------------------------------------------------------------
# Sec. 6.4: package roots
# ---------------------------------------------------------------------------


def _manifest_path_of(root: str) -> str:
    return MANIFEST_NAME if root == "" else root + "/" + MANIFEST_NAME


def package_roots(inventory: PayloadInventory) -> tuple[str, ...]:
    """The payload root ``""`` plus every ``…/node_modules/<N>`` or
    ``…/node_modules/<@S>/<N>`` directory that has a ``package.json`` FILE
    child, in inventory order. A name outside the component grammar refuses
    (C5); a directory without its own ``package.json`` is not a root.
    """
    if type(inventory) is not PayloadInventory:
        raise Cfg1ManifestError("MALFORMED_INVENTORY")
    roots = [""]
    for entry in inventory.entries:
        if entry[0] != INVENTORY_KIND_DIR:
            continue
        path = entry[1]
        if not inventory.is_file(_manifest_path_of(path)):
            continue
        segments = path.split("/")
        if len(segments) >= 2 and segments[-2] == "node_modules":
            if not _component_ok(segments[-1]):
                raise Cfg1ManifestError(PACKAGE_ROOT_NAME_OUTSIDE_HPP1_GRAMMAR, _manifest_path_of(path))
            roots.append(path)
        elif (
            len(segments) >= 3
            and segments[-3] == "node_modules"
            and segments[-2].startswith("@")
        ):
            if not _component_ok(segments[-2][1:]) or not _component_ok(segments[-1]):
                raise Cfg1ManifestError(PACKAGE_ROOT_NAME_OUTSIDE_HPP1_GRAMMAR, _manifest_path_of(path))
            roots.append(path)
    return tuple(roots)


def package_root_manifest_path(root: str) -> str:
    """The manifest path of a package root (``""`` -> ``package.json``)."""
    return _manifest_path_of(root)


# ---------------------------------------------------------------------------
# Sec. 6.5: declared projection (provenance only -- decides nothing)
# ---------------------------------------------------------------------------


def _declared_version(manifest: dict, manifest_path: str) -> str:
    if "version" not in manifest:
        raise Cfg1ManifestError(DECLARED_VERSION_INVALID, manifest_path)
    version = manifest["version"]
    if type(version) is not str or not 1 <= len(version) <= MAX_DECLARED_VERSION_CHARS:
        raise Cfg1ManifestError(DECLARED_VERSION_INVALID, manifest_path)
    for character in version:
        if not 0x21 <= ord(character) <= 0x7E:
            raise Cfg1ManifestError(DECLARED_VERSION_INVALID, manifest_path)
    return version


def _require_package_name(manifest: dict, manifest_path: str, expected: str) -> None:
    name = manifest.get("name")
    if type(name) is not str or name != expected:
        raise Cfg1ManifestError(DECLARED_PACKAGE_NAME_MISMATCH, manifest_path)


def declared_projection(parsed_root_manifests: Mapping[str, dict]) -> dict[str, str]:
    """The four declared provenance values from the three ``PI-SC1`` manifests.

    The three exact name equalities are package-IDENTITY checks (a mismatch
    is C5); no version is compared with anything here or anywhere it flows.
    """
    for path in (ROOT_MANIFEST_PATH, PI_AI_MANIFEST_PATH, PI_AGENT_CORE_MANIFEST_PATH):
        if path not in parsed_root_manifests or type(parsed_root_manifests[path]) is not dict:
            raise Cfg1ManifestError(DECLARED_MANIFEST_MISSING, path)
    root = parsed_root_manifests[ROOT_MANIFEST_PATH]
    pi_ai = parsed_root_manifests[PI_AI_MANIFEST_PATH]
    pi_agent_core = parsed_root_manifests[PI_AGENT_CORE_MANIFEST_PATH]
    _require_package_name(root, ROOT_MANIFEST_PATH, ROOT_PACKAGE_NAME)
    _require_package_name(pi_ai, PI_AI_MANIFEST_PATH, PI_AI_PACKAGE_NAME)
    _require_package_name(pi_agent_core, PI_AGENT_CORE_MANIFEST_PATH, PI_AGENT_CORE_PACKAGE_NAME)
    return {
        "package_name": ROOT_PACKAGE_NAME,
        "package_version": _declared_version(root, ROOT_MANIFEST_PATH),
        "pi_ai_version": _declared_version(pi_ai, PI_AI_MANIFEST_PATH),
        "pi_agent_core_version": _declared_version(pi_agent_core, PI_AGENT_CORE_MANIFEST_PATH),
    }


# ---------------------------------------------------------------------------
# Sec. 6.6: containment and the exposure set (frozen R3 algorithm)
# ---------------------------------------------------------------------------


def _join_relative(prefix: str, components: tuple[str, ...]) -> str:
    """In-memory ``<prefix>/node_modules/<components>`` from PARSER OUTPUT only."""
    parts = ("node_modules",) + components
    return "/".join(parts) if prefix == "" else "/".join((prefix,) + parts)


def _proper_ancestors_for_containment(root: str) -> tuple[str, ...]:
    """Proper ancestors of a package root, nearest first, up to and including
    ``""``, skipping every ancestor whose last segment is ``node_modules``."""
    if root == "":
        return ()
    segments = root.split("/")
    found = []
    for length in range(len(segments) - 1, -1, -1):
        if length > 0 and segments[length - 1] == "node_modules":
            continue
        found.append("/".join(segments[:length]))
    return tuple(found)


def compute_resolution_exposures(
    inventory: PayloadInventory, dependency_maps: Mapping[str, DependencyMaps]
) -> tuple[str, ...]:
    """Sec. 6.6: every declared dependency NOT contained inside the payload.

    ``dependency_maps`` maps each package root (exactly the roots of
    :func:`package_roots`) to its validated :class:`DependencyMaps`.
    Containment is a pure function of the inventory and parser output: a
    candidate is contained iff it is an inventory ``dir`` with a ``package.json``
    FILE child. Executes nothing and observes nothing.
    """
    if type(inventory) is not PayloadInventory:
        raise Cfg1ManifestError("MALFORMED_INVENTORY")
    roots = package_roots(inventory)
    if set(dependency_maps) != set(roots):
        raise Cfg1ManifestError("DEPENDENCY_MAPS_ROOT_SET_MISMATCH")
    exposures: set[str] = set()
    for root in roots:
        validated = dependency_maps[root]
        if type(validated) is not DependencyMaps:
            raise Cfg1ManifestError(DEPENDENCY_MAP_NOT_OBJECT)
        ancestors = _proper_ancestors_for_containment(root)
        for _field, entries in validated.maps:
            for components, _value in entries:
                candidates = (_join_relative(root, components),) + tuple(
                    _join_relative(ancestor, components) for ancestor in ancestors
                )
                contained = False
                for candidate in candidates:
                    if inventory.is_dir(candidate) and inventory.is_file(_manifest_path_of(candidate)):
                        contained = True
                        break
                if not contained:
                    exposures.add(package_name_text(components))
    return tuple(sorted(exposures))


def validate_resolution_exposures(exposures: object) -> tuple[str, ...]:
    """A canonical exposure list: strictly ascending, unique, each round-tripping."""
    if type(exposures) not in (list, tuple):
        raise Cfg1ManifestError("EXPOSURES_MALFORMED")
    previous: str | None = None
    for text in exposures:
        if package_name_text(parse_package_name(text)) != text:
            raise Cfg1ManifestError(PACKAGE_NAME_OUTSIDE_HPP1_GRAMMAR)
        if previous is not None and not previous < text:
            raise Cfg1ManifestError("EXPOSURES_NOT_CANONICAL")
        previous = text
    return tuple(exposures)


# ---------------------------------------------------------------------------
# Sec. 4.7: profile identity
# ---------------------------------------------------------------------------


def compute_profile_id(payload_fingerprint: object, resolution_exposures: object) -> str:
    """``SHA-256(b"aido.pi-profile.v1\\x00" || canonical_json_bytes({...}))``.

    Version text is not an input; it contributes only through the manifest
    bytes already bound into ``payload_fingerprint``.
    """
    if not is_lowercase_hex64(payload_fingerprint):
        raise Cfg1ManifestError("PROFILE_FINGERPRINT_MALFORMED")
    exposures = validate_resolution_exposures(resolution_exposures)
    body = canonical_json_bytes(
        {
            "payload_contract": PAYLOAD_CONTRACT,
            "payload_fingerprint": payload_fingerprint,
            "resolution_exposures": list(exposures),
        }
    )
    return hashlib.sha256(PROFILE_ID_DOMAIN_TAG + body).hexdigest()


# ---------------------------------------------------------------------------
# Sec. 6.6: the exposure-absence observer (shared primitive; NOT wired into
# P2X, L14 or L21A by PE-2a)
# ---------------------------------------------------------------------------

EXPOSURES_PROVEN_ABSENT = "EXPOSURES_PROVEN_ABSENT"
EXPOSURE_PRESENT_OR_UNOBSERVABLE = "EXPOSURE_PRESENT_OR_UNOBSERVABLE"


class ExposureAbsenceResult:
    """One closed status plus, when not absent, the (validated) exposure text."""

    __slots__ = ("status", "exposure")

    def __init__(self, status: str, exposure: str | None) -> None:
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "exposure", exposure)

    def __setattr__(self, name: str, value: object) -> None:  # noqa: D105
        raise AttributeError("ExposureAbsenceResult is immutable")

    def __repr__(self) -> str:  # noqa: D105
        return f"{type(self).__name__}({self.status!r})"


def _lexical_ancestors_for_absence(payload_root: str) -> tuple[str, ...]:
    """Proper lexical ancestors of the payload root, nearest first, up to the
    volume root, skipping those whose last component is exactly ``node_modules``."""
    found = []
    current = payload_root
    while True:
        parent = ntpath.dirname(current)
        if parent == current or not parent:
            break
        if ntpath.basename(parent) != "node_modules":
            found.append(parent)
        current = parent
    return tuple(found)


def _absent_under(
    ancestor: str, components: tuple[str, ...], inspect: Callable[[str], NoFollowObservation]
) -> bool:
    """``ancestor\\node_modules\\<components>``, each component no-follow.

    Intermediate components must be a plain directory or missing (missing ends
    this ancestor's check as absent); the final entry must be missing.
    """
    parts = ("node_modules",) + components
    current = ancestor
    for position, part in enumerate(parts):
        current = ntpath.join(current, part)
        observation = inspect(current)
        if type(observation) is not NoFollowObservation:
            return False
        classification = observation.classification
        if type(classification) is not str or classification not in CLASSIFICATIONS:
            return False
        if classification == CLASSIFICATION_MISSING:
            return True
        if position == len(parts) - 1 or classification != CLASSIFICATION_DIRECTORY:
            return False
    return False


def observe_exposure_absence(
    payload_root: str,
    resolution_exposures: Sequence[str],
    *,
    inspect: Callable[[str], NoFollowObservation],
) -> ExposureAbsenceResult:
    """Sec. 6.6 exposure absence: every exposure absent from every ancestor.

    Each exposure is RE-PARSED first, so only parser output ever forms a path.
    A present final entry, any reparse point, any ``other`` classification or
    any observation failure is ``EXPOSURE_PRESENT_OR_UNOBSERVABLE``.
    """
    if type(payload_root) is not str or not payload_root:
        raise Cfg1ManifestError("MALFORMED_PAYLOAD_ROOT")
    drive, _rest = ntpath.splitdrive(payload_root)
    if not drive or not ntpath.isabs(payload_root):
        raise Cfg1ManifestError("MALFORMED_PAYLOAD_ROOT")
    if not callable(inspect):
        raise Cfg1ManifestError("MALFORMED_INSPECT_LEAF")
    exposures = validate_resolution_exposures(resolution_exposures)
    parsed = tuple((text, parse_package_name(text)) for text in exposures)
    ancestors = _lexical_ancestors_for_absence(payload_root)
    for text, components in parsed:
        for ancestor in ancestors:
            try:
                absent = _absent_under(ancestor, components, inspect)
            except Exception:  # noqa: BLE001 - an observation failure is "unobservable"
                absent = False
            if not absent:
                return ExposureAbsenceResult(EXPOSURE_PRESENT_OR_UNOBSERVABLE, text)
    return ExposureAbsenceResult(EXPOSURES_PROVEN_ABSENT, None)
