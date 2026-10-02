"""Static, non-executing Pi profile discovery and its candidate staging (PE-2a).

Implements the discovery surface of
``docs/PHASE_5F3B_PI_HARNESS_PROFILE_EVOLUTION_PE1_AMENDMENT.md`` Sec. 26.1
and its ONE write boundary, Sec. 9.10 (R1, B12).

**What discovery does.** Reads exactly one ambient name, ``PATH``, as its only
install-selection input; selects ``node.exe`` and the Pi package root with the
UNCHANGED P1 first-admissible-candidate functions of :mod:`pi_identity`
(nothing is executed -- the selected candidate is only observed); performs two
complete ``PI-PC1`` observations and refuses unless their canonical bytes are
identical; captures every ``package.json`` and binds each to its inventory
entry by size and SHA-256; derives the profile facts; observes declared
exposure absence; re-proves the two P1 identities; and only then stages
candidate artifacts.

**What discovery never does.** It starts no process; runs no Node, Pi, npm or
``pi --version``; imports or evaluates no Pi JavaScript; opens no socket;
reads no credential, endpoint or other environment name; invokes no model;
selects no policy; and never compares a version with anything.

**The floor (PE-2b, B-15).** After the P2R re-proof, the candidate's
mechanical floor is computed by the ACCEPTED PE-2a ``classify_floor`` (by
identity) over the PE-2b loader-owned ``head_reference_view()`` -- a fresh
reference view rebuilt from the committed policy chain the loader validated at
its own import, from its own ``__file__``-derived directory. Discovery passes
no path, snapshot, view or classifier anywhere and reads no policy itself. If
the committed reference view cannot be obtained, or the classifier refuses or
returns anything outside the closed floor vocabulary, discovery REFUSES and
stages nothing: there is no ``NOT_COMPUTED`` fallback and no default view.
The floor is classification only; the candidate stays NON-AUTHORITY.

**The staging boundary is fixed and NON-AUTHORITY.** Its only filesystem
mutation is inside ``<CFG1 package dir>\\pi_profile_candidates``, derived from
THIS module's own ``__file__`` -- never from an argument, a command-line
option, an environment variable, the current directory or Pi content. The
entry points accept no output path, directory or file name of any kind. The
three files are created exclusively, candidate last; nothing is overwritten,
appended, truncated, renamed, swapped, cleaned up or removed, and a
mid-sequence failure leaves earlier files as residue. No runtime module, no
policy loader and no PE-2a module other than this writer refers to that
directory, and nothing reads a staged file back as authority.
"""

from __future__ import annotations

import ntpath
import os
import re
import sys
from collections.abc import Mapping
from pathlib import Path

from .pi_fs_leaves import (
    CLASSIFICATION_DIRECTORY,
    CLASSIFICATION_MISSING,
    CLASSIFICATION_REGULAR_FILE,
    CLASSIFICATIONS,
    NoFollowObservation,
    PayloadFileRead,
    read_payload_file_bytes,
)
from .pi_identity import (
    PiProofLeaves,
    _identity_still_holds,
    _path_entries,
    _resolve_node,
    _resolve_package_root,
    genuine_pi_proof_leaves,
)
from . import pi_manifest, pi_profile_floor
from .pi_manifest import (
    EXPOSURE_PRESENT_OR_UNOBSERVABLE,
    build_manifest_bundle,
    bundle_manifest_paths,
    observe_exposure_absence,
)
from .pi_payload import (
    PAYLOAD_CONTRACT,
    SEAM_CONTRACT,
    PayloadLeaves,
    genuine_payload_leaves,
    is_lowercase_hex64,
    observe_payload,
)
from .pi_profile_floor import (
    FLOOR_CLASSES,
    ProfileFacts,
    ReferenceView,
    classify_floor,
    compute_profile_facts,
    policy_file_bytes,
)

# ---------------------------------------------------------------------------
# Literals
# ---------------------------------------------------------------------------

