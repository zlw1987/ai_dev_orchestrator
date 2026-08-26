"""5F3B-I2-FU3 item 9 -- binds config/secret/route identity for one composed run.

**OFFLINE ONLY.** This module performs no I/O beyond re-reading the
already-authority-verified generated ``models.json`` (via a fresh
authority re-verification, exactly like every other FU2/FU3 consumption
boundary) to compare its recorded ``baseUrl`` against the run's secret
context -- never a live route call, never a credential read.

I2's offline pieces -- :class:`~qualification.i2_pi_config.GeneratedQualificationConfig`,
:class:`~qualification.i2_secret_context.QualificationRouteSecretContext`,
and :class:`~qualification.i2_route.RouteDescriptor` -- are each
independently valid by construction (I2A/FU1/FU2/FU3), but nothing
previously required the THREE to agree with each other once composed for
one run: a caller could build a perfectly valid secret context for
Candidate A and a perfectly valid route descriptor for Candidate B, and
nothing would refuse the pairing. This is the ONE narrow, I2-owned
composition validator that closes that gap -- deliberately not a generic
runtime/integration framework, and deliberately not
``AgentRuntime``-shaped: it is a single function with a single job.
"""

from __future__ import annotations

import json
from pathlib import Path

from .i2_pi_config import GeneratedQualificationConfig, verify_generated_config_integrity
from .i2_route import RouteDescriptor
from .i2_secret_context import QualificationRouteSecretContext


class I2IdentityBindingError(Exception):
    """The config/secret/route identity triple does not agree. Fails closed.

    Never echoes a base URL, host, endpoint, or credential value -- only a
    fixed, bounded reason code.
    """

    def __init__(self, reason_code: str) -> None:
        super().__init__(f"I2 identity binding refused: {reason_code}")
        self.reason_code = reason_code


def verify_i2_identity_binding(
    *,
    generated_config: GeneratedQualificationConfig,
    secret_context: QualificationRouteSecretContext,
    route_descriptor: RouteDescriptor,
) -> None:
    """The ONE shared composition check for one run's three offline objects.

    **5F3B-I2-FU3A: checks the actual FINALIZED config, not just the
    dataclass fields.** Re-verifies ``generated_config``'s own COMPLETE
    integrity FIRST -- :func:`~qualification.i2_pi_config.verify_generated_config_integrity`
    (cleanup authority, genuine I2 issuance, AND matching content digests;
    the same defense-in-depth reasoning
    ``i2_environment.build_child_environment`` already applies) -- so a
    caller-relabeled ``generated_config.model_id``/``provider_id``, or a
    config whose on-disk bytes were edited after generation, is refused
    HERE before any field on it is trusted for the comparisons below. Then
    requires ALL of:

        secret_context.model_id      == route_descriptor.model_id
        generated_config.model_id    == route_descriptor.model_id
        secret_context.provider_id   == route_descriptor.provider_id
        generated_config.provider_id == route_descriptor.provider_id
        generated_config's own recorded baseUrl == secret_context.base_url
            (compared in memory only; neither value is ever rendered in an
            error, logged, or persisted by this function)

    Raises :class:`I2IdentityBindingError` (bounded reason code only) on
    the first mismatch found; returns ``None`` silently on success.
    """
    verify_generated_config_integrity(
        config_dir=generated_config.config_dir,
        settings_path=generated_config.settings_path,
        models_path=generated_config.models_path,
        authority_token=generated_config.authority_token,
        provider_id=generated_config.provider_id,
        model_id=generated_config.model_id,
    )

    if secret_context.model_id != route_descriptor.model_id:
        raise I2IdentityBindingError("SECRET_CONTEXT_MODEL_ID_MISMATCH")
    if generated_config.model_id != route_descriptor.model_id:
        raise I2IdentityBindingError("GENERATED_CONFIG_MODEL_ID_MISMATCH")
    if secret_context.provider_id != route_descriptor.provider_id:
        raise I2IdentityBindingError("SECRET_CONTEXT_PROVIDER_ID_MISMATCH")
    if generated_config.provider_id != route_descriptor.provider_id:
        raise I2IdentityBindingError("GENERATED_CONFIG_PROVIDER_ID_MISMATCH")

    models_document = json.loads(Path(generated_config.models_path).read_text(encoding="utf-8"))
    provider_document = models_document.get("providers", {}).get(generated_config.provider_id, {})
    generated_base_url = provider_document.get("baseUrl")
    if generated_base_url != secret_context.base_url:
        raise I2IdentityBindingError("GENERATED_CONFIG_BASE_URL_MISMATCH")
