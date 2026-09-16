"""Stage output filesystem authority -- provenance, not string manipulation.

Design Sec. 16.3 in full: the ``stage_execution_id`` identifier contract
(16.3.1), the fixed results root and its two-level provenance proof (16.3.2),
the mint-registry-backed :class:`CFG1StageOutputAuthority` (16.3.3), the
consumption-boundary re-proof (16.3.4), the structural containment proof
(16.3.5), one-shot execution-directory creation (16.3.6), the hard-stop rule
(16.3.7), and the ACTIVE/RETIRED lifecycle (16.3.9).

Three separate things this module refuses to conflate:

* an **identifier** is never a path fragment -- a small closed positive
  alphabet mechanically excludes ``.``, ``..``, both separators, drive and UNC
  forms, NUL, every other control character, and whitespace, with no
  normalization, stripping, truncation or repair anywhere;
* ``RESULTS_ROOT`` is **package infrastructure** -- present already is the
  ordinary case, and creating it when absent is not a security event -- while
  an **execution directory** is a one-shot evidence namespace whose existing
  case refuses the entire stage (Sec. 16.3.0);
* ``resolve()`` returning a value is **never** proof that value is the trusted
  root. A redirected lexical root resolves on both sides of a parent/child
  comparison and passes it, which is precisely the FU2 defect Sec. 16.3.2
  closes with an explicit, unconditional provenance proof at two levels.

Nothing in this module reads a CLI flag, a function parameter, an environment
variable or a config file to select or replace ``RESULTS_ROOT`` or
``_CAPTURED_PACKAGE_DIR``. Neither is part of the stage authorization's
vocabulary.
"""

from __future__ import annotations

import os
import re
import secrets
import stat as stat_module
from dataclasses import dataclass, field
from pathlib import Path

from ai_dev_orchestrator.workspace.canonical import _is_symlink_or_reparse_point

from .schedule import STAGE_IDS


class StageOutputAuthorityError(Exception):
    """Stage output authority could not be established or re-proven.

    Carries a CLOSED reason code and never raw exception text, a path, or any
    other unbounded detail (Sec. 21.1's reduction rule).
    """

    def __init__(self, reason_code: str) -> None:
        super().__init__(f"cfg1 stage output authority refused: {reason_code}")
        self.reason_code = reason_code


# ---------------------------------------------------------------------------
# Sec. 16.3.1 -- the identifier contract
# ---------------------------------------------------------------------------

#: The closed positive alphabet and length bound. ASCII letters, digits, ``-``
#: and ``_`` only, 1..64 characters. Because the alphabet excludes ``/``,
#: ``\``, ``:``, NUL, every other control character, whitespace and ``.``
#: itself, this ONE check mechanically refuses ``.``, ``..``, every absolute
#: Unix path, every Windows drive-qualified path, every UNC/device form, both
#: platforms' separators, and leading/trailing whitespace -- with no separate
#: check needed and no normalization ever attempted.
STAGE_EXECUTION_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,64}")
MAX_STAGE_EXECUTION_ID_LENGTH = 64


def _require_valid_stage_execution_id(value: object) -> str:
    """Read the identifier EXACTLY ONCE into one local binding, and prove it.

    ``type(value) is str`` exactly -- not ``isinstance``. A ``pathlib.Path``,
    any object with ``__fspath__``, a ``str`` subclass whose ``__eq__`` or
    ``__str__`` could disagree with its true content, an ``int``, a ``bool``,
    ``None``, and any Mapping/object wrapper are all refused here, before any
    filesystem access (T-19, T-22).

    Because the accepted value is an ordinary immutable ``str``, there is
    nothing left for a TOCTOU gap to exploit at the identifier itself: the
    binding returned here is what the frozen authority field stores.
    """
    if type(value) is not str:
        raise StageOutputAuthorityError("MALFORMED_STAGE_EXECUTION_ID")
    if STAGE_EXECUTION_ID_PATTERN.fullmatch(value) is None:
        raise StageOutputAuthorityError("MALFORMED_STAGE_EXECUTION_ID")
    return value


def _require_valid_stage_id(value: object) -> str:
    """The closed ``{"S1", "S2"}`` domain, exact ``str`` typing."""
    if type(value) is not str or value not in STAGE_IDS:
        raise StageOutputAuthorityError("UNKNOWN_STAGE_ID")
    return value