DISCOVERY_TOOL_REVISION = "PE-2b"
CANDIDATE_RECORD_KIND = "aido-pi-profile-candidate.v1"
CANDIDATE_AUTHORITY = "NON_AUTHORITY_CANDIDATE"
APPROVABILITY_FLOOR_MET = "APPROVABILITY_FLOOR_MET"
APPROVABILITY_C5_UNDER_HPP1 = "C5_UNDER_HPP1"
EXPOSURE_ABSENCE_NOT_OBSERVED = "NOT_OBSERVED"

#: PE-1 Sec. 3 (B7): bounded authority wording carried by every candidate.
PI_PROFILE_AUTHORITY_SCOPE = "PI_PACKAGE_PAYLOAD_AND_DECLARED_RESOLUTION_BOUNDARY"
PI_EXTERNAL_RUNTIME_RESIDUAL = "NOT_IDENTIFIED_BY_PROFILE"

STAGING_DIRECTORY_NAME = "pi_profile_candidates"
INVENTORY_SUFFIX = ".inventory.json"
MANIFEST_BUNDLE_SUFFIX = ".manifest_bundle.json"
CANDIDATE_SUFFIX = ".candidate.json"

#: Fixed creation order: candidate LAST.
_WRITE_ORDER: tuple[str, str, str] = (INVENTORY_SUFFIX, MANIFEST_BUNDLE_SUFFIX, CANDIDATE_SUFFIX)

STAGING_FILENAME_GRAMMAR = re.compile(r"^[0-9a-f]{64}\.(candidate|inventory|manifest_bundle)\.json$")

#: ``<ROOT>\experiments\pi_harness_cfg1`` -- this module's own directory, the
#: same derivation :mod:`stage_output` uses for its package directory.
_CFG1_PACKAGE_DIRECTORY: str = str(Path(__file__).resolve().parent)

#: ``<CFG1 package dir>\pi_profile_candidates``. The ONE staging location.
_STAGING_DIRECTORY: str = ntpath.join(_CFG1_PACKAGE_DIRECTORY, STAGING_DIRECTORY_NAME)

# -- console / outcome codes (closed) ---------------------------------------

DISCOVERY_CANDIDATE_STAGED = "DISCOVERY_CANDIDATE_STAGED"
DISCOVERY_REFUSED_ARGUMENTS = "DISCOVERY_REFUSED_ARGUMENTS"
DISCOVERY_REFUSED_PI_RESOLUTION_FAILED = "DISCOVERY_REFUSED_PI_RESOLUTION_FAILED"
DISCOVERY_REFUSED_PAYLOAD_UNPROVEN = "DISCOVERY_REFUSED_PAYLOAD_UNPROVEN"
DISCOVERY_REFUSED_PAYLOAD_CHANGED_BETWEEN_WALKS = "DISCOVERY_REFUSED_PAYLOAD_CHANGED_BETWEEN_WALKS"
DISCOVERY_REFUSED_MANIFEST_CAPTURE_UNBOUND = "DISCOVERY_REFUSED_MANIFEST_CAPTURE_UNBOUND"
DISCOVERY_REFUSED_ARTIFACT_BOUND_EXCEEDED = "DISCOVERY_REFUSED_ARTIFACT_BOUND_EXCEEDED"
DISCOVERY_REFUSED_IDENTITY_DRIFTED = "DISCOVERY_REFUSED_IDENTITY_DRIFTED"
DISCOVERY_REFUSED_STAGING_TOPOLOGY = "DISCOVERY_REFUSED_STAGING_TOPOLOGY"
DISCOVERY_REFUSED_STAGING_TARGET_OCCUPIED = "DISCOVERY_REFUSED_STAGING_TARGET_OCCUPIED"
DISCOVERY_STAGING_WRITE_FAILED_RESIDUE_LEFT = "DISCOVERY_STAGING_WRITE_FAILED_RESIDUE_LEFT"
DISCOVERY_REFUSED_UNEXPECTED_FAILURE = "DISCOVERY_REFUSED_UNEXPECTED_FAILURE"
DISCOVERY_REFUSED_POLICY_REFERENCE_UNAVAILABLE = "DISCOVERY_REFUSED_POLICY_REFERENCE_UNAVAILABLE"
DISCOVERY_REFUSED_FLOOR_UNCLASSIFIABLE = "DISCOVERY_REFUSED_FLOOR_UNCLASSIFIABLE"


