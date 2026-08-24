"""The AR2 delegated implementation capability: SED + RS. EXPERIMENT ONLY.

FU1 section 3 replaced AR2D's "monotonically shrinking" vocabulary with an
explicit two-layer model, and this module implements exactly that model.

    The static read/write eligibility domains are immutable after mint and never
    expand. Runtime events may satisfy fixed operation preconditions, such as the
    write-after-read precondition, while consumption budgets can only reduce
    remaining authority. No runtime request can add a new path, operation class,
    exclusion exception, cap, root, or privilege to the minted capability.

Layer 1 -- :class:`StaticEligibilityDomain` (SED). Frozen at mint, before Pi is
launched. Never expands, never contracts.

Layer 2 -- :class:`RunState` (RS). AIDO-owned, AIDO-authored, mutable. Nothing in
it is supplied, named, or negotiated by the runtime.

The set AIDO will authorize *right now* is::

    OIS(t) = { (op, path) : path in SED(op)
                            AND every FIXED precondition of op is satisfied by RS(t) }

``OIS`` is **not** monotone. ``SED`` is immutable. Remaining authority is
non-increasing. All three are true at once, and no sentence in AR2 asserts
monotonic shrinkage of the capability as a whole.
"""

from __future__ import annotations

import fnmatch
import json
import os
import secrets
import stat as stat_module
import tempfile
from dataclasses import dataclass, field
from typing import Any

from ai_dev_orchestrator.workspace.canonical import _is_symlink_or_reparse_point

# -- operation classes ---------------------------------------------------------

READ_FILE = "read_file"
EDIT_FILE = "edit_file"
OPERATION_CLASSES: frozenset[str] = frozenset({READ_FILE, EDIT_FILE})

ROOT_CLASS_DISPOSABLE_SYNTHETIC = "disposable_synthetic"

# -- cap DEFINITIONS (the numbers themselves, never the remaining balances) ----

MAX_READ_BYTES_PER_FILE = 256 * 1024
MAX_READ_BYTES_PER_RUN = 1024 * 1024
MAX_READ_OPERATIONS_PER_RUN = 32

MAX_CHANGED_FILES_PER_RUN = 2
MAX_EDIT_OPERATIONS_PER_RUN = 16
MAX_WRITE_BYTES_PER_RUN = 512 * 1024
MAX_POST_IMAGE_BYTES = 256 * 1024


@dataclass(frozen=True)
class CapDefinitions:
    """The cap definitions. Immutable, and part of the SED."""

    max_read_bytes_per_file: int = MAX_READ_BYTES_PER_FILE
    max_read_bytes_per_run: int = MAX_READ_BYTES_PER_RUN
    max_read_operations_per_run: int = MAX_READ_OPERATIONS_PER_RUN
    max_changed_files_per_run: int = MAX_CHANGED_FILES_PER_RUN
    max_edit_operations_per_run: int = MAX_EDIT_OPERATIONS_PER_RUN
    max_write_bytes_per_run: int = MAX_WRITE_BYTES_PER_RUN
    max_post_image_bytes: int = MAX_POST_IMAGE_BYTES

    def as_dict(self) -> dict[str, int]:
        return {
            "max_read_bytes_per_file": self.max_read_bytes_per_file,
            "max_read_bytes_per_run": self.max_read_bytes_per_run,
            "max_read_operations_per_run": self.max_read_operations_per_run,
            "max_changed_files_per_run": self.max_changed_files_per_run,
            "max_edit_operations_per_run": self.max_edit_operations_per_run,
            "max_write_bytes_per_run": self.max_write_bytes_per_run,
            "max_post_image_bytes": self.max_post_image_bytes,
        }


# -- exclusions ----------------------------------------------------------------
#
# Matched case-insensitively against the repository-relative POSIX path, because
# this is a Windows experiment and ``Calc.py`` and ``calc.py`` name one file.
# ``fnmatch``'s ``*`` crosses ``/``, which is why a bare pattern and a ``*/``
# prefixed pattern together cover root-level and nested spellings.