# ---------------------------------------------------------------------------
# Sec. 16.3.2 -- the fixed results root, proven at two levels
# ---------------------------------------------------------------------------

#: Captured EXACTLY ONCE, at module import -- a read, never a write. Every
#: later check re-proves THIS captured value rather than re-deriving
#: ``Path(__file__)`` again, which is what makes Level A a genuine re-proof of
#: the trusted package directory instead of a tautology.
#:
#: There is deliberately no supported way to replace it: no parameter, flag,
#: environment variable or config key reads or writes this name. (An offline
#: regression suite necessarily rebinds it to a synthetic directory under
#: ``tmp_path`` -- same-process memory manipulation by the test harness is
#: explicitly outside this design's threat model, Sec. 16.3.4, and T-43
#: cannot be constructed at all without it.)
_CAPTURED_PACKAGE_DIR: str = str(Path(__file__).resolve().parent)

#: The one fixed results-root component. A single literal, joined lexically.
RESULTS_ROOT_NAME = "results"


def _expected_results_root() -> Path:
    """The lexical join of the captured package directory and one literal.

    Not yet trusted: Level A must prove the parent, and Level B must prove
    this path itself, before either is used for anything.
    """
    return Path(_CAPTURED_PACKAGE_DIR) / RESULTS_ROOT_NAME


def _reprove_trusted_package_directory() -> str:
    """LEVEL A -- re-prove the captured package directory. No writes first.

    Runs before ANY ``RESULTS_ROOT`` ``mkdir`` or other filesystem write,
    every single time the root is established or re-proven, and is never
    reordered after Level B. Creation authority must never run ahead of the
    provenance proof of what it is creating under: a redirected package
    ancestor could otherwise get a foreign ``results/`` created under it, with
    only the subsequent check noticing -- after the write already happened.

    Step (d) is what catches an ANCESTOR-level redirect: steps (a)-(c) can see
    a perfectly ordinary, non-reparse leaf directory while
    ``resolve(strict=True)`` walks a now-redirected ancestor and returns a
    different canonical path. That is refused identically to a leaf-level
    redirect, never adopted as close enough.
    """
    captured = _CAPTURED_PACKAGE_DIR
    try:
        lex = os.lstat(captured)
    except OSError as exc:
        raise StageOutputAuthorityError("PACKAGE_DIR_ABSENT") from exc
    if _is_symlink_or_reparse_point(lex):
        raise StageOutputAuthorityError("PACKAGE_DIR_REDIRECTED")
    if not stat_module.S_ISDIR(lex.st_mode):
        raise StageOutputAuthorityError("PACKAGE_DIR_NOT_A_DIRECTORY")
    try:
        canonical = str(Path(captured).resolve(strict=True))
    except OSError as exc:
        raise StageOutputAuthorityError("PACKAGE_DIR_NOT_CANONICAL") from exc
    if canonical != captured:
        raise StageOutputAuthorityError("PACKAGE_DIR_NOT_CANONICAL")
    return canonical


def _prove_results_root(expected: Path) -> str:
    """LEVEL B step 2 -- unconditional provenance, never skipped.

    Runs whether or not step 1 created anything: ``exist_ok=True`` follows a
    symlink when deciding whether the target already "is a directory", so a
    redirect would also make step 1 a silent no-op. That is exactly why this
    proof always runs.
    """
    expected_str = str(expected)
    try:
        lex = os.lstat(expected_str)
    except OSError as exc:
        raise StageOutputAuthorityError("RESULTS_ROOT_ABSENT") from exc
    if _is_symlink_or_reparse_point(lex):
        raise StageOutputAuthorityError("RESULTS_ROOT_REDIRECTED")
    if not stat_module.S_ISDIR(lex.st_mode):
        raise StageOutputAuthorityError("RESULTS_ROOT_NOT_A_DIRECTORY")
    try:
        canonical = str(Path(expected_str).resolve(strict=True))
    except OSError as exc:
        raise StageOutputAuthorityError("RESULTS_ROOT_NOT_CANONICAL") from exc
    if canonical != expected_str:
        raise StageOutputAuthorityError("RESULTS_ROOT_NOT_CANONICAL")
    return canonical


