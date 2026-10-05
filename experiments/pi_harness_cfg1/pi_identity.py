"""The ONE canonical, static, profile-aware Pi proof P -- and its consumers.

Design ``PHASE_5F3B_HARNESS_CFG1_L1_BOUNDARY_FU1_DESIGN.md`` (R6) Sec. 5/7, as
amended by ``..._OC3_AMEND1_DESIGN.md`` (AMD-1 .. AMD-8) and
``..._P1_TOPOLOGY_ADMISSIBILITY_AMEND_DESIGN.md`` (P1 admissibility, see
:func:`_first_candidate`), and -- for every profile-aware CFG1 run -- by
``PHASE_5F3B_PI_HARNESS_PROFILE_EVOLUTION_PE1_AMENDMENT.md`` (HPP-1, PE-2c)
Sec. 11-15. The effective proof is::

    P0   read exactly one ambient name, PATH, by name
    P1   first admissible node.exe + Pi package root (UNCHANGED);
         capture I_n (node.exe) and I_r (package root)
    P2   the COMPLETE, uncached PI-PC1 payload observation
           incomplete / unobservable / bound exceeded -> PI_PAYLOAD_UNPROVEN
    P2M  exact membership of the payload fingerprint in the module-level
         SEALED HPP-1 snapshot's eligible runtime profiles
           none -> PI_PROFILE_UNAPPROVED; more than one RAISES, never chooses
    P2X  the matched profile's declared resolution exposures proven absent
           present / unobservable -> PI_EXTERNAL_RESOLUTION_EXPOSED
    P2R  re-prove I_r, then I_n
           drift -> PI_IDENTITY_DRIFTED_DURING_PROOF
    ->   one typed PiProofResult; a pass carries matched_profile_id

**P executes nothing.** It has no process-runner leaf, no child-environment
leaf, and no leaf whose genuine binding can create a process: its injectable
leaves are exactly the no-follow inspection primitive, the one-handle
payload-file reader, the no-follow directory enumerator (PE-1 X-1) and the
checkout root, plus the explicit ambient mapping it is handed. It runs no
``--version`` probe, reads no package-manager metadata, reads no credential or
endpoint, writes nothing, and **parses nothing Pi-authored**: bytes are hashed
and dropped, and the exposure names it checks are the sealed snapshot's
loader-verified parser-output component tuples. This module imports no
manifest parser.

**The policy is the module-level sealed snapshot, and nothing else.** P, the
gate, L1, L14 and L21A read
:data:`pi_profile_policy_loader.SEALED_POLICY_SNAPSHOT` at call time. No
parameter anywhere accepts a snapshot, a profile, a fingerprint or an
eligible set. A version string never grants authority and is never compared.

**What a pass establishes, exactly.** The PROFILE-COVERED FACT: every byte of
every file and directory AIDO read under the lexical payload root equalled an
eligible profile's approved payload, and every declared-dependency exposure of
that profile was absent from every ancestor ``node_modules``, at the stated
boundaries. It claims NOTHING about ``node.exe``'s bytes, built-ins, undeclared
or dynamic resolution, or any other external runtime residual (PE-1 Sec. 4.7,
Sec. 27): those are ``NOT_IDENTIFIED_BY_PROFILE``. Nothing ran, and nothing
reported a version.
"""

from __future__ import annotations

import ntpath
import os
import re
from pathlib import Path
from typing import Callable, Mapping

from . import pi_fs_leaves
from . import pi_profile_policy_loader as _policy
from .pi_fs_leaves import (
    CLASSIFICATION_DIRECTORY,
    CLASSIFICATION_MISSING,
    CLASSIFICATION_REGULAR_FILE,
    CLASSIFICATION_REPARSE_POINT,
    CLASSIFICATIONS,
    DirectoryListing,
    NoFollowObservation,
    PayloadFileRead,
)
from .pi_payload import PayloadLeaves, PayloadObservation, is_lowercase_hex64, observe_payload

# ---------------------------------------------------------------------------
# Closed vocabularies (PE-1 Sec. 12)
# ---------------------------------------------------------------------------

#: PE-1 Sec. 12.1 -- exactly FIVE canonical proof failure codes, produced ONLY
#: by P. They are never pre-dispatch refusal codes.
PI_RESOLUTION_FAILED = "PI_RESOLUTION_FAILED"
PI_PAYLOAD_UNPROVEN = "PI_PAYLOAD_UNPROVEN"
PI_PROFILE_UNAPPROVED = "PI_PROFILE_UNAPPROVED"
PI_EXTERNAL_RESOLUTION_EXPOSED = "PI_EXTERNAL_RESOLUTION_EXPOSED"
PI_IDENTITY_DRIFTED_DURING_PROOF = "PI_IDENTITY_DRIFTED_DURING_PROOF"

PI_PROOF_FAILURE_CODES: frozenset[str] = frozenset(
    {
        PI_RESOLUTION_FAILED,
        PI_PAYLOAD_UNPROVEN,
        PI_PROFILE_UNAPPROVED,
        PI_EXTERNAL_RESOLUTION_EXPOSED,
        PI_IDENTITY_DRIFTED_DURING_PROOF,
    }
)

#: PE-1 Sec. 12.3 -- the stage-level consistency code. Produced ONLY by L1,
#: for an ordinal after the first, after a PASSING P whose matched profile
#: differs from the stage's fixed profile. Never a P code, never a gate value.
PI_PROFILE_CHANGED_WITHIN_STAGE = "PI_PROFILE_CHANGED_WITHIN_STAGE"

#: PE-1 Sec. 12.1 terminology resolution: the SIX values of the v3 durable
#: field ``pi_identity_failure_code`` -- the five proof codes plus the stage
#: code. Committed only by L1.
PI_IDENTITY_FAILURE_CODES_V3: frozenset[str] = PI_PROOF_FAILURE_CODES | frozenset(
    {PI_PROFILE_CHANGED_WITHIN_STAGE}
)