FORBIDDEN_READ_PATTERNS: tuple[str, ...] = (
    # Repository and runtime state: never repository content.
    ".git/*", "*/.git/*", ".git", "*/.git",
    ".pi/*", "*/.pi/*", ".pi", "*/.pi",
    # Environment / credential / key shapes. A backstop, never a guarantee.
    ".env", ".env.*", "*/.env", "*/.env.*",
    "*.pem", "*.key", "*.pfx", "*.p12", "*.jks",
    "id_rsa*", "*/id_rsa*",
    "*credentials*", "*secret*",
    # Generated / vendor trees: huge, low value, high context cost.
    "node_modules/*", "*/node_modules/*",
    "dist/*", "*/dist/*",
    "build/*", "*/build/*",
    ".venv/*", "*/.venv/*",
    "*.min.*",
    # Repository lockfiles.
    "package-lock.json", "*/package-lock.json",
    "yarn.lock", "*/yarn.lock",
    "pnpm-lock.yaml", "*/pnpm-lock.yaml",
    "poetry.lock", "*/poetry.lock",
    "cargo.lock", "*/cargo.lock",
    "uv.lock", "*/uv.lock",
    # Repository guidance files. This is an INJECTION control, not a
    # confidentiality one: content read through the broker is data to AIDO and
    # reads as INSTRUCTIONS to the model (AR2D section 5.4). It is a decision
    # about AR2's broker read channel only, and it does NOT establish that a
    # future AIDO-controlled guidance channel can never exist (FU1 section 13).
    "agents.md", "*/agents.md",
    "agents.override.md", "*/agents.override.md",
    "claude.md", "*/claude.md",
    ".cursorrules", "*/.cursorrules",
    "copilot-instructions.md", "*/copilot-instructions.md",
)


def matches_forbidden(relative_posix_path: str) -> str | None:
    """The first forbidden pattern this path matches, or ``None``."""
    lowered = relative_posix_path.lower()
    for pattern in FORBIDDEN_READ_PATTERNS:
        if fnmatch.fnmatchcase(lowered, pattern):
            return pattern
    return None


def matches_any(relative_posix_path: str, patterns: tuple[str, ...]) -> bool:
    lowered = relative_posix_path.lower()
    return any(fnmatch.fnmatchcase(lowered, p.lower()) for p in patterns)


# -- layer 1: the static eligibility domain ------------------------------------


@dataclass(frozen=True)
class StaticEligibilityDomain:
    """Layer 1. Minted before launch; immutable for the run.

    Frozen on purpose: the immutability is a language-enforced property a test
    can assert, not a comment. ``read_eligible`` and ``write_eligible`` hold
    repository-relative POSIX paths exactly as the mint-time ``ls_files_stage``
    manifest spelled them.
    """

    capability_id: str
    canonical_root: str
    root_class: str
    operation_classes: frozenset[str]
    manifest: tuple[str, ...]
    read_eligible: frozenset[str]
    write_eligible: frozenset[str]
    protected_paths: frozenset[str]
    verification_witness_paths: frozenset[str]
    excluded: tuple[tuple[str, str], ...]
    caps: CapDefinitions
    lifetime: str

    # -- static eligibility predicates (mint-time facts only) ------------------

    def is_read_eligible(self, relative_posix_path: str) -> bool:
        return relative_posix_path in self.read_eligible

    def is_write_eligible(self, relative_posix_path: str) -> bool:
        return relative_posix_path in self.write_eligible

    def canonical_manifest_spelling(self, relative_posix_path: str) -> str | None:
        """The manifest's own spelling of a case-insensitively equal path."""
        if relative_posix_path in self.read_eligible:
            return relative_posix_path
        lowered = relative_posix_path.lower()
        for entry in self.manifest:
            if entry.lower() == lowered:
                return entry
        return None

    def summary(self) -> dict[str, Any]:
        """A recordable SED summary. No absolute host path, ever."""
        return {
            "capability_id": self.capability_id,
            "canonical_root_recorded": False,
            "root_class": self.root_class,
            "operation_classes": sorted(self.operation_classes),
            "tracked_manifest_entry_count": len(self.manifest),
            "read_eligible_count": len(self.read_eligible),
            "read_eligible_paths": sorted(self.read_eligible),
            "write_eligible_count": len(self.write_eligible),
            "write_eligible_paths": sorted(self.write_eligible),
            "protected_paths": sorted(self.protected_paths),
            "verification_witness_paths": sorted(self.verification_witness_paths),
            "excluded_path_count": len(self.excluded),
            "excluded_paths_with_reason": [
                {"path": path, "reason": reason} for path, reason in self.excluded
            ],
            "write_domain_is_proper_subset_of_read_domain": (
                self.write_eligible < self.read_eligible
            ),
            "cap_definitions": self.caps.as_dict(),
            "lifetime": self.lifetime,
            "immutability": (
                "The static read/write eligibility domains are immutable after "
                "mint and never expand. No runtime request can add a path, "
                "operation class, exclusion exception, cap, root, or privilege."
            ),
        }


