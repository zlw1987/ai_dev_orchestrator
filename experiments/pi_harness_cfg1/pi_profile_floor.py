"""Profile facts, approvability, the mechanical floor classifier and PMD deltas (PE-2a).

Implements ``docs/PHASE_5F3B_PI_HARNESS_PROFILE_EVOLUTION_PE1_AMENDMENT.md``
Sec. 4.6 (approvability), Sec. 8.2 (floor classes C5/C1/C1R/C2/C3), Sec. 8.3
(the C2 relation and its structure-preserving projection) and Sec. 10.2 (the
mechanical PMD delta list) as PURE FUNCTIONS over SUPPLIED data.

**Nothing here is authority.** These functions load no policy, read no APS,
approve nothing, transfer no conclusion and compare no version to decide
anything. A reference set is whatever the caller supplies; until PE-2b wires
the committed reference view, discovery does not call :func:`classify_floor`
at all and records its floor as ``NOT_COMPUTED``. C4 is never mechanical.

**C2 is values-only.** Key PRESENCE of the two internal dependencies is
checked first and a difference makes C2 false before any projection runs; the
projection then copies every key at every position and replaces only the
permitted VALUE slots with a module-private marker that no parsed JSON value
can equal. Nothing is deleted, popped, filtered or re-keyed.
"""

from __future__ import annotations

from collections.abc import Iterable

from .pi_manifest import (
    DECLARED_MANIFEST_MISSING,
    PI_AGENT_CORE_MANIFEST_PATH,
    PI_AGENT_CORE_PACKAGE_NAME,
    PI_AI_MANIFEST_PATH,
    PI_AI_PACKAGE_NAME,
    ROOT_MANIFEST_PATH,
    Cfg1ManifestError,
    DependencyMaps,
    ManifestBundle,
    bundle_manifest_paths,
    compute_profile_id,
    compute_resolution_exposures,
    declared_projection,
    package_root_manifest_path,
    package_roots,
    parse_manifest_strict,
    validate_dependency_maps,
)
from .pi_payload import (
    INVENTORY_KIND_FILE,
    LAUNCH_TARGET_PATH,
    PayloadInventory,
    canonical_json_bytes,
    compute_seam_fingerprint,
    is_lowercase_hex64,
    project_seam_digests,
)

# ---------------------------------------------------------------------------
# Frozen literals and bounds
# ---------------------------------------------------------------------------

#: PE-1 Sec. 4.4: committed-file bounds a candidate must fit (Sec. 4.6 item 6).
MAX_INVENTORY_FILE_BYTES = 100663296
MAX_MANIFEST_BUNDLE_FILE_BYTES = 100663296

FLOOR_C5 = "C5"
FLOOR_C1 = "C1"
FLOOR_C1R = "C1R"
FLOOR_C2 = "C2"
FLOOR_C3_SEAM_EQUAL = "C3_SEAM_EQUAL"
FLOOR_C3_SEAM_CHANGED = "C3_SEAM_CHANGED"
FLOOR_NOT_COMPUTED = "NOT_COMPUTED"

FLOOR_CLASSES: frozenset[str] = frozenset(
    {FLOOR_C5, FLOOR_C1, FLOOR_C1R, FLOOR_C2, FLOOR_C3_SEAM_EQUAL, FLOOR_C3_SEAM_CHANGED}
)

PERMITTED_MANIFESTS: frozenset[str] = frozenset(
    {ROOT_MANIFEST_PATH, PI_AI_MANIFEST_PATH, PI_AGENT_CORE_MANIFEST_PATH}
)

#: The two internal names whose ``dependencies`` VALUE may differ under C2.
INTERNAL_DEPENDENCY_NAMES: tuple[str, str] = (PI_AI_PACKAGE_NAME, PI_AGENT_CORE_PACKAGE_NAME)

DELTA_RAW_BYTES = "RAW_BYTES"
DELTA_VERSION = "VERSION"
DELTA_INTERNAL_DEPENDENCY_PI_AI = "INTERNAL_DEPENDENCY:" + PI_AI_PACKAGE_NAME
DELTA_INTERNAL_DEPENDENCY_PI_AGENT_CORE = "INTERNAL_DEPENDENCY:" + PI_AGENT_CORE_PACKAGE_NAME