#: PE-1 Sec. 19.3 ``Allowed_O``: the one ``pi_payload_observation_complete``
#: value each failure can carry. The first five constrain P's refusals.
ALLOWED_PAYLOAD_OBSERVATION_COMPLETE: dict[str, bool] = {
    PI_RESOLUTION_FAILED: False,
    PI_PAYLOAD_UNPROVEN: False,
    PI_PROFILE_UNAPPROVED: True,
    PI_EXTERNAL_RESOLUTION_EXPOSED: True,
    PI_IDENTITY_DRIFTED_DURING_PROOF: True,
    PI_PROFILE_CHANGED_WITHIN_STAGE: True,
}

#: PE-1 Sec. 12.2 -- the gate's two non-P closed codes. A gate that could not
#: complete its own proof says so; it never reports a pass it did not observe.
PI_IDENTITY_GATE_PASSED = "PI_IDENTITY_PROVEN"
PI_IDENTITY_GATE_UNEXPECTED_FAILURE = "PI_IDENTITY_GATE_UNEXPECTED_FAILURE"

#: Exactly SEVEN. Never contains the stage code.
PI_IDENTITY_GATE_CODES: frozenset[str] = frozenset(
    {PI_IDENTITY_GATE_PASSED, PI_IDENTITY_GATE_UNEXPECTED_FAILURE} | PI_PROOF_FAILURE_CODES
)

#: PE-1 Sec. 15.2 -- the closed ``pi_profile_post_runtime_reobservation``
#: domain. ``NOT_APPLICABLE`` is decided by the executor alone.
PI_PROFILE_REOBSERVATION_NOT_APPLICABLE = "NOT_APPLICABLE"
PI_PROFILE_REOBSERVATION_CHANGED = "CHANGED"
PI_PROFILE_REOBSERVATION_UNPROVEN = "UNPROVEN"
PI_PROFILE_REOBSERVATION_PROVEN_UNCHANGED = "PROVEN_UNCHANGED"

PI_PROFILE_REOBSERVATION_VALUES: frozenset[str] = frozenset(
    {
        PI_PROFILE_REOBSERVATION_NOT_APPLICABLE,
        PI_PROFILE_REOBSERVATION_CHANGED,
        PI_PROFILE_REOBSERVATION_UNPROVEN,
        PI_PROFILE_REOBSERVATION_PROVEN_UNCHANGED,
    }
)

#: The three values the L21A PROCEDURE may return (never NOT_APPLICABLE).
PI_PROFILE_REOBSERVATION_PROCEDURE_VALUES: frozenset[str] = frozenset(
    {
        PI_PROFILE_REOBSERVATION_CHANGED,
        PI_PROFILE_REOBSERVATION_UNPROVEN,
        PI_PROFILE_REOBSERVATION_PROVEN_UNCHANGED,
    }
)

#: PE-1 Sec. 6.6 exposure absence, as the three outcomes the runtime needs:
#: P2X and L14 refuse on anything but ABSENT; L21A tells PRESENT (``CHANGED``)
#: apart from UNOBSERVABLE (``UNPROVEN``).
EXPOSURES_ABSENT = "EXPOSURES_ABSENT"
EXPOSURE_PRESENT = "EXPOSURE_PRESENT"
EXPOSURE_UNOBSERVABLE = "EXPOSURE_UNOBSERVABLE"

#: The two AR2 package-root layouts a ``pi.cmd`` anchors (R6 Sec. 5 P1).
_PI_PACKAGE_PARTS: tuple[str, ...] = ("node_modules", "@earendil-works", "pi-coding-agent")

_NODE_NAME = "node.exe"
_PI_ANCHOR_NAME = "pi.cmd"

#: PE-1 Sec. 4.4 / Sec. 6.5: a declared package version is bounded printable
#: ASCII provenance text. Checked for shape only; never compared.
_DECLARED_VERSION = re.compile(r"[\x21-\x7e]{1,128}")


class Cfg1PiIdentityError(Exception):
    """P could not run its own proof (a malformed input, leaf output or policy).

    NOT an anticipated refusal: it propagates to L1's catch-all, which records
    ``UNEXPECTED_STEP_FAILURE`` with nothing of P's family committed. It
    carries a closed code only -- never a path, a value, or leaf text.
    """

    def __init__(self, reason_code: str) -> None:
        super().__init__(f"cfg1 pi identity proof could not run: {reason_code}")
        self.reason_code = reason_code


#: Construction key for the two objects only P may build. A module-private
#: sentinel: neither class can be instantiated meaningfully from outside.
_P_ONLY = object()


def _require_identity_pair(value: object) -> tuple[int, int]:
    if (
        type(value) is not tuple
        or len(value) != 2
        or type(value[0]) is not int
        or type(value[1]) is not int
        or value[0] < 0
        or value[1] < 0
    ):
        raise Cfg1PiIdentityError("MALFORMED_IDENTITY")
    return value


