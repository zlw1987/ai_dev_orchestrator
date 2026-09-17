"""CFG1's own config-issuance registry -- ownership by handle, never by name.

Design Sec. 17 row 3: the generated Pi config directory is owned through an
in-memory issuance record ``(token -> resolved dir, digests)``, mirroring the
already-accepted ``qualification.i2_issuance`` shape without importing it (no
frozen module is amended).

**Why a registry at all.** L24 verified-unlinks ``models.json`` (the
endpoint-bearing file) and L27 removes the whole owned root. Neither step may
act on a directory merely because its NAME looks like one CFG1 creates
(Sec. 16.1 principle 1, Sec. 17's "never, by construction" list). Holding a
token this module issued -- and re-proving the on-disk digests against what
was finalized -- is the only ownership proof.

The token is process-local, in-memory only, never persisted, never an evidence
field, and never rendered in any repr.

**FU15 (Sec. 37.3.1 step 10, Sec. 37.3.2a).** A digest is a statement about
BYTES, and identical bytes can belong to a different object -- so the record
now also binds the ``(volume_serial, file_id)`` of the pinned config directory
and of each generated child, as L9's parentage gate proved them. That is what
gives L24 a PRECISE child authority: it may unlink the generated
``models.json`` only while the object still at that path is the object issuance
bound, never merely one whose name and contents match. L27's root-namespace
teardown is a different, broader authority and is deliberately not derived from
this record.

Registration additionally requires the unforgeable proofs L9 mints -- the
parentage proof and the two exclusive children it was minted FOR -- so a
caller cannot pair a genuine proof with substituted children, and cannot
register an issuance for files that never passed the gate.

**CFG1-IMPL-FU4 -- a genuine token means L9 RAN, not that genuine-looking
files exist.** Requiring the L9-minted proofs was necessary and was not
sufficient: :mod:`win_config_authority`'s minting entry points are
module-level callables, so a caller holding a genuine workspace could acquire
genuine pins, create the two genuine exclusive children, pass the genuine
parentage gate, write whatever bytes it liked through the proven descriptors,
and register a GENUINE issuance -- never once calling
``write_cfg1_pi_config``. Every object it presented was individually genuine;
what was missing was origin. So registration now additionally requires
:func:`win_config_authority.require_production_issuance_provenance`: the proof
and both children must have been minted inside ONE generation interval that
only the bound CFG1 generator's own code object can open, and that is still
open. Byte-for-byte legitimate content does not substitute for it, and neither
do correct path names, correct arm/provider/model literals or a genuine
workspace.

**CFG1-IMPL-FU4-FU1 -- a genuine token also means L9 RETURNED.** FU4 closed
the origin question, but left one gap: a genuine generation that registered an
issuance here and then failed during its OWN release cleanup (Sec. 37.3.2 row
11 -- closing the children, releasing the config pin, releasing the root pin)
still left that issuance ACTIVE in this registry, even though
``write_cfg1_pi_config`` raised instead of returning it. The token string
never left that routine, so no caller could present it -- but the registry
FACT itself was still live, which is a state this module's own contract
(Sec. 19.1 item 4) does not distinguish from a genuinely durable issuance.
:func:`discard_config_issuance` is now called by L9's own ``finally`` whenever
a registration it just made is about to be followed by a raise, so retirement
is transactional with the generation: an ACTIVE record here is now also a
statement that the generation which minted it reached its own successful
*return*, never merely that it reached registration.

**CFG1-IMPL-FU4-FU2.** :func:`discard_config_issuance` itself is a local,
in-process registry pop with no filesystem, network, subprocess, model or
handle dependency, and it is idempotent by construction -- there is no
supported runtime failure mode for L9's retirement call to encounter, so it is
called plainly, with no wrapping error-handling code and no closed code of its
own for "retirement failed". An earlier draft invented one by monkeypatching
this exact function into a throwing stand-in and treating that as a production
fault; that was test-only interpreter manipulation, the same class the frozen
FU4 threat model already excludes, not a state CFG1 must defend against.

**CFG1-IMPL-FU1 Finding 2.** Neither ``register_config_issuance`` nor
``verify_config_issuance`` accepts a ``config_dir``, ``settings_path`` or
``models_path`` parameter -- there is deliberately no parameter naming a path
here at all, mirroring :mod:`run_workspace`'s own "no parameter naming a path"
precedent. The ONLY input either takes, besides bounded config-identity
literals, is a genuine, ACTIVE ``Cfg1RunWorkspace`` ownership handle,
re-verified every time; the three paths are a pure function of that handle's
own (re-verified) ``experiment_root``, derived HERE and nowhere else. A caller
holding a genuine workspace therefore cannot bless an arbitrary existing
directory or file as a genuine CFG1 issuance, cannot mint a token for a
foreign location, and cannot rebind one workspace's genuine issuance to
another's, because there is no supported way to name a location that differs
from the one this module derives for that exact workspace.
"""

from __future__ import annotations

import hashlib
import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