class CapabilityMintError(Exception):
    """The delegated capability could not be minted. Fails closed."""


class RootAuthorityError(CapabilityMintError):
    """A presented :class:`DisposableRootAuthority` does not hold up under
    independent verification. Always fails closed."""


# The one file whose presence and content PROVE a root was created BY
# ``ar2.fixtures.create_disposable_experiment_root`` -- never retroactively
# stamped onto a pre-existing directory. A fixed, non-secret name: unlike the
# marker's nonce, the filename itself carries no proof value on its own, so
# there is nothing gained by keeping it out of source.
ROOT_AUTHORITY_MARKER_FILENAME = ".aido_ar2_disposable_root_authority"

# The fixed marker schema. Bumping this is a breaking change to what
# ``mint_capability`` will accept; every marker AIDO writes carries it, and a
# marker at a different version is refused rather than interpreted leniently.
ROOT_AUTHORITY_MARKER_SCHEMA = "ar2-root-authority.v1"

# The one relative name a case repository is ever created under, beneath its
# freshly-created experiment root. Recorded IN the marker (not merely assumed)
# so mint_capability verifies the structural relationship against a claim that
# was fixed at creation time, not against a constant it would otherwise have to
# trust the caller to have honored.
DEFAULT_REPO_CHILD_NAME = "repo"


@dataclass(frozen=True)
class DisposableRootAuthority:
    """Experiment-local provenance proving one root was CREATED BY AIDO itself.

    5F3A-AR2-FU1A closes the residual FU-A gap: the first version of this type
    could be obtained for ANY already-existing directory by calling
    ``create_disposable_root_authority(that_directory)`` -- a function that
    accepted a bare path and retroactively wrote a marker into its parent. That
    proved only "this directory was stamped, at some point, by something that
    called the stamping function" -- not "this exact disposable experiment
    root was created by AIDO's fixture creation path." Any caller holding a
    string could convert it.

    There is no such function any more. Authority now originates ONLY at
    :func:`ar2.fixtures.create_disposable_experiment_root`, which creates a
    FRESH directory itself (``tempfile.mkdtemp()``, guaranteed not to have
    existed a moment before), writes the marker as part of that same creation
    step (exclusive create -- fails if one is somehow already there, rather
    than overwriting), and returns this object. ``repo_root`` names a
    location beneath that fresh root that does not exist yet either; the
    caller (:func:`ar2.fixtures.build_case_repository` or
    :func:`ar2.fixtures.build_synthetic_repository`) creates exactly that one
    directory next. Nothing can retroactively convert an arbitrary existing
    directory into one of these.

    **This is not a defense against a same-user adversary.** It is protection
    against an AIDO configuration or programming mistake -- a stale variable, a
    copy-paste error, a future refactor that hands ``mint_capability`` the
    wrong object. A same-user process could forge a matching marker file
    trivially; it does not need to, because it does not need the broker at all
    (AR2D section 10.4's reasoning applies here identically).

    :func:`mint_capability` trusts none of these fields at face value: it
    independently re-reads the on-disk marker, and re-derives the temp-scratch
    and structural-relationship facts, rather than trusting the object.
    """

    experiment_id: str
    case_id: str
    experiment_root: str
    repo_root: str
    repo_child_name: str
    nonce: str