class Cfg1PiIdentity:
    """The CFG1-owned static identity object L12, L14 and L21A use.

    AMEND1 Sec. 10's five attributes plus exactly ONE added by PE-1 Sec. 11.3,
    ``matched_profile_id`` -- deliberately no ``version``, ``reported_version``
    or ``launch_shape``. Never durable, never rendered, never returned by the
    gate, never accepted by ``run_cfg1_stage``, and constructible only by a
    passing P.

    The frozen ``ar2.launch.build_pi_argv`` reads exactly ``node_executable``
    and ``pi_cli_js`` from it (Test AG pins that).
    """

    __slots__ = (
        "node_executable",
        "pi_cli_js",
        "pi_package_root",
        "node_identity",
        "package_root_identity",
        "matched_profile_id",
    )

    def __init__(
        self,
        key: object,
        *,
        node_executable: str,
        pi_cli_js: str,
        pi_package_root: str,
        node_identity: tuple[int, int],
        package_root_identity: tuple[int, int],
        matched_profile_id: str,
    ) -> None:
        if key is not _P_ONLY:
            raise Cfg1PiIdentityError("IDENTITY_NOT_PRODUCED_BY_P")
        for value in (node_executable, pi_cli_js, pi_package_root):
            if type(value) is not str or not value:
                raise Cfg1PiIdentityError("MALFORMED_IDENTITY_PATH")
        if not is_lowercase_hex64(matched_profile_id):
            raise Cfg1PiIdentityError("MALFORMED_MATCHED_PROFILE_ID")
        object.__setattr__(self, "node_executable", node_executable)
        object.__setattr__(self, "pi_cli_js", pi_cli_js)
        object.__setattr__(self, "pi_package_root", pi_package_root)
        object.__setattr__(self, "node_identity", _require_identity_pair(node_identity))
        object.__setattr__(
            self, "package_root_identity", _require_identity_pair(package_root_identity)
        )
        object.__setattr__(self, "matched_profile_id", matched_profile_id)

    def __setattr__(self, name: str, value: object) -> None:  # noqa: D105
        raise Cfg1PiIdentityError("IDENTITY_IS_IMMUTABLE")

    def __delattr__(self, name: str) -> None:  # noqa: D105
        raise Cfg1PiIdentityError("IDENTITY_IS_IMMUTABLE")

    def __reduce__(self):  # noqa: D105 - never copied, pickled or re-materialized
        raise Cfg1PiIdentityError("IDENTITY_IS_NOT_TRANSFERABLE")

    def __repr__(self) -> str:  # noqa: D105 - paths and identities never rendered
        return f"{type(self).__name__}(<bound>)"


class PiProofResult:
    """P's ONE return value -- a pass or an anticipated refusal, never both.

    PE-1 Sec. 11.3. Pass: ``failure_code is None``,
    ``payload_observation_complete is True`` and ``identity`` is a
    :class:`Cfg1PiIdentity`. Refusal: ``failure_code`` is one of the five proof
    codes, ``payload_observation_complete`` is its ``Allowed_O`` value, and
    ``identity is None``. There is no ``seam_digests_match``: the profile-aware
    result never claims anything about the historical 20-entry table. L1
    re-validates this exact shape before it commits anything.
    """

    __slots__ = ("failure_code", "payload_observation_complete", "identity")

    def __init__(
        self,
        key: object,
        *,
        failure_code: str | None,
        payload_observation_complete: bool,
        identity: Cfg1PiIdentity | None,
    ) -> None:
        if key is not _P_ONLY:
            raise Cfg1PiIdentityError("RESULT_NOT_PRODUCED_BY_P")
        object.__setattr__(self, "failure_code", failure_code)
        object.__setattr__(self, "payload_observation_complete", payload_observation_complete)
        object.__setattr__(self, "identity", identity)

    def __setattr__(self, name: str, value: object) -> None:  # noqa: D105
        raise Cfg1PiIdentityError("RESULT_IS_IMMUTABLE")

    def __delattr__(self, name: str) -> None:  # noqa: D105
        raise Cfg1PiIdentityError("RESULT_IS_IMMUTABLE")

    def __reduce__(self):  # noqa: D105
        raise Cfg1PiIdentityError("RESULT_IS_NOT_TRANSFERABLE")

    def __repr__(self) -> str:  # noqa: D105
        return f"{type(self).__name__}(failure_code={self.failure_code!r})"


class PiProofLeaves:
    """P's injectable leaf surface -- and, by construction, all of it.

    PE-1 Sec. 11.2 (X-1), exactly these four slots:

    ``inspect``
        the Sec. 7.2 no-follow inspection/identity primitive (unchanged)
    ``read_digest``
        the one-handle payload-file reader: classification, exact byte
        count, SHA-256, within-bound and size stability, from ONE handle
    ``enumerate_directory``
        the no-follow directory enumerator that lists THROUGH its own handle
    ``checkout_root``
        not an effect: the checkout P derives from this package's own
        location, used for containment refusal only

    There is no field through which a process runner, a child-environment
    builder, or any other executing leaf could be supplied.
    """

    __slots__ = ("inspect", "read_digest", "enumerate_directory", "checkout_root")

    def __init__(
        self,
        *,
        inspect: Callable[[str], NoFollowObservation],
        read_digest: Callable[[str, int], PayloadFileRead],
        enumerate_directory: Callable[[str, int], DirectoryListing],
        checkout_root: str,
    ) -> None:
        if not callable(inspect) or not callable(read_digest) or not callable(enumerate_directory):
            raise Cfg1PiIdentityError("MALFORMED_PROOF_LEAVES")
        if type(checkout_root) is not str or not ntpath.isabs(checkout_root):
            raise Cfg1PiIdentityError("MALFORMED_CHECKOUT_ROOT")
        object.__setattr__(self, "inspect", inspect)
        object.__setattr__(self, "read_digest", read_digest)
        object.__setattr__(self, "enumerate_directory", enumerate_directory)
        object.__setattr__(self, "checkout_root", checkout_root)

    def __setattr__(self, name: str, value: object) -> None:  # noqa: D105
        raise Cfg1PiIdentityError("PROOF_LEAVES_ARE_IMMUTABLE")

    def __repr__(self) -> str:  # noqa: D105
        return f"{type(self).__name__}(<bound>)"


#: The checkout this package executes from: ``<ROOT>`` in
#: ``<ROOT>\experiments\pi_harness_cfg1``. Derived from the executing module's
#: own location (the same fact the launcher's G6 proves), never from an
#: argument, an environment variable or the current directory.
_GENUINE_CHECKOUT_ROOT = str(Path(__file__).resolve().parents[2])


def genuine_pi_proof_leaves() -> PiProofLeaves:
    """The ONE genuine leaf binding. Shared by the gate, L1, L14 and L21A.

    Takes no parameter, so a caller cannot select a leaf. The three effects
    are looked up on :mod:`pi_fs_leaves` at call time.
    """
    return PiProofLeaves(
        inspect=pi_fs_leaves.inspect_no_follow,
        read_digest=pi_fs_leaves.read_payload_file_digest,
        enumerate_directory=pi_fs_leaves.enumerate_directory_no_follow,
        checkout_root=_GENUINE_CHECKOUT_ROOT,
    )