def _establish_results_root(*, create_if_absent: bool) -> str:
    """Level A, strictly before Level B. Returns the proven ``RESULTS_ROOT``.

    ``create_if_absent`` is NOT a caller-selected policy knob: stage
    establishment passes ``True`` (the frozen create-then-prove ordering of
    Sec. 16.3.2's root-presence contract), and every consumption-boundary
    re-proof passes ``False``, because a root that has since vanished is a
    provenance failure to be refused, never a directory to be recreated
    underneath already-written evidence.
    """
    _reprove_trusted_package_directory()
    expected = _expected_results_root()
    if create_if_absent:
        try:
            expected.mkdir(parents=False, exist_ok=True)
        except FileExistsError as exc:
            # A plain FILE occupying the path: exist_ok=True does not suppress
            # this, and step 2(c) would independently refuse it anyway.
            raise StageOutputAuthorityError("RESULTS_ROOT_NOT_A_DIRECTORY") from exc
        except OSError as exc:
            raise StageOutputAuthorityError("RESULTS_ROOT_ABSENT") from exc
    return _prove_results_root(expected)


# ---------------------------------------------------------------------------
# Sec. 16.3.5 -- structural containment, not lexical concatenation
# ---------------------------------------------------------------------------


def _prove_execution_directory_containment(results_root: str, validated_id: str) -> str:
    """Prove the derived directory is the immediate child the root was to gain.

    Sound only because Sec. 16.3.2 has already proven ``results_root`` is
    non-redirected and canonical: FU2's version of this check ran against a
    merely-``resolve()``d root, which a redirected root passes just as easily
    as a genuine one.
    """
    root = Path(results_root)
    candidate = root / validated_id
    try:
        resolved_root = root.resolve()
        resolved_exec = candidate.resolve()
    except OSError as exc:
        raise StageOutputAuthorityError("EXECUTION_DIRECTORY_NOT_CONTAINED") from exc
    if resolved_exec == resolved_root:
        raise StageOutputAuthorityError("EXECUTION_DIRECTORY_NOT_CONTAINED")
    if resolved_root not in resolved_exec.parents:
        raise StageOutputAuthorityError("EXECUTION_DIRECTORY_NOT_CONTAINED")
    if resolved_exec.parent != resolved_root:
        raise StageOutputAuthorityError("EXECUTION_DIRECTORY_NOT_CONTAINED")
    return str(candidate)


# ---------------------------------------------------------------------------
# Sec. 16.3.3 -- the mint registry, and the authority it makes unforgeable
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _StageOutputMintRecord:
    """The four freshly-proven values recorded at the moment of minting."""

    stage_id: str
    stage_execution_id: str
    results_root: str = field(repr=False)
    execution_directory: str = field(repr=False)

    def __repr__(self) -> str:  # noqa: D105 - paths are never rendered
        return f"{type(self).__name__}(<bound>)"


#: Process-local, in-memory only, never persisted. Registry MEMBERSHIP IS the
#: ACTIVE/RETIRED state (Sec. 16.3.9) -- there is no second field and no
#: parallel bookkeeping, so a retired nonce and a nonce that was never issued
#: produce, deliberately, the identical refusal.
_STAGE_OUTPUT_MINTED: dict[str, _StageOutputMintRecord] = {}

_MINT_NONCE_BYTES = 16


@dataclass(frozen=True)
class CFG1StageOutputAuthority:
    """The ONE source of every run/stage output path for one stage execution.

    Valid by construction and unforgeable by API. ``__post_init__`` refuses
    any instance whose ``mint_nonce`` is unregistered, and any instance whose
    four bound fields disagree with what was registered under that nonce --
    so a nonce copied from a genuine object alongside substituted fields gains
    no authority beyond that exact mint (T-25, T-26, T-27).

    ``frozen=True`` prevents mutation; the registry re-check is what prevents
    CONSTRUCTION. Both are needed: a frozen dataclass a caller can build with
    arbitrary fields is a documentation claim, not a mechanism.

    ``mint_nonce`` is ``field(repr=False)`` AND excluded from this class's own
    bounded ``__repr__``: it is in-memory authority only, never written to
    disk, never shown in any diagnostic or evidence, and never read by any
    record builder.
    """

    mint_nonce: str = field(repr=False)
    stage_id: str
    stage_execution_id: str
    results_root: str = field(repr=False)
    execution_directory: str = field(repr=False)

    def __post_init__(self) -> None:
        if type(self.mint_nonce) is not str or not self.mint_nonce:
            raise StageOutputAuthorityError("UNKNOWN_MINT_NONCE")
        record = _STAGE_OUTPUT_MINTED.get(self.mint_nonce)
        if record is None:
            raise StageOutputAuthorityError("UNKNOWN_MINT_NONCE")
        if (
            record.stage_id,
            record.stage_execution_id,
            record.results_root,
            record.execution_directory,
        ) != (
            self.stage_id,
            self.stage_execution_id,
            self.results_root,
            self.execution_directory,
        ):
            raise StageOutputAuthorityError("MINT_FIELD_MISMATCH")

    def __repr__(self) -> str:  # noqa: D105 - see class docstring
        return (
            f"{type(self).__name__}(stage_id={self.stage_id!r}, "
            f"stage_execution_id={self.stage_execution_id!r}, "
            "results_root=<bound>, execution_directory=<bound>)"
        )


