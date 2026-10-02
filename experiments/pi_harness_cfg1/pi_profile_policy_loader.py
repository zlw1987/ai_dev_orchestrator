"""HPP-1 policy authority: the committed policy chain and its sealed snapshot (PE-2b).

Implements ``docs/PHASE_5F3B_PI_HARNESS_PROFILE_EVOLUTION_PE1_AMENDMENT.md``
Sec. 7.2-7.3 (canonical policy bytes and the strict policy parser), Sec. 9.1-9.7
(the loader-owned policy directory, the closed record schemas, recomputation,
the append-only APS chain, eligibility and the head), Sec. 10.4 (PMD structural
validation) and Sec. 11.4 (the sealed policy snapshot).

**Authority originates only from canonical committed policy bytes.** The ONE
genuine load happens at import, from ``<this module's directory>\\pi_profile_policy``
-- derived from this module's own ``__file__``, never from an argument, the
environment, the current directory, a record field or Pi content. Every policy
file is read no-follow through one handle (the shared ``pi_fs_leaves``
readers), parsed strictly, and must re-encode byte-for-byte. Every derivable
field -- fingerprints, profile ids, exposures, declared projection, seam
digests and fingerprints, every evidence/approval/retirement id, every floor
and every PMD delta -- is RECOMPUTED here from committed bytes with the
ACCEPTED PE-2a primitives (by identity, never a copy); presence of a field is
never proof of its truth. Any disagreement refuses the WHOLE chain, and a
refused genuine chain makes this module fail to import. There is no partial
policy, no default snapshot and no fallback.

**Eligibility is computed, never stored**: ``approved(profile, CFG1-CC1, HPP-1)
and not retired(profile, CFG1-CC1)``, as an exact-``str`` ``frozenset``.

**The sealed snapshot carries only policy**, as immutable scalars, tuples and
frozensets. No mutable record, parsed manifest, inventory index or PE-2a
facts object survives the load as authority. It is not an observation of any
installed Pi, and nothing here wires it into P, the gate, L1, L14 or L21A.

**PMD validation is structural only.** The loader proves every actual delta is
listed and every category and reused item is addressed consistently. It never
proves that a finding such as ``NOT_READ`` or ``NOT_AFFECTED`` is TRUE: that
remains independent review (PE-1 Sec. 10.5).

**Evidence references are syntax-checked only.** No reference is ever opened
here; the offline evidence-reference verifier is separate review tooling and
is never imported by this module.

**What this module never does.** It reads no environment variable, opens no
network connection, starts no process, writes no file, executes no Pi, Node or
npm, and opens no path taken from a record: every file name is formed from a
validated revision integer or a validated 64-hex payload fingerprint.
"""

from __future__ import annotations

import hashlib
import json
import ntpath
import re
from pathlib import Path

from . import pi_fs_leaves
from .pi_fs_leaves import (
    CLASSIFICATION_DIRECTORY,
    CLASSIFICATION_REGULAR_FILE,
    ENTRY_KIND_DIRECTORY,
    ENTRY_KIND_FILE,
    ENTRY_KINDS,
    DirectoryListing,
    PayloadFileRead,
)
from .pi_manifest import (
    Cfg1ManifestError,
    bundle_from_record,
    parse_package_name,
    validate_resolution_exposures,
)
from .pi_payload import (
    MAX_CANONICAL_INT,
    PAYLOAD_CONTRACT,
    PI_SC1_PATHS,
    SEAM_CONTRACT,
    Cfg1PayloadError,
    compute_seam_fingerprint,
    inventory_from_record,
    is_lowercase_hex64,
)
from .pi_profile_floor import (
    DELTA_INTERNAL_DEPENDENCY_PI_AGENT_CORE,
    DELTA_INTERNAL_DEPENDENCY_PI_AI,
    DELTA_RAW_BYTES,
    DELTA_VERSION,
    FLOOR_C2,
    FLOOR_C3_SEAM_CHANGED,
    FLOOR_C3_SEAM_EQUAL,
    MAX_INVENTORY_FILE_BYTES,
    MAX_MANIFEST_BUNDLE_FILE_BYTES,
    Cfg1FloorError,
    ProfileFacts,
    ReferenceView,
    c2_relation,
    classify_floor,
    compute_pmd_deltas,
    compute_profile_facts,
    policy_file_bytes,
)

# ---------------------------------------------------------------------------
# Frozen literals (PE-1 Sec. 3)
# ---------------------------------------------------------------------------

POLICY_REVISION = "HPP-1"
CONSUMER_CONTRACT = "CFG1-CC1"

SEAM_EVIDENCE_RECORD_KIND = "aido-pi-seam-evidence.v1"
PROFILE_RECORD_KIND = "aido-pi-profile.v1"
APPROVAL_RECORD_KIND = "aido-pi-profile-approval.v1"
RETIREMENT_RECORD_KIND = "aido-pi-profile-retirement.v1"
APS_RECORD_KIND = "aido-pi-approved-profile-set.v1"

POLICY_DIRECTORY_NAME = "pi_profile_policy"
APS_DIRECTORY_NAME = "aps"
INVENTORIES_DIRECTORY_NAME = "inventories"
MANIFEST_BUNDLES_DIRECTORY_NAME = "manifest_bundles"
POLICY_FILE_SUFFIX = ".json"

#: Approval classes in conservativeness order, least -> most (Sec. 8.4).
QUALIFICATION_CLASSES: tuple[str, ...] = (
    "C2_MANIFEST_ONLY",
    "C2_MANIFEST_DELTA_REACQUIRED",
    "C3_SEAM_EQUAL",
    "C3_SEAM_CHANGED",
    "C4_CONTRACT_REVISED",
    "CC_REAPPROVAL",
)
#: Admissible under ``CFG1-CC1`` (Sec. 9.5). The last two are reserved names
#: for a future consumer contract and are refused here.
CC1_ADMISSIBLE_CLASSES: frozenset[str] = frozenset(QUALIFICATION_CLASSES[:4])
_CLASS_RANK: dict[str, int] = {name: rank for rank, name in enumerate(QUALIFICATION_CLASSES)}

#: Mechanical floor -> least admissible approval class (Sec. 8.4). C5, C1 and
#: C1R are absent on purpose: they are never approvable.
LEAST_ADMISSIBLE_CLASS: dict[str, str] = {
    FLOOR_C2: "C2_MANIFEST_ONLY",
    FLOOR_C3_SEAM_EQUAL: "C3_SEAM_EQUAL",
    FLOOR_C3_SEAM_CHANGED: "C3_SEAM_CHANGED",
}

REUSABLE_EVIDENCE_KINDS: frozenset[str] = frozenset({"E1", "E3", "E4", "E5", "E6"})
PREMISE_SEAM_FILES = "SEAM_FILES"
PREMISE_PAYLOAD_EXCEPT_PERMITTED_MANIFEST_FIELDS = "PAYLOAD_EXCEPT_PERMITTED_MANIFEST_FIELDS"
#: PE-0 Sec. 8.5: which kinds each premise scope may carry.
_PREMISE_KINDS: dict[str, frozenset[str]] = {
    PREMISE_SEAM_FILES: frozenset({"E1"}),
    PREMISE_PAYLOAD_EXCEPT_PERMITTED_MANIFEST_FIELDS: frozenset({"E3", "E4", "E5", "E6"}),
}

RETIREMENT_REASON_CODES: frozenset[str] = frozenset(
    {"SECURITY_ADVISORY", "DERIVATION_INVALIDATED", "OPERATOR_WITHDRAWN", "SUPERSEDED_BY_POLICY"}
)

PMD_DELTA_LABELS: frozenset[str] = frozenset(
    {DELTA_RAW_BYTES, DELTA_VERSION, DELTA_INTERNAL_DEPENDENCY_PI_AI, DELTA_INTERNAL_DEPENDENCY_PI_AGENT_CORE}
)
PMD_CATEGORIES: frozenset[str] = frozenset(
    {
        "PROMPT_OR_MODEL_VISIBLE_CONTENT",
        "RPC_BEHAVIOR",
        "REQUEST_SHAPE",
        "PROVIDER_OR_MODEL_SELECTION",
        "FEATURE_GATES",
        "CONFIG_MIGRATION",
        "TOOL_REGISTRATION_OR_DISPATCH",
        "EXTENSION_BEHAVIOR",
        "FILESYSTEM_BEHAVIOR",
        "NETWORK_BEHAVIOR",
        "TELEMETRY_USER_AGENT_OR_HEADERS",
    }
)
_PARSED_FIELD_FINDINGS = frozenset({"NOT_APPLICABLE", "NOT_READ", "READ"})
_RAW_MANIFEST_FINDINGS = frozenset({"NOT_READ", "READ"})
_CATEGORY_FINDINGS = frozenset({"NOT_REACHED", "REACHED_NO_EFFECT", "AFFECTS"})
_EFFECTS = frozenset({"NOT_AFFECTED", "AFFECTED"})

