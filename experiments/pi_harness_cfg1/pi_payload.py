"""``PI-PC1`` payload observation and ``PI-SC1`` seam projection (PE-2a).

Implements ``docs/PHASE_5F3B_PI_HARNESS_PROFILE_EVOLUTION_PE1_AMENDMENT.md``
Sec. 4 (the payload contract), Sec. 5.2 (the seam projection) and Sec. 7.1
(``canonical_json_bytes``). These are SHARED, PURE-OR-LEAF-INJECTED primitives:
PE-2a's static discovery uses them now; the PE-2b loader and PE-2c's canonical
proof P will consume them later. Nothing here is wired into P, the gate, L1,
L14 or L21A, and nothing here loads, grants or implies any profile authority.

**The walk is complete, no-follow, bounded and deterministic.** It records
EVERY entry below the payload root -- every directory (empty ones included),
every regular file of every type and extension, nested ``node_modules``, dot
files -- and ignores nothing. A reparse point anywhere, any entry that is not
a plain directory or a regular disk file, any open/enumeration/read failure,
a size that is not stable across its one-handle read, a grammar failure, a
case-fold collision, or any resource bound exceeded makes the payload
UNOBSERVABLE: the result then carries no inventory, no fingerprint and no
partial list.

**An on-disk name is validated BEFORE it becomes a path.** A name enumerated
from the Pi tree is Pi-controlled data; it reaches ``ntpath.join`` only after
it has passed the Sec. 4.2 segment grammar, so ``..``, a drive, an alternate
data stream, a device name or a trailing-dot alias can never be joined.

**Nothing here executes anything, writes anything, or parses Pi bytes.** File
bytes are hashed, counted and dropped by the leaf.
"""

from __future__ import annotations

import hashlib
import json
import ntpath
import re
from typing import Callable

from . import pi_fs_leaves
from .pi_fs_leaves import (
    CLASSIFICATION_DIRECTORY,
    CLASSIFICATION_MISSING,
    CLASSIFICATION_REGULAR_FILE,
    CLASSIFICATION_REPARSE_POINT,
    CLASSIFICATIONS,
    ENTRY_KIND_DIRECTORY,
    ENTRY_KIND_REPARSE,
    ENTRY_KINDS,
    DirectoryListing,
    PayloadFileRead,
)

# ---------------------------------------------------------------------------
# Frozen literals (PE-1 Sec. 3)
# ---------------------------------------------------------------------------

PAYLOAD_CONTRACT = "PI-PC1"
SEAM_CONTRACT = "PI-SC1"
PAYLOAD_INVENTORY_RECORD_KIND = "aido-pi-payload-inventory.v1"

PAYLOAD_FINGERPRINT_DOMAIN_TAG = b"aido.pi-payload.v1\x00"
SEAM_FINGERPRINT_DOMAIN_TAG = b"aido.pi-seam.v1\x00"

INVENTORY_KIND_DIR = "dir"
INVENTORY_KIND_FILE = "file"

# ---------------------------------------------------------------------------
# Frozen resource refusal bounds (PE-1 Sec. 4.4). Resource-safety limits, NOT
# product token limits. Exceeding one REFUSES; nothing is ever truncated.
# ---------------------------------------------------------------------------

MAX_PAYLOAD_ENTRIES = 250000
MAX_PAYLOAD_FILE_BYTES = 536870912
MAX_PAYLOAD_TOTAL_BYTES = 4294967296
MAX_RELATIVE_PATH_CHARS = 1024
MAX_PATH_SEGMENTS = 128
MAX_SEGMENT_CHARS = 255

#: Sec. 7.1: every integer in canonical data is exact, non-``bool``, in range.
MAX_CANONICAL_INT = 9007199254740991

# ---------------------------------------------------------------------------
# PI-SC1 (PE-1 Sec. 5.1): exactly these 20 relative paths. Derivation
# evidence ONLY -- never profile identity, never live eligibility.
# ---------------------------------------------------------------------------