def _diagnostic_forbidden_root(candidate_root: str) -> str | None:
    """A cheap, belt-and-braces denylist check. **NOT the proof.**

    This is the ENTIRE mechanism the pre-FU-A design relied on, demoted to a
    diagnostic: it catches an obviously wrong candidate cheaply and early, before
    :func:`_verify_root_authority` ever touches the marker file, but a candidate
    passing this check is not thereby authorized. Only a verified marker match,
    inside the approved scratch boundary, authorizes anything.
    """
    normalized = os.path.normcase(os.path.realpath(candidate_root))
    orchestrator = os.path.normcase(
        os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    )
    if normalized == orchestrator:
        return "the delegated root is the orchestrator repository itself"
    if orchestrator.startswith(normalized + os.sep) or normalized == os.path.normcase(
        os.path.dirname(orchestrator)
    ):
        return "the delegated root is at or above the orchestrator repository"
    for reserved in (
        "c:\\dev\\mis_project",
        "c:\\dev\\a8_oa",
        "c:\\dev\\bible_reading_v2",
    ):
        if normalized == reserved or normalized.startswith(reserved + os.sep):
            return "the delegated root names a real project workspace"
    return None


def diagnostic_forbidden_root_reason(candidate_root: str) -> str | None:
    """Public accessor for :func:`_diagnostic_forbidden_root`.

    Used by ``ar2.fixtures.create_disposable_experiment_root`` so the same
    belt-and-braces check runs at creation time too -- the one function
    allowed to create and mark a fresh root must not be able to authorize a
    real workspace by mistake either (it never should reach one, since it
    always calls ``tempfile.mkdtemp()`` itself, but the check costs nothing).
    """
    return _diagnostic_forbidden_root(candidate_root)


def approved_scratch_boundary() -> str:
    """The canonical, realpath'd system temp directory AR2 roots must live under.

    Not a denylist of what is forbidden -- a POSITIVE boundary of what is
    approved. ``ar2.fixtures.create_disposable_experiment_root`` always creates
    fresh roots here via ``tempfile.mkdtemp()``; :func:`_verify_root_authority`
    independently re-derives and re-checks the same boundary rather than
    trusting that fact about how the authority was built.
    """
    return os.path.normcase(os.path.realpath(tempfile.gettempdir()))


def _is_safe_repo_child_name(name: str) -> bool:
    """A repo child name must be one plain path SEGMENT -- never a traversal."""
    if not name or name in (".", ".."):
        return False
    return os.sep not in name and (os.altsep is None or os.altsep not in name)