def establish_stage_output_authority(
    *, stage_id: str, stage_execution_id: str
) -> CFG1StageOutputAuthority:
    """The ONLY supported path to a genuine authority. Called once per stage.

    The frozen six-step sequence of Sec. 16.3.3, in order:

    1. validate ``stage_id`` against the closed domain;
    2. validate ``stage_execution_id`` per Sec. 16.3.1's grammar and single-read
       binding -- both BEFORE any filesystem operation of any kind (T-22);
    3. establish ``RESULTS_ROOT`` (Level A, then create-if-absent, then the
       unconditional Level B proof);
    4. derive the execution directory as a ``pathlib`` join of one
       already-separator-free component and prove containment structurally;
    5. prove the directory is absent, create it exactly once, and immediately
       re-``lstat`` the freshly created directory;
    6. mint: generate the nonce, register the record, then construct.
    """
    stage = _require_valid_stage_id(stage_id)
    validated_id = _require_valid_stage_execution_id(stage_execution_id)

    results_root = _establish_results_root(create_if_absent=True)
    execution_directory = _prove_execution_directory_containment(results_root, validated_id)

    try:
        os.mkdir(execution_directory)
    except FileExistsError as exc:
        # Sec. 16.3.6: an execution id is a ONE-SHOT namespace. An existing
        # directory refuses the entire stage before any run; its content is
        # never read, merged, appended to, renamed around, or deleted.
        raise StageOutputAuthorityError("EXECUTION_DIRECTORY_EXISTS") from exc
    except OSError as exc:
        raise StageOutputAuthorityError("EXECUTION_DIRECTORY_NOT_CREATED") from exc

    # Immediately re-lstat what was just created: closes a same-tick creation
    # race under adversarial testing, and proves the thing that now occupies
    # the path is a real directory rather than a reparse point.
    try:
        fresh = os.lstat(execution_directory)
    except OSError as exc:
        raise StageOutputAuthorityError("EXECUTION_DIRECTORY_ABSENT") from exc
    if _is_symlink_or_reparse_point(fresh):
        raise StageOutputAuthorityError("EXECUTION_DIRECTORY_REDIRECTED")
    if not stat_module.S_ISDIR(fresh.st_mode):
        raise StageOutputAuthorityError("EXECUTION_DIRECTORY_NOT_A_DIRECTORY")

    nonce = secrets.token_hex(_MINT_NONCE_BYTES)
    if nonce in _STAGE_OUTPUT_MINTED:  # pragma: no cover - a 128-bit collision
        raise StageOutputAuthorityError("MINT_NONCE_ALREADY_REGISTERED")
    _STAGE_OUTPUT_MINTED[nonce] = _StageOutputMintRecord(
        stage_id=stage,
        stage_execution_id=validated_id,
        results_root=results_root,
        execution_directory=execution_directory,
    )
    return CFG1StageOutputAuthority(
        mint_nonce=nonce,
        stage_id=stage,
        stage_execution_id=validated_id,
        results_root=results_root,
        execution_directory=execution_directory,
    )


# ---------------------------------------------------------------------------
# Sec. 16.3.4 -- consumption-boundary re-proof
# ---------------------------------------------------------------------------