def _payload_leaves(leaves: PiProofLeaves) -> PayloadLeaves:
    """The PI-PC1 walk's leaves, taken from P's own leaf surface only."""
    return PayloadLeaves(
        enumerate_directory=leaves.enumerate_directory, read_file=leaves.read_digest
    )


# ---------------------------------------------------------------------------
# The sealed HPP-1 policy snapshot -- read at call time, never a parameter
# ---------------------------------------------------------------------------


def sealed_policy_snapshot() -> _policy.Cfg1PolicySnapshot:
    """The module-level sealed snapshot, exact-typed. Never a caller value."""
    snapshot = _policy.SEALED_POLICY_SNAPSHOT
    if type(snapshot) is not _policy.Cfg1PolicySnapshot:
        raise Cfg1PiIdentityError("POLICY_SNAPSHOT_MALFORMED")
    if type(snapshot.eligible_profiles) is not tuple or type(snapshot.eligible_profile_ids) is not frozenset:
        raise Cfg1PiIdentityError("POLICY_SNAPSHOT_MALFORMED")
    return snapshot


def _require_view(view: object, snapshot: _policy.Cfg1PolicySnapshot) -> _policy.Cfg1EligibleProfileView:
    if type(view) is not _policy.Cfg1EligibleProfileView:
        raise Cfg1PiIdentityError("POLICY_SNAPSHOT_MALFORMED")
    if not is_lowercase_hex64(view.profile_id) or view.profile_id not in snapshot.eligible_profile_ids:
        raise Cfg1PiIdentityError("POLICY_SNAPSHOT_MALFORMED")
    if not is_lowercase_hex64(view.payload_fingerprint):
        raise Cfg1PiIdentityError("POLICY_SNAPSHOT_MALFORMED")
    return view


def _view_for_fingerprint(
    snapshot: _policy.Cfg1PolicySnapshot, fingerprint: str
) -> _policy.Cfg1EligibleProfileView | None:
    """P2M: EXACT membership, never a nearest match. More than one RAISES."""
    matches = []
    for view in snapshot.eligible_profiles:
        candidate = _require_view(view, snapshot)
        if candidate.payload_fingerprint == fingerprint:
            matches.append(candidate)
    if len(matches) > 1:
        # Impossible for a loaded chain (the loader refuses duplicate
        # fingerprints). Never choose between them.
        raise Cfg1PiIdentityError("DUPLICATE_PROFILE_MATCH")
    return matches[0] if matches else None


def eligible_profile_view(profile_id: object) -> _policy.Cfg1EligibleProfileView:
    """The ONE eligible runtime view of ``profile_id`` in the sealed snapshot.

    Used where a profile has ALREADY been selected by P (L1's declared
    version, L14, L21A) and by the stage-closure writer's design-B derivation.
    This is never a membership choice: an id that is not exactly one eligible
    runtime profile of the snapshot RAISES.
    """
    snapshot = sealed_policy_snapshot()
    if not is_lowercase_hex64(profile_id) or profile_id not in snapshot.eligible_profile_ids:
        raise Cfg1PiIdentityError("PROFILE_NOT_ELIGIBLE_IN_SNAPSHOT")
    matches = [
        view
        for view in snapshot.eligible_profiles
        if _require_view(view, snapshot).profile_id == profile_id
    ]
    if len(matches) != 1:
        raise Cfg1PiIdentityError("PROFILE_NOT_ELIGIBLE_IN_SNAPSHOT")
    return matches[0]


def declared_package_version_for_profile(profile_id: object) -> str:
    """The matched profile's loader-bound ``declared.package_version``.

    Provenance only: copied into evidence, never compared, never authority.
    """
    version = eligible_profile_view(profile_id).declared_package_version
    if type(version) is not str or _DECLARED_VERSION.fullmatch(version) is None:
        raise Cfg1PiIdentityError("POLICY_DECLARED_VERSION_MALFORMED")
    return version


# ---------------------------------------------------------------------------
# Leaf wrappers -- every leaf output is exact-typed before anything reads it
# ---------------------------------------------------------------------------


def _observe(leaves: PiProofLeaves, path: str) -> NoFollowObservation:
    observation = leaves.inspect(path)
    if type(observation) is not NoFollowObservation:
        raise Cfg1PiIdentityError("MALFORMED_LEAF_OBSERVATION")
    classification = observation.classification
    if type(classification) is not str or classification not in CLASSIFICATIONS:
        raise Cfg1PiIdentityError("MALFORMED_LEAF_OBSERVATION")
    if classification in (CLASSIFICATION_REGULAR_FILE, CLASSIFICATION_DIRECTORY):
        _require_identity_pair(observation.identity)
    elif observation.identity is not None:
        raise Cfg1PiIdentityError("MALFORMED_LEAF_OBSERVATION")
    return observation


def _observe_payload(leaves: PiProofLeaves, payload_root: str) -> PayloadObservation:
    """ONE complete, uncached PI-PC1 walk through P's own leaves.

    Anticipated refusals come back as an incomplete observation; a malformed
    leaf output raises (``observe_payload``'s own exact typing).
    """
    observation = observe_payload(payload_root, leaves=_payload_leaves(leaves))
    if type(observation) is not PayloadObservation or type(observation.complete) is not bool:
        raise Cfg1PiIdentityError("MALFORMED_PAYLOAD_OBSERVATION")
    if observation.complete and not is_lowercase_hex64(observation.payload_fingerprint):
        raise Cfg1PiIdentityError("MALFORMED_PAYLOAD_OBSERVATION")
    return observation


# ---------------------------------------------------------------------------
# Lexical path helpers -- Windows semantics, explicitly (ntpath)
# ---------------------------------------------------------------------------


