"""The ONE canonical, static Pi identity proof P -- and its three consumers.

Design ``PHASE_5F3B_HARNESS_CFG1_L1_BOUNDARY_FU1_DESIGN.md`` (R6) Sec. 5/7,
as amended by ``..._OC3_AMEND1_DESIGN.md`` (AMD-1 .. AMD-8). The effective
proof is::

    P0   read exactly one ambient name, PATH, by name
    P1   resolve node.exe and the Pi package root (R6 Sec. 5 P1, unchanged);
         capture I_n (node.exe) and I_r (package root) -- Sec. 7.2 identities
    P2   the COMPLETE 20-file frozen seam proof, never a subset
    P2R  re-prove I_r and then I_n; no second seam walk
    ->   one typed PiProofResult

**P executes nothing.** It has no process-runner leaf, no child-environment
leaf, and no leaf whose genuine binding can create a process: its injectable
leaves are exactly the Sec. 7.2 no-follow inspection primitive and a
one-handle bounded digest reader (:mod:`pi_fs_leaves`), plus the explicit
ambient mapping it is handed. The ORDER lives in this module's own function
bodies, which no leaf can reorder. There is no ``--version`` probe anywhere:
the first execution of the resolved ``node.exe`` and the first evaluation of
Pi-controlled JavaScript in a CFG1 run is L14's ``launch()``, immediately
after :func:`reprove_pi_identity_for_launch` (AMD-6).

**Three consumers, one proof.**

* :func:`pre_consumption_pi_identity_gate` -- read-only, non-consuming waste
  avoidance, called by a future launcher before
  ``establish_stage_output_authority``. It returns ONE closed code and nothing
  reusable.
* L1 (``run_executor``) -- calls :func:`prove_pi_identity`, the SAME function
  object, from scratch. ``run_cfg1_stage`` has no parameter through which a
  gate observation could be handed to it.
* L14 (``run_executor``) -- calls :func:`reprove_pi_identity_for_launch`: the
  complete uncached seam re-walk, then I_r, then I_n, immediately before
  ``launch()``.

**What a pass establishes, exactly.** Filesystem and package provenance only:
resolution, the two Sec. 7.2 identities, and that the 20 pinned files --
among them the Pi root's own ``package.json`` -- are byte-identical to the
reviewed bytes. **Nothing ran, and nothing reported a version.** No field,
attribute or console code here is named ``version``, ``observed`` or
``reported``, and :data:`identity.PINNED_PI_VERSION` is never read.
"""

from __future__ import annotations

import ntpath
import os
from pathlib import Path
from typing import Callable, Mapping

from . import pi_fs_leaves
from .pi_fs_leaves import (
    CLASSIFICATION_DIRECTORY,
    CLASSIFICATION_MISSING,
    CLASSIFICATION_REGULAR_FILE,
    CLASSIFICATIONS,
    BoundedSeamRead,
    NoFollowObservation,
)
from .preflight import PINNED_PI_SEAM_DIGESTS

# ---------------------------------------------------------------------------
# Closed vocabularies
# ---------------------------------------------------------------------------

#: AMEND1 Sec. 8.1 -- exactly three anticipated P refusal codes. They live
#: ONLY in ``pi_identity_failure_code``; they are never refusal codes.
PI_RESOLUTION_FAILED = "PI_RESOLUTION_FAILED"
PI_SEAM_UNPROVEN = "PI_SEAM_UNPROVEN"
PI_IDENTITY_DRIFTED_DURING_PROOF = "PI_IDENTITY_DRIFTED_DURING_PROOF"

PI_IDENTITY_FAILURE_CODES: frozenset[str] = frozenset(
    {PI_RESOLUTION_FAILED, PI_SEAM_UNPROVEN, PI_IDENTITY_DRIFTED_DURING_PROOF}
)

#: ``Allowed(F)`` (AMEND1 Sec. 8.2): the one ``pi_seam_digests_match`` value
#: each anticipated refusal can carry.
ALLOWED_SEAM_MATCH_FOR_FAILURE: dict[str, bool] = {
    PI_RESOLUTION_FAILED: False,
    PI_SEAM_UNPROVEN: False,
    PI_IDENTITY_DRIFTED_DURING_PROOF: True,
}

#: The gate's two non-P closed codes. A gate that could not complete its own
#: proof says so; it never reports a pass it did not observe.
PI_IDENTITY_GATE_PASSED = "PI_IDENTITY_PROVEN"
PI_IDENTITY_GATE_UNEXPECTED_FAILURE = "PI_IDENTITY_GATE_UNEXPECTED_FAILURE"

PI_IDENTITY_GATE_CODES: frozenset[str] = frozenset(
    {PI_IDENTITY_GATE_PASSED, PI_IDENTITY_GATE_UNEXPECTED_FAILURE}
    | PI_IDENTITY_FAILURE_CODES
)