PI_SC1_PATHS: tuple[str, ...] = (
    "package.json",
    "dist/cli.js",
    "dist/main.js",
    "dist/core/sdk.js",
    "dist/core/defaults.js",
    "dist/core/model-config.js",
    "dist/core/provider-composer.js",
    "dist/core/model-runtime.js",
    "dist/core/model-resolver.js",
    "dist/core/system-prompt.js",
    "dist/core/agent-session.js",
    "dist/modes/rpc/rpc-mode.js",
    "dist/modes/rpc/jsonl.js",
    "node_modules/@earendil-works/pi-ai/package.json",
    "node_modules/@earendil-works/pi-ai/dist/api/openai-completions.js",
    "node_modules/@earendil-works/pi-ai/dist/api/simple-options.js",
    "node_modules/@earendil-works/pi-ai/dist/models.js",
    "node_modules/@earendil-works/pi-agent-core/package.json",
    "node_modules/@earendil-works/pi-agent-core/dist/agent.js",
    "node_modules/@earendil-works/pi-agent-core/dist/agent-loop.js",
)

PI_SC1_ENTRY_COUNT = 20

#: Sec. 4.1 / 4.6 item 2: the launch target, a regular payload file.
LAUNCH_TARGET_PATH = "dist/cli.js"

# ---------------------------------------------------------------------------
# Closed refusal vocabulary for an unobservable payload (Sec. 4.3 step 4)
# ---------------------------------------------------------------------------

PAYLOAD_REPARSE_POINT = "PAYLOAD_REPARSE_POINT"
PAYLOAD_ENTRY_NOT_FILE_OR_DIRECTORY = "PAYLOAD_ENTRY_NOT_FILE_OR_DIRECTORY"
PAYLOAD_ENTRY_MISSING = "PAYLOAD_ENTRY_MISSING"
PAYLOAD_ENTRY_UNOBSERVABLE = "PAYLOAD_ENTRY_UNOBSERVABLE"
PAYLOAD_ENTRY_KIND_CHANGED = "PAYLOAD_ENTRY_KIND_CHANGED"
PAYLOAD_ENUMERATION_FAILED = "PAYLOAD_ENUMERATION_FAILED"
PAYLOAD_FILE_UNSTABLE = "PAYLOAD_FILE_UNSTABLE"
PAYLOAD_PATH_GRAMMAR = "PAYLOAD_PATH_GRAMMAR"
PAYLOAD_PATH_BOUND_EXCEEDED = "PAYLOAD_PATH_BOUND_EXCEEDED"
PAYLOAD_CASE_FOLD_COLLISION = "PAYLOAD_CASE_FOLD_COLLISION"
PAYLOAD_ENTRY_BOUND_EXCEEDED = "PAYLOAD_ENTRY_BOUND_EXCEEDED"
PAYLOAD_FILE_BYTES_EXCEEDED = "PAYLOAD_FILE_BYTES_EXCEEDED"
PAYLOAD_TOTAL_BYTES_EXCEEDED = "PAYLOAD_TOTAL_BYTES_EXCEEDED"

PAYLOAD_REFUSAL_CODES: frozenset[str] = frozenset(
    {
        PAYLOAD_REPARSE_POINT,
        PAYLOAD_ENTRY_NOT_FILE_OR_DIRECTORY,
        PAYLOAD_ENTRY_MISSING,
        PAYLOAD_ENTRY_UNOBSERVABLE,
        PAYLOAD_ENTRY_KIND_CHANGED,
        PAYLOAD_ENUMERATION_FAILED,
        PAYLOAD_FILE_UNSTABLE,
        PAYLOAD_PATH_GRAMMAR,
        PAYLOAD_PATH_BOUND_EXCEEDED,
        PAYLOAD_CASE_FOLD_COLLISION,
        PAYLOAD_ENTRY_BOUND_EXCEEDED,
        PAYLOAD_FILE_BYTES_EXCEEDED,
        PAYLOAD_TOTAL_BYTES_EXCEEDED,
    }
)


class Cfg1PayloadError(Exception):
    """A malformed input, inventory or leaf output. Closed reason code only.

    Never carries a path, a name, a digest or leaf text: an inventory built
    from Pi-controlled names must not echo those names into an exception.
    """

    def __init__(self, reason_code: str) -> None:
        super().__init__(f"cfg1 pi payload refused: {reason_code}")
        self.reason_code = reason_code