def _plain_absolute_entry(raw: str) -> str | None:
    """A drive- or UNC-absolute ``PATH`` entry, lexically normalized; else ``None``.

    Empty, relative, drive-relative (``C:foo``), rooted-without-drive
    (``\\foo``) and device-namespace (``\\\\?\\``, ``\\\\.\\``) entries are
    skipped: the current directory is never consulted. Lexical normalization of
    ``.``/``..`` is exactly what Win32 itself applies before the object manager
    sees a path, so the normalized form is the form an open would resolve.
    """
    if not raw:
        return None
    if raw.startswith(("\\\\?\\", "\\\\.\\", "//?/", "//./")):
        return None
    drive, _rest = ntpath.splitdrive(raw)
    if not drive or not ntpath.isabs(raw):
        return None
    return ntpath.normpath(raw)


def _lexical_chain(path: str) -> list[str]:
    """Every lexical prefix of an absolute, normalized path, root first."""
    drive, rest = ntpath.splitdrive(path)
    current = drive + "\\"
    chain = [current]
    for part in rest.replace("/", "\\").split("\\"):
        if not part:
            continue
        current = ntpath.join(current, part)
        chain.append(current)
    return chain


_WALK_OK = "ok"
_WALK_MISSING = "missing"
_WALK_UNSAFE = "unsafe"


def _walk_directories(leaves: PiProofLeaves, path: str) -> tuple[str, tuple[int, int] | None]:
    """Inspect every lexical component, no-follow, root first.

    ``missing`` anywhere -> the path does not exist (the entry cannot hold a
    candidate); a reparse point, a file, or anything but a directory anywhere
    -> ``unsafe``, refused where it is found and never resolved further.
    Returns the final component's identity on ``ok``.
    """
    identity = None
    for component in _lexical_chain(path):
        observation = _observe(leaves, component)
        if observation.classification == CLASSIFICATION_MISSING:
            return _WALK_MISSING, None
        if observation.classification != CLASSIFICATION_DIRECTORY:
            return _WALK_UNSAFE, None
        identity = observation.identity
    return _WALK_OK, identity


def _inside(candidate: str, root: str) -> bool:
    """Case-insensitive containment of ``candidate`` in ``root`` (or equality)."""
    normalized_candidate = ntpath.normcase(ntpath.normpath(candidate))
    normalized_root = ntpath.normcase(ntpath.normpath(root))
    try:
        return ntpath.commonpath([normalized_candidate, normalized_root]) == normalized_root
    except ValueError:  # different drives: not contained
        return False


def _outside_checkout(lexical: str, checkout_root: str) -> bool:
    """Containment refusal on the LEXICAL form and the realpath'd destination.

    realpath is used only to CONFIRM a candidate that already passed every
    no-follow check -- never to launder one that did not.
    """
    if _inside(lexical, checkout_root):
        return False
    try:
        destination = os.path.realpath(lexical, strict=True)
    except (OSError, ValueError):
        return False
    try:
        checkout_destination = os.path.realpath(checkout_root)
    except (OSError, ValueError):
        return False
    if _inside(destination, checkout_root) or _inside(destination, checkout_destination):
        return False
    return True


# ---------------------------------------------------------------------------
# P1 -- resolution (R6 Sec. 5 P1, preserved exactly by AMEND1 Sec. 4 and PE-1)
# ---------------------------------------------------------------------------


def _path_entries(path_value: str) -> list[str]:
    entries = []
    for raw in path_value.split(";"):
        entry = _plain_absolute_entry(raw)
        if entry is not None:
            entries.append(entry)
    return entries


def _first_candidate(
    leaves: PiProofLeaves, entries: list[str], name: str
) -> tuple[str, str, tuple[int, int]] | None:
    """The FIRST ADMISSIBLE ``PATH`` entry holding exactly ``name``, as a
    regular file.

    Returns ``(entry, candidate, identity)``, or ``None`` for a refusal.

    **P1 topology-admissibility amendment.** A ``PATH`` entry whose directory
    topology cannot be proven safe by the no-follow walk (a reparse point,
    junction, or non-directory anywhere in its lexical chain) is
    INADMISSIBLE as a candidate namespace: it is never followed, never
    resolved through, never used to derive an identity, and it is skipped —
    the search continues at the next entry, exactly as a missing entry is
    already skipped. This does not widen what may be selected: once an
    entry's topology IS admissible and it holds a candidate at ``name``, that
    candidate is authoritative and is never bypassed in favor of a later
    entry — a candidate that is not a regular file refuses the WHOLE search
    outright, with no fallthrough. There is no ``PATHEXT`` expansion.
    """
    for entry in entries:
        status, _identity = _walk_directories(leaves, entry)
        if status in (_WALK_MISSING, _WALK_UNSAFE):
            continue
        candidate = ntpath.join(entry, name)
        observation = _observe(leaves, candidate)
        if observation.classification == CLASSIFICATION_MISSING:
            continue
        if observation.classification != CLASSIFICATION_REGULAR_FILE:
            return None
        return entry, candidate, observation.identity
    return None


def _resolve_node(
    leaves: PiProofLeaves, entries: list[str]
) -> tuple[str, tuple[int, int]] | None:
    found = _first_candidate(leaves, entries, _NODE_NAME)
    if found is None:
        return None
    _entry, candidate, identity = found
    if not _outside_checkout(candidate, leaves.checkout_root):
        return None
    try:
        destination = os.path.realpath(candidate, strict=True)
    except (OSError, ValueError):
        return None
    if ntpath.normcase(ntpath.basename(destination)) != _NODE_NAME:
        return None
    return candidate, identity