# ---------------------------------------------------------------------------
# Frozen policy resource refusal bounds (PE-1 Sec. 4.4). Exceeding one
# REFUSES the whole chain; nothing is ever truncated. Read at call time.
# ---------------------------------------------------------------------------

MAX_APS_REVISION_FILE_BYTES = 16777216
MAX_APS_REVISIONS = 9999
MAX_PROFILES = 256
MAX_POLICY_TOTAL_BYTES = 1073741824
MAX_POLICY_JSON_DEPTH = 24
MAX_POLICY_INT = MAX_CANONICAL_INT
MAX_EVIDENCE_REFS = 256
MAX_FINDING_REFS = 64
MAX_REPO_PATH_CHARS = 512
MAX_ACCEPTANCE_REFERENCE_CHARS = 1024
_MAX_POLICY_INT_TOKEN_CHARS = len(str(MAX_CANONICAL_INT))
#: Enumeration budget headroom over each directory's legitimate maximum, so a
#: stray entry is reported AS a stray. Still a finite resource bound.
_ENUMERATION_SLACK = 64

_APS_FILENAME = re.compile(r"aps\.r([0-9]{4})\.json")
_REPO_PATH_SEGMENT = re.compile(r"[A-Za-z0-9._-]+")
_AIDO_COMMIT = re.compile(r"[0-9a-f]{40}")
_DISCOVERY_TOOL_REVISION = re.compile(r"[A-Za-z0-9._-]{1,64}")


class Cfg1PolicyError(Exception):
    """The committed policy chain is refused. Closed reason code only.

    Never carries a path, a record value, manifest text or a dependency key.
    """

    def __init__(self, reason_code: str) -> None:
        super().__init__(f"cfg1 pi profile policy refused: {reason_code}")
        self.reason_code = reason_code


# ---------------------------------------------------------------------------
# The strict policy parser (PE-1 Sec. 7.2, 7.3)
# ---------------------------------------------------------------------------


def _policy_object(pairs: list) -> dict:
    """Duplicate keys refuse at ANY depth."""
    result: dict = {}
    for name, value in pairs:
        if name in result:
            raise Cfg1PolicyError("POLICY_DUPLICATE_KEY")
        result[name] = value
    return result


def _refuse_constant(_token: str):
    raise Cfg1PolicyError("POLICY_NON_FINITE_NUMBER")


def _refuse_float(_token: str):
    raise Cfg1PolicyError("POLICY_FLOAT")


def _policy_int(token: str) -> int:
    if len(token) > _MAX_POLICY_INT_TOKEN_CHARS:
        raise Cfg1PolicyError("POLICY_INT_OUT_OF_RANGE")
    value = int(token)
    if not 0 <= value <= MAX_POLICY_INT:
        raise Cfg1PolicyError("POLICY_INT_OUT_OF_RANGE")
    return value


def _policy_depth(value: object) -> int:
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


def _parse_policy_bytes(data: object) -> dict:
    """One policy file's bytes -> one exact-typed record, or refuse.

    Every byte < 0x80; no CR anywhere; exactly one trailing LF; duplicate
    keys, floats, ``NaN``/``Infinity`` and out-of-range integers refuse;
    nesting <= 24; top level an object; and ``canonical_json_bytes(record) +
    b"\\n"`` must equal the input EXACTLY (one admissible encoding). Nothing is
    normalized or repaired.
    """
    if type(data) is not bytes:
        raise Cfg1PolicyError("POLICY_FILE_MALFORMED")
    if not data.isascii():
        raise Cfg1PolicyError("POLICY_FILE_NOT_ASCII")
    if b"\r" in data:
        raise Cfg1PolicyError("POLICY_FILE_CONTAINS_CR")
    if not data.endswith(b"\n") or b"\n" in data[:-1]:
        raise Cfg1PolicyError("POLICY_FILE_LINE_ENDING")
    try:
        value = json.loads(
            data[:-1].decode("ascii"),
            object_pairs_hook=_policy_object,
            parse_constant=_refuse_constant,
            parse_float=_refuse_float,
            parse_int=_policy_int,
            strict=True,
        )
    except Cfg1PolicyError as refusal:
        raise Cfg1PolicyError(refusal.reason_code) from None
    except RecursionError:
        raise Cfg1PolicyError("POLICY_DEPTH_EXCEEDED") from None
    except ValueError:
        raise Cfg1PolicyError("POLICY_JSON_INVALID") from None
    if _policy_depth(value) > MAX_POLICY_JSON_DEPTH:
        raise Cfg1PolicyError("POLICY_DEPTH_EXCEEDED")
    if type(value) is not dict:
        raise Cfg1PolicyError("POLICY_TOP_LEVEL_NOT_OBJECT")
    try:
        canonical = policy_file_bytes(value)
    except Cfg1PayloadError:
        raise Cfg1PolicyError("POLICY_NOT_CANONICAL") from None
    if canonical != data:
        raise Cfg1PolicyError("POLICY_NOT_CANONICAL")
    return value


def _record_id(record: dict, id_field: str) -> str:
    """``SHA-256(canonical_json_bytes(record without id_field))``."""
    body = {name: value for name, value in record.items() if name != id_field}
    return hashlib.sha256(policy_file_bytes(body)[:-1]).hexdigest()


# ---------------------------------------------------------------------------
# Closed record schemas (PE-1 Sec. 9.3). Exact types; no truthiness.
# ---------------------------------------------------------------------------


def _require_keys(record: object, keys: frozenset[str], code: str) -> dict:
    if type(record) is not dict or frozenset(record) != keys:
        raise Cfg1PolicyError(code)
    return record


def _require_literal(value: object, literal: str, code: str) -> None:
    if type(value) is not str or value != literal:
        raise Cfg1PolicyError(code)


def _require_member(value: object, members: frozenset[str], code: str) -> str:
    if type(value) is not str or value not in members:
        raise Cfg1PolicyError(code)
    return value


def _require_hex64(value: object, code: str) -> str:
    if not is_lowercase_hex64(value):
        raise Cfg1PolicyError(code)
    return value


def repo_path_is_valid(value: object) -> bool:
    """PE-1 Sec. 9.9 ``repo_path`` grammar: SYNTAX ONLY, never opened here."""
    if type(value) is not str or not 1 <= len(value) <= MAX_REPO_PATH_CHARS:
        return False
    for segment in value.split("/"):
        if segment in (".", "..") or _REPO_PATH_SEGMENT.fullmatch(segment) is None:
            return False
    return True


_REF_KEYS = frozenset({"repo_path", "sha256"})


def _validate_refs(value: object, *, max_count: int, non_empty: bool) -> list:
    """A list of ``{"repo_path", "sha256"}`` evidence references (syntax only)."""
    if type(value) is not list or len(value) > max_count:
        raise Cfg1PolicyError("POLICY_REFS_MALFORMED")
    if non_empty and not value:
        raise Cfg1PolicyError("POLICY_REFS_EMPTY")
    for item in value:
        _require_keys(item, _REF_KEYS, "POLICY_REF_MALFORMED")
        if not repo_path_is_valid(item["repo_path"]):
            raise Cfg1PolicyError("POLICY_REF_REPO_PATH_GRAMMAR")
        _require_hex64(item["sha256"], "POLICY_REF_DIGEST_MALFORMED")
    return value


def _validate_seam_digests(value: object) -> dict:
    if type(value) is not dict or frozenset(value) != frozenset(PI_SC1_PATHS):
        raise Cfg1PolicyError("POLICY_SEAM_DIGESTS_MALFORMED")
    for path in PI_SC1_PATHS:
        _require_hex64(value[path], "POLICY_SEAM_DIGESTS_MALFORMED")
    return value


_SEAM_EVIDENCE_KEYS = frozenset(
    {"record_kind", "seam_contract", "seam_digests", "seam_fingerprint", "evidence", "evidence_id"}
)