#: Sec. 4.6 approvability failures (C5 reasons) that are not manifest codes.
C5_LAUNCH_TARGET_NOT_A_FILE = "LAUNCH_TARGET_NOT_A_FILE"
C5_PI_SC1_PATH_NOT_A_FILE = "PI_SC1_PATH_NOT_A_FILE"
C5_INVENTORY_FILE_BOUND_EXCEEDED = "INVENTORY_FILE_BOUND_EXCEEDED"
C5_MANIFEST_BUNDLE_FILE_BOUND_EXCEEDED = "MANIFEST_BUNDLE_FILE_BOUND_EXCEEDED"


class Cfg1FloorError(Exception):
    """A malformed input to a floor primitive. Closed reason code only."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(f"cfg1 pi profile floor refused: {reason_code}")
        self.reason_code = reason_code


def policy_file_bytes(record: object) -> bytes:
    """PE-1 Sec. 7.2 file bytes: ``canonical_json_bytes(record) + b"\\n"``."""
    return canonical_json_bytes(record) + b"\n"


# ---------------------------------------------------------------------------
# Profile facts and approvability (Sec. 4.6, 4.7, 5.2, 6.4-6.6)
# ---------------------------------------------------------------------------


class ProfileFacts:
    """Every mechanically derivable fact of ONE inventory + bound bundle.

    ``c5_reason is None`` means every Sec. 4.6 approvability item holds; it
    NEVER means approved, eligible or live-eligible. Facts that could not be
    derived are ``None``. Constructible only by :func:`compute_profile_facts`.
    """

    __slots__ = (
        "inventory",
        "bundle",
        "payload_fingerprint",
        "c5_reason",
        "c5_manifest_path",
        "profile_id",
        "seam_digests",
        "seam_fingerprint",
        "declared",
        "resolution_exposures",
        "_parsed_root_manifests",
    )

    def __init__(self, key: object, **values: object) -> None:
        if key is not _FACTS_KEY:
            raise Cfg1FloorError("FACTS_NOT_COMPUTED_BY_PRIMITIVE")
        for name in self.__slots__:
            object.__setattr__(self, name, values[name])

    def __setattr__(self, name: str, value: object) -> None:  # noqa: D105
        raise AttributeError("ProfileFacts is immutable")

    def __repr__(self) -> str:  # noqa: D105
        return f"{type(self).__name__}(c5_reason={self.c5_reason!r})"

    @property
    def approvability_floor_met(self) -> bool:
        return self.c5_reason is None

    def parsed_root_manifest(self, path: str) -> dict | None:
        return self._parsed_root_manifests.get(path)

    def seam_digests_dict(self) -> dict[str, str] | None:
        return None if self.seam_digests is None else dict(self.seam_digests)

    def declared_dict(self) -> dict[str, str] | None:
        return None if self.declared is None else dict(self.declared)


_FACTS_KEY = object()


def compute_profile_facts(inventory: PayloadInventory, bundle: ManifestBundle) -> ProfileFacts:
    """Derive every fact a candidate profile carries, from bound data only.

    Approvability is evaluated in Sec. 4.6 order and the FIRST failing item
    is the C5 reason. Independent facts are still derived where possible
    (diagnostics only). Every dependency key passes the schema and the
    package-name parser before any in-memory candidate path is formed.
    """
    if type(inventory) is not PayloadInventory:
        raise Cfg1FloorError("MALFORMED_INVENTORY")
    if type(bundle) is not ManifestBundle:
        raise Cfg1FloorError("MALFORMED_BUNDLE")
    if bundle.payload_fingerprint != inventory.payload_fingerprint or tuple(
        path for path, _data in bundle.manifests
    ) != bundle_manifest_paths(inventory):
        raise Cfg1FloorError("BUNDLE_NOT_BOUND_TO_INVENTORY")

    seam_digests = project_seam_digests(inventory)
    seam_fingerprint = None if seam_digests is None else compute_seam_fingerprint(seam_digests)

    manifest_failure: tuple[str, str | None] | None = None
    parsed: dict[str, dict] = {}
    maps: dict[str, DependencyMaps] = {}
    try:
        roots = package_roots(inventory)
        for root in roots:
            path = package_root_manifest_path(root)
            data = bundle.manifest_bytes(path)
            if data is None:
                raise Cfg1ManifestError(DECLARED_MANIFEST_MISSING, path)
            try:
                document = parse_manifest_strict(data)
            except Cfg1ManifestError as refusal:
                raise Cfg1ManifestError(refusal.reason_code, path) from None
            maps[root] = validate_dependency_maps(document, path)
            parsed[path] = document
    except Cfg1ManifestError as refusal:
        manifest_failure = (refusal.reason_code, refusal.manifest_path)
        parsed = {}
        maps = {}

    exposures = None
    profile_id = None
    declared = None
    declared_failure: tuple[str, str | None] | None = None
    if manifest_failure is None:
        exposures = compute_resolution_exposures(inventory, maps)
        profile_id = compute_profile_id(inventory.payload_fingerprint, exposures)
        try:
            declared = declared_projection(parsed)
        except Cfg1ManifestError as refusal:
            declared_failure = (refusal.reason_code, refusal.manifest_path)

    c5_reason: str | None = None
    c5_manifest_path: str | None = None
    if not inventory.is_file(LAUNCH_TARGET_PATH):
        c5_reason = C5_LAUNCH_TARGET_NOT_A_FILE
    elif seam_digests is None:
        c5_reason = C5_PI_SC1_PATH_NOT_A_FILE
    elif manifest_failure is not None:
        c5_reason, c5_manifest_path = manifest_failure
    elif declared_failure is not None:
        c5_reason, c5_manifest_path = declared_failure
    elif len(inventory.canonical_bytes) + 1 > MAX_INVENTORY_FILE_BYTES:
        c5_reason = C5_INVENTORY_FILE_BOUND_EXCEEDED
    elif len(policy_file_bytes(bundle.to_record())) > MAX_MANIFEST_BUNDLE_FILE_BYTES:
        c5_reason = C5_MANIFEST_BUNDLE_FILE_BOUND_EXCEEDED

    return ProfileFacts(
        _FACTS_KEY,
        inventory=inventory,
        bundle=bundle,
        payload_fingerprint=inventory.payload_fingerprint,
        c5_reason=c5_reason,
        c5_manifest_path=c5_manifest_path,
        profile_id=profile_id,
        seam_digests=None if seam_digests is None else tuple(seam_digests.items()),
        seam_fingerprint=seam_fingerprint,
        declared=None if declared is None else tuple(declared.items()),
        resolution_exposures=exposures,
        _parsed_root_manifests=parsed,
    )


# ---------------------------------------------------------------------------
# The C2 relation (Sec. 8.3, B9)
# ---------------------------------------------------------------------------


class _Marker:
    """The module-private value-slot marker. Outside the JSON value domain:
    it equals only itself, by identity, and no parsed value is ever one."""

    __slots__ = ()

    def __eq__(self, other: object) -> bool:  # noqa: D105
        return self is other

    def __hash__(self) -> int:  # noqa: D105
        return id(self)

    def __repr__(self) -> str:  # noqa: D105
        return "<permitted value slot>"


_MARKER = _Marker()


def project_permitted_value_slots(document: dict, internal_present_on_both: tuple[str, ...]) -> dict:
    """Copy ``document`` keeping EVERY key at EVERY position; replace ONLY the
    top-level ``version`` value and ``dependencies[I]`` for each ``I`` in
    ``internal_present_on_both`` with the private marker.

    Never deletes, pops, filters or re-keys anything, and never builds a key
    set: a key added, removed or moved therefore survives into the projection
    and makes the comparison fail.
    """
    if type(document) is not dict:
        raise Cfg1FloorError("PROJECTION_INPUT_NOT_OBJECT")
    projected: dict = {}
    for key, value in document.items():
        if key == "version":
            projected[key] = _MARKER
        elif key == "dependencies" and type(value) is dict:
            slots: dict = {}
            for name, specifier in value.items():
                slots[name] = _MARKER if name in internal_present_on_both else specifier
            projected[key] = slots
        else:
            projected[key] = value
    return projected


def _ordered_equal(left: object, right: object) -> bool:
    """Complete ordered key/value equality at every level, with exact types."""
    if left is _MARKER or right is _MARKER:
        return left is right
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        left_items = list(left.items())
        right_items = list(right.items())
        if len(left_items) != len(right_items):
            return False
        for (left_key, left_value), (right_key, right_value) in zip(left_items, right_items):
            if type(left_key) is not str or type(right_key) is not str or left_key != right_key:
                return False
            if not _ordered_equal(left_value, right_value):
                return False
        return True
    if type(left) is list:
        if len(left) != len(right):
            return False
        return all(_ordered_equal(a, b) for a, b in zip(left, right))
    if left is None or type(left) in (str, int, float, bool):
        return left == right
    raise Cfg1FloorError("UNEXPECTED_VALUE_TYPE")


def _dependencies_of(document: dict) -> dict:
    """The ``dependencies`` map; a missing field means "no keys" (Sec. 8.3)."""
    if "dependencies" not in document:
        return {}
    value = document["dependencies"]
    if type(value) is not dict:
        raise Cfg1FloorError("DEPENDENCIES_NOT_OBJECT")
    return value


def _require_approvable(facts: object) -> ProfileFacts:
    if type(facts) is not ProfileFacts:
        raise Cfg1FloorError("MALFORMED_FACTS")
    if facts.c5_reason is not None or not is_lowercase_hex64(facts.profile_id):
        raise Cfg1FloorError("FACTS_NOT_APPROVABLE")
    return facts


def _differing_files(candidate: ProfileFacts, reference: ProfileFacts) -> list[str] | None:
    """``None`` if the ``(path, kind)`` trees differ; else ``D`` in inventory order."""
    candidate_tree = [(entry[1], entry[0]) for entry in candidate.inventory.entries]
    reference_tree = [(entry[1], entry[0]) for entry in reference.inventory.entries]
    if candidate_tree != reference_tree:
        return None
    differing = []
    for entry in candidate.inventory.entries:
        if entry[0] != INVENTORY_KIND_FILE:
            continue
        other = reference.inventory.entry(entry[1])
        if (entry[3], entry[2]) != (other[3], other[2]):
            differing.append(entry[1])
    return differing


def _presence_on_both(candidate_doc: dict, reference_doc: dict) -> tuple[str, ...] | None:
    """``None`` if any internal key's PRESENCE differs; else the names on both."""
    candidate_deps = _dependencies_of(candidate_doc)
    reference_deps = _dependencies_of(reference_doc)
    on_both = []
    for name in INTERNAL_DEPENDENCY_NAMES:
        in_candidate = name in candidate_deps
        if in_candidate != (name in reference_deps):
            return None
        if in_candidate:
            on_both.append(name)
    return tuple(on_both)