def verify_stage_output_authority(authority: object) -> None:
    """Re-prove an authority, FRESH, at EVERY consumption boundary.

    A validated object is never trusted forever. This is the unconditional
    first action of every ``emit_cfg1_*`` writer and of every other function
    that derives or consumes a stage-output path. Five steps, every time:

    1. exact type -- a lookalike or subclass is refused;
    2. registry re-lookup -- ``UNKNOWN_MINT_NONCE`` is ALSO what a RETIRED
       authority produces (Sec. 16.3.9), deliberately indistinguishable,
       because both mean exactly the same security fact;
    3. all four bound fields re-compared against the registry record -- this is
       what catches an ``object.__setattr__`` bypass of ``frozen=True``;
    4. ``RESULTS_ROOT`` provenance re-established from scratch, BOTH levels,
       Level A strictly before Level B, never a cached result of either;
    5. the execution directory re-``lstat``ed -- existence, non-reparse,
       directory, canonical, resolved parent equal to the just-re-proven root,
       and basename equal to the authority's own ``stage_execution_id``.

    This is deliberately not a defense against arbitrary same-user in-process
    memory manipulation (explicitly out of scope). It is a defense against
    ordinary filesystem tampering occurring BETWEEN lifecycle steps -- a
    deletion, a rename, a symlink swap -- which must fail closed at the next
    consumption point rather than silently succeed against whatever now
    occupies the path.
    """
    if type(authority) is not CFG1StageOutputAuthority:
        raise StageOutputAuthorityError("NOT_A_STAGE_OUTPUT_AUTHORITY")

    record = _STAGE_OUTPUT_MINTED.get(authority.mint_nonce)
    if record is None:
        raise StageOutputAuthorityError("UNKNOWN_MINT_NONCE")
    if (
        record.stage_id,
        record.stage_execution_id,
        record.results_root,
        record.execution_directory,
    ) != (
        authority.stage_id,
        authority.stage_execution_id,
        authority.results_root,
        authority.execution_directory,
    ):
        raise StageOutputAuthorityError("MINT_FIELD_MISMATCH")

    results_root = _establish_results_root(create_if_absent=False)
    if results_root != authority.results_root:
        raise StageOutputAuthorityError("RESULTS_ROOT_NOT_CANONICAL")

    execution_directory = authority.execution_directory
    try:
        lex = os.lstat(execution_directory)
    except OSError as exc:
        raise StageOutputAuthorityError("EXECUTION_DIRECTORY_ABSENT") from exc
    if _is_symlink_or_reparse_point(lex):
        raise StageOutputAuthorityError("EXECUTION_DIRECTORY_REDIRECTED")
    if not stat_module.S_ISDIR(lex.st_mode):
        raise StageOutputAuthorityError("EXECUTION_DIRECTORY_NOT_A_DIRECTORY")
    try:
        resolved = Path(execution_directory).resolve(strict=True)
    except OSError as exc:
        raise StageOutputAuthorityError("EXECUTION_DIRECTORY_NOT_CANONICAL") from exc
    if str(resolved) != execution_directory:
        raise StageOutputAuthorityError("EXECUTION_DIRECTORY_NOT_CANONICAL")
    if str(resolved.parent) != results_root:
        raise StageOutputAuthorityError("EXECUTION_DIRECTORY_PARENT_MISMATCH")
    if resolved.name != authority.stage_execution_id:
        raise StageOutputAuthorityError("EXECUTION_DIRECTORY_NAME_MISMATCH")


# ---------------------------------------------------------------------------
# Sec. 16.3.9 -- ACTIVE while minted, RETIRED on every exit path
# ---------------------------------------------------------------------------


def _retire_stage_output_authority(authority: object) -> None:
    """Remove the mint -- never merely mark it, never revertibly.

    Retirement IS a security boundary, not memory hygiene: while an entry
    remains registered, a genuine, unmutated authority object from a stage
    that has already ended would still pass every check above and could still
    derive a path. Idempotent, and deliberately takes the OWNERSHIP HANDLE
    rather than a bare nonce string, so nothing is ever retired because its
    identifier merely looked right.
    """
    if type(authority) is not CFG1StageOutputAuthority:
        return
    _STAGE_OUTPUT_MINTED.pop(authority.mint_nonce, None)


def stage_output_authority_is_active(authority: object) -> bool:
    """A pure read of registry membership. Grants nothing; proves nothing else."""
    if type(authority) is not CFG1StageOutputAuthority:
        return False
    return authority.mint_nonce in _STAGE_OUTPUT_MINTED


def minted_authority_count() -> int:
    """How many stage-output mints are currently ACTIVE in this process."""
    return len(_STAGE_OUTPUT_MINTED)