def _validate_seam_evidence(record: object) -> dict:
    _require_keys(record, _SEAM_EVIDENCE_KEYS, "POLICY_SEAM_EVIDENCE_KEYS")
    _require_literal(record["record_kind"], SEAM_EVIDENCE_RECORD_KIND, "POLICY_SEAM_EVIDENCE_KIND")
    _require_literal(record["seam_contract"], SEAM_CONTRACT, "POLICY_SEAM_CONTRACT")
    digests = _validate_seam_digests(record["seam_digests"])
    _require_hex64(record["seam_fingerprint"], "POLICY_SEAM_FINGERPRINT_MALFORMED")
    _validate_refs(record["evidence"], max_count=MAX_EVIDENCE_REFS, non_empty=True)
    _require_hex64(record["evidence_id"], "POLICY_EVIDENCE_ID_MALFORMED")
    if compute_seam_fingerprint(digests) != record["seam_fingerprint"]:
        raise Cfg1PolicyError("POLICY_SEAM_FINGERPRINT_MISMATCH")
    if _record_id(record, "evidence_id") != record["evidence_id"]:
        raise Cfg1PolicyError("POLICY_EVIDENCE_ID_MISMATCH")
    return record


_PROFILE_KEYS = frozenset(
    {
        "record_kind",
        "payload_contract",
        "payload_fingerprint",
        "resolution_exposures",
        "profile_id",
        "seam_contract",
        "seam_digests",
        "seam_fingerprint",
        "declared",
        "discovery",
    }
)
_DECLARED_KEYS = frozenset({"package_name", "package_version", "pi_ai_version", "pi_agent_core_version"})
_DISCOVERY_KEYS = frozenset({"aido_commit", "discovery_tool_revision"})


def _validate_profile_schema(record: object) -> dict:
    """Closed schema only. Every derivable value is recomputed separately."""
    _require_keys(record, _PROFILE_KEYS, "POLICY_PROFILE_KEYS")
    _require_literal(record["record_kind"], PROFILE_RECORD_KIND, "POLICY_PROFILE_KIND")
    _require_literal(record["payload_contract"], PAYLOAD_CONTRACT, "POLICY_PAYLOAD_CONTRACT")
    _require_literal(record["seam_contract"], SEAM_CONTRACT, "POLICY_SEAM_CONTRACT")
    _require_hex64(record["payload_fingerprint"], "POLICY_PAYLOAD_FINGERPRINT_MALFORMED")
    _require_hex64(record["profile_id"], "POLICY_PROFILE_ID_MALFORMED")
    _require_hex64(record["seam_fingerprint"], "POLICY_SEAM_FINGERPRINT_MALFORMED")
    _validate_seam_digests(record["seam_digests"])
    if type(record["resolution_exposures"]) is not list:
        raise Cfg1PolicyError("POLICY_EXPOSURES_MALFORMED")
    declared = _require_keys(record["declared"], _DECLARED_KEYS, "POLICY_DECLARED_KEYS")
    for name in _DECLARED_KEYS:
        if type(declared[name]) is not str:
            raise Cfg1PolicyError("POLICY_DECLARED_MALFORMED")
    discovery = _require_keys(record["discovery"], _DISCOVERY_KEYS, "POLICY_DISCOVERY_KEYS")
    commit = discovery["aido_commit"]
    if type(commit) is not str or _AIDO_COMMIT.fullmatch(commit) is None:
        raise Cfg1PolicyError("POLICY_DISCOVERY_MALFORMED")
    revision = discovery["discovery_tool_revision"]
    if type(revision) is not str or _DISCOVERY_TOOL_REVISION.fullmatch(revision) is None:
        raise Cfg1PolicyError("POLICY_DISCOVERY_MALFORMED")
    return record


_APPROVAL_KEYS = frozenset(
    {
        "record_kind",
        "profile_id",
        "consumer_contract",
        "policy_revision",
        "qualification_class",
        "reused_evidence",
        "pmd",
        "evidence",
        "acceptance_reference",
        "approval_id",
    }
)
_REUSE_KEYS = frozenset({"evidence_kind", "source_id", "premise_scope", "refs"})
_SEAM_FILES_SCOPE_KEYS = frozenset({"kind", "paths"})
_PAYLOAD_SCOPE_KEYS = frozenset({"kind"})
_PMD_KEYS = frozenset({"reference_profile_id", "deltas", "conclusion_refs"})
_PMD_DELTA_KEYS = frozenset(
    {
        "delta",
        "manifest_path",
        "old",
        "new",
        "read_as_parsed_field",
        "read_as_raw_manifest",
        "categories",
        "cfg1_cc1_effect",
        "evidence_effect",
    }
)
_FINDING_KEYS = frozenset({"finding", "refs"})


def _validate_finding(value: object, findings: frozenset[str]) -> dict:
    _require_keys(value, _FINDING_KEYS, "POLICY_PMD_FINDING_KEYS")
    _require_member(value["finding"], findings, "POLICY_PMD_FINDING_VALUE")
    _validate_refs(value["refs"], max_count=MAX_FINDING_REFS, non_empty=False)
    return value


def _validate_reuse_schema(entry: object) -> dict:
    _require_keys(entry, _REUSE_KEYS, "POLICY_REUSE_KEYS")
    _require_member(entry["evidence_kind"], REUSABLE_EVIDENCE_KINDS, "POLICY_REUSE_EVIDENCE_KIND")
    _require_hex64(entry["source_id"], "POLICY_REUSE_SOURCE_MALFORMED")
    scope = entry["premise_scope"]
    if type(scope) is not dict or type(scope.get("kind")) is not str:
        raise Cfg1PolicyError("POLICY_REUSE_PREMISE_MALFORMED")
    if scope["kind"] == PREMISE_SEAM_FILES:
        _require_keys(scope, _SEAM_FILES_SCOPE_KEYS, "POLICY_REUSE_PREMISE_MALFORMED")
        paths = scope["paths"]
        if type(paths) is not list or not paths:
            raise Cfg1PolicyError("POLICY_REUSE_SEAM_PATHS_MALFORMED")
        previous: str | None = None
        for path in paths:
            if type(path) is not str or path not in PI_SC1_PATHS:
                raise Cfg1PolicyError("POLICY_REUSE_SEAM_PATHS_MALFORMED")
            if previous is not None and not previous < path:
                raise Cfg1PolicyError("POLICY_REUSE_SEAM_PATHS_MALFORMED")
            previous = path
    elif scope["kind"] == PREMISE_PAYLOAD_EXCEPT_PERMITTED_MANIFEST_FIELDS:
        _require_keys(scope, _PAYLOAD_SCOPE_KEYS, "POLICY_REUSE_PREMISE_MALFORMED")
    else:
        raise Cfg1PolicyError("POLICY_REUSE_PREMISE_MALFORMED")
    if entry["evidence_kind"] not in _PREMISE_KINDS[scope["kind"]]:
        raise Cfg1PolicyError("POLICY_REUSE_KIND_NOT_APPLICABLE_TO_PREMISE")
    _validate_refs(entry["refs"], max_count=MAX_EVIDENCE_REFS, non_empty=True)
    return entry


def _validate_pmd_schema(pmd: object) -> dict:
    _require_keys(pmd, _PMD_KEYS, "POLICY_PMD_KEYS")
    _require_hex64(pmd["reference_profile_id"], "POLICY_PMD_REFERENCE_MALFORMED")
    if type(pmd["deltas"]) is not list:
        raise Cfg1PolicyError("POLICY_PMD_DELTAS_MALFORMED")
    for delta in pmd["deltas"]:
        _require_keys(delta, _PMD_DELTA_KEYS, "POLICY_PMD_DELTA_KEYS")
        _require_member(delta["delta"], PMD_DELTA_LABELS, "POLICY_PMD_DELTA_LABEL")
        for name in ("manifest_path", "old", "new"):
            if type(delta[name]) is not str:
                raise Cfg1PolicyError("POLICY_PMD_DELTA_MALFORMED")
        _validate_finding(delta["read_as_parsed_field"], _PARSED_FIELD_FINDINGS)
        _validate_finding(delta["read_as_raw_manifest"], _RAW_MANIFEST_FINDINGS)
        categories = _require_keys(delta["categories"], PMD_CATEGORIES, "POLICY_PMD_CATEGORY_KEYS")
        for name in PMD_CATEGORIES:
            _validate_finding(categories[name], _CATEGORY_FINDINGS)
        _require_member(delta["cfg1_cc1_effect"], _EFFECTS, "POLICY_PMD_EFFECT_VALUE")
        effects = delta["evidence_effect"]
        if type(effects) is not dict:
            raise Cfg1PolicyError("POLICY_PMD_EVIDENCE_EFFECT_MALFORMED")
        for name, value in effects.items():
            if type(name) is not str:
                raise Cfg1PolicyError("POLICY_PMD_EVIDENCE_EFFECT_MALFORMED")
            _require_member(value, _EFFECTS, "POLICY_PMD_EFFECT_VALUE")
    _validate_refs(pmd["conclusion_refs"], max_count=MAX_EVIDENCE_REFS, non_empty=True)
    return pmd