def c2_relation(candidate: ProfileFacts, reference: ProfileFacts) -> bool:
    """``C2(X, R)`` exactly as Sec. 8.3 (B9) freezes it."""
    candidate = _require_approvable(candidate)
    reference = _require_approvable(reference)
    differing = _differing_files(candidate, reference)
    if differing is None or not differing:
        return False
    for path in differing:
        if path not in PERMITTED_MANIFESTS:
            return False
    for path in differing:
        candidate_doc = candidate.parsed_root_manifest(path)
        reference_doc = reference.parsed_root_manifest(path)
        if type(candidate_doc) is not dict or type(reference_doc) is not dict:
            raise Cfg1FloorError("PERMITTED_MANIFEST_NOT_PARSED")
        on_both = _presence_on_both(candidate_doc, reference_doc)
        if on_both is None:
            return False  # presence differs: no projection is attempted
        if not _ordered_equal(
            project_permitted_value_slots(candidate_doc, on_both),
            project_permitted_value_slots(reference_doc, on_both),
        ):
            return False
    return candidate.resolution_exposures == reference.resolution_exposures


# ---------------------------------------------------------------------------
# Floor classification (Sec. 8.1, 8.2) over a SUPPLIED reference view
# ---------------------------------------------------------------------------


class ReferenceView:
    """A caller-supplied reference set for :func:`classify_floor`. Not policy.

    ``eligible``: facts of profiles the caller states are eligible;
    ``present_ineligible_profile_ids``: profile ids present but not eligible
    (retired); ``seam_fingerprints``: seam-evidence fingerprints. PE-2a never
    constructs one from committed data -- that is PE-2b's reference view.
    """

    __slots__ = ("eligible", "present_ineligible_profile_ids", "seam_fingerprints")

    def __init__(
        self,
        *,
        eligible: Iterable[ProfileFacts],
        present_ineligible_profile_ids: Iterable[str],
        seam_fingerprints: Iterable[str],
    ) -> None:
        eligible_tuple = tuple(_require_approvable(facts) for facts in eligible)
        ineligible = frozenset(present_ineligible_profile_ids)
        seams = frozenset(seam_fingerprints)
        for value in ineligible | seams:
            if not is_lowercase_hex64(value):
                raise Cfg1FloorError("REFERENCE_ID_MALFORMED")
        if ineligible & {facts.profile_id for facts in eligible_tuple}:
            raise Cfg1FloorError("REFERENCE_PROFILE_BOTH_ELIGIBLE_AND_INELIGIBLE")
        object.__setattr__(self, "eligible", eligible_tuple)
        object.__setattr__(self, "present_ineligible_profile_ids", ineligible)
        object.__setattr__(self, "seam_fingerprints", seams)

    def __setattr__(self, name: str, value: object) -> None:  # noqa: D105
        raise AttributeError("ReferenceView is immutable")