def _verify_root_authority(authority: DisposableRootAuthority) -> str:
    """Independently prove ``authority`` names a root AIDO actually created.

    Returns the verified, canonical repo root on success. Raises
    :class:`RootAuthorityError` on ANY discrepancy: a missing marker, a
    mismatched claim, a structural mismatch between ``repo_root`` and
    ``experiment_root``, a root outside the approved scratch boundary, a
    non-canonical claimed path, a reparse-point marker, or a match against the
    belt-and-braces denylist. Nothing in ``authority`` is trusted at face value
    -- every claim is re-derived from the object's own internal consistency, or
    re-read fresh from disk.
    """
    if not isinstance(authority, DisposableRootAuthority):
        raise RootAuthorityError(
            "capability mint refused: no DisposableRootAuthority was presented"
        )

    # Cheap, string-only diagnostic FIRST, so a hard-coded forbidden path is
    # refused before any marker-file access is attempted.
    for candidate in (authority.repo_root, authority.experiment_root):
        reason = _diagnostic_forbidden_root(candidate)
        if reason is not None:
            raise RootAuthorityError(f"capability mint refused: {reason}")

    # The claimed paths must already be canonical. A caller presenting a
    # non-canonical spelling (a trailing slash, an unresolved '..', different
    # casing) is refused rather than silently normalized on its behalf.
    if os.path.realpath(authority.repo_root) != authority.repo_root:
        raise RootAuthorityError(
            "capability mint refused: authority.repo_root is not already canonical"
        )
    if os.path.realpath(authority.experiment_root) != authority.experiment_root:
        raise RootAuthorityError(
            "capability mint refused: authority.experiment_root is not already "
            "canonical"
        )

    # THE SCRATCH-BOUNDARY PROOF. A real project path does not become eligible
    # merely because a caller constructs a DisposableRootAuthority object by
    # hand -- this check runs regardless of how the object was obtained, and it
    # is a POSITIVE membership test (inside the approved temp domain), not
    # another entry on a denylist.
    boundary = approved_scratch_boundary()
    normalized_experiment_root = os.path.normcase(authority.experiment_root)
    if not normalized_experiment_root.startswith(boundary + os.sep):
        raise RootAuthorityError(
            "capability mint refused: experiment_root is not inside the "
            "approved temp/scratch boundary"
        )

    # The expected structural relationship, verified against the CHILD NAME
    # the marker itself will claim (checked below), not merely assumed.
    if not _is_safe_repo_child_name(authority.repo_child_name):
        raise RootAuthorityError(
            "capability mint refused: repo_child_name is not one safe path segment"
        )
    if authority.repo_root != os.path.join(authority.experiment_root, authority.repo_child_name):
        raise RootAuthorityError(
            "capability mint refused: repo_root does not have the expected "
            "relationship to experiment_root (repo_root must be exactly "
            "experiment_root/repo_child_name)"
        )

    # THE PROOF. Independently re-read the marker AIDO's own fixture creator
    # wrote to disk AT CREATION TIME, and require EXACT agreement on every
    # claimed field. A directory nobody has ever authorized -- a real project,
    # an unrelated tmp_path, a stale or deleted root -- has no such file, or
    # has a non-matching one, and is refused regardless of what the presented
    # authority object claims.
    marker_path = os.path.join(authority.experiment_root, ROOT_AUTHORITY_MARKER_FILENAME)
    try:
        marker_stat = os.lstat(marker_path)
    except OSError:
        raise RootAuthorityError(
            "capability mint refused: no root authority marker was found at the "
            "claimed experiment root; this root was never created by "
            "ar2.fixtures.create_disposable_experiment_root, or has since been "
            "removed"
        ) from None
    if _is_symlink_or_reparse_point(marker_stat):
        raise RootAuthorityError(
            "capability mint refused: the root authority marker is a symlink or "
            "reparse point, which is refused rather than followed"
        )
    if not stat_module.S_ISREG(marker_stat.st_mode):
        raise RootAuthorityError(
            "capability mint refused: the root authority marker is not a regular "
            "file"
        )
    try:
        with open(marker_path, encoding="utf-8") as handle:
            raw = handle.read()
    except OSError as exc:
        raise RootAuthorityError(
            f"capability mint refused: the root authority marker could not be "
            f"read: {type(exc).__name__}"
        ) from None
    try:
        marker = json.loads(raw)
    except json.JSONDecodeError:
        raise RootAuthorityError(
            "capability mint refused: the root authority marker is not valid JSON"
        ) from None
    if not isinstance(marker, dict):
        raise RootAuthorityError(
            "capability mint refused: the root authority marker is not a JSON object"
        )
    if marker.get("schema") != ROOT_AUTHORITY_MARKER_SCHEMA:
        raise RootAuthorityError(
            "capability mint refused: the root authority marker schema/version "
            "does not match"
        )
    if marker.get("experiment_id") != authority.experiment_id:
        raise RootAuthorityError(
            "capability mint refused: the root authority marker's experiment_id "
            "does not match"
        )
    if marker.get("case_id") != authority.case_id:
        raise RootAuthorityError(
            "capability mint refused: the root authority marker's case_id does "
            "not match"
        )
    if marker.get("repo_child_name") != authority.repo_child_name:
        raise RootAuthorityError(
            "capability mint refused: the root authority marker's "
            "repo_child_name does not match"
        )
    if marker.get("nonce") != authority.nonce:
        raise RootAuthorityError(
            "capability mint refused: the root authority marker's nonce does "
            "not match; this authority is stale, mismatched, or belongs to a "
            "different root"
        )

    return authority.repo_root