def _validate_approval_schema(record: object) -> dict:
    _require_keys(record, _APPROVAL_KEYS, "POLICY_APPROVAL_KEYS")
    _require_literal(record["record_kind"], APPROVAL_RECORD_KIND, "POLICY_APPROVAL_KIND")
    _require_hex64(record["profile_id"], "POLICY_PROFILE_ID_MALFORMED")
    _require_literal(record["consumer_contract"], CONSUMER_CONTRACT, "POLICY_CONSUMER_CONTRACT")
    _require_literal(record["policy_revision"], POLICY_REVISION, "POLICY_POLICY_REVISION")
    qualification_class = _require_member(
        record["qualification_class"], frozenset(QUALIFICATION_CLASSES), "POLICY_QUALIFICATION_CLASS_UNKNOWN"
    )
    if qualification_class not in CC1_ADMISSIBLE_CLASSES:
        raise Cfg1PolicyError("POLICY_QUALIFICATION_CLASS_RESERVED_FOR_FUTURE_CONTRACT")
    if type(record["reused_evidence"]) is not list:
        raise Cfg1PolicyError("POLICY_REUSE_MALFORMED")
    for entry in record["reused_evidence"]:
        _validate_reuse_schema(entry)
    if record["pmd"] is not None:
        _validate_pmd_schema(record["pmd"])
    _validate_refs(record["evidence"], max_count=MAX_EVIDENCE_REFS, non_empty=True)
    reference = record["acceptance_reference"]
    if type(reference) is not str or not 1 <= len(reference) <= MAX_ACCEPTANCE_REFERENCE_CHARS:
        raise Cfg1PolicyError("POLICY_ACCEPTANCE_REFERENCE_MALFORMED")
    for character in reference:
        if not 0x20 <= ord(character) <= 0x7E:
            raise Cfg1PolicyError("POLICY_ACCEPTANCE_REFERENCE_MALFORMED")
    _require_hex64(record["approval_id"], "POLICY_APPROVAL_ID_MALFORMED")
    if _record_id(record, "approval_id") != record["approval_id"]:
        raise Cfg1PolicyError("POLICY_APPROVAL_ID_MISMATCH")
    return record


_RETIREMENT_KEYS = frozenset(
    {"record_kind", "profile_id", "consumer_contract", "reason_code", "evidence", "retirement_id"}
)


def _validate_retirement_schema(record: object) -> dict:
    _require_keys(record, _RETIREMENT_KEYS, "POLICY_RETIREMENT_KEYS")
    _require_literal(record["record_kind"], RETIREMENT_RECORD_KIND, "POLICY_RETIREMENT_KIND")
    _require_hex64(record["profile_id"], "POLICY_PROFILE_ID_MALFORMED")
    _require_literal(record["consumer_contract"], CONSUMER_CONTRACT, "POLICY_CONSUMER_CONTRACT")
    _require_member(record["reason_code"], RETIREMENT_REASON_CODES, "POLICY_RETIREMENT_REASON_CODE")
    _validate_refs(record["evidence"], max_count=MAX_EVIDENCE_REFS, non_empty=True)
    _require_hex64(record["retirement_id"], "POLICY_RETIREMENT_ID_MALFORMED")
    if _record_id(record, "retirement_id") != record["retirement_id"]:
        raise Cfg1PolicyError("POLICY_RETIREMENT_ID_MISMATCH")
    return record


_APS_KEYS = frozenset(
    {
        "record_kind",
        "consumer_contract",
        "policy_revision",
        "payload_contract",
        "seam_contract",
        "revision",
        "previous_revision_sha256",
        "seam_evidence",
        "profiles",
        "approvals",
        "retirements",
    }
)
_APS_LISTS: tuple[str, ...] = ("seam_evidence", "profiles", "approvals", "retirements")


def _validate_aps_header(record: dict, revision: int, previous_sha256: str | None) -> None:
    _require_keys(record, _APS_KEYS, "POLICY_APS_KEYS")
    _require_literal(record["record_kind"], APS_RECORD_KIND, "POLICY_APS_KIND")
    _require_literal(record["consumer_contract"], CONSUMER_CONTRACT, "POLICY_CONSUMER_CONTRACT")
    _require_literal(record["policy_revision"], POLICY_REVISION, "POLICY_POLICY_REVISION")
    _require_literal(record["payload_contract"], PAYLOAD_CONTRACT, "POLICY_PAYLOAD_CONTRACT")
    _require_literal(record["seam_contract"], SEAM_CONTRACT, "POLICY_SEAM_CONTRACT")
    if type(record["revision"]) is not int or record["revision"] != revision:
        raise Cfg1PolicyError("POLICY_APS_REVISION_MISMATCH")
    previous = record["previous_revision_sha256"]
    if previous_sha256 is None:
        if previous is not None:
            raise Cfg1PolicyError("POLICY_APS_PREVIOUS_DIGEST_MISMATCH")
    elif not is_lowercase_hex64(previous) or previous != previous_sha256:
        raise Cfg1PolicyError("POLICY_APS_PREVIOUS_DIGEST_MISMATCH")
    for name in _APS_LISTS:
        if type(record[name]) is not list:
            raise Cfg1PolicyError("POLICY_APS_LIST_MALFORMED")


# ---------------------------------------------------------------------------
# Recomputation from committed bytes (PE-1 Sec. 9.4) -- ACCEPTED PE-2a
# primitives, by identity
# ---------------------------------------------------------------------------


def _facts_from_committed_bytes(
    payload_fingerprint: str, inventory_bytes: bytes, bundle_bytes: bytes
) -> ProfileFacts:
    """FRESH profile facts from one committed inventory + bundle byte pair.

    Strict policy parse of both files, then the accepted PE-2a inventory
    validator, bundle binder and facts derivation (which runs the accepted
    strict manifest parser, dependency-map schema and package-name parser).
    The recomputed fingerprint must equal the validated one the file name was
    formed from.
    """
    try:
        inventory = inventory_from_record(_parse_policy_bytes(inventory_bytes))
    except Cfg1PayloadError:
        raise Cfg1PolicyError("POLICY_INVENTORY_INVALID") from None
    if inventory.payload_fingerprint != payload_fingerprint:
        raise Cfg1PolicyError("POLICY_INVENTORY_FINGERPRINT_MISMATCH")
    try:
        bundle = bundle_from_record(_parse_policy_bytes(bundle_bytes), inventory)
    except Cfg1ManifestError:
        raise Cfg1PolicyError("POLICY_MANIFEST_BUNDLE_INVALID") from None
    try:
        return compute_profile_facts(inventory, bundle)
    except (Cfg1ManifestError, Cfg1FloorError, Cfg1PayloadError):
        raise Cfg1PolicyError("POLICY_PROFILE_FACTS_UNDERIVABLE") from None


def _verify_profile_against_facts(record: dict, facts: ProfileFacts) -> None:
    """Every derivable profile field must equal its recomputation exactly."""
    if facts.c5_reason is not None:
        raise Cfg1PolicyError("POLICY_PROFILE_NOT_APPROVABLE")
    if record["payload_fingerprint"] != facts.payload_fingerprint:
        raise Cfg1PolicyError("POLICY_PAYLOAD_FINGERPRINT_MISMATCH")
    stored_exposures = record["resolution_exposures"]
    try:
        validate_resolution_exposures(stored_exposures)
    except Cfg1ManifestError:
        raise Cfg1PolicyError("POLICY_EXPOSURES_MALFORMED") from None
    if tuple(stored_exposures) != facts.resolution_exposures:
        raise Cfg1PolicyError("POLICY_EXPOSURES_MISMATCH")
    if record["profile_id"] != facts.profile_id:
        raise Cfg1PolicyError("POLICY_PROFILE_ID_MISMATCH")
    if record["seam_digests"] != facts.seam_digests_dict():
        raise Cfg1PolicyError("POLICY_SEAM_DIGESTS_MISMATCH")
    if record["seam_fingerprint"] != facts.seam_fingerprint:
        raise Cfg1PolicyError("POLICY_SEAM_FINGERPRINT_MISMATCH")
    if record["declared"] != facts.declared_dict():
        raise Cfg1PolicyError("POLICY_DECLARED_MISMATCH")
    expected = {
        "record_kind": PROFILE_RECORD_KIND,
        "payload_contract": PAYLOAD_CONTRACT,
        "payload_fingerprint": facts.payload_fingerprint,
        "resolution_exposures": list(facts.resolution_exposures),
        "profile_id": facts.profile_id,
        "seam_contract": SEAM_CONTRACT,
        "seam_digests": facts.seam_digests_dict(),
        "seam_fingerprint": facts.seam_fingerprint,
        "declared": facts.declared_dict(),
        "discovery": {
            "aido_commit": record["discovery"]["aido_commit"],
            "discovery_tool_revision": record["discovery"]["discovery_tool_revision"],
        },
    }
    if policy_file_bytes(expected) != policy_file_bytes(record):
        raise Cfg1PolicyError("POLICY_PROFILE_RECORD_MISMATCH")