#: The complete frozen seam table has exactly this many entries (CFG1 Sec.
#: 14.2). A table of any other size is never accepted as "the complete set".
PINNED_SEAM_ENTRY_COUNT = 20

#: The per-file bound for one seam digest read (R6 Sec. 5 P2: "bounded size").
MAX_SEAM_FILE_BYTES = 16 * 1024 * 1024

#: The two AR2 package-root layouts a ``pi.cmd`` anchors (R6 Sec. 5 P1).
_PI_PACKAGE_PARTS: tuple[str, ...] = ("node_modules", "@earendil-works", "pi-coding-agent")

_NODE_NAME = "node.exe"
_PI_ANCHOR_NAME = "pi.cmd"


class Cfg1PiIdentityError(Exception):
    """P could not run its own proof (a malformed input or leaf output).

    NOT an anticipated refusal: it propagates to L1's catch-all, which records
    ``UNEXPECTED_STEP_FAILURE`` with ``pi_identity_failure_code = null``. It
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
    """AMEND1 Sec. 10: the CFG1-owned static identity object L12 and L14 use.

    Exactly five attributes and nothing else -- deliberately no
    ``reported_version``, ``version`` or ``launch_shape``. It is never durable,
    never rendered, never returned by the gate, never accepted by
    ``run_cfg1_stage``, and constructible only by a passing P.

    The frozen ``ar2.launch.build_pi_argv`` reads exactly ``node_executable``
    and ``pi_cli_js`` from it (Test AG pins that); ``ar2.launch.RuntimeIdentity``
    is deliberately NOT constructed, because it would need a version value.
    """

    __slots__ = (
        "node_executable",
        "pi_cli_js",
        "pi_package_root",
        "node_identity",
        "package_root_identity",
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
    ) -> None:
        if key is not _P_ONLY:
            raise Cfg1PiIdentityError("IDENTITY_NOT_PRODUCED_BY_P")
        for value in (node_executable, pi_cli_js, pi_package_root):
            if type(value) is not str or not value:
                raise Cfg1PiIdentityError("MALFORMED_IDENTITY_PATH")
        object.__setattr__(self, "node_executable", node_executable)
        object.__setattr__(self, "pi_cli_js", pi_cli_js)
        object.__setattr__(self, "pi_package_root", pi_package_root)
        object.__setattr__(self, "node_identity", _require_identity_pair(node_identity))
        object.__setattr__(
            self, "package_root_identity", _require_identity_pair(package_root_identity)
        )

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

    Pass: ``failure_code is None``, ``seam_digests_match is True`` and
    ``identity`` is a :class:`Cfg1PiIdentity`. Refusal: ``failure_code`` is one
    of the three codes, ``seam_digests_match`` is its ``Allowed(F)`` value,
    and ``identity is None``. L1 re-validates this exact shape before it
    commits anything.
    """

    __slots__ = ("seam_digests_match", "failure_code", "identity")

    def __init__(
        self,
        key: object,
        *,
        seam_digests_match: bool,
        failure_code: str | None,
        identity: Cfg1PiIdentity | None,
    ) -> None:
        if key is not _P_ONLY:
            raise Cfg1PiIdentityError("RESULT_NOT_PRODUCED_BY_P")
        object.__setattr__(self, "seam_digests_match", seam_digests_match)
        object.__setattr__(self, "failure_code", failure_code)
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

    ``inspect``
        the Sec. 7.2 no-follow inspection/identity primitive
    ``read_digest``
        the one-handle bounded digest reader
    ``checkout_root``
        not an effect: the checkout P0 derives from this package's own
        location, used for containment refusal only

    There is no field through which a process runner, a child-environment
    builder, or any other executing leaf could be supplied (Test L asserts
    the slot set structurally).
    """

    __slots__ = ("inspect", "read_digest", "checkout_root")

    def __init__(
        self,
        *,
        inspect: Callable[[str], NoFollowObservation],
        read_digest: Callable[[str, int], BoundedSeamRead],
        checkout_root: str,
    ) -> None:
        if not callable(inspect) or not callable(read_digest):
            raise Cfg1PiIdentityError("MALFORMED_PROOF_LEAVES")
        if type(checkout_root) is not str or not ntpath.isabs(checkout_root):
            raise Cfg1PiIdentityError("MALFORMED_CHECKOUT_ROOT")
        object.__setattr__(self, "inspect", inspect)
        object.__setattr__(self, "read_digest", read_digest)
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
    """The ONE genuine leaf binding. Shared by the gate, L1 and L14.

    Takes no parameter, so a caller cannot select a leaf. The two effects are
    looked up on :mod:`pi_fs_leaves` at call time.
    """
    return PiProofLeaves(
        inspect=pi_fs_leaves.inspect_no_follow,
        read_digest=pi_fs_leaves.read_bounded_digest,
        checkout_root=_GENUINE_CHECKOUT_ROOT,
    )


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


def _read_seam(leaves: PiProofLeaves, path: str) -> BoundedSeamRead:
    seam = leaves.read_digest(path, MAX_SEAM_FILE_BYTES)
    if type(seam) is not BoundedSeamRead:
        raise Cfg1PiIdentityError("MALFORMED_LEAF_DIGEST")
    if type(seam.classification) is not str or seam.classification not in CLASSIFICATIONS:
        raise Cfg1PiIdentityError("MALFORMED_LEAF_DIGEST")
    if type(seam.within_bound) is not bool:
        raise Cfg1PiIdentityError("MALFORMED_LEAF_DIGEST")
    if seam.sha256 is not None and type(seam.sha256) is not str:
        raise Cfg1PiIdentityError("MALFORMED_LEAF_DIGEST")
    return seam


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
# P1 -- resolution (R6 Sec. 5 P1, preserved exactly by AMEND1 Sec. 4)
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
    """The FIRST ``PATH`` entry holding exactly ``name``, as a regular file.

    Returns ``(entry, candidate, identity)``, or ``None`` for a refusal. An
    unsafe entry met before the name is found refuses the whole pass; a
    candidate that is not a regular file refuses; a candidate is never
    retried against a later entry. There is no ``PATHEXT`` expansion.
    """
    for entry in entries:
        status, _identity = _walk_directories(leaves, entry)
        if status == _WALK_MISSING:
            continue
        if status == _WALK_UNSAFE:
            return None
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
        # layout is never searched for one that would pass P2.
        if not _outside_checkout(layout, leaves.checkout_root):
            return None
        return layout, root_identity
    return None


# ---------------------------------------------------------------------------
# P2 / L14 (a) -- the complete seam proof
# ---------------------------------------------------------------------------


def _complete_seam_set_matches(leaves: PiProofLeaves, package_root: str) -> bool:
    """EVERY key of ``PINNED_PI_SEAM_DIGESTS``, walked lexically, no-follow.

    Each directory component must be a directory; the final entry must be a
    regular file within the bound, digested through ONE handle, and equal to
    its pin. Only pinned relative keys are ever formed -- no absolute path
    leaves this function. Never cached: every call re-reads every file.
    """
    if len(PINNED_PI_SEAM_DIGESTS) != PINNED_SEAM_ENTRY_COUNT:
        raise Cfg1PiIdentityError("SEAM_TABLE_INCOMPLETE")
    for relative in sorted(PINNED_PI_SEAM_DIGESTS):
        expected = PINNED_PI_SEAM_DIGESTS[relative]
        parts = relative.split("/")
        current = package_root
        for part in parts[:-1]:
            current = ntpath.join(current, part)
            if _observe(leaves, current).classification != CLASSIFICATION_DIRECTORY:
                return False
        seam = _read_seam(leaves, ntpath.join(current, parts[-1]))
        if (
            seam.classification != CLASSIFICATION_REGULAR_FILE
            or seam.within_bound is not True
            or seam.sha256 != expected
        ):
            return False
    return True


def _identity_still_holds(
    leaves: PiProofLeaves, path: str, *, classification: str, expected: tuple[int, int]
) -> bool:
    """Sec. 7.2 step 3: re-classify, re-capture, compare. Anything else fails."""
    observation = _observe(leaves, path)
    return observation.classification == classification and observation.identity == expected


# ---------------------------------------------------------------------------
# P itself
# ---------------------------------------------------------------------------


def _refusal(failure_code: str, *, seam_digests_match: bool) -> PiProofResult:
    return PiProofResult(
        _P_ONLY,
        seam_digests_match=seam_digests_match,
        failure_code=failure_code,
        identity=None,
    )


def prove_pi_identity(
    ambient_environ: Mapping[str, str], *, leaves: PiProofLeaves
) -> PiProofResult:
    """THE canonical static Pi identity proof. Starts no process, ever.

    Anticipated failures are RETURNED as a typed refusal, never raised.
    Anything this function cannot complete (a malformed leaf output, a leaf
    that raises, a truncated seam table) propagates as an exception, so L1
    records it as ``UNEXPECTED_STEP_FAILURE`` with nothing of P's family
    committed.
    """
    if type(leaves) is not PiProofLeaves:
        raise Cfg1PiIdentityError("MALFORMED_PROOF_LEAVES")

    # -- P0: exactly one ambient name, by name ------------------------------
    try:
        path_value = ambient_environ["PATH"]
    except KeyError:
        return _refusal(PI_RESOLUTION_FAILED, seam_digests_match=False)
    if type(path_value) is not str:
        return _refusal(PI_RESOLUTION_FAILED, seam_digests_match=False)

    # -- P1: resolve and capture I_n, I_r -----------------------------------
    entries = _path_entries(path_value)
    node = _resolve_node(leaves, entries)
    if node is None:
        return _refusal(PI_RESOLUTION_FAILED, seam_digests_match=False)
    root = _resolve_package_root(leaves, entries)
    if root is None:
        return _refusal(PI_RESOLUTION_FAILED, seam_digests_match=False)
    node_path, node_identity = node
    root_path, root_identity = root

    # -- P2: the complete seam proof ----------------------------------------
    if not _complete_seam_set_matches(leaves, root_path):
        return _refusal(PI_SEAM_UNPROVEN, seam_digests_match=False)

    # -- P2R: identity consistency -- root first, then node.exe -------------
    if not _identity_still_holds(
        leaves, root_path, classification=CLASSIFICATION_DIRECTORY, expected=root_identity
    ):
        return _refusal(PI_IDENTITY_DRIFTED_DURING_PROOF, seam_digests_match=True)
    if not _identity_still_holds(
        leaves, node_path, classification=CLASSIFICATION_REGULAR_FILE, expected=node_identity
    ):
        return _refusal(PI_IDENTITY_DRIFTED_DURING_PROOF, seam_digests_match=True)

    identity = Cfg1PiIdentity(
        _P_ONLY,
        node_executable=node_path,
        pi_cli_js=ntpath.join(root_path, "dist", "cli.js"),
        pi_package_root=root_path,
        node_identity=node_identity,
        package_root_identity=root_identity,
    )
    return PiProofResult(
        _P_ONLY, seam_digests_match=True, failure_code=None, identity=identity
    )


def require_pi_proof_result_shape(result: object) -> PiProofResult:
    """L1's exact-shape validation of P's result, BEFORE anything is committed.

    Raises :class:`Cfg1PiIdentityError` for anything that is not exactly one of
    the two admissible shapes, so a malformed result can never fail open
    through Python truthiness and is recorded as an unexpected failure.
    """
    if type(result) is not PiProofResult:
        raise Cfg1PiIdentityError("MALFORMED_PROOF_RESULT")
    seam = result.seam_digests_match
    code = result.failure_code
    identity = result.identity
    if type(seam) is not bool:
        raise Cfg1PiIdentityError("MALFORMED_PROOF_RESULT")
    if code is None:
        if seam is not True or type(identity) is not Cfg1PiIdentity:
            raise Cfg1PiIdentityError("MALFORMED_PROOF_RESULT")
        return result
    if type(code) is not str or code not in PI_IDENTITY_FAILURE_CODES:
        raise Cfg1PiIdentityError("MALFORMED_PROOF_RESULT")
    if identity is not None or seam is not ALLOWED_SEAM_MATCH_FOR_FAILURE[code]:
        raise Cfg1PiIdentityError("MALFORMED_PROOF_RESULT")
    return result


# ---------------------------------------------------------------------------
# L14 -- the sole pre-first-execution proof (AMD-6)
# ---------------------------------------------------------------------------


def reprove_pi_identity_for_launch(
    identity: object, *, leaves: PiProofLeaves
) -> bool:
    """L14's fixed-order re-proof: (a) all 20 seams, (b) I_r, (c) I_n.

    Uncached and complete; the two identity checks sit nearest the use.
    Returns an exact ``True`` only when all three hold. The caller performs
    NOTHING that reads the Pi tree, resolves a name, or executes code between
    this returning ``True`` and ``Popen``. Residual, stated not closed: the
    check->use sliver from each item's own read here to ``Popen``.
    """
    if type(identity) is not Cfg1PiIdentity or type(leaves) is not PiProofLeaves:
        return False
    if not _complete_seam_set_matches(leaves, identity.pi_package_root):
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
# The pre-consumption gate (R6 Sec. 7.1, AMEND1 Sec. 12)
# ---------------------------------------------------------------------------


def pre_consumption_pi_identity_gate(ambient_environ: Mapping[str, str]) -> str:
    """Waste avoidance before ``establish_stage_output_authority``. ONE code out.

    Calls the SAME :func:`prove_pi_identity` with the SAME genuine leaves L1
    uses. Reads exactly ``PATH`` from ``ambient_environ``; reads no credential
    or endpoint; starts no process and executes no Node, Pi or JavaScript;
    writes nothing; never touches stage-output authority or ``RESULTS_ROOT``;
    and returns only a closed code -- no identity object, path, digest or
    timestamp -- so nothing it observed can be reused by the run. L1 re-proves
    from scratch; skipping this gate wastes an authorization but bypasses no
    security invariant.
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