def _resolve_package_root(
    leaves: PiProofLeaves, entries: list[str]
) -> tuple[str, tuple[int, int]] | None:
    found = _first_candidate(leaves, entries, _PI_ANCHOR_NAME)
    if found is None:
        return None
    entry, anchor, _anchor_identity = found
    # The anchor is never read and never executed; it only locates the root.
    if _inside(anchor, leaves.checkout_root):
        return None
    layouts = (
        ntpath.normpath(ntpath.join(entry, *_PI_PACKAGE_PARTS)),
        ntpath.normpath(ntpath.join(entry, "..", *_PI_PACKAGE_PARTS)),
    )
    for layout in layouts:
        status, root_identity = _walk_directories(leaves, layout)
        if status == _WALK_MISSING:
            continue
        if status == _WALK_UNSAFE:
            return None
        manifest = _observe(leaves, ntpath.join(layout, "package.json"))
        if manifest.classification == CLASSIFICATION_MISSING:
            continue
        if manifest.classification != CLASSIFICATION_REGULAR_FILE:
            return None
        # First existing candidate with a package.json -- and ONLY it. A later
        # layout (or a later PATH entry) is never searched for one that would
        # pass P2/P2M: P never searches onward for a matching installation.
        if not _outside_checkout(layout, leaves.checkout_root):
            return None
        return layout, root_identity
    return None


def _identity_still_holds(
    leaves: PiProofLeaves, path: str, *, classification: str, expected: tuple[int, int]
) -> bool:
    """Sec. 7.2 step 3: re-classify, re-capture, compare. Anything else fails."""
    observation = _observe(leaves, path)
    return observation.classification == classification and observation.identity == expected


# ---------------------------------------------------------------------------
# P2X / L14 / L21A -- exposure absence (PE-1 Sec. 6.6), from POLICY components
# ---------------------------------------------------------------------------


def _require_exposure_components(resolution_exposures: object) -> tuple[tuple[str, ...], ...]:
    """The sealed view's exposures: parser-output component tuples, exact-typed.

    They come from the loader, which produced them with the accepted package
    name parser from committed bytes. Nothing here parses them again; this is
    a structural guard only, so a malformed policy object can never form a
    traversing path.
    """
    if type(resolution_exposures) is not tuple:
        raise Cfg1PiIdentityError("MALFORMED_POLICY_EXPOSURES")
    for components in resolution_exposures:
        if type(components) is not tuple or len(components) not in (1, 2):
            raise Cfg1PiIdentityError("MALFORMED_POLICY_EXPOSURES")
        for component in components:
            if (
                type(component) is not str
                or not component
                or component in (".", "..")
                or any(character in component for character in '\\/:\x00')
            ):
                raise Cfg1PiIdentityError("MALFORMED_POLICY_EXPOSURES")
        if len(components) == 2 and not components[0].startswith("@"):
            raise Cfg1PiIdentityError("MALFORMED_POLICY_EXPOSURES")
    return resolution_exposures


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


def _exposure_status_under(
    ancestor: str, components: tuple[str, ...], inspect: Callable[[str], NoFollowObservation]
) -> str:
    """``ancestor\\node_modules\\<components>``, every component no-follow.

    Intermediate components must be a plain directory or missing (missing ends
    this ancestor's check as absent); the final entry must be missing. A final
    entry that is a regular file, a directory or a reparse point is PRESENT;
    any other classification, any non-directory intermediate, any malformed
    leaf output and any raise is UNOBSERVABLE.
    """
    parts = ("node_modules",) + components
    last = len(parts) - 1
    current = ancestor
    for position, part in enumerate(parts):
        current = ntpath.join(current, part)
        try:
            observation = inspect(current)
        except Exception:  # noqa: BLE001 - an observation failure is unobservable
            return EXPOSURE_UNOBSERVABLE
        if type(observation) is not NoFollowObservation:
            return EXPOSURE_UNOBSERVABLE
        classification = observation.classification
        if type(classification) is not str or classification not in CLASSIFICATIONS:
            return EXPOSURE_UNOBSERVABLE
        if classification == CLASSIFICATION_MISSING:
            return EXPOSURES_ABSENT
        if position == last:
            if classification in (
                CLASSIFICATION_REGULAR_FILE,
                CLASSIFICATION_DIRECTORY,
                CLASSIFICATION_REPARSE_POINT,
            ):
                return EXPOSURE_PRESENT
            return EXPOSURE_UNOBSERVABLE
        if classification != CLASSIFICATION_DIRECTORY:
            return EXPOSURE_UNOBSERVABLE
    return EXPOSURE_UNOBSERVABLE  # pragma: no cover - the loop always returns


def observe_profile_exposures(
    payload_root: str,
    resolution_exposures: tuple[tuple[str, ...], ...],
    *,
    inspect: Callable[[str], NoFollowObservation],
) -> str:
    """PE-1 Sec. 6.6 exposure absence for ONE already-matched profile.

    Every exposure, every qualifying lexical ancestor of the proven payload
    root, nearest first. ``EXPOSURE_PRESENT`` as soon as any is present; else
    ``EXPOSURE_UNOBSERVABLE`` if any could not be observed; else
    ``EXPOSURES_ABSENT``. The observed path set is fixed by the policy and the
    root's lexical ancestry -- nothing Pi supplies selects what is checked.
    """
    if type(payload_root) is not str or not payload_root:
        raise Cfg1PiIdentityError("MALFORMED_PAYLOAD_ROOT")
    drive, _rest = ntpath.splitdrive(payload_root)
    if not drive or not ntpath.isabs(payload_root):
        raise Cfg1PiIdentityError("MALFORMED_PAYLOAD_ROOT")
    exposures = _require_exposure_components(resolution_exposures)
    ancestors = _lexical_ancestors_for_absence(payload_root)
    unobservable = False
    for components in exposures:
        for ancestor in ancestors:
            status = _exposure_status_under(ancestor, components, inspect)
            if status == EXPOSURE_PRESENT:
                return EXPOSURE_PRESENT
            if status != EXPOSURES_ABSENT:
                unobservable = True
    return EXPOSURE_UNOBSERVABLE if unobservable else EXPOSURES_ABSENT


# ---------------------------------------------------------------------------
# P itself
# ---------------------------------------------------------------------------


def _refusal(failure_code: str) -> PiProofResult:
    return PiProofResult(
        _P_ONLY,
        failure_code=failure_code,
        payload_observation_complete=ALLOWED_PAYLOAD_OBSERVATION_COMPLETE[failure_code],
        identity=None,
    )