# ---------------------------------------------------------------------------
# Chain state, approvals, PMD, evidence reuse, retirements (Sec. 9.5, 10.4)
# ---------------------------------------------------------------------------


class _ChainState:
    """Loader-private, per-load bookkeeping. Never leaves :func:`_load_policy_directory`."""

    def __init__(self) -> None:
        self.seam_evidence: dict[str, dict] = {}
        self.profiles: dict[str, ProfileFacts] = {}
        self.profile_payloads: dict[str, tuple[str, bytes, bytes]] = {}
        self.fingerprints: set[str] = set()
        self.approved: set[str] = set()
        self.approval_ids: set[str] = set()
        self.retired: set[str] = set()
        self.retirement_ids: set[str] = set()
        self.eligible: frozenset[str] = frozenset()


def _reference_view(state: _ChainState, revision_seam_evidence: dict[str, dict]) -> ReferenceView:
    """The loader-owned PE-2a reference view of revision ``N-1``.

    ``R``: profiles eligible in ``N-1``; C1R: profiles present but not
    eligible; ``S``: seam fingerprints of the seam evidence of ``N-1`` plus
    revision ``N`` itself (Sec. 8.1). Built from facts the loader itself
    recomputed in this load.
    """
    eligible = tuple(state.profiles[profile_id] for profile_id in sorted(state.eligible))
    present_ineligible = frozenset(state.profiles) - state.eligible
    seams = frozenset(evidence["seam_fingerprint"] for evidence in revision_seam_evidence.values())
    return ReferenceView(
        eligible=eligible, present_ineligible_profile_ids=present_ineligible, seam_fingerprints=seams
    )


def _validate_pmd(
    pmd: dict,
    *,
    candidate: ProfileFacts,
    qualification_class: str,
    reuse_count: int,
    state: _ChainState,
) -> None:
    """PE-1 Sec. 10.4 rules 1-9: structural completeness and consistency ONLY.

    Never a proof that any finding is true (Sec. 10.5).
    """
    reference_id = pmd["reference_profile_id"]
    if reference_id not in state.eligible:
        raise Cfg1PolicyError("POLICY_PMD_REFERENCE_NOT_ELIGIBLE")
    reference = state.profiles[reference_id]
    if not c2_relation(candidate, reference):
        raise Cfg1PolicyError("POLICY_PMD_REFERENCE_NOT_C2")
    expected = tuple(
        (item["delta"], item["manifest_path"], item["old"], item["new"])
        for item in compute_pmd_deltas(candidate, reference)
    )
    stored = tuple((item["delta"], item["manifest_path"], item["old"], item["new"]) for item in pmd["deltas"])
    # Rule 1: exactly the recomputed list -- same entries, order and values.
    if stored != expected:
        raise Cfg1PolicyError("POLICY_PMD_DELTAS_MISMATCH")
    expected_effect_keys = frozenset(str(index) for index in range(reuse_count))
    raw_finding_by_manifest: dict[str, str] = {}
    for delta in pmd["deltas"]:
        parsed = delta["read_as_parsed_field"]
        raw = delta["read_as_raw_manifest"]
        # Rule 2.
        if delta["delta"] == DELTA_RAW_BYTES:
            if parsed["finding"] != "NOT_APPLICABLE" or parsed["refs"] != []:
                raise Cfg1PolicyError("POLICY_PMD_PARSED_FIELD_RULE")
        elif parsed["finding"] == "NOT_APPLICABLE" or not parsed["refs"]:
            raise Cfg1PolicyError("POLICY_PMD_PARSED_FIELD_RULE")
        # Rule 3.
        if not raw["refs"]:
            raise Cfg1PolicyError("POLICY_PMD_RAW_MANIFEST_RULE")
        previous_raw = raw_finding_by_manifest.setdefault(delta["manifest_path"], raw["finding"])
        if previous_raw != raw["finding"]:
            raise Cfg1PolicyError("POLICY_PMD_RAW_MANIFEST_RULE")
        # Rule 4 (key set is enforced by the schema).
        affects = False
        for name in sorted(PMD_CATEGORIES):
            finding = delta["categories"][name]
            if (finding["finding"] == "NOT_REACHED") != (finding["refs"] == []):
                raise Cfg1PolicyError("POLICY_PMD_CATEGORY_RULE")
            affects = affects or finding["finding"] == "AFFECTS"
        # Rule 5.
        effects = delta["evidence_effect"]
        if frozenset(effects) != expected_effect_keys:
            raise Cfg1PolicyError("POLICY_PMD_EVIDENCE_EFFECT_KEYS")
        any_evidence_affected = any(value == "AFFECTED" for value in effects.values())
        cfg1_affected = delta["cfg1_cc1_effect"] == "AFFECTED"
        # Rule 6: some category AFFECTS <=> CC1 or some reused item AFFECTED.
        if affects != (cfg1_affected or any_evidence_affected):
            raise Cfg1PolicyError("POLICY_PMD_CONSISTENCY_RULE")
        # Rule 7: an affected item may not be reused.
        if any_evidence_affected:
            raise Cfg1PolicyError("POLICY_PMD_REUSED_EVIDENCE_AFFECTED")
        # Rules 8 and 9.
        if cfg1_affected and _CLASS_RANK[qualification_class] < _CLASS_RANK["C2_MANIFEST_DELTA_REACQUIRED"]:
            raise Cfg1PolicyError("POLICY_PMD_CLASS_INADMISSIBLE")


def _validate_reuse(
    entry: dict,
    *,
    candidate: ProfileFacts,
    pmd: dict | None,
    state: _ChainState,
    revision_seam_evidence: dict[str, dict],
    revision_profile_ids: frozenset[str],
) -> None:
    """PE-0 Sec. 8.5 premise verification. CONCLUSIONS NEVER TRANSFER: this
    proves only that the declared premise holds mechanically."""
    source_id = entry["source_id"]
    is_profile = source_id in state.profiles or source_id in revision_profile_ids
    is_seam_evidence = source_id in revision_seam_evidence
    if is_profile == is_seam_evidence:
        raise Cfg1PolicyError("POLICY_REUSE_SOURCE_UNRESOLVED")
    if is_profile and source_id not in state.eligible:
        raise Cfg1PolicyError("POLICY_REUSE_SOURCE_NOT_ELIGIBLE")
    scope = entry["premise_scope"]
    if scope["kind"] == PREMISE_SEAM_FILES:
        if is_profile:
            source_digests = state.profiles[source_id].seam_digests_dict()
        else:
            source_digests = revision_seam_evidence[source_id]["seam_digests"]
        candidate_digests = candidate.seam_digests_dict()
        for path in scope["paths"]:
            if candidate_digests[path] != source_digests[path]:
                raise Cfg1PolicyError("POLICY_REUSE_SEAM_PREMISE_FAILED")
        return
    # PAYLOAD_EXCEPT_PERMITTED_MANIFEST_FIELDS
    if not is_profile:
        raise Cfg1PolicyError("POLICY_REUSE_SOURCE_NOT_A_PROFILE")
    if pmd is None:
        raise Cfg1PolicyError("POLICY_REUSE_REQUIRES_PMD")
    # Rule 10.
    if source_id != pmd["reference_profile_id"]:
        raise Cfg1PolicyError("POLICY_REUSE_SOURCE_NOT_PMD_REFERENCE")
    if not c2_relation(candidate, state.profiles[source_id]):
        raise Cfg1PolicyError("POLICY_REUSE_PAYLOAD_PREMISE_FAILED")