def classify_floor(candidate: ProfileFacts, reference: ReferenceView) -> str:
    """Sec. 8.2, first match wins: C5, C1, C1R, C2, C3_SEAM_EQUAL, C3_SEAM_CHANGED."""
    if type(candidate) is not ProfileFacts:
        raise Cfg1FloorError("MALFORMED_FACTS")
    if type(reference) is not ReferenceView:
        raise Cfg1FloorError("MALFORMED_REFERENCE_VIEW")
    if candidate.c5_reason is not None:
        return FLOOR_C5
    _require_approvable(candidate)
    eligible_ids = frozenset(facts.profile_id for facts in reference.eligible)
    if candidate.profile_id in eligible_ids:
        return FLOOR_C1
    if candidate.profile_id in reference.present_ineligible_profile_ids:
        return FLOOR_C1R
    for facts in reference.eligible:
        if c2_relation(candidate, facts):
            return FLOOR_C2
    seams = reference.seam_fingerprints | frozenset(
        facts.seam_fingerprint for facts in reference.eligible
    )
    if candidate.seam_fingerprint in seams:
        return FLOOR_C3_SEAM_EQUAL
    return FLOOR_C3_SEAM_CHANGED


# ---------------------------------------------------------------------------
# The mechanical PMD delta list (Sec. 10.2)
# ---------------------------------------------------------------------------