class Cfg1DiscoveryError(Exception):
    """A malformed discovery input or leaf output. Closed reason code only."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(f"cfg1 pi profile discovery refused: {reason_code}")
        self.reason_code = reason_code


class DiscoveryOutcome:
    """What one discovery invocation did. Carries no absolute path.

    ``staged_files`` names (never paths) the staging files this invocation
    created, in creation order -- on a mid-sequence failure, exactly the
    residue it left. ``console_lines`` are bounded diagnostic lines: closed
    codes, 64-hex identifiers and grammar-validated payload-relative paths
    only -- never a raw dependency key, a manifest value or an absolute path.
    """

    __slots__ = ("code", "payload_fingerprint", "staged_files", "console_lines")

    def __init__(
        self,
        code: str,
        payload_fingerprint: str | None,
        staged_files: tuple[str, ...],
        console_lines: tuple[str, ...],
    ) -> None:
        object.__setattr__(self, "code", code)
        object.__setattr__(self, "payload_fingerprint", payload_fingerprint)
        object.__setattr__(self, "staged_files", staged_files)
        object.__setattr__(self, "console_lines", console_lines)

    def __setattr__(self, name: str, value: object) -> None:  # noqa: D105
        raise AttributeError("DiscoveryOutcome is immutable")

    def __repr__(self) -> str:  # noqa: D105
        return f"{type(self).__name__}({self.code!r})"


class _Refused(Exception):
    def __init__(self, code: str, *detail: str) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail


# ---------------------------------------------------------------------------
# The candidate record (its schema is a PE-2a detail: it is never authority)
# ---------------------------------------------------------------------------


def build_candidate_record(facts: ProfileFacts, exposure_absence: object, *, floor: str) -> dict:
    """The non-authority candidate record for one set of profile facts.

    ``floor`` is the mechanical floor :func:`_classify_against_committed_policy`
    computed; it must be one of the closed floor classes (never
    ``NOT_COMPUTED``). It is classification only and grants nothing.
    """
    if type(facts) is not ProfileFacts:
        raise Cfg1DiscoveryError("MALFORMED_FACTS")
    if type(floor) is not str or floor not in FLOOR_CLASSES:
        raise Cfg1DiscoveryError("MALFORMED_FLOOR")
    if exposure_absence is None:
        absence_status, absence_exposure = EXPOSURE_ABSENCE_NOT_OBSERVED, None
    else:
        absence_status, absence_exposure = exposure_absence.status, exposure_absence.exposure
    return {
        "record_kind": CANDIDATE_RECORD_KIND,
        "authority": CANDIDATE_AUTHORITY,
        "payload_contract": PAYLOAD_CONTRACT,
        "payload_fingerprint": facts.payload_fingerprint,
        "profile_id": facts.profile_id,
        "floor": floor,
        "approvability": {
            "status": APPROVABILITY_FLOOR_MET
            if facts.c5_reason is None
            else APPROVABILITY_C5_UNDER_HPP1,
            "reason": facts.c5_reason,
            "manifest_path": facts.c5_manifest_path,
        },
        "seam_contract": SEAM_CONTRACT,
        "seam_digests": facts.seam_digests_dict(),
        "seam_fingerprint": facts.seam_fingerprint,
        "declared": facts.declared_dict(),
        "resolution_exposures": None
        if facts.resolution_exposures is None
        else list(facts.resolution_exposures),
        "exposure_absence_observation": absence_status,
        "exposure_present_or_unobservable": absence_exposure,
        "pi_profile_authority_scope": PI_PROFILE_AUTHORITY_SCOPE,
        "pi_external_runtime_residual": PI_EXTERNAL_RUNTIME_RESIDUAL,
        "discovery": {"discovery_tool_revision": DISCOVERY_TOOL_REVISION},
    }


# ---------------------------------------------------------------------------
# The staging write boundary (PE-1 Sec. 9.10)
# ---------------------------------------------------------------------------


def _observe_classification(inspect, path: str) -> str:
    observation = inspect(path)
    if type(observation) is not NoFollowObservation:
        raise Cfg1DiscoveryError("MALFORMED_LEAF_OBSERVATION")
    classification = observation.classification
    if type(classification) is not str or classification not in CLASSIFICATIONS:
        raise Cfg1DiscoveryError("MALFORMED_LEAF_OBSERVATION")
    return classification


def _make_staging_directory(path: str) -> None:
    """Exactly ONE non-recursive, exclusive directory creation."""
    os.mkdir(path)


def _write_all(handle, data: bytes) -> None:
    written = 0
    while written < len(data):
        progress = handle.write(data[written:])
        if type(progress) is not int or progress <= 0 or progress > len(data) - written:
            raise Cfg1DiscoveryError("SHORT_WRITE")
        written += progress


def _create_exclusive(path: str, data: bytes) -> None:
    """``O_CREAT | O_EXCL`` (a ``FileExistsError`` IS the collision proof);
    written once, flushed, closed. Never truncates or replaces anything."""
    with open(path, "xb") as handle:
        _write_all(handle, data)
        handle.flush()
        os.fsync(handle.fileno())


def _staging_targets(payload_fingerprint: str, staging: str) -> tuple[tuple[str, str], ...]:
    """``(name, path)`` per suffix, in write order, with structural containment."""
    if not is_lowercase_hex64(payload_fingerprint):
        raise Cfg1DiscoveryError("FINGERPRINT_MALFORMED")
    targets = []
    for suffix in _WRITE_ORDER:
        name = payload_fingerprint + suffix
        if STAGING_FILENAME_GRAMMAR.fullmatch(name) is None:
            raise Cfg1DiscoveryError("STAGING_NAME_GRAMMAR")
        path = ntpath.join(staging, name)
        if ntpath.dirname(path) != staging or ntpath.basename(path) != name:
            raise Cfg1DiscoveryError("STAGING_CONTAINMENT")
        targets.append((name, path))
    return tuple(targets)


def _stage_candidate_artifacts(
    payload_fingerprint: str, artifacts: Mapping[str, bytes], inspect
) -> tuple[str, tuple[str, ...]]:
    """Write the three artifacts under the ONE fixed staging directory.

    Takes no directory or path: the location is the module-level
    ``_STAGING_DIRECTORY``. Returns ``(code, created_names)``.
    """
    staging = _STAGING_DIRECTORY
    parent = ntpath.dirname(staging)
    if ntpath.basename(staging) != STAGING_DIRECTORY_NAME:
        raise Cfg1DiscoveryError("STAGING_LOCATION_MALFORMED")
    targets = _staging_targets(payload_fingerprint, staging)
    for suffix in _WRITE_ORDER:
        if type(artifacts.get(suffix)) is not bytes:
            raise Cfg1DiscoveryError("ARTIFACT_MALFORMED")

    # 1. Topology proof before any write: parent a plain directory; staging a
    #    plain directory or missing (then ONE exclusive mkdir, re-observed).
    if _observe_classification(inspect, parent) != CLASSIFICATION_DIRECTORY:
        return DISCOVERY_REFUSED_STAGING_TOPOLOGY, ()
    observed = _observe_classification(inspect, staging)
    if observed == CLASSIFICATION_MISSING:
        try:
            _make_staging_directory(staging)
        except OSError:
            return DISCOVERY_REFUSED_STAGING_TOPOLOGY, ()
        observed = _observe_classification(inspect, staging)
    if observed != CLASSIFICATION_DIRECTORY:
        return DISCOVERY_REFUSED_STAGING_TOPOLOGY, ()

    # 3. All three targets must be MISSING before the first create.
    for _name, path in targets:
        if _observe_classification(inspect, path) != CLASSIFICATION_MISSING:
            return DISCOVERY_REFUSED_STAGING_TARGET_OCCUPIED, ()

    # 4. Exclusive create, fixed order, candidate last; residue is left.
    created: list[str] = []
    for suffix, (name, path) in zip(_WRITE_ORDER, targets):
        try:
            _create_exclusive(path, artifacts[suffix])
        except Exception:  # noqa: BLE001 - stop; leave residue; delete nothing
            return DISCOVERY_STAGING_WRITE_FAILED_RESIDUE_LEFT, tuple(created)
        created.append(name)
    return DISCOVERY_CANDIDATE_STAGED, tuple(created)


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def _require_manifest_read(read: object) -> PayloadFileRead:
    if type(read) is not PayloadFileRead:
        raise Cfg1DiscoveryError("MALFORMED_LEAF_READ")
    return read


def _capture_manifests(inventory, payload_root: str, read_manifest) -> dict[str, bytes]:
    """Read every bundle manifest and bind it to its inventory entry.

    Each path is an inventory path (already through the Sec. 4.2 grammar);
    a size or digest that differs from the second walk refuses.
    """
    paths = bundle_manifest_paths(inventory)
    if len(paths) > pi_manifest.MAX_MANIFEST_COUNT:
        raise _Refused(DISCOVERY_REFUSED_ARTIFACT_BOUND_EXCEEDED, "MANIFEST_COUNT_EXCEEDED")
    total = 0
    for path in paths:
        size = inventory.entry(path)[3]
        if size > pi_manifest.MAX_MANIFEST_BYTES:
            raise _Refused(DISCOVERY_REFUSED_ARTIFACT_BOUND_EXCEEDED, "MANIFEST_TOO_LARGE", path)
        total += size
        if total > pi_manifest.MAX_MANIFEST_TOTAL_BYTES:
            raise _Refused(DISCOVERY_REFUSED_ARTIFACT_BOUND_EXCEEDED, "MANIFEST_TOTAL_BYTES_EXCEEDED")
    captured: dict[str, bytes] = {}
    for path in paths:
        entry = inventory.entry(path)
        read = _require_manifest_read(
            read_manifest(ntpath.join(payload_root, *path.split("/")), pi_manifest.MAX_MANIFEST_BYTES)
        )
        if (
            read.classification != CLASSIFICATION_REGULAR_FILE
            or read.within_bound is not True
            or read.stable is not True
            or type(read.content) is not bytes
            or read.size != entry[3]
            or read.sha256 != entry[2]
        ):
            raise _Refused(DISCOVERY_REFUSED_MANIFEST_CAPTURE_UNBOUND, path)
        captured[path] = read.content
    return captured


def _ascii_line(text: str) -> str:
    """Render one console line as pure ASCII.

    A payload-relative path passes the Sec. 4.2 grammar yet may hold
    non-ASCII characters (including bidirectional controls); escaping them
    keeps a line from being visually spoofed and from failing to print on a
    non-UTF-8 stream after artifacts were already staged.
    """
    return text.encode("ascii", "backslashreplace").decode("ascii")


def _console(code: str, *detail: str) -> tuple[str, ...]:
    return (_ascii_line("PI_PROFILE_DISCOVERY " + code),) + tuple(
        _ascii_line("  " + item) for item in detail
    )


def _classify_against_committed_policy(facts: ProfileFacts) -> str:
    """PE-1 Sec. 26.2 B-15: the floor of ONE candidate against the committed head.

    The reference view comes ONLY from the PE-2b loader's zero-argument
    ``head_reference_view()``, rebuilt from the chain that module validated at
    its own import from its own ``__file__``-derived policy directory; the
    classifier is the ACCEPTED PE-2a :func:`classify_floor`, by identity.
    Nothing here takes a path, a snapshot, a view or a classifier, and nothing
    reads the staging namespace. A loader that cannot import (malformed or
    missing committed policy), a view that cannot be built or is not an exact
    ``ReferenceView``, a classifier that raises, or a result outside the
    closed floor vocabulary REFUSES -- never ``NOT_COMPUTED``, never a default.
    """
    try:
        # The loader validates the committed policy tree when it is imported;
        # a refused chain makes this import fail, which refuses here.
        from . import pi_profile_policy_loader

        reference = pi_profile_policy_loader.head_reference_view()
    except Exception:  # noqa: BLE001 - one closed code; no policy text escapes
        raise _Refused(DISCOVERY_REFUSED_POLICY_REFERENCE_UNAVAILABLE) from None
    if type(reference) is not ReferenceView:
        raise _Refused(DISCOVERY_REFUSED_POLICY_REFERENCE_UNAVAILABLE)
    try:
        floor = classify_floor(facts, reference)
    except Exception:  # noqa: BLE001 - one closed code
        raise _Refused(DISCOVERY_REFUSED_FLOOR_UNCLASSIFIABLE) from None
    if type(floor) is not str or floor not in FLOOR_CLASSES:
        raise _Refused(DISCOVERY_REFUSED_FLOOR_UNCLASSIFIABLE)
    return floor


def _discover(
    ambient_environ: Mapping[str, str],
    *,
    proof_leaves: PiProofLeaves,
    payload_leaves: PayloadLeaves,
    read_manifest,
) -> DiscoveryOutcome:
    if type(proof_leaves) is not PiProofLeaves or type(payload_leaves) is not PayloadLeaves:
        raise Cfg1DiscoveryError("MALFORMED_DISCOVERY_LEAVES")
    if not callable(read_manifest):
        raise Cfg1DiscoveryError("MALFORMED_DISCOVERY_LEAVES")
    fingerprint: str | None = None
    try:
        # -- P0: exactly one ambient name, by name ---------------------------
        try:
            path_value = ambient_environ["PATH"]
        except KeyError:
            raise _Refused(DISCOVERY_REFUSED_PI_RESOLUTION_FAILED) from None
        if type(path_value) is not str:
            raise _Refused(DISCOVERY_REFUSED_PI_RESOLUTION_FAILED)

        # -- P1: the UNCHANGED first-admissible-candidate selection ----------
        entries = _path_entries(path_value)
        node = _resolve_node(proof_leaves, entries)
        if node is None:
            raise _Refused(DISCOVERY_REFUSED_PI_RESOLUTION_FAILED)
        root = _resolve_package_root(proof_leaves, entries)
        if root is None:
            raise _Refused(DISCOVERY_REFUSED_PI_RESOLUTION_FAILED)
        node_path, node_identity = node
        root_path, root_identity = root

        # -- two complete PI-PC1 observations, which must be identical -------
        first = observe_payload(root_path, leaves=payload_leaves)
        if not first.complete:
            raise _Refused(DISCOVERY_REFUSED_PAYLOAD_UNPROVEN, first.refusal_code)
        second = observe_payload(root_path, leaves=payload_leaves)
        if not second.complete:
            raise _Refused(DISCOVERY_REFUSED_PAYLOAD_UNPROVEN, second.refusal_code)
        if first.inventory.canonical_bytes != second.inventory.canonical_bytes:
            raise _Refused(DISCOVERY_REFUSED_PAYLOAD_CHANGED_BETWEEN_WALKS)
        inventory = second.inventory
        fingerprint = inventory.payload_fingerprint

        # -- bound manifest capture, facts, exposure absence ----------------
        bundle = build_manifest_bundle(
            inventory, _capture_manifests(inventory, root_path, read_manifest)
        )
        facts = compute_profile_facts(inventory, bundle)
        absence = None
        if facts.resolution_exposures is not None:
            absence = observe_exposure_absence(
                root_path, facts.resolution_exposures, inspect=proof_leaves.inspect
            )

        # -- P2R: re-prove I_r, then I_n --------------------------------------
        if not _identity_still_holds(
            proof_leaves, root_path, classification=CLASSIFICATION_DIRECTORY, expected=root_identity
        ) or not _identity_still_holds(
            proof_leaves, node_path, classification=CLASSIFICATION_REGULAR_FILE, expected=node_identity
        ):
            raise _Refused(DISCOVERY_REFUSED_IDENTITY_DRIFTED)

        # -- B-15: the mechanical floor against the COMMITTED policy head ----
        floor = _classify_against_committed_policy(facts)

        # -- artifacts: written only if all three fit their frozen bounds ----
        artifacts = {
            INVENTORY_SUFFIX: policy_file_bytes(inventory.to_record()),
            MANIFEST_BUNDLE_SUFFIX: policy_file_bytes(bundle.to_record()),
            CANDIDATE_SUFFIX: policy_file_bytes(build_candidate_record(facts, absence, floor=floor)),
        }
        if len(artifacts[INVENTORY_SUFFIX]) > pi_profile_floor.MAX_INVENTORY_FILE_BYTES:
            raise _Refused(DISCOVERY_REFUSED_ARTIFACT_BOUND_EXCEEDED, "INVENTORY_FILE_BOUND_EXCEEDED")
        if len(artifacts[MANIFEST_BUNDLE_SUFFIX]) > pi_profile_floor.MAX_MANIFEST_BUNDLE_FILE_BYTES:
            raise _Refused(
                DISCOVERY_REFUSED_ARTIFACT_BOUND_EXCEEDED, "MANIFEST_BUNDLE_FILE_BOUND_EXCEEDED"
            )
        code, created = _stage_candidate_artifacts(fingerprint, artifacts, proof_leaves.inspect)
    except _Refused as refusal:
        detail = tuple(item for item in refusal.detail if item is not None)
        if refusal.code == DISCOVERY_REFUSED_ARTIFACT_BOUND_EXCEEDED:
            # Sec. 4.4 / 4.6 item 6: such a candidate is C5 under HPP-1; with
            # no artifact that fits its bound, nothing is staged.
            detail = ("approvability " + APPROVABILITY_C5_UNDER_HPP1,) + detail
        if fingerprint is not None:
            detail = ("payload_fingerprint " + fingerprint,) + detail
        return DiscoveryOutcome(refusal.code, fingerprint, (), _console(refusal.code, *detail))
    except Exception:  # noqa: BLE001 - reduced to one closed code; no text escapes
        return DiscoveryOutcome(
            DISCOVERY_REFUSED_UNEXPECTED_FAILURE,
            None,
            (),
            _console(DISCOVERY_REFUSED_UNEXPECTED_FAILURE),
        )

    detail = [
        "payload_fingerprint " + fingerprint,
        "profile_id " + (facts.profile_id if facts.profile_id is not None else "NOT_DERIVABLE"),
        "floor " + floor,
        "approvability "
        + (APPROVABILITY_FLOOR_MET if facts.c5_reason is None else APPROVABILITY_C5_UNDER_HPP1),
    ]
    if facts.c5_reason is not None:
        detail.append("c5_reason " + facts.c5_reason)
    if facts.c5_manifest_path is not None:
        detail.append("c5_manifest_path " + facts.c5_manifest_path)
    if absence is not None and absence.status == EXPOSURE_PRESENT_OR_UNOBSERVABLE:
        detail.append("exposure_absence " + absence.status)
    detail.append("authority " + CANDIDATE_AUTHORITY)
    detail.extend("staged " + name for name in created)
    return DiscoveryOutcome(code, fingerprint, created, _console(code, *detail))


def discover_pi_profile_candidate(ambient_environ: Mapping[str, str]) -> DiscoveryOutcome:
    """THE discovery entry point. Accepts no output path of any kind.

    Reads exactly ``PATH`` from ``ambient_environ``; uses only the genuine
    no-follow leaves; executes nothing; stages only under the fixed,
    ``__file__``-derived staging directory.
    """
    return _discover(
        ambient_environ,
        proof_leaves=genuine_pi_proof_leaves(),
        payload_leaves=genuine_payload_leaves(),
        read_manifest=read_payload_file_bytes,
    )


def main(argv: list[str] | None = None) -> int:
    """Operator entry point. Takes NO option: any argument refuses."""
    arguments = sys.argv[1:] if argv is None else list(argv)
    if arguments:
        for line in _console(DISCOVERY_REFUSED_ARGUMENTS):
            print(line)
        return 2
    outcome = discover_pi_profile_candidate(os.environ)
    for line in outcome.console_lines:
        print(line)
    return 0 if outcome.code == DISCOVERY_CANDIDATE_STAGED else 1


if __name__ == "__main__":  # pragma: no cover - operator invocation (PE-3)
    raise SystemExit(main())