def prove_pi_identity(
    ambient_environ: Mapping[str, str], *, leaves: PiProofLeaves
) -> PiProofResult:
    """THE canonical static profile-aware Pi proof. Starts no process, ever.

    Anticipated failures are RETURNED as a typed refusal, never raised, in the
    fixed function order P0/P1 -> P2 -> P2M -> P2X -> P2R. Anything this
    function cannot complete (a malformed leaf output, a leaf that raises, a
    malformed or duplicate-matching policy snapshot) propagates as an
    exception, so L1 records it as ``UNEXPECTED_STEP_FAILURE`` with nothing of
    P's family committed. There is no snapshot parameter: the policy is the
    module-level sealed snapshot.
    """
    if type(leaves) is not PiProofLeaves:
        raise Cfg1PiIdentityError("MALFORMED_PROOF_LEAVES")
    snapshot = sealed_policy_snapshot()

    # -- P0: exactly one ambient name, by name ------------------------------
    try:
        path_value = ambient_environ["PATH"]
    except KeyError:
        return _refusal(PI_RESOLUTION_FAILED)
    if type(path_value) is not str:
        return _refusal(PI_RESOLUTION_FAILED)

    # -- P1: resolve and capture I_n, I_r (unchanged) -----------------------
    entries = _path_entries(path_value)
    node = _resolve_node(leaves, entries)
    if node is None:
        return _refusal(PI_RESOLUTION_FAILED)
    root = _resolve_package_root(leaves, entries)
    if root is None:
        return _refusal(PI_RESOLUTION_FAILED)
    node_path, node_identity = node
    root_path, root_identity = root

    # -- P2: the complete, uncached PI-PC1 payload observation --------------
    observation = _observe_payload(leaves, root_path)
    if observation.complete is not True:
        return _refusal(PI_PAYLOAD_UNPROVEN)

    # -- P2M: exact membership in the sealed eligible set -------------------
    view = _view_for_fingerprint(snapshot, observation.payload_fingerprint)
    if view is None:
        return _refusal(PI_PROFILE_UNAPPROVED)

    # -- P2X: the matched profile's declared exposures absent ---------------
    exposure = observe_profile_exposures(
        root_path, view.resolution_exposures, inspect=leaves.inspect
    )
    if exposure != EXPOSURES_ABSENT:
        return _refusal(PI_EXTERNAL_RESOLUTION_EXPOSED)

    # -- P2R: identity consistency -- root first, then node.exe -------------
    if not _identity_still_holds(
        leaves, root_path, classification=CLASSIFICATION_DIRECTORY, expected=root_identity
    ):
        return _refusal(PI_IDENTITY_DRIFTED_DURING_PROOF)
    if not _identity_still_holds(
        leaves, node_path, classification=CLASSIFICATION_REGULAR_FILE, expected=node_identity
    ):
        return _refusal(PI_IDENTITY_DRIFTED_DURING_PROOF)

    identity = Cfg1PiIdentity(
        _P_ONLY,
        node_executable=node_path,
        pi_cli_js=ntpath.join(root_path, "dist", "cli.js"),
        pi_package_root=root_path,
        node_identity=node_identity,
        package_root_identity=root_identity,
        matched_profile_id=view.profile_id,
    )
    return PiProofResult(
        _P_ONLY, failure_code=None, payload_observation_complete=True, identity=identity
    )


def require_pi_proof_result_shape(result: object) -> PiProofResult:
    """L1's exact-shape validation of P's result, BEFORE anything is committed.

    PE-1 Sec. 11.3. Raises :class:`Cfg1PiIdentityError` for anything that is
    not exactly one of the two admissible shapes -- including a failure code
    from the stage or gate namespaces (``PI_PROFILE_CHANGED_WITHIN_STAGE``,
    ``PI_IDENTITY_PROVEN``, ``PI_IDENTITY_GATE_UNEXPECTED_FAILURE``), a wrong
    ``Allowed_O``, a ``bool``/``int`` substitution, and a pass whose
    ``matched_profile_id`` is not in the sealed snapshot's eligible set -- so a
    malformed result can never fail open through Python truthiness.
    """
    if type(result) is not PiProofResult:
        raise Cfg1PiIdentityError("MALFORMED_PROOF_RESULT")
    code = result.failure_code
    complete = result.payload_observation_complete
    identity = result.identity
    if type(complete) is not bool:
        raise Cfg1PiIdentityError("MALFORMED_PROOF_RESULT")
    if code is None:
        if complete is not True or type(identity) is not Cfg1PiIdentity:
            raise Cfg1PiIdentityError("MALFORMED_PROOF_RESULT")
        matched = identity.matched_profile_id
        if not is_lowercase_hex64(matched) or matched not in sealed_policy_snapshot().eligible_profile_ids:
            raise Cfg1PiIdentityError("MALFORMED_PROOF_RESULT")
        return result
    if type(code) is not str or code not in PI_PROOF_FAILURE_CODES:
        raise Cfg1PiIdentityError("MALFORMED_PROOF_RESULT")
    if identity is not None or complete is not ALLOWED_PAYLOAD_OBSERVATION_COMPLETE[code]:
        raise Cfg1PiIdentityError("MALFORMED_PROOF_RESULT")
    return result


# ---------------------------------------------------------------------------
# L14 -- the launch-nearest re-proof (PE-1 Sec. 15.1). NOT a membership choice.
# ---------------------------------------------------------------------------


