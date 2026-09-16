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
) -> str:
    """Register the just-written config directory for ``workspace``'s run.

    Digests are taken from the bytes actually READ BACK from disk, never from
    the in-memory text re-encoded: ``Path.write_text`` performs newline
    translation, so the two can legitimately differ. The directory itself is
    never accepted as an argument here: :func:`derive_cfg1_config_paths`
    re-derives it from ``workspace`` alone, so there is no supported way to
    register a genuine issuance for any path but this run's own.
    """
    config_dir, settings_path, models_path = derive_cfg1_config_paths(workspace)
    _prove_not_redirected(config_dir)
    _prove_not_redirected(settings_path)

    token = secrets.token_hex(_TOKEN_BYTES)
    if token in _ISSUED:  # pragma: no cover - a 128-bit collision
        raise ConfigIssuanceError("ISSUANCE_TOKEN_ALREADY_REGISTERED")
    try:
        record = _IssuanceRecord(
            run_workspace_nonce=workspace.run_workspace_nonce,
            config_dir=config_dir,
            settings_path=settings_path,
            models_path=models_path,
            arm_id=arm_id,
            provider_id=provider_id,
            model_id=model_id,
            settings_sha256=_digest(settings_path),
            models_sha256=_digest(models_path),
        )
    except OSError as exc:
        raise ConfigIssuanceError("GENERATED_FILES_UNREADABLE") from exc
    _ISSUED[token] = record
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