def _version_value(document: dict) -> str:
    value = document.get("version")
    if type(value) is not str:
        raise Cfg1FloorError("PERMITTED_MANIFEST_VERSION_NOT_STR")
    return value


def compute_pmd_deltas(candidate: ProfileFacts, reference: ProfileFacts) -> tuple[dict, ...]:
    """The complete ordered ``(delta, manifest_path, old, new)`` list for a C2 pair.

    For each differing manifest, in inventory order: ``RAW_BYTES`` always;
    ``VERSION`` iff the top-level version values differ;
    ``INTERNAL_DEPENDENCY:<name>`` iff that key is present in ``dependencies``
    on BOTH sides and the exact-``str`` values differ. ``old`` is the
    reference's, ``new`` the candidate's. This is a mechanical enumeration,
    never a review finding.
    """
    if not c2_relation(candidate, reference):
        raise Cfg1FloorError("PMD_REQUIRES_C2")
    differing = _differing_files(candidate, reference)
    deltas: list[dict] = []
    for path in differing:
        candidate_doc = candidate.parsed_root_manifest(path)
        reference_doc = reference.parsed_root_manifest(path)
        deltas.append(
            {
                "delta": DELTA_RAW_BYTES,
                "manifest_path": path,
                "old": reference.inventory.entry(path)[2],
                "new": candidate.inventory.entry(path)[2],
            }
        )
        old_version = _version_value(reference_doc)
        new_version = _version_value(candidate_doc)
        if old_version != new_version:
            deltas.append(
                {"delta": DELTA_VERSION, "manifest_path": path, "old": old_version, "new": new_version}
            )
        candidate_deps = _dependencies_of(candidate_doc)
        reference_deps = _dependencies_of(reference_doc)
        for name, label in (
            (PI_AI_PACKAGE_NAME, DELTA_INTERNAL_DEPENDENCY_PI_AI),
            (PI_AGENT_CORE_PACKAGE_NAME, DELTA_INTERNAL_DEPENDENCY_PI_AGENT_CORE),
        ):
            if name in candidate_deps and name in reference_deps:
                old_value = reference_deps[name]
                new_value = candidate_deps[name]
                if type(old_value) is not str or type(new_value) is not str:
                    raise Cfg1FloorError("INTERNAL_DEPENDENCY_VALUE_NOT_STR")
                if old_value != new_value:
                    deltas.append(
                        {"delta": label, "manifest_path": path, "old": old_value, "new": new_value}
                    )
    return tuple(deltas)