def reprove_pi_identity_for_launch(
    identity: object, *, leaves: PiProofLeaves
) -> bool:
    """L14's fixed-order re-proof of L1's EXACT matched profile.

    1. complete, uncached PI-PC1 walk -> ``pf'``;
    2. ``pf'`` equals the payload fingerprint of ``identity.matched_profile_id``
       (equality with L1's profile, NOT re-membership: a different but
       independently approved profile is refused);
    3. that profile's exposures absent;
    4. I_r re-proof; 5. I_n re-proof.

    Returns an exact ``True`` only when all five hold; the caller treats
    anything else, or a raise, as ``RUNTIME_LAUNCH_FAILED`` with no launch.
    The caller performs NOTHING that reads the Pi tree, resolves a name, or
    executes code between this returning ``True`` and ``Popen``. Residual,
    stated not closed: the check->use sliver from each read here to ``Popen``,
    now spanning the payload walk (R-SLIVER).
    """
    if type(identity) is not Cfg1PiIdentity or type(leaves) is not PiProofLeaves:
        return False
    view = eligible_profile_view(identity.matched_profile_id)
    observation = _observe_payload(leaves, identity.pi_package_root)
    if observation.complete is not True:
        return False
    if observation.payload_fingerprint != view.payload_fingerprint:
        return False
    if (
        observe_profile_exposures(
            identity.pi_package_root, view.resolution_exposures, inspect=leaves.inspect
        )
        != EXPOSURES_ABSENT
    ):
        return False
    if not _identity_still_holds(
        leaves,
        identity.pi_package_root,
        classification=CLASSIFICATION_DIRECTORY,
        expected=identity.package_root_identity,
    ):
        return False
    return _identity_still_holds(
        leaves,
        identity.node_executable,
        classification=CLASSIFICATION_REGULAR_FILE,
        expected=identity.node_identity,
    )


# ---------------------------------------------------------------------------
# L21A -- the mandatory post-runtime payload re-observation (PE-1 Sec. 15.2)
# ---------------------------------------------------------------------------


def reobserve_pi_profile_after_runtime(
    identity: object, *, leaves: PiProofLeaves, runtime_exit_observed: object
) -> str:
    """The L21A PROCEDURE for a run whose ``runtime_created`` is true.

    Complete walk -> ``pf''``; the matched profile's exposure check; I_r
    (``node.exe`` is outside the profile and is not re-proved). Returns one of
    ``CHANGED`` / ``UNPROVEN`` / ``PROVEN_UNCHANGED``, evaluated in that order:

    * ``CHANGED`` -- the walk completed and ``pf''`` differs from the run's
      profile fingerprint, or an exposure is PRESENT;
    * ``UNPROVEN`` -- not ``CHANGED``, and any of: ``runtime_exit_observed``
      is not exactly ``True``; the walk did not complete (or raised); an
      exposure was unobservable; I_r drifted (or its observation raised);
    * ``PROVEN_UNCHANGED`` -- otherwise.

    The executor alone decides ``NOT_APPLICABLE`` and contains any raise from
    here as ``UNPROVEN``. ``PROVEN_UNCHANGED`` means only that the payload at
    L14 and here were identical and the direct child had exited when this
    observed: no continuity between the two instants is claimed (an A->B->A
    change is undetectable, R-ABA), descendants are not tracked, and nothing
    is prevented. Executes nothing; reads no credential; writes nothing.
    """
    if type(identity) is not Cfg1PiIdentity or type(leaves) is not PiProofLeaves:
        return PI_PROFILE_REOBSERVATION_UNPROVEN
    view = eligible_profile_view(identity.matched_profile_id)

    walk_complete = False
    fingerprint_changed = False
    try:
        observation = _observe_payload(leaves, identity.pi_package_root)
        if observation.complete is True:
            walk_complete = True
            fingerprint_changed = observation.payload_fingerprint != view.payload_fingerprint
    except Exception:  # noqa: BLE001 - a walk that cannot complete is not complete
        walk_complete = False
        fingerprint_changed = False

    exposure = observe_profile_exposures(
        identity.pi_package_root, view.resolution_exposures, inspect=leaves.inspect
    )

    try:
        root_unchanged = _identity_still_holds(
            leaves,
            identity.pi_package_root,
            classification=CLASSIFICATION_DIRECTORY,
            expected=identity.package_root_identity,
        )
    except Exception:  # noqa: BLE001 - an unobservable root is not proven unchanged
        root_unchanged = False

    if fingerprint_changed or exposure == EXPOSURE_PRESENT:
        return PI_PROFILE_REOBSERVATION_CHANGED
    if (
        runtime_exit_observed is not True
        or not walk_complete
        or exposure != EXPOSURES_ABSENT
        or root_unchanged is not True
    ):
        return PI_PROFILE_REOBSERVATION_UNPROVEN
    return PI_PROFILE_REOBSERVATION_PROVEN_UNCHANGED


# ---------------------------------------------------------------------------
# The pre-consumption gate (PE-1 Sec. 13)
# ---------------------------------------------------------------------------


def pre_consumption_pi_identity_gate(ambient_environ: Mapping[str, str]) -> str:
    """Waste avoidance before ``establish_stage_output_authority``. ONE code out.

    Calls the SAME :func:`prove_pi_identity` with the SAME genuine leaves L1
    uses and the SAME module-level sealed snapshot. Reads exactly ``PATH``
    from ``ambient_environ``; reads no credential or endpoint; starts no
    process and executes no Node, Pi or JavaScript; writes nothing; never
    touches stage-output authority or ``RESULTS_ROOT``; and returns exactly
    one of the seven closed codes -- no identity object, path, digest, profile
    id or timestamp -- so nothing it observed can be reused by the run. Only
    the exact built-in ``str`` ``PI_IDENTITY_PROVEN`` is a pass. L1 re-proves
    from scratch; skipping this gate wastes an authorization but bypasses no
    security invariant. It never returns ``PI_PROFILE_CHANGED_WITHIN_STAGE``
    (it has no stage).
    """
    try:
        result = require_pi_proof_result_shape(
            prove_pi_identity(ambient_environ, leaves=genuine_pi_proof_leaves())
        )
    except Exception:  # noqa: BLE001 - reduced to one closed code; nothing escapes
        return PI_IDENTITY_GATE_UNEXPECTED_FAILURE
    if result.failure_code is None:
        return PI_IDENTITY_GATE_PASSED
    return result.failure_code