def mint_capability(
    *,
    authority: DisposableRootAuthority,
    tracked_manifest: tuple[str, ...],
    protected_patterns: tuple[str, ...] = (),
    verification_witness_paths: tuple[str, ...] = (),
    caps: CapDefinitions | None = None,
) -> StaticEligibilityDomain:
    """Mint the immutable SED. Called ONCE, before the runtime is launched.

    ``authority`` must be a :class:`DisposableRootAuthority` obtained from
    :func:`ar2.fixtures.create_disposable_experiment_root` (directly, or via
    :func:`ar2.fixtures.build_case_repository` /
    :func:`ar2.fixtures.build_synthetic_repository`); it is independently
    re-verified against the filesystem here rather than trusted (see
    :func:`_verify_root_authority`). There is no bare-string ``canonical_root``
    parameter, and no function anywhere that converts an existing directory
    into one of these: a caller cannot mint a capability for an arbitrary
    directory merely because that directory does not appear on a denylist.

    ``tracked_manifest`` comes from the accepted fixed ``ls_files_stage``
    operation, so no new Git operation is introduced and the runtime -- which has
    no shell and no ``git`` capability -- cannot change the index underneath it.

    Read eligibility is the tracked manifest minus every exclusion. Write
    eligibility is a **proper subset**: read-eligible, not protected, and not a
    declared verification witness. The proper-subset property is asserted here
    rather than left as a comment.
    """
    canonical_root = _verify_root_authority(authority)

    caps = caps or CapDefinitions()
    witnesses = frozenset(verification_witness_paths)

    read_eligible: set[str] = set()
    excluded: list[tuple[str, str]] = []
    for entry in tracked_manifest:
        pattern = matches_forbidden(entry)
        if pattern is not None:
            excluded.append((entry, "forbidden_pattern"))
            continue
        read_eligible.add(entry)

    protected: set[str] = {
        entry for entry in read_eligible if matches_any(entry, protected_patterns)
    }
    protected |= {entry for entry in read_eligible if entry in witnesses}

    write_eligible = {entry for entry in read_eligible if entry not in protected}

    if not write_eligible < read_eligible:
        raise CapabilityMintError(
            "capability mint refused: the static write eligibility domain is not a "
            "PROPER subset of the static read eligibility domain"
        )

    return StaticEligibilityDomain(
        capability_id="ar2-cap-" + secrets.token_hex(8),
        canonical_root=canonical_root,
        root_class=ROOT_CLASS_DISPOSABLE_SYNTHETIC,
        operation_classes=OPERATION_CLASSES,
        manifest=tuple(tracked_manifest),
        read_eligible=frozenset(read_eligible),
        write_eligible=frozenset(write_eligible),
        protected_paths=frozenset(protected),
        verification_witness_paths=witnesses,
        excluded=tuple(excluded),
        caps=caps,
        lifetime="one runtime process",
    )


# -- layer 2: AIDO-owned run state ---------------------------------------------

TERMINAL_PROTOCOL = "protocol_terminal"
TERMINAL_UNAUTHORIZED = "unauthorized"
TERMINAL_SHUTDOWN = "shutdown_requested"
TERMINAL_INTERNAL = "internal_error"