def _validate_approval(
    approval: dict,
    *,
    candidate: ProfileFacts,
    state: _ChainState,
    revision_seam_evidence: dict[str, dict],
    revision_profile_ids: frozenset[str],
) -> None:
    """One approval first appearing in revision ``N``, against ``N-1``."""
    qualification_class = approval["qualification_class"]
    floor = classify_floor(candidate, _reference_view(state, revision_seam_evidence))
    least = LEAST_ADMISSIBLE_CLASS.get(floor)
    if least is None:
        raise Cfg1PolicyError("POLICY_APPROVAL_FLOOR_NOT_APPROVABLE")
    if _CLASS_RANK[qualification_class] < _CLASS_RANK[least]:
        raise Cfg1PolicyError("POLICY_APPROVAL_CLASS_BELOW_FLOOR")
    reused = approval["reused_evidence"]
    payload_reuse = any(
        entry["premise_scope"]["kind"] == PREMISE_PAYLOAD_EXCEPT_PERMITTED_MANIFEST_FIELDS for entry in reused
    )
    pmd = approval["pmd"]
    pmd_required = floor == FLOOR_C2 or payload_reuse
    if pmd_required and pmd is None:
        raise Cfg1PolicyError("POLICY_PMD_REQUIRED")
    if not pmd_required and pmd is not None:
        raise Cfg1PolicyError("POLICY_PMD_NOT_PERMITTED")
    if pmd is not None:
        _validate_pmd(
            pmd,
            candidate=candidate,
            qualification_class=qualification_class,
            reuse_count=len(reused),
            state=state,
        )
    for entry in reused:
        _validate_reuse(
            entry,
            candidate=candidate,
            pmd=pmd,
            state=state,
            revision_seam_evidence=revision_seam_evidence,
            revision_profile_ids=revision_profile_ids,
        )


# ---------------------------------------------------------------------------
# The sealed snapshot (PE-1 Sec. 11.4)
# ---------------------------------------------------------------------------

_SEAL_KEY = object()


class _Sealed:
    """Immutable, loader-constructed, not copyable, not picklable, not subclassable."""

    __slots__ = ()

    def __init_subclass__(cls, **kwargs) -> None:
        if cls.__module__ != __name__ or cls.__qualname__ not in _SEALED_CLASS_NAMES:
            raise TypeError("sealed policy types cannot be subclassed")
        super().__init_subclass__(**kwargs)

    def __setattr__(self, name: str, value: object) -> None:  # noqa: D105
        raise AttributeError(f"{type(self).__name__} is sealed")

    def __delattr__(self, name: str) -> None:  # noqa: D105
        raise AttributeError(f"{type(self).__name__} is sealed")

    def __reduce_ex__(self, protocol: object):  # noqa: D105
        raise TypeError(f"{type(self).__name__} cannot be copied or pickled")

    def __copy__(self):  # noqa: D105
        raise TypeError(f"{type(self).__name__} cannot be copied")

    def __deepcopy__(self, memo: object):  # noqa: D105
        raise TypeError(f"{type(self).__name__} cannot be copied")


_SEALED_CLASS_NAMES = frozenset(
    {"Cfg1EligibleProfileView", "Cfg1PolicySnapshot", "_HeadReferenceMaterial", "_PolicyLoad"}
)


class Cfg1EligibleProfileView(_Sealed):
    """The immutable runtime view of ONE eligible profile (Sec. 11.4).

    ``resolution_exposures`` is a tuple of validated package-name component
    tuples (parser output); ``declared_package_version`` is provenance only and
    decides nothing.
    """

    __slots__ = ("profile_id", "payload_fingerprint", "resolution_exposures", "declared_package_version")

    def __init__(
        self,
        key: object,
        *,
        profile_id: str,
        payload_fingerprint: str,
        resolution_exposures: tuple[tuple[str, ...], ...],
        declared_package_version: str,
    ) -> None:
        if key is not _SEAL_KEY:
            raise Cfg1PolicyError("POLICY_VIEW_NOT_CONSTRUCTED_BY_LOADER")
        object.__setattr__(self, "profile_id", profile_id)
        object.__setattr__(self, "payload_fingerprint", payload_fingerprint)
        object.__setattr__(self, "resolution_exposures", resolution_exposures)
        object.__setattr__(self, "declared_package_version", declared_package_version)

    def __repr__(self) -> str:  # noqa: D105
        return f"{type(self).__name__}({self.profile_id})"


class Cfg1PolicySnapshot(_Sealed):
    """The sealed HPP-1 policy snapshot. POLICY, never an observation of Pi.

    Constructible only by the loader. Carries only the frozen literals, the
    APS revision and head digest, the policy directory (for G6), the COMPUTED
    eligible set and one immutable runtime view per eligible profile.
    """

    __slots__ = (
        "policy_revision",
        "payload_contract",
        "seam_contract",
        "consumer_contract",
        "aps_revision",
        "aps_head_sha256",
        "policy_directory",
        "eligible_profile_ids",
        "eligible_profiles",
    )

    def __init__(
        self,
        key: object,
        *,
        aps_revision: int,
        aps_head_sha256: str,
        policy_directory: str,
        eligible_profiles: tuple[Cfg1EligibleProfileView, ...],
    ) -> None:
        if key is not _SEAL_KEY:
            raise Cfg1PolicyError("POLICY_SNAPSHOT_NOT_CONSTRUCTED_BY_LOADER")
        object.__setattr__(self, "policy_revision", POLICY_REVISION)
        object.__setattr__(self, "payload_contract", PAYLOAD_CONTRACT)
        object.__setattr__(self, "seam_contract", SEAM_CONTRACT)
        object.__setattr__(self, "consumer_contract", CONSUMER_CONTRACT)
        object.__setattr__(self, "aps_revision", aps_revision)
        object.__setattr__(self, "aps_head_sha256", aps_head_sha256)
        object.__setattr__(self, "policy_directory", policy_directory)
        object.__setattr__(
            self, "eligible_profile_ids", frozenset(view.profile_id for view in eligible_profiles)
        )
        object.__setattr__(self, "eligible_profiles", eligible_profiles)

    def __repr__(self) -> str:  # noqa: D105
        return (
            f"{type(self).__name__}(aps_revision={self.aps_revision}, "
            f"eligible={len(self.eligible_profile_ids)})"
        )


class _HeadReferenceMaterial(_Sealed):
    """Loader-owned, immutable HEAD reference material: committed BYTES only.

    Not policy authority and not part of the snapshot. Each use rebuilds fresh
    PE-2a facts from these bytes (:func:`_reference_view_from_material`), so
    no mutable object derived at load is ever handed out.
    """

    __slots__ = ("eligible_payloads", "present_ineligible_profile_ids", "seam_fingerprints")

    def __init__(
        self,
        key: object,
        *,
        eligible_payloads: tuple[tuple[str, str, bytes, bytes], ...],
        present_ineligible_profile_ids: frozenset[str],
        seam_fingerprints: frozenset[str],
    ) -> None:
        if key is not _SEAL_KEY:
            raise Cfg1PolicyError("POLICY_REFERENCE_NOT_CONSTRUCTED_BY_LOADER")
        object.__setattr__(self, "eligible_payloads", eligible_payloads)
        object.__setattr__(self, "present_ineligible_profile_ids", present_ineligible_profile_ids)
        object.__setattr__(self, "seam_fingerprints", seam_fingerprints)


class _PolicyLoad(_Sealed):
    """The private result of one load: the snapshot, the head reference
    material and every revision's ``(revision, sha256, eligible set)``."""

    __slots__ = ("snapshot", "head_reference", "revisions")

    def __init__(
        self,
        key: object,
        *,
        snapshot: Cfg1PolicySnapshot,
        head_reference: _HeadReferenceMaterial,
        revisions: tuple[tuple[int, str, frozenset[str]], ...],
    ) -> None:
        if key is not _SEAL_KEY:
            raise Cfg1PolicyError("POLICY_LOAD_NOT_CONSTRUCTED_BY_LOADER")
        object.__setattr__(self, "snapshot", snapshot)
        object.__setattr__(self, "head_reference", head_reference)
        object.__setattr__(self, "revisions", revisions)


def _profile_view(profile_id: str, facts: ProfileFacts) -> Cfg1EligibleProfileView:
    exposures = tuple(parse_package_name(text) for text in facts.resolution_exposures)
    declared = facts.declared_dict()
    version = declared["package_version"]
    if type(version) is not str:
        raise Cfg1PolicyError("POLICY_DECLARED_MALFORMED")
    return Cfg1EligibleProfileView(
        _SEAL_KEY,
        profile_id=profile_id,
        payload_fingerprint=facts.payload_fingerprint,
        resolution_exposures=exposures,
        declared_package_version=version,
    )


# ---------------------------------------------------------------------------
# The loader (PE-1 Sec. 9.1, 9.2, 9.5)
# ---------------------------------------------------------------------------


class _ReadBudget:
    def __init__(self) -> None:
        self.consumed = 0


