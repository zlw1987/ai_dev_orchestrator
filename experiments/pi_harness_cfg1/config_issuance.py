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
"""

from __future__ import annotations

import hashlib
import os
import secrets
from dataclasses import dataclass, field


class ConfigIssuanceError(Exception):
    """A generated-config ownership claim could not be proven."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(f"cfg1 config issuance refused: {reason_code}")
        self.reason_code = reason_code


@dataclass(frozen=True)
class _IssuanceRecord:
    """One process-local issuance fact. Never leaves this module."""

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


def register_config_issuance(
    *,
    config_dir: str,
    settings_path: str,
    models_path: str,
    arm_id: str,
    provider_id: str,
    model_id: str,
) -> str:
    """Register one freshly written config directory; return its token.

    Digests are taken from the bytes actually READ BACK from disk, never from
    the in-memory text re-encoded: ``Path.write_text`` performs newline
    translation, so the two can legitimately differ.
    """
    token = secrets.token_hex(_TOKEN_BYTES)
    if token in _ISSUED:  # pragma: no cover - a 128-bit collision
        raise ConfigIssuanceError("ISSUANCE_TOKEN_ALREADY_REGISTERED")
    try:
        record = _IssuanceRecord(
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


def verify_config_issuance(
    *, token: str, config_dir: str, settings_path: str, models_path: str
) -> _IssuanceRecord:
    """Re-prove ownership of this exact directory at a consumption boundary.

    Called fresh at every consumption point -- never once, and never trusted
    from a previous call. ``models.json`` may legitimately be absent after
    L24's verified unlink, so its digest is re-checked only while the file is
    still present; ``settings.json`` must always still match.
    """
    if type(token) is not str or not token:
        raise ConfigIssuanceError("MALFORMED_ISSUANCE_TOKEN")
    record = _ISSUED.get(token)
    if record is None:
        raise ConfigIssuanceError("UNKNOWN_ISSUANCE_TOKEN")
    if (
        config_dir != record.config_dir
        or settings_path != record.settings_path
        or models_path != record.models_path
    ):
        raise ConfigIssuanceError("ISSUANCE_PATH_MISMATCH")
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