class _PayloadRefusal(Exception):
    """Internal control flow only: one anticipated Sec. 4.3 refusal."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


# ---------------------------------------------------------------------------
# canonical_json_bytes (PE-1 Sec. 7.1)
# ---------------------------------------------------------------------------


def _require_canonical_value(value: object, depth: int) -> None:
    if depth > 64:
        raise Cfg1PayloadError("CANONICAL_VALUE_TOO_DEEP")
    kind = type(value)
    if value is None or kind is bool:
        return
    if kind is int:
        if not 0 <= value <= MAX_CANONICAL_INT:
            raise Cfg1PayloadError("CANONICAL_INT_OUT_OF_RANGE")
        return
    if kind is str:
        try:
            value.encode("utf-8")
        except UnicodeEncodeError:
            raise Cfg1PayloadError("CANONICAL_STR_LONE_SURROGATE") from None
        return
    if kind is list:
        for item in value:
            _require_canonical_value(item, depth + 1)
        return
    if kind is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise Cfg1PayloadError("CANONICAL_KEY_NOT_STR")
            _require_canonical_value(key, depth + 1)
            _require_canonical_value(item, depth + 1)
        return
    raise Cfg1PayloadError("CANONICAL_VALUE_TYPE")


def canonical_json_bytes(value: object) -> bytes:
    """The ONE canonical encoding (Sec. 7.1), over its restricted value domain.

    ``dict`` with ``str`` keys, ``list``, ``str`` (no lone surrogate), ``int``
    (exact, not ``bool``, ``0 .. 2**53-1``), ``bool``, ``None``. No float,
    tuple, subclass or other type is accepted -- they refuse, never coerce.
    """
    _require_canonical_value(value, 0)
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


# ---------------------------------------------------------------------------
# Relative-path grammar (PE-1 Sec. 4.2)
# ---------------------------------------------------------------------------

_FORBIDDEN_SEGMENT_CHARACTERS = frozenset('\\/:*?"<>|')
_RESERVED_STEMS = frozenset(
    {"con", "prn", "aux", "nul"}
    | {f"com{digit}" for digit in range(10)}
    | {f"lpt{digit}" for digit in range(10)}
)
_HEX64 = re.compile(r"[0-9a-f]{64}")


def _segment_grammar_ok(segment: object) -> bool:
    """The Sec. 4.2 segment rules other than its length bound."""
    if type(segment) is not str or not segment:
        return False
    if segment in (".", ".."):
        return False
    for character in segment:
        point = ord(character)
        if point <= 0x1F or 0x7F <= point <= 0x9F or 0xD800 <= point <= 0xDFFF:
            return False
        if character in _FORBIDDEN_SEGMENT_CHARACTERS:
            return False
    if segment.endswith((".", " ")):
        return False
    stem = segment.split(".", 1)[0]
    return not (stem.isascii() and stem.lower() in _RESERVED_STEMS)


def segment_is_valid(segment: object) -> bool:
    """One payload path segment, Sec. 4.2 exactly (length bound included)."""
    return (
        type(segment) is str
        and 1 <= len(segment) <= MAX_SEGMENT_CHARS
        and _segment_grammar_ok(segment)
    )


def relative_path_is_valid(path: object) -> bool:
    """One payload relative path, Sec. 4.2 exactly."""
    if type(path) is not str or not 1 <= len(path) <= MAX_RELATIVE_PATH_CHARS:
        return False
    segments = path.split("/")
    if not 1 <= len(segments) <= MAX_PATH_SEGMENTS:
        return False
    return all(segment_is_valid(segment) for segment in segments)


def _parent_path(path: str) -> str | None:
    """The proper parent of a validated relative path, ``None`` for top level."""
    index = path.rfind("/")
    return None if index < 0 else path[:index]


def last_segment(path: str) -> str:
    """The last segment of a validated relative path."""
    return path[path.rfind("/") + 1 :]


# ---------------------------------------------------------------------------
# The canonical inventory (PE-1 Sec. 4.5)
# ---------------------------------------------------------------------------


class PayloadInventory:
    """A validated ``PI-PC1`` canonical inventory and its payload fingerprint.

    Constructible only through :func:`inventory_from_entries` /
    :func:`inventory_from_record`, which enforce every Sec. 4.2/4.4/4.5 rule
    (grammar, strict code-point order, no duplicate, case-fold uniqueness,
    tree closure, exact types, bounds). Immutable. ``entries`` holds
    ``("dir", path)`` and ``("file", path, sha256, size)`` tuples.
    """

    __slots__ = ("entries", "canonical_bytes", "payload_fingerprint", "_index")

    def __init__(self, key: object, entries: tuple, canonical: bytes, index: dict) -> None:
        if key is not _INVENTORY_KEY:
            raise Cfg1PayloadError("INVENTORY_NOT_VALIDATED")
        object.__setattr__(self, "entries", entries)
        object.__setattr__(self, "canonical_bytes", canonical)
        object.__setattr__(
            self,
            "payload_fingerprint",
            hashlib.sha256(PAYLOAD_FINGERPRINT_DOMAIN_TAG + canonical).hexdigest(),
        )
        object.__setattr__(self, "_index", index)

    def __setattr__(self, name: str, value: object) -> None:  # noqa: D105
        raise Cfg1PayloadError("INVENTORY_IS_IMMUTABLE")

    def __delattr__(self, name: str) -> None:  # noqa: D105
        raise Cfg1PayloadError("INVENTORY_IS_IMMUTABLE")

    def __repr__(self) -> str:  # noqa: D105 - paths are never rendered
        return f"{type(self).__name__}(entries={len(self.entries)})"

    def entry(self, path: str) -> tuple | None:
        """The entry at an exact relative path, or ``None``."""
        if type(path) is not str:
            return None
        return self._index.get(path)

    def is_file(self, path: str) -> bool:
        found = self.entry(path)
        return found is not None and found[0] == INVENTORY_KIND_FILE

    def is_dir(self, path: str) -> bool:
        found = self.entry(path)
        return found is not None and found[0] == INVENTORY_KIND_DIR

    def to_record(self) -> dict:
        """A fresh canonical inventory record (a new object on every call)."""
        return _inventory_record(self.entries)


_INVENTORY_KEY = object()


def _entry_record(entry: tuple) -> dict:
    if entry[0] == INVENTORY_KIND_DIR:
        return {"kind": INVENTORY_KIND_DIR, "path": entry[1]}
    return {"kind": INVENTORY_KIND_FILE, "path": entry[1], "sha256": entry[2], "size": entry[3]}


def _inventory_record(entries: tuple) -> dict:
    return {
        "record_kind": PAYLOAD_INVENTORY_RECORD_KIND,
        "payload_contract": PAYLOAD_CONTRACT,
        "entries": [_entry_record(entry) for entry in entries],
    }


def _require_entry_shape(entry: object) -> tuple:
    if type(entry) is not tuple or not entry:
        raise Cfg1PayloadError("INVENTORY_ENTRY_MALFORMED")
    kind = entry[0]
    if type(kind) is not str:
        raise Cfg1PayloadError("INVENTORY_ENTRY_MALFORMED")
    if kind == INVENTORY_KIND_DIR:
        if len(entry) != 2:
            raise Cfg1PayloadError("INVENTORY_ENTRY_MALFORMED")
    elif kind == INVENTORY_KIND_FILE:
        if len(entry) != 4:
            raise Cfg1PayloadError("INVENTORY_ENTRY_MALFORMED")
        sha256, size = entry[2], entry[3]
        if type(sha256) is not str or _HEX64.fullmatch(sha256) is None:
            raise Cfg1PayloadError("INVENTORY_DIGEST_MALFORMED")
        if type(size) is not int or not 0 <= size <= MAX_PAYLOAD_FILE_BYTES:
            raise Cfg1PayloadError("INVENTORY_SIZE_OUT_OF_BOUNDS")
    else:
        raise Cfg1PayloadError("INVENTORY_ENTRY_KIND_UNKNOWN")
    if not relative_path_is_valid(entry[1]):
        raise Cfg1PayloadError("INVENTORY_PATH_GRAMMAR")
    return entry


def inventory_from_entries(entries: object) -> PayloadInventory:
    """Validate an ordered entry tuple into a :class:`PayloadInventory`.

    The entries must ALREADY be in strict ascending code-point order of their
    paths (equivalently, UTF-8 byte order); this function never sorts, so an
    out-of-order or duplicated list refuses rather than being repaired.
    """
    if type(entries) is not tuple:
        raise Cfg1PayloadError("INVENTORY_ENTRIES_MALFORMED")
    if len(entries) > MAX_PAYLOAD_ENTRIES:
        raise Cfg1PayloadError("INVENTORY_ENTRY_BOUND_EXCEEDED")
    index: dict[str, tuple] = {}
    folded: set[str] = set()
    total = 0
    previous: str | None = None
    for raw in entries:
        entry = _require_entry_shape(raw)
        path = entry[1]
        if previous is not None and not previous < path:
            raise Cfg1PayloadError("INVENTORY_NOT_STRICTLY_ORDERED")
        previous = path
        case_folded = path.casefold()
        if case_folded in folded:
            raise Cfg1PayloadError("INVENTORY_CASE_FOLD_COLLISION")
        folded.add(case_folded)
        if entry[0] == INVENTORY_KIND_FILE:
            total += entry[3]
            if total > MAX_PAYLOAD_TOTAL_BYTES:
                raise Cfg1PayloadError("INVENTORY_TOTAL_BYTES_EXCEEDED")
        index[path] = entry
    # Tree closure: every proper ancestor is a ``dir`` entry -- which also
    # means no entry can be a descendant of a ``file`` entry.
    for path in index:
        parent = _parent_path(path)
        while parent is not None:
            found = index.get(parent)
            if found is None or found[0] != INVENTORY_KIND_DIR:
                raise Cfg1PayloadError("INVENTORY_TREE_NOT_CLOSED")
            parent = _parent_path(parent)
    canonical = canonical_json_bytes(_inventory_record(entries))
    return PayloadInventory(_INVENTORY_KEY, entries, canonical, index)


_INVENTORY_RECORD_KEYS = ("entries", "payload_contract", "record_kind")
_DIR_ENTRY_KEYS = ("kind", "path")
_FILE_ENTRY_KEYS = ("kind", "path", "sha256", "size")


def inventory_from_record(record: object) -> PayloadInventory:
    """Strictly validate a canonical inventory RECORD (closed key sets, exact types)."""
    if type(record) is not dict or tuple(sorted(record)) != _INVENTORY_RECORD_KEYS:
        raise Cfg1PayloadError("INVENTORY_RECORD_KEYS")
    if type(record["record_kind"]) is not str or record["record_kind"] != PAYLOAD_INVENTORY_RECORD_KIND:
        raise Cfg1PayloadError("INVENTORY_RECORD_KIND")
    if type(record["payload_contract"]) is not str or record["payload_contract"] != PAYLOAD_CONTRACT:
        raise Cfg1PayloadError("INVENTORY_PAYLOAD_CONTRACT")
    raw_entries = record["entries"]
    if type(raw_entries) is not list:
        raise Cfg1PayloadError("INVENTORY_ENTRIES_MALFORMED")
    if len(raw_entries) > MAX_PAYLOAD_ENTRIES:
        raise Cfg1PayloadError("INVENTORY_ENTRY_BOUND_EXCEEDED")
    entries = []
    for raw in raw_entries:
        if type(raw) is not dict:
            raise Cfg1PayloadError("INVENTORY_ENTRY_MALFORMED")
        keys = tuple(sorted(raw))
        kind = raw.get("kind")
        if type(kind) is not str:
            raise Cfg1PayloadError("INVENTORY_ENTRY_MALFORMED")
        if kind == INVENTORY_KIND_DIR and keys == _DIR_ENTRY_KEYS:
            entries.append((INVENTORY_KIND_DIR, raw["path"]))
        elif kind == INVENTORY_KIND_FILE and keys == _FILE_ENTRY_KEYS:
            entries.append((INVENTORY_KIND_FILE, raw["path"], raw["sha256"], raw["size"]))
        else:
            raise Cfg1PayloadError("INVENTORY_ENTRY_MALFORMED")
    return inventory_from_entries(tuple(entries))


# ---------------------------------------------------------------------------
# The walk (PE-1 Sec. 4.3)
# ---------------------------------------------------------------------------


class PayloadLeaves:
    """The walk's injectable leaf surface -- and, by construction, all of it.

    ``enumerate_directory(path, max_entries) -> DirectoryListing`` and
    ``read_file(path, max_bytes) -> PayloadFileRead``. Neither can create a
    process; the genuine binding is :func:`genuine_payload_leaves`.
    """

    __slots__ = ("enumerate_directory", "read_file")

    def __init__(
        self,
        *,
        enumerate_directory: Callable[[str, int], DirectoryListing],
        read_file: Callable[[str, int], PayloadFileRead],
    ) -> None:
        if not callable(enumerate_directory) or not callable(read_file):
            raise Cfg1PayloadError("MALFORMED_PAYLOAD_LEAVES")
        object.__setattr__(self, "enumerate_directory", enumerate_directory)
        object.__setattr__(self, "read_file", read_file)

    def __setattr__(self, name: str, value: object) -> None:  # noqa: D105
        raise Cfg1PayloadError("PAYLOAD_LEAVES_ARE_IMMUTABLE")

    def __repr__(self) -> str:  # noqa: D105
        return f"{type(self).__name__}(<bound>)"


def genuine_payload_leaves() -> PayloadLeaves:
    """The ONE genuine walk-leaf binding. Takes no parameter."""
    return PayloadLeaves(
        enumerate_directory=pi_fs_leaves.enumerate_directory_no_follow,
        read_file=pi_fs_leaves.read_payload_file_digest,
    )


class PayloadObservation:
    """The walk's ONE result: complete with an inventory, or refused with none.

    Complete: ``complete is True``, ``refusal_code is None``, ``inventory`` a
    :class:`PayloadInventory`. Refused: ``complete is False``, ``refusal_code``
    in :data:`PAYLOAD_REFUSAL_CODES`, ``inventory is None`` -- never a partial
    list and never a fingerprint.
    """

    __slots__ = ("complete", "refusal_code", "inventory")

    def __init__(
        self,
        key: object,
        *,
        complete: bool,
        refusal_code: str | None,
        inventory: PayloadInventory | None,
    ) -> None:
        if key is not _OBSERVATION_KEY:
            raise Cfg1PayloadError("OBSERVATION_NOT_PRODUCED_BY_WALK")
        object.__setattr__(self, "complete", complete)
        object.__setattr__(self, "refusal_code", refusal_code)
        object.__setattr__(self, "inventory", inventory)

    def __setattr__(self, name: str, value: object) -> None:  # noqa: D105
        raise Cfg1PayloadError("OBSERVATION_IS_IMMUTABLE")

    def __repr__(self) -> str:  # noqa: D105
        return f"{type(self).__name__}(complete={self.complete!r}, refusal_code={self.refusal_code!r})"

    @property
    def payload_fingerprint(self) -> str | None:
        return None if self.inventory is None else self.inventory.payload_fingerprint


_OBSERVATION_KEY = object()


def _require_listing(listing: object) -> DirectoryListing:
    if type(listing) is not DirectoryListing:
        raise Cfg1PayloadError("MALFORMED_LEAF_LISTING")
    if type(listing.classification) is not str or listing.classification not in CLASSIFICATIONS:
        raise Cfg1PayloadError("MALFORMED_LEAF_LISTING")
    if type(listing.complete) is not bool or type(listing.over_budget) is not bool:
        raise Cfg1PayloadError("MALFORMED_LEAF_LISTING")
    if listing.complete:
        if listing.over_budget or listing.classification != CLASSIFICATION_DIRECTORY:
            raise Cfg1PayloadError("MALFORMED_LEAF_LISTING")
        if type(listing.entries) is not tuple:
            raise Cfg1PayloadError("MALFORMED_LEAF_LISTING")
        for item in listing.entries:
            if (
                type(item) is not tuple
                or len(item) != 2
                or type(item[1]) is not str
                or item[1] not in ENTRY_KINDS
            ):
                raise Cfg1PayloadError("MALFORMED_LEAF_LISTING")
    elif listing.entries is not None:
        raise Cfg1PayloadError("MALFORMED_LEAF_LISTING")
    return listing


def _require_file_read(read: object) -> PayloadFileRead:
    if type(read) is not PayloadFileRead:
        raise Cfg1PayloadError("MALFORMED_LEAF_READ")
    if type(read.classification) is not str or read.classification not in CLASSIFICATIONS:
        raise Cfg1PayloadError("MALFORMED_LEAF_READ")
    if type(read.within_bound) is not bool or type(read.stable) is not bool:
        raise Cfg1PayloadError("MALFORMED_LEAF_READ")
    if read.within_bound and read.stable:
        if read.classification != CLASSIFICATION_REGULAR_FILE:
            raise Cfg1PayloadError("MALFORMED_LEAF_READ")
        if type(read.size) is not int or read.size < 0:
            raise Cfg1PayloadError("MALFORMED_LEAF_READ")
        if type(read.sha256) is not str or _HEX64.fullmatch(read.sha256) is None:
            raise Cfg1PayloadError("MALFORMED_LEAF_READ")
    return read


def _refuse_for_classification(classification: str) -> None:
    if classification == CLASSIFICATION_REPARSE_POINT:
        raise _PayloadRefusal(PAYLOAD_REPARSE_POINT)
    if classification == CLASSIFICATION_MISSING:
        raise _PayloadRefusal(PAYLOAD_ENTRY_MISSING)
    if classification in (CLASSIFICATION_DIRECTORY, CLASSIFICATION_REGULAR_FILE):
        raise _PayloadRefusal(PAYLOAD_ENTRY_KIND_CHANGED)
    raise _PayloadRefusal(PAYLOAD_ENTRY_UNOBSERVABLE)


def _validated_payload_root(payload_root: object) -> str:
    if type(payload_root) is not str or not payload_root:
        raise Cfg1PayloadError("MALFORMED_PAYLOAD_ROOT")
    drive, _rest = ntpath.splitdrive(payload_root)
    if not drive or not ntpath.isabs(payload_root):
        raise Cfg1PayloadError("MALFORMED_PAYLOAD_ROOT")
    return payload_root


def _walk(payload_root: str, leaves: PayloadLeaves) -> tuple:
    collected: list[tuple] = []
    folded: set[str] = set()
    total_bytes = 0
    # (segments-tuple, absolute lexical path); depth first, iterative.
    pending: list[tuple[tuple[str, ...], str]] = [((), payload_root)]
    while pending:
        segments, absolute = pending.pop()
        budget = MAX_PAYLOAD_ENTRIES - len(collected)
        listing = _require_listing(leaves.enumerate_directory(absolute, budget))
        if listing.classification != CLASSIFICATION_DIRECTORY:
            _refuse_for_classification(listing.classification)
        if listing.over_budget:
            raise _PayloadRefusal(PAYLOAD_ENTRY_BOUND_EXCEEDED)
        if not listing.complete:
            raise _PayloadRefusal(PAYLOAD_ENUMERATION_FAILED)
        for name, kind in listing.entries:
            # The name is Pi-controlled: grammar FIRST, path second.
            if type(name) is not str or not _segment_grammar_ok(name):
                raise _PayloadRefusal(PAYLOAD_PATH_GRAMMAR)
            if len(name) > MAX_SEGMENT_CHARS:
                raise _PayloadRefusal(PAYLOAD_PATH_BOUND_EXCEEDED)
            child_segments = segments + (name,)
            if len(child_segments) > MAX_PATH_SEGMENTS:
                raise _PayloadRefusal(PAYLOAD_PATH_BOUND_EXCEEDED)
            relative = "/".join(child_segments)
            if len(relative) > MAX_RELATIVE_PATH_CHARS:
                raise _PayloadRefusal(PAYLOAD_PATH_BOUND_EXCEEDED)
            case_folded = relative.casefold()
            if case_folded in folded:
                raise _PayloadRefusal(PAYLOAD_CASE_FOLD_COLLISION)
            folded.add(case_folded)
            if len(collected) >= MAX_PAYLOAD_ENTRIES:
                raise _PayloadRefusal(PAYLOAD_ENTRY_BOUND_EXCEEDED)
            if kind == ENTRY_KIND_REPARSE:
                raise _PayloadRefusal(PAYLOAD_REPARSE_POINT)
            child_absolute = ntpath.join(absolute, name)
            if kind == ENTRY_KIND_DIRECTORY:
                collected.append((INVENTORY_KIND_DIR, relative))
                pending.append((child_segments, child_absolute))
                continue
            remaining_total = MAX_PAYLOAD_TOTAL_BYTES - total_bytes
            cap = min(MAX_PAYLOAD_FILE_BYTES, remaining_total)
            read = _require_file_read(leaves.read_file(child_absolute, cap))
            if read.classification != CLASSIFICATION_REGULAR_FILE:
                _refuse_for_classification(read.classification)
            if not read.within_bound:
                raise _PayloadRefusal(
                    PAYLOAD_TOTAL_BYTES_EXCEEDED
                    if cap < MAX_PAYLOAD_FILE_BYTES
                    else PAYLOAD_FILE_BYTES_EXCEEDED
                )
            if not read.stable:
                raise _PayloadRefusal(PAYLOAD_FILE_UNSTABLE)
            if read.size > cap:
                raise Cfg1PayloadError("MALFORMED_LEAF_READ")
            total_bytes += read.size
            collected.append((INVENTORY_KIND_FILE, relative, read.sha256, read.size))
    collected.sort(key=lambda entry: entry[1])
    return tuple(collected)


def observe_payload(payload_root: str, *, leaves: PayloadLeaves) -> PayloadObservation:
    """ONE complete ``PI-PC1`` observation of the tree below ``payload_root``.

    Anticipated Sec. 4.3 refusals are RETURNED (no inventory, no fingerprint,
    no partial list). A malformed input or leaf output raises
    :class:`Cfg1PayloadError`; a leaf that cannot complete its own handle
    protocol raises its own error. Either way nothing partial escapes.
    Uncached: every call re-enumerates and re-reads everything.
    """
    root = _validated_payload_root(payload_root)
    if type(leaves) is not PayloadLeaves:
        raise Cfg1PayloadError("MALFORMED_PAYLOAD_LEAVES")
    try:
        entries = _walk(root, leaves)
    except _PayloadRefusal as refusal:
        return PayloadObservation(
            _OBSERVATION_KEY, complete=False, refusal_code=refusal.reason_code, inventory=None
        )
    inventory = inventory_from_entries(entries)
    return PayloadObservation(
        _OBSERVATION_KEY, complete=True, refusal_code=None, inventory=inventory
    )


# ---------------------------------------------------------------------------
# PI-SC1 projection (PE-1 Sec. 5.2) -- derivation evidence only
# ---------------------------------------------------------------------------


def project_seam_digests(inventory: PayloadInventory) -> dict[str, str] | None:
    """``{p: inventory[p].sha256 for p in PI-SC1}``, or ``None`` unless all 20 are files."""
    if type(inventory) is not PayloadInventory:
        raise Cfg1PayloadError("MALFORMED_INVENTORY")
    if len(PI_SC1_PATHS) != PI_SC1_ENTRY_COUNT:
        raise Cfg1PayloadError("SEAM_SELECTOR_INCOMPLETE")
    digests: dict[str, str] = {}
    for path in PI_SC1_PATHS:
        entry = inventory.entry(path)
        if entry is None or entry[0] != INVENTORY_KIND_FILE:
            return None
        digests[path] = entry[2]
    return digests


def compute_seam_fingerprint(seam_digests: object) -> str:
    """Sec. 5.2: the domain-separated fingerprint of exactly the 20 seam digests."""
    if type(seam_digests) is not dict or set(seam_digests) != set(PI_SC1_PATHS):
        raise Cfg1PayloadError("SEAM_DIGESTS_MALFORMED")
    for path in PI_SC1_PATHS:
        digest = seam_digests[path]
        if type(digest) is not str or _HEX64.fullmatch(digest) is None:
            raise Cfg1PayloadError("SEAM_DIGESTS_MALFORMED")
    body = canonical_json_bytes(
        {"seam_contract": SEAM_CONTRACT, "seam_digests": dict(seam_digests)}
    )
    return hashlib.sha256(SEAM_FINGERPRINT_DOMAIN_TAG + body).hexdigest()


def is_lowercase_hex64(value: object) -> bool:
    """``type(value) is str`` and ``fullmatch [0-9a-f]{64}``."""
    return type(value) is str and _HEX64.fullmatch(value) is not None