def _plain_directory_entries(enumerate_directory, path: str, max_entries: int) -> dict[str, str]:
    """``{name: kind}`` of one no-follow enumerated PLAIN directory, or refuse."""
    listing = enumerate_directory(path, max_entries)
    if type(listing) is not DirectoryListing:
        raise Cfg1PolicyError("POLICY_LEAF_MALFORMED")
    if listing.classification != CLASSIFICATION_DIRECTORY:
        raise Cfg1PolicyError("POLICY_DIRECTORY_NOT_PLAIN")
    if listing.over_budget:
        raise Cfg1PolicyError("POLICY_DIRECTORY_ENTRY_BOUND_EXCEEDED")
    if listing.complete is not True or type(listing.entries) is not tuple:
        raise Cfg1PolicyError("POLICY_DIRECTORY_UNREADABLE")
    entries: dict[str, str] = {}
    for item in listing.entries:
        if type(item) is not tuple or len(item) != 2:
            raise Cfg1PolicyError("POLICY_LEAF_MALFORMED")
        name, kind = item
        if type(name) is not str or type(kind) is not str or kind not in ENTRY_KINDS:
            raise Cfg1PolicyError("POLICY_LEAF_MALFORMED")
        if name in entries:
            raise Cfg1PolicyError("POLICY_DIRECTORY_DUPLICATE_ENTRY")
        entries[name] = kind
    return entries


def _read_policy_file(read_file, path: str, per_file_bound: int, budget: _ReadBudget) -> bytes:
    """One no-follow, one-handle read of a regular policy file, bounded."""
    remaining = MAX_POLICY_TOTAL_BYTES - budget.consumed
    cap = min(per_file_bound, remaining)
    result = read_file(path, cap)
    if type(result) is not PayloadFileRead:
        raise Cfg1PolicyError("POLICY_LEAF_MALFORMED")
    if result.classification != CLASSIFICATION_REGULAR_FILE:
        raise Cfg1PolicyError("POLICY_FILE_NOT_REGULAR")
    if result.within_bound is not True:
        raise Cfg1PolicyError(
            "POLICY_TOTAL_BYTES_EXCEEDED" if cap < per_file_bound else "POLICY_FILE_BOUND_EXCEEDED"
        )
    if result.stable is not True:
        raise Cfg1PolicyError("POLICY_FILE_UNSTABLE")
    content = result.content
    if (
        type(content) is not bytes
        or type(result.size) is not int
        or len(content) != result.size
        or len(content) > cap
        or hashlib.sha256(content).hexdigest() != result.sha256
    ):
        raise Cfg1PolicyError("POLICY_LEAF_MALFORMED")
    budget.consumed += len(content)
    return content


def _require_referenced_entries(
    top_entries: dict[str, str], name: str, enumerate_directory, policy_directory: str, expected: frozenset[str]
) -> str | None:
    """A fingerprint-named subdirectory holds EXACTLY the referenced files.

    May be absent iff nothing is referenced (Git tracks no empty directory).
    """
    if name not in top_entries:
        if expected:
            raise Cfg1PolicyError("POLICY_REFERENCED_FILE_MISSING")
        return None
    directory = ntpath.join(policy_directory, name)
    entries = _plain_directory_entries(enumerate_directory, directory, MAX_PROFILES + _ENUMERATION_SLACK)
    names = frozenset(entries)
    if names - expected:
        raise Cfg1PolicyError("POLICY_UNREFERENCED_FILE")
    if expected - names:
        raise Cfg1PolicyError("POLICY_REFERENCED_FILE_MISSING")
    for kind in entries.values():
        if kind != ENTRY_KIND_FILE:
            raise Cfg1PolicyError("POLICY_FILE_NOT_REGULAR")
    return directory


