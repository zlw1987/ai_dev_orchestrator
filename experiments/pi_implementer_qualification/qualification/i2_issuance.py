"""I2-6 -- process-local I2 issuance authority registry (5F3B-I2-FU3A,
encapsulated in 5F3B-I2-FU3B).

**OFFLINE ONLY. The other true leaf module.** Like ``i2_identity``, this file
imports nothing else from this package, so ``i2_pi_config`` (which needs it
for genuine-issuance authority) can import it without any cycle risk.

**Why this exists (FU3A).** Independent review of 5F3B-I2-FU3's authority
scheme found it was still forgeable: the FU3 marker is ``SHA256(caller-
supplied token + canonical path)``, but nothing ever required that the
caller's token be one I2 itself generated. A caller could mint its own
token, compute the (public, unkeyed-in-the-sense-of-attacker-controlled)
binding formula by hand, write a marker into an arbitrary directory, and
``GeneratedQualificationConfig`` -- and therefore cleanup -- would accept it.
FU3A added the missing fact: a genuine token must have been *issued by I2
itself*, for *that exact canonical directory*, in *this process*.

**Why this changed again (5F3B-I2-FU3B).** FU3A's registry mutation
functions (``register_issuance``/``finalize_issuance``/``discard_issuance``)
were PUBLIC. Independent review reproduced, using ONLY that public surface
(no ``object.__new__``, no private-global mutation, no live activity):

1. **Self-issuance.** A caller calls the public ``register_issuance``
   itself, for its own chosen token/path/identity, then satisfies every
   downstream check (marker binding + registry presence + metadata
   agreement) and deletes an arbitrary victim directory. The registry
   proved only "someone called ``register_issuance``", never "I2's own
   generator issued this".
2. **Re-finalization.** After a genuine config was finalized and then
   TAMPERED on disk, calling the public ``finalize_issuance`` again, with
   the tampered file's digest, silently overwrote the trusted digest and
   made the tampered file pass integrity verification again.
3. **Mutable returned records.** ``lookup_issuance`` returned the actual
   mutable object stored in the registry; a caller could set
   ``record.models_sha256 = ...`` directly and change the registry itself.
4. **Repr leakage.** The record's default dataclass repr rendered the
   token and the canonical absolute path.

FU3B keeps every FU3A guarantee (genuine issuance, cleanup-authority-vs-
content-integrity split, finalized-digest binding) but makes mutation
**package-internal only** and the record **immutable and repr-safe**:

- :func:`_register_issuance`, :func:`_finalize_issuance`,
  :func:`_discard_issuance`, :func:`_lookup_issuance` -- all
  underscore-prefixed. There is deliberately no public function anywhere in
  this module that mutates or reads the registry; ``i2_pi_config`` and
  ``i2_cleanup`` are this package's only supported callers, per the design's
  own "only i2_pi_config / i2_cleanup should use issuance mutation" rule.
  Per the accepted FU3A threat boundary, this is NOT a defense against a
  caller that deliberately imports underscored internals -- that remains
  explicitly out of scope -- it is the removal of a PUBLIC, SUPPORTED API
  surface that a well-behaved caller could misuse without any such bypass.
- :class:`IssuanceRecord` is now ``@dataclass(frozen=True)``. Finalization
  never mutates a returned record; it replaces the registry's entry with a
  freshly constructed record (``dataclasses.replace``), and it is one-shot:
  a record that is already finalized refuses a second finalization
  (``ISSUANCE_ALREADY_FINALIZED``) rather than silently overwriting trusted
  digests.
- The registry is now keyed by **token alone** (``dict[str,
  IssuanceRecord]``), because one authority token represents exactly one
  issued config. A token already registered for ANY path is refused
  (``ISSUANCE_ALREADY_REGISTERED``) -- this is internal capability
  coherence, not an authorization/version gate. Every function that also
  takes a ``config_dir`` (lookup/finalize/discard) additionally checks that
  the SUPPLIED path agrees with the record's own canonical path, so a
  correct token used against the wrong directory still fails.
- :class:`IssuanceRecord` never renders its ``token`` or
  ``canonical_config_dir`` in ``repr()``/``str()`` -- both fields are
  ``field(repr=False)`` *and* the class defines its own bounded
  ``__repr__`` (two independent reasons, matching this package's existing
  repr-safety convention for every other credential/path-bearing value
  object).

**This registry is EPHEMERAL PROCESS MEMORY ONLY.** It is a plain
module-level ``dict``, never written to disk, never an evidence artifact,
and carries no claim of surviving a process restart, a crash, or being
recoverable across processes.

**This is deliberately NOT generic filesystem authority.** There is no
"register any path" API, no wildcard lookup, no directory-tree walk, and
nothing here ever touches the filesystem itself -- every filesystem
operation (marker write/read, digest computation) remains in
``i2_pi_config``.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path


class IssuanceError(Exception):
    """A caller's I2 issuance authority claim could not be honored.

    **Never echoes a token or a path.** Only a fixed, bounded reason code.
    """

    def __init__(self, reason_code: str) -> None:
        super().__init__(f"I2 issuance authority refused: {reason_code}")
        self.reason_code = reason_code


@dataclass(frozen=True)
class IssuanceRecord:
    """One run-local issuance fact. Immutable (5F3B-I2-FU3B).

    ``settings_sha256``/``models_sha256`` are ``None`` until
    :func:`_finalize_issuance` runs -- a partially generated config (marker
    written, files not yet written or not yet both written) has a record
    with both digests still ``None``, and that is exactly what distinguishes
    "genuinely issued but not yet finalized" from "genuinely issued and
    finalized" for ``i2_pi_config``'s cleanup-authority-vs-content-integrity
    split.

    **Immutable and repr-safe.** There is no supported way to mutate a
    record once constructed -- :func:`_finalize_issuance` replaces the
    registry's entry with a NEW record via :func:`dataclasses.replace`
    rather than assigning to an existing instance's fields, and this class
    is frozen so a caller holding a reference (e.g. one returned from
    :func:`_lookup_issuance`) cannot change it even if it wanted to.
    ``token``/``canonical_config_dir`` are ``field(repr=False)`` *and* this
    class defines its own bounded ``__repr__`` -- two independent reasons
    the token and the absolute path can never appear in a rendered value.
    """

    token: str = field(repr=False)
    canonical_config_dir: str = field(repr=False)
    provider_id: str
    model_id: str
    settings_sha256: str | None = field(default=None, repr=False)
    models_sha256: str | None = field(default=None, repr=False)

    @property
    def is_finalized(self) -> bool:
        return self.settings_sha256 is not None and self.models_sha256 is not None

    def __repr__(self) -> str:  # noqa: D105 - see class docstring
        return (
            f"{type(self).__name__}(provider_id={self.provider_id!r}, "
            f"model_id={self.model_id!r}, finalized={self.is_finalized!r})"
        )


#: Process-local, in-memory only. Never persisted, never an evidence field.
#: Keyed by TOKEN ALONE (5F3B-I2-FU3B) -- one authority token represents
#: exactly one issued config, never a (token, path) pair that could let the
#: same token silently back two different directories.
_REGISTRY: dict[str, IssuanceRecord] = {}


def _canonical(config_dir: Path | str) -> str:
    return str(Path(config_dir).resolve())


def _register_issuance(
    *, token: str, config_dir: Path | str, provider_id: str, model_id: str
) -> None:
    """Record that I2 itself issued ``token`` for the resolved ``config_dir``.

    **Package-internal only (5F3B-I2-FU3B).** Not part of the supported
    public API -- only ``i2_pi_config.write_qualification_pi_config`` calls
    this, immediately after it creates the config directory.

    Raises :class:`IssuanceError` (``ISSUANCE_ALREADY_REGISTERED``) if
    ``token`` is already registered for ANY path -- this should be
    unreachable in practice, since the token is a fresh 128-bit value per
    call, but the check keeps the registry from silently overwriting an
    existing record's identity.
    """
    if token in _REGISTRY:
        raise IssuanceError("ISSUANCE_ALREADY_REGISTERED")
    _REGISTRY[token] = IssuanceRecord(
        token=token,
        canonical_config_dir=_canonical(config_dir),
        provider_id=provider_id,
        model_id=model_id,
    )


def _finalize_issuance(
    *, token: str, config_dir: Path | str, settings_sha256: str, models_sha256: str
) -> None:
    """Record the exact content digests of a successfully completed config.

    **Package-internal only (5F3B-I2-FU3B).** Not part of the supported
    public API -- only ``i2_pi_config.write_qualification_pi_config`` calls
    this, once, after both files are successfully on disk.

    **One-shot (5F3B-I2-FU3B).** Raises :class:`IssuanceError`
    (``ISSUANCE_ALREADY_FINALIZED``) if the matched record is already
    finalized -- a second finalization can NEVER replace already-trusted
    digests, closing the independent-review "tamper, then re-finalize with
    the tampered digest" attack. The registry's entry is replaced with a
    freshly constructed record (:func:`dataclasses.replace`); the OLD
    record object, if a caller is still holding one from an earlier
    :func:`_lookup_issuance` call, is untouched (it is frozen and was never
    the object stored back into the registry).

    Raises :class:`IssuanceError` (``NOT_ISSUED_BY_I2``) if no matching
    record exists, or (``PATH_MISMATCH``) if ``config_dir`` does not match
    the path the token was originally registered for.
    """
    record = _REGISTRY.get(token)
    if record is None:
        raise IssuanceError("NOT_ISSUED_BY_I2")
    if record.canonical_config_dir != _canonical(config_dir):
        raise IssuanceError("PATH_MISMATCH")
    if record.is_finalized:
        raise IssuanceError("ISSUANCE_ALREADY_FINALIZED")
    _REGISTRY[token] = replace(
        record, settings_sha256=settings_sha256, models_sha256=models_sha256
    )


def _lookup_issuance(*, token: str, config_dir: Path | str) -> IssuanceRecord | None:
    """Read-only lookup. ``None`` if no genuine I2 issuance exists for this pair.

    **Package-internal only (5F3B-I2-FU3B).** Not part of the supported
    public API -- only ``i2_pi_config`` calls this. Returns an immutable
    :class:`IssuanceRecord`; there is no supported way to use the returned
    value to change the registry.
    """
    record = _REGISTRY.get(token)
    if record is None:
        return None
    if record.canonical_config_dir != _canonical(config_dir):
        return None
    return record


def _discard_issuance(*, token: str, config_dir: Path | str) -> None:
    """Remove a record, e.g. after a verified cleanup or a failed generation.

    **Package-internal only (5F3B-I2-FU3B).** Not part of the supported
    public API -- only ``i2_pi_config``/``i2_cleanup`` call this.

    Idempotent: a missing record, or a ``config_dir`` that does not match
    the record's own path, is a silent no-op, so a double-discard never
    raises.
    """
    record = _REGISTRY.get(token)
    if record is None:
        return
    if record.canonical_config_dir != _canonical(config_dir):
        return
    _REGISTRY.pop(token, None)
