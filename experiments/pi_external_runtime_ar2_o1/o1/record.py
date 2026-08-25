"""O1's own record header/refusal emission. A NEW record identity, not AR2's.

``ar2.record.record_header`` and ``ar2.record.refusal_record`` both hard-code
AR2's own ``EXPERIMENT_ID`` ("5F3A-AR2") and ``EXPERIMENT_RECORD_VERSION``
("ar2-run-record.v2") from ``ar2/__init__.py``. Calling them unmodified would
make every O1 record misrepresent itself as an AR2 R1-R4 record, which the
operating brief explicitly forbids ("do not modify or reinterpret AR2
records... use a new experiment-local record identity/version"). So this
module reimplements ONLY the two small header-shaping functions, using O1's
own identity from :mod:`o1` -- and reuses everything else from
``ar2.record`` completely unchanged: ``scrub_check``, ``redact_value``,
``broker_secret_denylist``, ``CAPABILITY_BOUNDARY``, ``RESIDUAL_LIMITATIONS``
and ``TOKEN_POLICY`` carry no R1-R4-specific content and are imported
directly rather than duplicated.
"""

from __future__ import annotations

from typing import Any

from ar2.record import (  # noqa: F401 -- re-exported for run_o1.py callers
    CAPABILITY_BOUNDARY,
    RESIDUAL_LIMITATIONS,
    TOKEN_POLICY,
    broker_secret_denylist,
    redact_value,
    scrub_check,
)

from . import EXPERIMENT_ID, EXPERIMENT_RECORD_VERSION, PARENT_ARCHITECTURE, PARENT_ARCHITECTURE_STATUS


def record_header(**extra: Any) -> dict[str, Any]:
    return {
        "experiment": EXPERIMENT_ID,
        "record_version": EXPERIMENT_RECORD_VERSION,
        "record_kind": "experiment run record",
        "is_production_review_packet": False,
        "reviewer_invoked": False,
        "parent_architecture": PARENT_ARCHITECTURE,
        "parent_architecture_status": PARENT_ARCHITECTURE_STATUS,
        "parent_architecture_note": (
            "5F3A-AR2 (experiments/pi_external_runtime_ar2/) is accepted and "
            "frozen. O1 imports and reuses its broker, capability, candidate, "
            "operations, observation, verification, supervisor, launch, "
            "handshake, route-check, pi-config and environment machinery "
            "unmodified. This is a NEW experiment-local record; it is never "
            "an AR2 R1-R4 record and must never be reinterpreted as one."
        ),
        "trust_namespaces": {
            "runtime_reported_*": "UNTRUSTED CLAIM (the runtime's own account)",
            "broker_recorded_*": "AIDO-AUTHORED, DIAGNOSTIC ONLY (never repository truth)",
            "orchestrator_observed_*": "AUTHORITATIVE (AIDO's independent derivation)",
        },
        **extra,
    }


def refusal_record(*, phase: str, finding_count: int, finding_categories: list[str]) -> dict[str, Any]:
    return {
        "experiment": EXPERIMENT_ID,
        "record_version": EXPERIMENT_RECORD_VERSION,
        "record_kind": "artifact emission refusal",
        "is_production_review_packet": False,
        "reviewer_invoked": False,
        "parent_architecture": PARENT_ARCHITECTURE,
        "parent_architecture_status": PARENT_ARCHITECTURE_STATUS,
        "phase": phase,
        "outcome": "artifact_emission_refused",
        "scrub_checked": True,
        "candidate_artifact_not_emitted": True,
        "finding_count": finding_count,
        "finding_categories": sorted(set(finding_categories)),
    }
