"""I2-5 -- generated-config cleanup, phase-aware failure classification, and the
pre-persistence raw-diagnostic safety boundary (I2A Sec. 11/16/17/18).

**OFFLINE ONLY.** Cleanup here operates only on caller-supplied, synthetic,
disposable directories built by the offline test suite -- never a real Pi
process's config directory, because no Pi process is ever launched by this
phase.

Two independent things live in this module, both required by the I2A
design's cleanup semantics:

1. :func:`scrub_generated_qualification_config` -- delete the disposable I2
   Pi config directory and VERIFY the removal by ``stat``. Never a forensic-
   erasure claim (I2A Sec. 21).
2. :func:`classify_cleanup_failure` -- the PHASE-AWARE rule (I2A Sec. 16/18):
   a cleanup-verification failure while ``semantic_prompts_sent == 0`` is
   folded into ``INFRASTRUCTURE_REFUSAL``; while ``semantic_prompts_sent ==
   1`` it is ``run_validity = INFRASTRUCTURE_CONTAMINATED`` /
   ``scoring_eligible = False``. **Never** the other way around, and this
   function never rewrites ``semantic_prompts_sent`` -- it is accepted as an
   already-true fact and returned unchanged inside the result.

A third piece, :func:`prepare_diagnostic_text_for_retention`, establishes the
API SHAPE a future live adapter must route any retainable raw Pi/RPC output
through before it may be persisted. No raw-output file writer and no Pi
stdout capture exist anywhere in this offline phase; this function only
proves the boundary, reusing ``qualification.safety``'s existing scrub
primitive UNMODIFIED rather than building a second secret scanner.

**5F3B-I2-FU2/FU3: cleanup requires REAL creation-time authority.**
Independent review reproduced ``scrub_generated_qualification_config``
recursively deleting an arbitrary, caller-supplied directory -- a synthetic
victim directory and its unrelated file were both destroyed (FU2), and
later reproduced that FU2's fixed PUBLIC marker text was itself forgeable
by copying it into any directory (FU3). This function no longer accepts a
raw path at all: it takes the typed
``i2_pi_config.GeneratedQualificationConfig`` capability object, which is
itself valid-by-construction against a fresh, per-run, never-persisted
128-bit token (it cannot be built pointing at a directory whose marker does
not bind to the SUPPLIED token), and this function additionally
RE-VERIFIES that same token/path binding immediately before deleting
anything, in case the marker was removed, tampered with, or the directory
otherwise changed after the object was constructed. On any authority
failure, :class:`~qualification.i2_pi_config.CleanupAuthorityError` is
raised and NOTHING is deleted.

**5F3B-I2-FU3A.** That re-verification now also requires the
process-local :mod:`qualification.i2_issuance` registry to hold the
supplied token for the exact resolved directory, and requires the
registered identity to agree with the object's own ``provider_id``/
``model_id`` -- closing the gap where a caller-forged token with a
correctly hand-computed FU3 marker (but no genuine I2 issuance) could
still authorize deletion.

**5F3B-I2-FU3B.** The registry functions this module calls
(``i2_issuance._discard_issuance``) are now package-internal (underscore-
prefixed) -- FU3A's public ``register_issuance`` let a caller self-issue
authority for its own chosen path/identity through the supported API alone,
with no bypass required. This module remains one of exactly two legitimate
callers of the internal issuance API (the other is ``i2_pi_config`` itself);
nothing here changed except the import name.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import i2_issuance
from .i2_pi_config import GeneratedQualificationConfig, verify_cleanup_authority
from .outcomes import AutonomousClassification
from .safety import ArtifactSafetyContext, qualification_scrub_check
from .validity import RunValidity


@dataclass(frozen=True)
class CleanupResult:
    """The truthful, stat-verified outcome of one cleanup attempt.

    ``verified_by_stat`` is always ``True`` -- absence is checked, not
    assumed -- and is kept as an explicit field (rather than folded into
    ``removed``) so a caller can see that verification itself was
    performed, distinct from what it found.
    """

    existed: bool
    removed: bool
    verified_by_stat: bool

    @property
    def scrub_verified(self) -> bool:
        """Whether the disposable config is truthfully confirmed gone."""
        return self.verified_by_stat and self.removed


def scrub_generated_qualification_config(
    generated: GeneratedQualificationConfig,
) -> CleanupResult:
    """Delete a genuinely I2-generated disposable config directory, and VERIFY removal.

    Accepts ONLY a :class:`~qualification.i2_pi_config.GeneratedQualificationConfig`
    -- never an arbitrary raw path string. Before any deletion, RE-VERIFIES
    cleanup authority (marker/token/path binding, PLUS the 5F3B-I2-FU3A
    genuine-issuance-registry fact and issued-metadata agreement) via
    :func:`~qualification.i2_pi_config.verify_cleanup_authority` (the
    object's own construction already checked this once; the filesystem may
    have changed since). Deliberately the PERMISSIVE check, not
    ``verify_generated_config_integrity`` -- a partially generated
    (marker-only, or content-tampered) but genuinely-issued config must
    still be cleanable, never stranded. On any authority failure,
    :class:`~qualification.i2_pi_config.CleanupAuthorityError` is raised
    and NOTHING is deleted.

    A ``stat``/``exists()`` check only for the delete itself -- never a
    claim that prior on-disk bytes are forensically unrecoverable (I2A
    Sec. 21). On a VERIFIED successful removal, the process-local issuance
    record is discarded too (5F3B-I2-FU3A) -- a failed removal leaves it in
    place, since the directory (and therefore a future cleanup attempt
    against it) still exists.
    """
    verify_cleanup_authority(
        config_dir=generated.config_dir,
        settings_path=generated.settings_path,
        models_path=generated.models_path,
        authority_token=generated.authority_token,
        provider_id=generated.provider_id,
        model_id=generated.model_id,
    )
    target = Path(generated.config_dir).resolve()
    existed = target.exists()
    if existed:
        shutil.rmtree(target, ignore_errors=True)
    removed = not target.exists()
    if removed:
        i2_issuance._discard_issuance(
            token=generated.authority_token, config_dir=generated.config_dir
        )
    return CleanupResult(existed=existed, removed=removed, verified_by_stat=True)


class CleanupClassificationError(Exception):
    """A cleanup-failure classification was requested for an impossible run shape."""


@dataclass(frozen=True)
class CleanupFailureClassification:
    """The phase-aware classification of one cleanup-verification failure.

    Exactly one of ``autonomous_classification`` / ``run_validity`` is set,
    matching I1's own pre-prompt-vs-post-prompt record shape
    (``qualification.records``): a pre-prompt refusal carries no
    ``run_validity`` at all, and a post-prompt contaminated run carries no
    top-level ``autonomous_classification``.
    """

    semantic_prompts_sent: int
    autonomous_classification: AutonomousClassification | None
    run_validity: RunValidity | None
    scoring_eligible: bool


def classify_cleanup_failure(*, semantic_prompts_sent: int) -> CleanupFailureClassification:
    """I2A Sec. 16/18's phase-aware cleanup-failure rule -- BOTH branches, exactly.

    ``semantic_prompts_sent`` is accepted as an already-true fact about the
    run and is returned unchanged inside the result -- this function never
    rewrites it, and never infers it from timing.
    """
    if semantic_prompts_sent == 0:
        return CleanupFailureClassification(
            semantic_prompts_sent=0,
            autonomous_classification=AutonomousClassification.INFRASTRUCTURE_REFUSAL,
            run_validity=None,
            scoring_eligible=False,
        )
    if semantic_prompts_sent == 1:
        return CleanupFailureClassification(
            semantic_prompts_sent=1,
            autonomous_classification=None,
            run_validity=RunValidity.INFRASTRUCTURE_CONTAMINATED,
            scoring_eligible=False,
        )
    raise CleanupClassificationError(
        "semantic_prompts_sent must be 0 or 1 for a cleanup-failure classification "
        f"(the primary policy sends at most one prompt per task); got "
        f"{semantic_prompts_sent!r}"
    )


@dataclass(frozen=True)
class DiagnosticRetentionResult:
    """Either a retention-ready safe value, or a bounded, non-leaking refusal.

    ``text`` is populated ONLY when ``retention_ready`` is ``True`` -- an
    unsafe input never reaches this field, and callers must never fall back
    to the original raw text on a refusal.
    """

    retention_ready: bool
    text: str | None
    scrub: dict[str, Any]


def prepare_diagnostic_text_for_retention(
    raw_text: str, *, safety: ArtifactSafetyContext, field: str = "text"
) -> DiagnosticRetentionResult:
    """The pre-persistence safety boundary for any future raw Pi/RPC output.

    Reuses ``qualification.safety.qualification_scrub_check`` UNMODIFIED --
    the same scrub the record/lineage emission choke point already uses --
    rather than building a second secret scanner. ``field`` lets a caller
    place the text under a reasoning-bearing key (e.g. ``"reasoning"``) so
    reasoning-shaped content is caught by the existing key-based reasoning
    detector, exactly as ordinary qualification records already are.
    """
    payload = {field: raw_text}
    check = qualification_scrub_check(payload, safety)
    if check["clean"]:
        return DiagnosticRetentionResult(retention_ready=True, text=raw_text, scrub=check)
    return DiagnosticRetentionResult(retention_ready=False, text=None, scrub=check)