@dataclass
class ConsumedBudgets:
    """Consumption only. Never refilled, for any reason, by anything."""

    read_operations: int = 0
    read_bytes: int = 0
    edit_operations: int = 0
    write_bytes: int = 0
    changed_files: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "read_operations": self.read_operations,
            "read_bytes": self.read_bytes,
            "edit_operations": self.edit_operations,
            "write_bytes": self.write_bytes,
            "changed_files": self.changed_files,
        }


@dataclass
class RunState:
    """Layer 2. AIDO-owned and AIDO-authored; the runtime negotiates none of it."""

    caps: CapDefinitions
    read_receipts: dict[str, str] = field(default_factory=dict)
    consumed: ConsumedBudgets = field(default_factory=ConsumedBudgets)
    mutated_paths: list[str] = field(default_factory=list)
    seen_request_ids: set[str] = field(default_factory=set)
    terminal_flags: set[str] = field(default_factory=set)
    in_flight: bool = False
    lifecycle_state: str = "CREATED"

    # -- terminal state ---------------------------------------------------

    @property
    def terminal(self) -> bool:
        return bool(self.terminal_flags)

    def mark_terminal(self, flag: str) -> None:
        """Terminal flags are monotone: once terminal, terminal for the run."""
        self.terminal_flags.add(flag)

    # -- fixed preconditions, evaluated against RS ------------------------

    def read_budget_allows(self, byte_count: int) -> str | None:
        """``None`` when a read of ``byte_count`` bytes may proceed."""
        if self.consumed.read_operations >= self.caps.max_read_operations_per_run:
            return "read_operation_budget_exhausted"
        if self.consumed.read_bytes + byte_count > self.caps.max_read_bytes_per_run:
            return "aggregate_read_byte_budget_exhausted"
        return None

    def edit_budget_allows(self, relative_path: str, post_image_bytes: int) -> str | None:
        """``None`` when an edit producing ``post_image_bytes`` may proceed."""
        if self.consumed.edit_operations >= self.caps.max_edit_operations_per_run:
            return "edit_operation_budget_exhausted"
        if self.consumed.write_bytes + post_image_bytes > self.caps.max_write_bytes_per_run:
            return "write_byte_budget_exhausted"
        if (
            relative_path not in self.mutated_paths
            and len(self.mutated_paths) >= self.caps.max_changed_files_per_run
        ):
            return "changed_file_budget_exhausted"
        return None

    def has_read_receipt(self, relative_path: str) -> bool:
        return relative_path in self.read_receipts

    def receipt_matches(self, relative_path: str, presented_sha256: str) -> bool:
        recorded = self.read_receipts.get(relative_path)
        if recorded is None:
            return False
        return recorded.lower() == presented_sha256.lower()

    # -- AIDO-authored state transitions ----------------------------------

    def record_read(self, relative_path: str, sha256: str, byte_count: int) -> None:
        self.read_receipts[relative_path] = sha256
        self.consumed.read_operations += 1
        self.consumed.read_bytes += byte_count

    def record_edit(self, relative_path: str, post_sha256: str, post_bytes: int) -> None:
        """Replace the receipt with the post-image hash AIDO just computed.

        FU1 section 3.6: this is not domain growth (the path was already write
        eligible and already had a receipt), it is not a blind write (the runtime
        observed the pre-image and authored the exact splice), and it refills no
        budget -- every counter below is consumed normally.
        """
        self.read_receipts[relative_path] = post_sha256
        self.consumed.edit_operations += 1
        self.consumed.write_bytes += post_bytes
        if relative_path not in self.mutated_paths:
            self.mutated_paths.append(relative_path)
            self.consumed.changed_files += 1

    def as_dict(self) -> dict[str, Any]:
        return {
            "consumed_budgets": self.consumed.as_dict(),
            "read_receipt_path_count": len(self.read_receipts),
            "read_receipt_paths": sorted(self.read_receipts),
            "broker_recorded_mutated_paths": list(self.mutated_paths),
            "terminal_flags": sorted(self.terminal_flags),
            "request_ids_seen": len(self.seen_request_ids),
            "budgets_never_refilled": True,
        }