def _load_policy_directory(
    policy_directory: str,
    *,
    enumerate_directory=pi_fs_leaves.enumerate_directory_no_follow,
    read_file=pi_fs_leaves.read_payload_file_bytes,
) -> _PolicyLoad:
    """Load, strictly validate and seal ONE policy directory, or refuse.

    Module-private. Production calls it exactly once, at import, with the
    ``__file__``-derived ``_POLICY_DIR``; the parameters exist only so tests
    can load synthetic trees under ``tmp_path`` through leaf doubles.
    """
    if type(policy_directory) is not str or not ntpath.isabs(policy_directory):
        raise Cfg1PolicyError("POLICY_DIRECTORY_MALFORMED")
    budget = _ReadBudget()

    # -- layout: exactly aps (+ inventories, manifest_bundles iff referenced)
    top = _plain_directory_entries(enumerate_directory, policy_directory, 3 + _ENUMERATION_SLACK)
    allowed_top = {APS_DIRECTORY_NAME, INVENTORIES_DIRECTORY_NAME, MANIFEST_BUNDLES_DIRECTORY_NAME}
    for name, kind in top.items():
        if name not in allowed_top:
            raise Cfg1PolicyError("POLICY_STRAY_ENTRY")
        if kind != ENTRY_KIND_DIRECTORY:
            raise Cfg1PolicyError("POLICY_DIRECTORY_NOT_PLAIN")
    if APS_DIRECTORY_NAME not in top:
        raise Cfg1PolicyError("POLICY_APS_DIRECTORY_MISSING")
    aps_directory = ntpath.join(policy_directory, APS_DIRECTORY_NAME)
    aps_entries = _plain_directory_entries(
        enumerate_directory, aps_directory, MAX_APS_REVISIONS + _ENUMERATION_SLACK
    )
    numbers: set[int] = set()
    for name, kind in aps_entries.items():
        match = _APS_FILENAME.fullmatch(name)
        if match is None:
            raise Cfg1PolicyError("POLICY_STRAY_ENTRY")
        if kind != ENTRY_KIND_FILE:
            raise Cfg1PolicyError("POLICY_FILE_NOT_REGULAR")
        numbers.add(int(match.group(1)))
    if not numbers:
        raise Cfg1PolicyError("POLICY_APS_EMPTY")
    head_revision = max(numbers)
    if head_revision > MAX_APS_REVISIONS:
        raise Cfg1PolicyError("POLICY_APS_REVISION_BOUND_EXCEEDED")
    if numbers != set(range(1, head_revision + 1)):
        raise Cfg1PolicyError("POLICY_APS_NOT_CONTIGUOUS")

    # -- pass 1: every revision's bytes, schema, ids and append-only chain --
    revisions: list[tuple[int, bytes, dict]] = []
    previous_bytes: bytes | None = None
    previous_record: dict | None = None
    for revision in range(1, head_revision + 1):
        name = f"aps.r{revision:04d}.json"
        if name not in aps_entries:
            raise Cfg1PolicyError("POLICY_APS_NOT_CONTIGUOUS")
        data = _read_policy_file(
            read_file, ntpath.join(aps_directory, name), MAX_APS_REVISION_FILE_BYTES, budget
        )
        record = _parse_policy_bytes(data)
        _validate_aps_header(
            record,
            revision,
            None if previous_bytes is None else hashlib.sha256(previous_bytes).hexdigest(),
        )
        for list_name in _APS_LISTS:
            current = record[list_name]
            old = [] if previous_record is None else previous_record[list_name]
            if len(current) < len(old):
                raise Cfg1PolicyError("POLICY_APS_NOT_APPEND_ONLY")
            for index, item in enumerate(old):
                if policy_file_bytes(current[index]) != policy_file_bytes(item):
                    raise Cfg1PolicyError("POLICY_APS_NOT_APPEND_ONLY")
            additions = current[len(old) :]
            validator = {
                "seam_evidence": _validate_seam_evidence,
                "profiles": _validate_profile_schema,
                "approvals": _validate_approval_schema,
                "retirements": _validate_retirement_schema,
            }[list_name]
            for item in additions:
                validator(item)
        if len(record["profiles"]) > MAX_PROFILES:
            raise Cfg1PolicyError("POLICY_PROFILE_BOUND_EXCEEDED")
        revisions.append((revision, data, record))
        previous_bytes, previous_record = data, record

    # -- the referenced payload files, formed only from validated fingerprints
    head_record = revisions[-1][2]
    fingerprints = [profile["payload_fingerprint"] for profile in head_record["profiles"]]
    if len(set(fingerprints)) != len(fingerprints):
        raise Cfg1PolicyError("POLICY_DUPLICATE_PAYLOAD_FINGERPRINT")
    expected_names = frozenset(
        _require_hex64(fingerprint, "POLICY_PAYLOAD_FINGERPRINT_MALFORMED") + POLICY_FILE_SUFFIX
        for fingerprint in fingerprints
    )
    inventories = _require_referenced_entries(
        top, INVENTORIES_DIRECTORY_NAME, enumerate_directory, policy_directory, expected_names
    )
    bundles = _require_referenced_entries(
        top, MANIFEST_BUNDLES_DIRECTORY_NAME, enumerate_directory, policy_directory, expected_names
    )

    # -- pass 2: per revision, recompute and verify against revision N-1 ------
    state = _ChainState()
    revision_summaries: list[tuple[int, str, frozenset[str]]] = []
    previous_record = None
    for revision, data, record in revisions:
        counts = {name: 0 if previous_record is None else len(previous_record[name]) for name in _APS_LISTS}
        new_seam_evidence = record["seam_evidence"][counts["seam_evidence"] :]
        new_profiles = record["profiles"][counts["profiles"] :]
        new_approvals = record["approvals"][counts["approvals"] :]
        new_retirements = record["retirements"][counts["retirements"] :]

        revision_seam_evidence = dict(state.seam_evidence)
        for evidence in new_seam_evidence:
            if evidence["evidence_id"] in revision_seam_evidence:
                raise Cfg1PolicyError("POLICY_DUPLICATE_EVIDENCE_ID")
            revision_seam_evidence[evidence["evidence_id"]] = evidence

        new_facts: dict[str, ProfileFacts] = {}
        new_payloads: dict[str, tuple[str, bytes, bytes]] = {}
        for profile in new_profiles:
            profile_id = profile["profile_id"]
            fingerprint = profile["payload_fingerprint"]
            if profile_id in state.profiles or profile_id in new_facts:
                raise Cfg1PolicyError("POLICY_DUPLICATE_PROFILE_ID")
            if fingerprint in state.fingerprints:
                raise Cfg1PolicyError("POLICY_DUPLICATE_PAYLOAD_FINGERPRINT")
            state.fingerprints.add(fingerprint)
            file_name = fingerprint + POLICY_FILE_SUFFIX
            inventory_bytes = _read_policy_file(
                read_file, ntpath.join(inventories, file_name), MAX_INVENTORY_FILE_BYTES, budget
            )
            bundle_bytes = _read_policy_file(
                read_file, ntpath.join(bundles, file_name), MAX_MANIFEST_BUNDLE_FILE_BYTES, budget
            )
            facts = _facts_from_committed_bytes(fingerprint, inventory_bytes, bundle_bytes)
            _verify_profile_against_facts(profile, facts)
            new_facts[profile_id] = facts
            new_payloads[profile_id] = (fingerprint, inventory_bytes, bundle_bytes)

        # Approvals first appearing in N: each names a profile first
        # appearing in N, at most one per profile, verified against N-1.
        approved_now: set[str] = set()
        new_profile_ids = frozenset(new_facts)
        for approval in new_approvals:
            if approval["approval_id"] in state.approval_ids:
                raise Cfg1PolicyError("POLICY_DUPLICATE_APPROVAL_ID")
            state.approval_ids.add(approval["approval_id"])
            profile_id = approval["profile_id"]
            if profile_id in state.approved or profile_id in approved_now:
                raise Cfg1PolicyError("POLICY_DUPLICATE_APPROVAL_FOR_PROFILE")
            if profile_id not in new_facts:
                raise Cfg1PolicyError("POLICY_APPROVAL_PROFILE_NOT_IN_REVISION")
            try:
                _validate_approval(
                    approval,
                    candidate=new_facts[profile_id],
                    state=state,
                    revision_seam_evidence=revision_seam_evidence,
                    revision_profile_ids=new_profile_ids,
                )
            except (Cfg1FloorError, Cfg1ManifestError, Cfg1PayloadError):
                raise Cfg1PolicyError("POLICY_APPROVAL_UNDERIVABLE") from None
            approved_now.add(profile_id)
        if approved_now != set(new_facts):
            raise Cfg1PolicyError("POLICY_PROFILE_WITHOUT_APPROVAL")

        # Retirements first appearing in N: target eligible in N-1; terminal.
        retired_now: set[str] = set()
        for retirement in new_retirements:
            if retirement["retirement_id"] in state.retirement_ids:
                raise Cfg1PolicyError("POLICY_DUPLICATE_RETIREMENT_ID")
            state.retirement_ids.add(retirement["retirement_id"])
            profile_id = retirement["profile_id"]
            if profile_id in retired_now or profile_id in state.retired:
                raise Cfg1PolicyError("POLICY_DUPLICATE_RETIREMENT_FOR_PROFILE")
            if profile_id not in state.eligible:
                raise Cfg1PolicyError("POLICY_RETIREMENT_TARGET_NOT_ELIGIBLE")
            retired_now.add(profile_id)

        # Commit revision N.
        state.seam_evidence = revision_seam_evidence
        state.profiles.update(new_facts)
        state.profile_payloads.update(new_payloads)
        state.approved |= approved_now
        state.retired |= retired_now
        state.eligible = _eligible_profile_ids(record)
        revision_summaries.append((revision, hashlib.sha256(data).hexdigest(), state.eligible))
        previous_record = record

    head_sha256 = revision_summaries[-1][1]
    eligible_sorted = tuple(sorted(state.eligible))
    snapshot = Cfg1PolicySnapshot(
        _SEAL_KEY,
        aps_revision=head_revision,
        aps_head_sha256=head_sha256,
        policy_directory=policy_directory,
        eligible_profiles=tuple(
            _profile_view(profile_id, state.profiles[profile_id]) for profile_id in eligible_sorted
        ),
    )
    head_reference = _HeadReferenceMaterial(
        _SEAL_KEY,
        eligible_payloads=tuple((profile_id,) + state.profile_payloads[profile_id] for profile_id in eligible_sorted),
        present_ineligible_profile_ids=frozenset(state.profiles) - state.eligible,
        seam_fingerprints=frozenset(evidence["seam_fingerprint"] for evidence in state.seam_evidence.values()),
    )
    return _PolicyLoad(
        _SEAL_KEY, snapshot=snapshot, head_reference=head_reference, revisions=tuple(revision_summaries)
    )


def _eligible_profile_ids(record: dict) -> frozenset[str]:
    """PE-1 Sec. 9.6, computed from one revision's records; never stored."""
    approved = frozenset(
        approval["profile_id"]
        for approval in record["approvals"]
        if type(approval["consumer_contract"]) is str
        and approval["consumer_contract"] == CONSUMER_CONTRACT
        and type(approval["policy_revision"]) is str
        and approval["policy_revision"] == POLICY_REVISION
    )
    retired = frozenset(
        retirement["profile_id"]
        for retirement in record["retirements"]
        if type(retirement["consumer_contract"]) is str and retirement["consumer_contract"] == CONSUMER_CONTRACT
    )
    return approved - retired


def _reference_view_from_material(material: _HeadReferenceMaterial) -> ReferenceView:
    """A FRESH PE-2a :class:`ReferenceView` rebuilt from committed bytes."""
    if type(material) is not _HeadReferenceMaterial:
        raise Cfg1PolicyError("POLICY_REFERENCE_MALFORMED")
    eligible = []
    for profile_id, fingerprint, inventory_bytes, bundle_bytes in material.eligible_payloads:
        facts = _facts_from_committed_bytes(fingerprint, inventory_bytes, bundle_bytes)
        if facts.c5_reason is not None or facts.profile_id != profile_id:
            raise Cfg1PolicyError("POLICY_REFERENCE_MALFORMED")
        eligible.append(facts)
    return ReferenceView(
        eligible=eligible,
        present_ineligible_profile_ids=material.present_ineligible_profile_ids,
        seam_fingerprints=material.seam_fingerprints,
    )


# ---------------------------------------------------------------------------
# The ONE genuine load (import time)
# ---------------------------------------------------------------------------

#: ``<ROOT>\experiments\pi_harness_cfg1`` -- this module's own directory.
_CFG1_PACKAGE_DIRECTORY: str = str(Path(__file__).resolve().parent)

#: ``<CFG1 package dir>\pi_profile_policy``. The ONE genuine policy location.
_POLICY_DIR: str = ntpath.join(_CFG1_PACKAGE_DIRECTORY, POLICY_DIRECTORY_NAME)

_GENUINE_POLICY_LOAD: _PolicyLoad = _load_policy_directory(_POLICY_DIR)

#: The sealed HPP-1 policy snapshot of the committed chain's head.
SEALED_POLICY_SNAPSHOT: Cfg1PolicySnapshot = _GENUINE_POLICY_LOAD.snapshot


def head_reference_view() -> ReferenceView:
    """A FRESH PE-2a reference view of the committed head (Sec. 8.1, B-15).

    For floor classification of a NON-AUTHORITY candidate only. Rebuilt from
    the committed bytes on every call; takes no parameter and reloads nothing.
    """
    return _reference_view_from_material(_GENUINE_POLICY_LOAD.head_reference)