from ai_dev_orchestrator.workspace.canonical import _is_symlink_or_reparse_point

from . import win_config_authority as win
from .run_workspace import (
    Cfg1RunWorkspace,
    Cfg1WorkspaceAuthorityError,
    verify_cfg1_run_workspace,
)


class ConfigIssuanceError(Exception):
    """A generated-config ownership claim could not be proven."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(f"cfg1 config issuance refused: {reason_code}")
        self.reason_code = reason_code


@dataclass(frozen=True)
class _IssuanceRecord:
    """One process-local issuance fact. Never leaves this module."""

    run_workspace_nonce: str = field(repr=False)
    config_dir: str = field(repr=False)
    settings_path: str = field(repr=False)
    models_path: str = field(repr=False)
    arm_id: str
    provider_id: str
    model_id: str
    settings_sha256: str
    models_sha256: str
    #: Sec. 37.3.1 step 10 (FU15). The ``(volume_serial, file_id)`` of the
    #: pinned config directory and of each child, as the L9 parentage gate
    #: proved them. These are what make L24's cleanup a statement about an
    #: OBJECT rather than about a name: a same-name replacement planted after
    #: issuance no longer matches, and a mismatch is a refusal, never a delete.
    config_dir_identity: tuple[int, int] = field(repr=False, default=(-1, -1))
    settings_identity: tuple[int, int] = field(repr=False, default=(-1, -1))
    models_identity: tuple[int, int] = field(repr=False, default=(-1, -1))

    def __repr__(self) -> str:  # noqa: D105 - paths are never rendered
        return f"{type(self).__name__}(<bound>)"


#: token -> record. Process-local, in-memory only.
_ISSUED: dict[str, _IssuanceRecord] = {}

_TOKEN_BYTES = 16


def _digest(path: str) -> str:
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def _prove_not_redirected(path: str) -> None:
    """lstat, then refuse a symlink or reparse point. Never follows it."""
    try:
        lex = os.lstat(path)
    except OSError as exc:
        raise ConfigIssuanceError("GENERATED_FILES_UNREADABLE") from exc
    if _is_symlink_or_reparse_point(lex):
        raise ConfigIssuanceError("GENERATED_PATH_REDIRECTED")


def derive_cfg1_config_paths(workspace: Cfg1RunWorkspace) -> tuple[str, str, str]:
    """The ONE mechanical derivation of one run's config paths.

    Re-verifies ``workspace`` first. There is no parameter naming a path:
    the three paths are a pure, lexical function of the workspace's own
    (freshly re-proven) ``experiment_root`` plus fixed literals -- so this is
    the single place a config directory's location is ever computed, and
    every consumer (the writer, issuance, and the child-environment builder)
    calls it rather than re-deriving or accepting an equivalent independently.
    """
    if type(workspace) is not Cfg1RunWorkspace:
        raise ConfigIssuanceError("NOT_A_CFG1_RUN_WORKSPACE")
    try:
        verify_cfg1_run_workspace(workspace)
    except Cfg1WorkspaceAuthorityError as exc:
        raise ConfigIssuanceError("WORKSPACE_AUTHORITY_UNVERIFIED") from exc

    from .cfg1_pi_config import CFG1_CONFIG_DIR_NAME

    config_dir = str(Path(workspace.experiment_root) / CFG1_CONFIG_DIR_NAME)
    settings_path = str(Path(config_dir) / "settings.json")
    models_path = str(Path(config_dir) / "models.json")
    return config_dir, settings_path, models_path


def register_config_issuance(
    *,
    workspace: Cfg1RunWorkspace,
    arm_id: str,
    provider_id: str,
    model_id: str,
    proven: win.ProvenConfigChildren,
    settings_child: win.ExclusiveChild,
    models_child: win.ExclusiveChild,
) -> str:
    """Register the just-written config directory for ``workspace``'s run.

    **The three FU15 inputs are unforgeable, not descriptive.** ``proven`` is
    minted only by L9's parentage gate and ``settings_child``/``models_child``
    only by L9's own exclusive creates; each is re-proven against its minting
    registry here, so a caller cannot present a genuine workspace alongside
    fabricated child identities, nor register an issuance for children that
    never passed the gate. The directory itself is still never accepted as an
    argument: :func:`derive_cfg1_config_paths` re-derives it from ``workspace``
    alone, so there is no supported way to register a genuine issuance for any
    path but this run's own.

    Digests are taken from the bytes READ BACK THROUGH THE HELD DESCRIPTORS
    (Sec. 37.3.1 steps 9-10), never by re-opening a pathname and never from the
    in-memory text re-encoded -- the writer performs newline translation, so
    text and on-disk bytes legitimately differ, and a fresh pathname open would
    be asking about whatever the name resolves to a moment later rather than
    about the object the gate proved.
    """
    config_dir, settings_path, models_path = derive_cfg1_config_paths(workspace)
    if type(proven) is not win.ProvenConfigChildren:
        raise ConfigIssuanceError("PARENTAGE_NOT_PROVEN")
    if (
        type(settings_child) is not win.ExclusiveChild
        or type(models_child) is not win.ExclusiveChild
    ):
        raise ConfigIssuanceError("NOT_A_PROVEN_CONFIG_CHILD")
    # CFG1-IMPL-FU4, FIRST and on its own: the ORIGIN question, asked before
    # any other. Genuine Win32 authority a caller assembled for itself is
    # refused here whatever it proves about the filesystem and whatever bytes
    # the children hold, and it gets its own closed code so a provenance
    # refusal is never reported as an unreadable file.
    try:
        win.require_production_issuance_provenance(
            proven, (settings_child, models_child)
        )
    except win.Cfg1DirectoryAuthorityError as exc:
        raise ConfigIssuanceError("ISSUANCE_PROVENANCE_NOT_PROVEN") from exc
    try:
        # The proof is about THESE two objects, not about any two children.
        win.require_proven_children(proven, (settings_child, models_child))
        config_dir_identity = win.proven_config_identity(proven)
        if win.child_name(settings_child) != "settings.json":
            raise ConfigIssuanceError("CONFIG_CHILD_NAME_MISMATCH")
        if win.child_name(models_child) != "models.json":
            raise ConfigIssuanceError("CONFIG_CHILD_NAME_MISMATCH")
        settings_identity = win.child_identity(settings_child)
        models_identity = win.child_identity(models_child)
        settings_bytes = win.read_child_bytes(settings_child)
        models_bytes = win.read_child_bytes(models_child)
    except win.Cfg1DirectoryAuthorityError as exc:
        raise ConfigIssuanceError("GENERATED_FILES_UNREADABLE") from exc

    token = secrets.token_hex(_TOKEN_BYTES)
    if token in _ISSUED:  # pragma: no cover - a 128-bit collision
        raise ConfigIssuanceError("ISSUANCE_TOKEN_ALREADY_REGISTERED")
    _ISSUED[token] = _IssuanceRecord(
        run_workspace_nonce=workspace.run_workspace_nonce,
        config_dir=config_dir,
        settings_path=settings_path,
        models_path=models_path,
        arm_id=arm_id,
        provider_id=provider_id,
        model_id=model_id,
        settings_sha256=hashlib.sha256(settings_bytes).hexdigest(),
        models_sha256=hashlib.sha256(models_bytes).hexdigest(),
        config_dir_identity=config_dir_identity,
        settings_identity=settings_identity,
        models_identity=models_identity,
    )
    return token


def verify_config_issuance(*, token: str, workspace: Cfg1RunWorkspace) -> _IssuanceRecord:
    """Re-prove ownership of this run's own directory at a consumption boundary.

    Called fresh at every consumption point -- never once, and never trusted
    from a previous call. ``config_dir``/``settings_path``/``models_path`` are
    never accepted as arguments: they are re-derived from ``workspace`` alone,
    so a genuine token minted for run A's workspace is refused under run B's
    workspace even when B independently names the same-looking paths -- the
    ``run_workspace_nonce`` bound at registration must also match exactly.
    ``models.json`` may legitimately be absent after L24's verified unlink, so
    its digest and redirection are re-checked only while the file is still
    present; ``settings.json`` and the directory itself must always still
    exist, unredirected.
    """
    if type(token) is not str or not token:
        raise ConfigIssuanceError("MALFORMED_ISSUANCE_TOKEN")
    record = _ISSUED.get(token)
    if record is None:
        raise ConfigIssuanceError("UNKNOWN_ISSUANCE_TOKEN")
    if (
        type(workspace) is not Cfg1RunWorkspace
        or workspace.run_workspace_nonce != record.run_workspace_nonce
    ):
        raise ConfigIssuanceError("ISSUANCE_WORKSPACE_MISMATCH")

    config_dir, settings_path, models_path = derive_cfg1_config_paths(workspace)
    if (
        config_dir != record.config_dir
        or settings_path != record.settings_path
        or models_path != record.models_path
    ):
        raise ConfigIssuanceError("ISSUANCE_PATH_MISMATCH")

    _prove_not_redirected(config_dir)
    _prove_not_redirected(settings_path)
    if os.path.exists(models_path):
        _prove_not_redirected(models_path)

    try:
        if _digest(record.settings_path) != record.settings_sha256:
            raise ConfigIssuanceError("SETTINGS_CONTENT_MISMATCH")
        if os.path.exists(record.models_path):
            if _digest(record.models_path) != record.models_sha256:
                raise ConfigIssuanceError("MODELS_CONTENT_MISMATCH")
    except OSError as exc:
        raise ConfigIssuanceError("GENERATED_FILES_UNREADABLE") from exc
    return record


def discard_config_issuance(token: str) -> None:
    """Forget one issuance record. Idempotent, no I/O."""
    if type(token) is not str:
        return
    _ISSUED.pop(token, None)


def issued_token_count() -> int:
    """How many issuance records are still registered (Sec. 19.1 item 4)."""
    return len(_ISSUED)
