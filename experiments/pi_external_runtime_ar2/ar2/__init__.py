"""Phase 5F3A-AR2 - Delegated Synthetic Workspace Broker PoC (EXPERIMENT ONLY).

This package is not production code. It adds no ``ProjectConfig`` field, no CLI
command, no production broker, and no production Pi support. It lives outside
``src/`` deliberately, and the whole directory may be deleted as one experiment.

Authority read for this implementation:

- ``docs/PHASE_5F3A_AR2D_DELEGATED_WORKSPACE_AUTHORITY_DESIGN.md`` (AR2D)
- ``docs/PHASE_5F3A_AR2D_FU1_CAPABILITY_STATE_AND_BROKER_LIFECYCLE.md`` (FU1 --
  **supersedes AR2D wherever they conflict**)
- ``experiments/pi_external_runtime_ar1/`` -- the accepted AR1 experiment

The one architectural sentence this experiment exists to test::

    the runtime NOMINATES a repository-relative path candidate
    AIDO AUTHORIZES, per operation, from its own accepted Python primitives

No model output authorizes a filesystem operation.
"""

EXPERIMENT_ID = "5F3A-AR2"

# v1 (5F3A-AR2, shipped): R1-a, R1-b, R2, R3, R4. Historical v1 records are
# NEVER rewritten to v2 shape; a v1 record's ``retried: false`` field predates
# the FU-E wording correction below and must not be reinterpreted through it.
#
# v2 (5F3A-AR2-FU1, this follow-up): the ONLY change from v1 is unambiguous
# retry/rerun wording (FU-E). The generic ``retried: false`` field a v1 record
# carried was misleading for the historical R1 lineage: R1 itself WAS re-run,
# just not automatically and not by AIDO deciding to retry a disappointing
# result -- an operator explicitly authorized one separate replacement control
# run after R1-a failed on an infrastructure gate, before any model was
# reached. v2 records this distinction by name rather than collapsing it into
# one boolean. Nothing about SED/RS, the broker protocol, the wire format, or
# any accepted case verdict changed for this bump.
EXPERIMENT_RECORD_VERSION = "ar2-run-record.v2"

# The pinned runtime/provider/model. AR2 deliberately keeps the AR1-proven
# Qwen3.6 direct-vLLM route so that the broker and the runtime seam are the ONLY
# architecture variables. B300's google/gemma-4-26B-A4B-it belongs to a LATER Pi
# implementer-qualification pool and is NOT called here.
PINNED_PI_VERSION = "0.84.2"
LOGICAL_ROUTE_NAME = "qwen36-direct-vllm"
# Repinned on 2026-08-22 (operator decision). AR2 R1-a was consumed by an
# infrastructure mismatch: the direct-vLLM route had stopped serving the
# AR1-era id "Qwen3.6-27B-131K" and now serves "Qwen3.6-27B-262K".
#
# What the evidence establishes, and NO MORE: the SAME advertised Qwen3.6-27B
# family is served over the SAME logical direct-vLLM route, at a DIFFERENT
# served model id / context configuration. Nothing here proves the 131K and
# 262K ids name identical model weights -- that would require backend evidence
# this experiment does not have, and no future AR2 record may claim it. The
# provider route itself is unchanged, so the broker and the runtime seam
# remain the only ARCHITECTURE variables under test; that claim does not
# extend to the model's weights. A non-inference ``/models`` gate now proves
# the route serves this id BEFORE any prompt.
PINNED_MODEL_ID = "Qwen3.6-27B-262K"
PREVIOUS_PINNED_MODEL_ID = "Qwen3.6-27B-131K"
