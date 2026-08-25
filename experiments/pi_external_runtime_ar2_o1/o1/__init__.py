"""Phase 5F3A-AR2-O1 - Two-File Coordinated Implementation Case (EXPERIMENT ONLY).

This package is NOT production code, adds no ``ProjectConfig`` field, no CLI
command, and lives outside ``src/`` deliberately -- the whole directory may be
deleted as one experiment, exactly like ``experiments/pi_external_runtime_ar2/``.

O1 is a SEPARATE experiment built ON TOP OF the accepted, frozen AR2
architecture (``experiments/pi_external_runtime_ar2/``). It imports AR2's
``ar2`` package and reuses its broker, capability, candidate, operations,
observation, verification, supervisor, launch, handshake, route-check,
pi-config, environment and low-level record machinery **completely
unmodified**. Nothing under ``experiments/pi_external_runtime_ar2/`` is
edited, imported-and-monkeypatched, or forked by copy-paste.

What O1 does NOT reuse from AR2, by design:

- ``ar2.fixtures.CASES_BY_ID`` / ``REQUIRED_CASES`` -- those are the frozen
  R1-R4 case set. O1 defines its OWN :class:`ar2.fixtures.CaseFixture`
  instance locally (:mod:`o1.fixture`), using the same frozen dataclass type.
- ``ar2.verification.baseline_matches_case_contract`` -- that function
  requires the baseline to show EXACTLY ONE failing test, which is the R1-R4
  single-defect shape. O1's baseline must show its own case-specific defect
  shape (two independent missing behaviors), so it has its own contract
  checker in :mod:`o1.fixture`.
- ``run_ar2.py``'s ``_assess_case`` -- that dispatches on ``case_id in
  {R1,R2,R3,R4}``. O1's pass condition (:mod:`o1.assessment`) is new,
  case-specific evaluation logic over the same AIDO-observed facts.
- ``ar2.record.record_header`` / ``ar2.record.refusal_record`` -- both
  hard-code AR2's own ``EXPERIMENT_ID`` and ``EXPERIMENT_RECORD_VERSION``.
  O1 has its OWN experiment identity and record version
  (:mod:`o1.record`), and never writes an R1-R4-shaped record. The generic
  scrub/redaction primitives (``scrub_check``, ``redact_value``,
  ``broker_secret_denylist``, ``CAPABILITY_BOUNDARY``,
  ``RESIDUAL_LIMITATIONS``, ``TOKEN_POLICY``) ARE reused unchanged, because
  they carry no R1-R4-specific content.
- ``ar2.launch.resolve_runtime_identity`` / ``ar2.launch.PINNED_PI_VERSION``
  / ``ar2.PINNED_PI_VERSION`` -- corrected by the O1 Pi-compatibility policy
  (:mod:`o1.pi_compat`). AR2 hard-gates on an EXACT Pi version match; for O1
  a Pi version is observed and recorded as PROVENANCE ONLY and is never
  compared against a pin, exact or ranged. This package does not import
  ``PINNED_PI_VERSION`` from ``ar2`` at all -- see :mod:`o1.pi_compat` for
  the zero-prompt compatibility gate that replaces the version-equality
  check, and ``ar2/__init__.py``'s own frozen ``PINNED_PI_VERSION`` /
  historical R1-R4 records are untouched and remain truthful evidence of
  the Pi version AR2 actually used.

The route and model are the SAME accepted AR2 pin -- imported directly from
``ar2``, never redeclared, so there is exactly one place either experiment's
route/model pin could drift from the other's. Pi's version is deliberately
NOT imported from ``ar2`` at all (see above).
"""

from ar2 import (  # noqa: F401 -- re-exported for o1 callers; frozen AR2 constants
    LOGICAL_ROUTE_NAME,
    PINNED_MODEL_ID,
)

EXPERIMENT_ID = "5F3A-AR2-O1"
PARENT_ARCHITECTURE = "5F3A-AR2"
PARENT_ARCHITECTURE_STATUS = "accepted_frozen"
CASE_ID = "O1"

# A NEW experiment-local record identity. Never an AR2 R1-R4 v1/v2 record, and
# never rewritten to look like one.
EXPERIMENT_RECORD_VERSION = "ar2-o1-run-record.v1"

MAX_SEMANTIC_PROMPTS_TOTAL = 1
