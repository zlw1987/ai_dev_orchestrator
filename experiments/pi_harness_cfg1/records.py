"""The three CFG1 durable record families, and their three closed validators.

Design Sec. 22.1-22.3 (run record), Sec. 22.4.1 (refusal record), Sec. 22.4.2
(stage-closure record), Sec. 22.4.3 (the no-wrapper requirement).

**Three independent validators, never a wrapper.** ``pi-harness-cfg1-run.v1``,
``pi-harness-cfg1-refusal.v1`` and ``pi-harness-cfg1-stage-closure.v1`` are
different closed key sets, different literals and different cross-field
invariants. None of the three validators calls another and ignores the
failures that do not apply -- each enforces its own schema from first
principles, so a future change to one cannot silently alter another's
acceptance by accident of shared code (T-69).

**Payload validity is COHERENCE, never PROVENANCE.** Every validator here
proves a payload's declared fields agree with each other. None proves where
the artifact sits on disk (that is the post-hoc binding verifier,
:mod:`binding`), and none proves the payload equals the live decision or
observation it claims to describe (that is the writer's authority binding and,
for a stage closure, the sealed decision -- Sec. 16.3.8 step 7 and
Sec. 16.3.8.3).
"""

from __future__ import annotations

import re
from typing import Any, Mapping

from . import (
    CLAIM_SCOPE,
    PACKAGE_ID,
    REFUSAL_RECORD_KIND,
    REFUSAL_RECORD_VERSION,
    RUN_RECORD_KIND,
    RUN_RECORD_VERSION,
    STAGE_CLOSURE_RECORD_KIND,
    STAGE_CLOSURE_RECORD_VERSION,
)
from .arms import (
    ARM_EFFECTIVE,
    ARM_REDACTED_DIGEST,
    ARM_SHAPE,
    PINNED_SETTINGS_SHA256,
    DECLARED_COMPAT_SHAPES,
    DERIVED_REASONING_EFFORT_VALUES,
    DERIVED_SYSTEM_ROLES,
    EXPECTED_THINKING_LEVEL,
    RUNTIME_COMPAT_SHAPES,
    RUNTIME_MODEL_REASONING_VALUES,
    RUNTIME_THINKING_LEVELS,
)
from .classification import (
    CAPTURE_BASIS_AGENT_SETTLED,
    CAPTURE_BASIS_WAIT_ENDED_BEFORE_SETTLED,
    RUN_CLASSIFICATIONS,
    classify_cfg1_run,
)
from .fixture import CFG1_T1_FILES, CFG1_T1_REVISION, CFG1_TASK_ID
from .halt import (
    EMISSION_COLLISION,
    EMISSION_EVIDENCE_REFUSED,
    EMISSION_FAILED,
    EMISSION_RECORD_EMITTED,
    HALT_REASON_CODES,
    HALT_RUN_RECORD_EMISSION_COLLISION,
    HALT_RUN_RECORD_EMISSION_FAILED,
    ORDINAL_NOT_EXECUTED,
    ORDINAL_STATUS_VALUES,
)
from .identity import (
    BACKEND_GATEWAY_CLASS,
    CFG1_MODEL_ID,
    PROVIDER_ID,
)
from .lifecycle import (
    LIFECYCLE_FAILURE_STEPS,
    REFUSAL_STEPS,
    compute_lifecycle_closure,
)
from .schedule import (
    STAGE_ARMS,
    STAGE_IDS,
    _schedule_arm_for,
    _schedule_block_position,
    declared_ordinals,
)
from .stage_output import STAGE_EXECUTION_ID_PATTERN


# ---------------------------------------------------------------------------
# Failure vocabulary
# ---------------------------------------------------------------------------

#: Sec. 22.4.1's closed ``finding_categories`` enum. Bounded METADATA codes
#: only -- never the offending value, never a copied snippet, never a needle.
FINDING_SCHEMA_VIOLATION = "SCHEMA_VIOLATION"
FINDING_CROSS_FIELD_INVARIANT = "CROSS_FIELD_INVARIANT"
FINDING_AUTHORITY_BINDING = "AUTHORITY_BINDING"
FINDING_SCRUB_NEEDLE_MATCH = "SCRUB_NEEDLE_MATCH"
FINDING_SIZE_BOUND_EXCEEDED = "SIZE_BOUND_EXCEEDED"
FINDING_RECORD_INVARIANT = "RECORD_INVARIANT"

FINDING_CATEGORIES: frozenset[str] = frozenset(
    {
        FINDING_SCHEMA_VIOLATION,
        FINDING_CROSS_FIELD_INVARIANT,
        FINDING_AUTHORITY_BINDING,
        FINDING_SCRUB_NEEDLE_MATCH,
        FINDING_SIZE_BOUND_EXCEEDED,
        FINDING_RECORD_INVARIANT,
    }
)

#: The only record kind a refusal record may currently stand in for at a run
#: path. Widening this enum requires a separate, authorized amendment -- never
#: a silent addition.
REFUSABLE_RECORD_KINDS: frozenset[str] = frozenset({RUN_RECORD_VERSION})


class Cfg1RecordValidationError(Exception):
    """A payload failed its own closed schema. Carries a bounded category only."""

    def __init__(self, category: str, reason_code: str) -> None:
        super().__init__(f"cfg1 record refused: {category}/{reason_code}")
        self.category = category
        self.reason_code = reason_code


def _schema(reason_code: str) -> Cfg1RecordValidationError:
    return Cfg1RecordValidationError(FINDING_SCHEMA_VIOLATION, reason_code)


def _invariant(reason_code: str) -> Cfg1RecordValidationError:
    return Cfg1RecordValidationError(FINDING_CROSS_FIELD_INVARIANT, reason_code)


# ---------------------------------------------------------------------------
# Filename derivation -- one pure function per record family
# ---------------------------------------------------------------------------


def _run_record_filename(stage_id: str, run_ordinal: int, arm_id: str) -> str:
    """``<stage>_<ordinal:02d>_<arm>.json`` -- Sec. 16.3.8 step 9.

    A pure function of three already-validated values. The validator recomputes
    it from the record's OWN fields; the writer derives it from its authority
    and the schedule. Neither ever exposes it as a return value a caller could
    capture and pass elsewhere as if it were authority.
    """
    return f"{stage_id}_{run_ordinal:02d}_{arm_id}.json"


def _stage_closure_record_filename(stage_id: str) -> str:
    """``<stage>_stage_closure.json`` -- a pure function of ``stage_id`` alone."""
    return f"{stage_id}_stage_closure.json"


# ---------------------------------------------------------------------------
# Small exact-typing helpers. ``type(v) is X``, never ``isinstance``.
# ---------------------------------------------------------------------------


def _get(payload: Mapping[str, Any], key: str) -> Any:
    try:
        return payload[key]
    except KeyError:  # pragma: no cover - key sets are checked first
        raise _schema(f"MISSING_{key.upper()}") from None


def _require_literal(payload: Mapping[str, Any], key: str, expected: object) -> None:
    value = _get(payload, key)
    if type(value) is not type(expected) or value != expected:
        raise _schema(f"BAD_LITERAL_{key.upper()}")


def _require_bool(payload: Mapping[str, Any], key: str) -> bool:
    value = _get(payload, key)
    if type(value) is not bool:
        raise _schema(f"BAD_BOOL_{key.upper()}")
    return value


def _require_int(
    payload: Mapping[str, Any],
    key: str,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    value = _get(payload, key)
    # ``bool`` is an ``int`` subclass; ``type(...) is int`` refuses True/False.
    if type(value) is not int:
        raise _schema(f"BAD_INT_{key.upper()}")
    if minimum is not None and value < minimum:
        raise _schema(f"OUT_OF_RANGE_{key.upper()}")
    if maximum is not None and value > maximum:
        raise _schema(f"OUT_OF_RANGE_{key.upper()}")
    return value


def _require_str(payload: Mapping[str, Any], key: str) -> str:
    value = _get(payload, key)
    if type(value) is not str:
        raise _schema(f"BAD_STR_{key.upper()}")
    return value


def _require_enum(payload: Mapping[str, Any], key: str, domain) -> str:
    value = _require_str(payload, key)
    if value not in domain:
        raise _schema(f"BAD_ENUM_{key.upper()}")
    return value


def _require_optional_enum(payload: Mapping[str, Any], key: str, domain) -> str | None:
    value = _get(payload, key)
    if value is None:
        return None
    if type(value) is not str or value not in domain:
        raise _schema(f"BAD_ENUM_{key.upper()}")
    return value


def _require_optional_int(
    payload: Mapping[str, Any], key: str, *, minimum: int | None = None
) -> int | None:
    value = _get(payload, key)
    if value is None:
        return None
    if type(value) is not int:
        raise _schema(f"BAD_INT_{key.upper()}")
    if minimum is not None and value < minimum:
        raise _schema(f"OUT_OF_RANGE_{key.upper()}")
    return value


def _require_exact_keys(payload: Mapping[str, Any], expected: frozenset[str]) -> None:
    """Closed key set, checked by EXACT SET EQUALITY.

    An unrecognized key is a closed-key-set violation, never an ignorable
    extra: that is what makes a record carrying a removed field (for example a
    resurrected ``halt_triggered_by_this_run``) refused outright rather than
    silently tolerated (T-94).
    """
    present = frozenset(payload)
    if present != expected:
        raise _schema("CLOSED_KEY_SET_VIOLATION")


def _require_sorted_unique_subset(
    payload: Mapping[str, Any], key: str, allowed
) -> tuple[str, ...]:
    value = _get(payload, key)
    if type(value) is not list:
        raise _schema(f"BAD_LIST_{key.upper()}")
    for entry in value:
        if type(entry) is not str:
            raise _schema(f"BAD_LIST_ENTRY_{key.upper()}")
        if entry not in allowed:
            raise _schema(f"UNKNOWN_LIST_ENTRY_{key.upper()}")
    if list(value) != sorted(set(value)):
        raise _schema(f"UNSORTED_OR_DUPLICATED_{key.upper()}")
    return tuple(value)


def _require_exact_int_mapping(
    payload: Mapping[str, Any], key: str, expected_keys: frozenset[str]
) -> dict[str, int]:
    value = _get(payload, key)
    if type(value) is not dict:
        raise _schema(f"BAD_MAPPING_{key.upper()}")
    if frozenset(value) != expected_keys:
        raise _schema(f"CLOSED_KEY_SET_VIOLATION_{key.upper()}")
    for entry in value.values():
        if type(entry) is not int or entry < 0:
            raise _schema(f"BAD_MAPPING_VALUE_{key.upper()}")
    return value


def _require_stage_execution_id(payload: Mapping[str, Any]) -> str:
    """The SAME grammar ``establish_stage_output_authority`` enforces.

    Re-proven independently here rather than trusted from the field's mere
    presence: a durable record must be checkable without the live authority
    object that produced it.
    """
    value = _get(payload, "stage_execution_id")
    if type(value) is not str or STAGE_EXECUTION_ID_PATTERN.fullmatch(value) is None:
        raise _schema("BAD_STAGE_EXECUTION_ID")
    return value


# ---------------------------------------------------------------------------
# Sec. 22.2 -- the run record's closed key set
# ---------------------------------------------------------------------------

_HEADER_KEYS: tuple[str, ...] = (
    "experiment",
    "record_version",
    "record_kind",
    "scoring_authority",
    "qualification_credit",
    "is_review_packet",
    "reviewer_invoked",
    "claim_scope",
)

_SCHEDULE_KEYS: tuple[str, ...] = (
    "stage_id",
    "stage_execution_id",
    "run_ordinal",
    "block",
    "position",
    "arm_id",
    "record_filename",
)

_CONFIG_VARIANT_KEYS: tuple[str, ...] = (
    "declared_compat_shape",
    "models_json_redacted_sha256",
    "settings_json_sha256",
    "derived_effective_supports_developer_role",
    "derived_effective_supports_reasoning_effort",
    "derived_system_role",
    "derived_reasoning_effort_sent",
)

_IDENTITY_KEYS: tuple[str, ...] = (
    "model_id",
    "provider_id",
    "backend_gateway_class",
    "fixture_task_id",
    "fixture_revision",
    "pi_observed_version",
    "pi_seam_digests_match",
)

_PRE_DISPATCH_KEYS: tuple[str, ...] = (
    "base_url_compat_detection_clear",
    "route_reachable",
    "route_configured_model_served",
    "broker_reached_ready",
    "h1_extension_identity_matched",
    "h2_provider_model_identity_matched",
    "runtime_reported_compat_shape",
    "runtime_reported_model_reasoning",
    "runtime_reported_thinking_level",
    "manipulation_check_agrees",
    "pre_dispatch_refusal_code",
    "refused_at_step",
)

_DISPATCH_KEYS: tuple[str, ...] = (
    "dispatch_state",
    "prompt_writes",
    "automatic_semantic_retry",
    "operator_continuation",
)

_TURN_KEYS: tuple[str, ...] = ("runtime_wait_outcome",)

_OBS1_KEYS: tuple[str, ...] = (
    "runtime_reported_tool_activity_available",
    "runtime_reported_tool_activity_capture_basis",
    "runtime_reported_tool_execution_start_events",
    "runtime_reported_tool_execution_end_events",
    "runtime_reported_distinct_tool_call_ids",
    "runtime_reported_unidentified_tool_call_id_seen",
    "runtime_reported_aido_read_call_ids",
    "runtime_reported_aido_read_end_observed",
    "runtime_reported_aido_read_error_results",
    "runtime_reported_aido_edit_call_ids",
    "runtime_reported_aido_edit_end_observed",
    "runtime_reported_aido_edit_error_results",
    "runtime_reported_unexpected_tool_call_ids",
    "runtime_reported_unexpected_tool_end_observed",
    "runtime_reported_unexpected_tool_error_results",
    "activity_unavailable_reason",
)

_OBS1_COUNT_KEYS: tuple[str, ...] = tuple(
    key
    for key in _OBS1_KEYS
    if key
    not in (
        "runtime_reported_tool_activity_available",
        "runtime_reported_tool_activity_capture_basis",
        "runtime_reported_unidentified_tool_call_id_seen",
        "activity_unavailable_reason",
    )
)

_PROVIDER_KEYS: tuple[str, ...] = (
    "stop_reasons_available",
    "stop_reason_counts",
    "auto_retry_events",
    "extension_error_count",
)

_BROKER_KEYS: tuple[str, ...] = (
    "broker_recorded_activity_available",
    "broker_recorded_read_operation_count",
    "broker_recorded_edit_operation_count",
    "broker_recorded_edited_path_count",
    "broker_recorded_refusal_count",
)

_BROKER_COUNT_KEYS: tuple[str, ...] = tuple(
    key for key in _BROKER_KEYS if key != "broker_recorded_activity_available"
)

_LIFECYCLE_KEYS: tuple[str, ...] = (
    "runtime_created",
    "runtime_exit_observed",
    "runtime_transport_eof_observed",
    "broker_resource_created",
    "broker_state_closed",
    "broker_pending_unreaped_zero",
    "broker_worker_terminated_or_absent",
    "generated_config_scrub_verified",
    "extension_binding_scrub_verified",
    "verification_child_reaped_or_not_started",
    "workspace_authority_reproved",
    "workspace_removed_verified",
    "workspace_residual_file_count",
    "lifecycle_all_closed",
    "lifecycle_failure_steps",
)

_LIFECYCLE_BOOL_KEYS: tuple[str, ...] = tuple(
    key
    for key in _LIFECYCLE_KEYS
    if key not in ("workspace_residual_file_count", "lifecycle_failure_steps")
)

_REPOSITORY_KEYS: tuple[str, ...] = (
    "git_observation_1_performed",
    "head_moved",
    "changed_tracked_paths",
    "untracked_path_count",
    "staged_path_count",
    "broker_git_cross_check_agrees",
    "git_observation_2_performed",
    "post_verification_changed_tracked_paths",
)

_VERIFICATION_KEYS: tuple[str, ...] = (
    "verification_attempted",
    "verification_skip_reason",
    "verification_started",
    "verification_completed",
    "verification_timed_out",
    "verification_output_limit_exceeded",
    "verification_return_code",
    "verification_passed",
    "verification_counts",
)

_CLASSIFICATION_KEYS: tuple[str, ...] = ("run_classification",)

#: The complete, closed run-record key set. ``halt_triggered_by_this_run`` and
#: ``halt_reason_code`` are deliberately ABSENT (FU8 Finding 2): both depend on
#: this run's own not-yet-decided emission outcome, so a payload-only validator
#: could not recompute either without claiming to know its own future.
CFG1_RUN_RECORD_KEYS: frozenset[str] = frozenset(
    _HEADER_KEYS
    + _SCHEDULE_KEYS
    + _CONFIG_VARIANT_KEYS
    + _IDENTITY_KEYS
    + _PRE_DISPATCH_KEYS
    + _DISPATCH_KEYS
    + _TURN_KEYS
    + _OBS1_KEYS
    + _PROVIDER_KEYS
    + _BROKER_KEYS
    + _LIFECYCLE_KEYS
    + _REPOSITORY_KEYS
    + _VERIFICATION_KEYS
    + _CLASSIFICATION_KEYS
)

#: The fields a run executor observes. Everything else in a run record is a
#: pinned literal, a schedule derivation, an arm derivation, or the
#: independently recomputed classification.
CFG1_RUN_OBSERVATION_KEYS: frozenset[str] = frozenset(
    ("pi_observed_version", "pi_seam_digests_match")
    + _PRE_DISPATCH_KEYS
    + _DISPATCH_KEYS
    + _TURN_KEYS
    + _OBS1_KEYS
    + _PROVIDER_KEYS
    + _BROKER_KEYS
    + _LIFECYCLE_KEYS
    + _REPOSITORY_KEYS
    + _VERIFICATION_KEYS
)

# -- closed value domains ----------------------------------------------------

DISPATCH_STATES: frozenset[str] = frozenset(
    {
        "NOT_ATTEMPTED",
        "CONFIRMED_SENT",
        "CONFIRMED_NOT_SENT",
        "SEND_STATE_INDETERMINATE",
    }
)

RUNTIME_WAIT_OUTCOMES: frozenset[str] = frozenset(
    {
        "SETTLED",
        "DEADLINE_EXPIRED",
        "EXITED_EARLY",
        "PROTOCOL_VIOLATION",
        "OUTPUT_CAP_EXCEEDED",
        "EVENT_CAP_EXCEEDED",
        "READ_ERROR",
        "UNRECOGNIZED",
        "NOT_OBSERVED",
    }
)

PRE_DISPATCH_REFUSAL_CODES: frozenset[str] = frozenset(
    {
        "OFFLINE_PREFLIGHT_FAILED",
        "WORKSPACE_BASELINE_FAILED",
        "CREDENTIAL_BOUNDARY_FAILED",
        "SECRET_CONTEXT_FAILED",
        "BASE_URL_COMPAT_DETECTION_TRIGGERED",
        "ROUTE_UNAVAILABLE",
        "CAPABILITY_MINT_FAILED",
        "CONFIG_GENERATION_FAILED",
        "BROKER_CONSTRUCTION_FAILED",
        "EXTENSION_GENERATION_FAILED",
        "CHILD_ENVIRONMENT_FAILED",
        "BROKER_NOT_READY",
        "RUNTIME_LAUNCH_FAILED",
        "RUNTIME_CORRELATION_FAILED",
        "H1_MISMATCH",
        "H2_MISMATCH",
        "CONFIG_SHAPE_MISMATCH",
        "PRE_DISPATCH_BASELINE_FAILED",
        "PROMPT_REFUSED_BY_RUNTIME",
    }
)

ACTIVITY_UNAVAILABLE_REASONS: frozenset[str] = frozenset(
    {"PROJECTION_REFUSED", "INTERNAL_ERROR"}
)

VERIFICATION_SKIP_REASONS: frozenset[str] = frozenset(
    {"LIFECYCLE_UNPROVEN", "PRE_DISPATCH_REFUSAL"}
)

CAPTURE_BASES: frozenset[str] = frozenset(
    {CAPTURE_BASIS_AGENT_SETTLED, CAPTURE_BASIS_WAIT_ENDED_BEFORE_SETTLED}
)

STOP_REASON_KEYS: frozenset[str] = frozenset(
    {"stop", "length", "toolUse", "error", "aborted", "other"}
)

VERIFICATION_COUNT_KEYS: frozenset[str] = frozenset({"passed", "failed", "error"})

#: A bounded version pattern, or the closed literal ``UNRECOGNIZED``. Never a
#: raw, unbounded string a runtime could have chosen freely.
_PI_VERSION_PATTERN = re.compile(r"[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}")

_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


# ---------------------------------------------------------------------------
# Sec. 22.1-22.3 -- the RUN-record validator
# ---------------------------------------------------------------------------


def _require_valid_cfg1_run_payload(payload: Mapping[str, Any]) -> None:
    """The closed ``pi-harness-cfg1-run.v1`` schema. Raises, or returns ``None``.

    Never run against a refusal or stage-closure payload, and not a wrapper
    around either of the other two validators (Sec. 22.4.3).
    """
    if type(payload) is not dict:
        raise _schema("NOT_A_DICT")
    _require_exact_keys(payload, CFG1_RUN_RECORD_KEYS)

    # -- header: exact literals ---------------------------------------------
    _require_literal(payload, "experiment", PACKAGE_ID)
    _require_literal(payload, "record_version", RUN_RECORD_VERSION)
    _require_literal(payload, "record_kind", RUN_RECORD_KIND)
    _require_literal(payload, "scoring_authority", False)
    _require_literal(payload, "qualification_credit", False)
    _require_literal(payload, "is_review_packet", False)
    _require_literal(payload, "reviewer_invoked", False)
    _require_literal(payload, "claim_scope", CLAIM_SCOPE)

    # -- schedule binding ----------------------------------------------------
    stage_id = _require_enum(payload, "stage_id", STAGE_IDS)
    stage_execution_id = _require_stage_execution_id(payload)
    ordinals = declared_ordinals(stage_id)
    run_ordinal = _require_int(
        payload, "run_ordinal", minimum=ordinals[0], maximum=ordinals[-1]
    )
    block = _require_int(payload, "block", minimum=1)
    position = _require_int(payload, "position", minimum=1)
    arm_id = _require_enum(payload, "arm_id", STAGE_ARMS[stage_id])
    record_filename = _require_str(payload, "record_filename")

    # -- config variant ------------------------------------------------------
    declared_shape = _require_enum(payload, "declared_compat_shape", DECLARED_COMPAT_SHAPES)
    models_digest = _require_str(payload, "models_json_redacted_sha256")
    settings_sha = _require_str(payload, "settings_json_sha256")
    for key, value in (
        ("models_json_redacted_sha256", models_digest),
        ("settings_json_sha256", settings_sha),
    ):
        if _SHA256_PATTERN.fullmatch(value) is None:
            raise _schema(f"BAD_DIGEST_{key.upper()}")
    _require_bool(payload, "derived_effective_supports_developer_role")
    _require_bool(payload, "derived_effective_supports_reasoning_effort")
    _require_enum(payload, "derived_system_role", DERIVED_SYSTEM_ROLES)
    effort = _get(payload, "derived_reasoning_effort_sent")
    if effort is not None and (type(effort) is not str or effort not in DERIVED_REASONING_EFFORT_VALUES):
        raise _schema("BAD_ENUM_DERIVED_REASONING_EFFORT_SENT")

    # -- identity: pinned literals -------------------------------------------
    _require_literal(payload, "model_id", CFG1_MODEL_ID)
    _require_literal(payload, "provider_id", PROVIDER_ID)
    _require_literal(payload, "backend_gateway_class", BACKEND_GATEWAY_CLASS)
    _require_literal(payload, "fixture_task_id", CFG1_TASK_ID)
    _require_literal(payload, "fixture_revision", CFG1_T1_REVISION)
    pi_version = _require_str(payload, "pi_observed_version")
    if pi_version != "UNRECOGNIZED" and _PI_VERSION_PATTERN.fullmatch(pi_version) is None:
        raise _schema("BAD_PI_OBSERVED_VERSION")
    _require_bool(payload, "pi_seam_digests_match")

    # -- pre-dispatch --------------------------------------------------------
    for key in (
        "base_url_compat_detection_clear",
        "route_reachable",
        "route_configured_model_served",
        "broker_reached_ready",
        "h1_extension_identity_matched",
        "h2_provider_model_identity_matched",
        "manipulation_check_agrees",
    ):
        _require_bool(payload, key)
    runtime_shape = _require_enum(
        payload, "runtime_reported_compat_shape", RUNTIME_COMPAT_SHAPES
    )
    runtime_reasoning = _require_enum(
        payload, "runtime_reported_model_reasoning", RUNTIME_MODEL_REASONING_VALUES
    )
    runtime_thinking = _require_enum(
        payload, "runtime_reported_thinking_level", RUNTIME_THINKING_LEVELS
    )
    refusal_code = _require_optional_enum(
        payload, "pre_dispatch_refusal_code", PRE_DISPATCH_REFUSAL_CODES
    )
    _require_optional_enum(payload, "refused_at_step", REFUSAL_STEPS)

    # -- dispatch ------------------------------------------------------------
    dispatch_state = _require_enum(payload, "dispatch_state", DISPATCH_STATES)
    prompt_writes = _require_int(payload, "prompt_writes", minimum=0, maximum=1)
    _require_literal(payload, "automatic_semantic_retry", False)
    _require_literal(payload, "operator_continuation", False)

    # -- turn ----------------------------------------------------------------
    _require_enum(payload, "runtime_wait_outcome", RUNTIME_WAIT_OUTCOMES)

    # -- OBS1 ----------------------------------------------------------------
    activity_available = _require_bool(payload, "runtime_reported_tool_activity_available")
    capture_basis = _require_optional_enum(
        payload, "runtime_reported_tool_activity_capture_basis", CAPTURE_BASES
    )
    _require_bool(payload, "runtime_reported_unidentified_tool_call_id_seen")
    for key in _OBS1_COUNT_KEYS:
        _require_int(payload, key, minimum=0)
    _require_optional_enum(
        payload, "activity_unavailable_reason", ACTIVITY_UNAVAILABLE_REASONS
    )

    # -- provider ------------------------------------------------------------
    _require_bool(payload, "stop_reasons_available")
    _require_exact_int_mapping(payload, "stop_reason_counts", STOP_REASON_KEYS)
    _require_int(payload, "auto_retry_events", minimum=0)
    _require_int(payload, "extension_error_count", minimum=0)

    # -- broker --------------------------------------------------------------
    broker_available = _require_bool(payload, "broker_recorded_activity_available")
    for key in _BROKER_COUNT_KEYS:
        _require_int(payload, key, minimum=0)

    # -- lifecycle -----------------------------------------------------------
    for key in _LIFECYCLE_BOOL_KEYS:
        _require_bool(payload, key)
    _require_int(payload, "workspace_residual_file_count", minimum=0)
    failure_steps = _require_sorted_unique_subset(
        payload, "lifecycle_failure_steps", LIFECYCLE_FAILURE_STEPS
    )

    # -- repository ----------------------------------------------------------
    for key in ("git_observation_1_performed", "head_moved", "broker_git_cross_check_agrees",
                "git_observation_2_performed"):
        _require_bool(payload, key)
    changed = _require_sorted_unique_subset(payload, "changed_tracked_paths", CFG1_T1_FILES)
    _require_sorted_unique_subset(
        payload, "post_verification_changed_tracked_paths", CFG1_T1_FILES
    )
    _require_int(payload, "untracked_path_count", minimum=0)
    _require_int(payload, "staged_path_count", minimum=0)

    # -- verification --------------------------------------------------------
    verification_attempted = _require_bool(payload, "verification_attempted")
    skip_reason = _require_optional_enum(
        payload, "verification_skip_reason", VERIFICATION_SKIP_REASONS
    )
    for key in (
        "verification_started",
        "verification_completed",
        "verification_timed_out",
        "verification_output_limit_exceeded",
        "verification_passed",
    ):
        _require_bool(payload, key)
    _require_optional_int(payload, "verification_return_code")
    _require_exact_int_mapping(payload, "verification_counts", VERIFICATION_COUNT_KEYS)

    # -- classification ------------------------------------------------------
    _require_enum(payload, "run_classification", RUN_CLASSIFICATIONS)

    # =======================================================================
    # Sec. 22.3 -- cross-field invariants
    # =======================================================================
    if arm_id != _schedule_arm_for(stage_id, run_ordinal):
        raise _invariant("ARM_DISAGREES_WITH_SCHEDULE")
    expected_block, expected_position = _schedule_block_position(stage_id, run_ordinal)
    if (block, position) != (expected_block, expected_position):
        raise _invariant("BLOCK_POSITION_DISAGREE_WITH_SCHEDULE")
    if record_filename != _run_record_filename(stage_id, run_ordinal, arm_id):
        raise _invariant("RECORD_FILENAME_DISAGREES_WITH_DERIVATION")

    if declared_shape != ARM_SHAPE[arm_id]:
        raise _invariant("DECLARED_SHAPE_DISAGREES_WITH_ARM")
    if models_digest != ARM_REDACTED_DIGEST[arm_id]:
        raise _invariant("MODELS_DIGEST_DISAGREES_WITH_ARM")
    if settings_sha != PINNED_SETTINGS_SHA256:
        raise _invariant("SETTINGS_DIGEST_DISAGREES_WITH_PIN")
    for key, expected_value in ARM_EFFECTIVE[arm_id].items():
        if payload[key] != expected_value or type(payload[key]) is not type(expected_value):
            raise _invariant("DERIVED_EFFECTIVE_DISAGREES_WITH_ARM")

    if (prompt_writes == 0) != (dispatch_state == "NOT_ATTEMPTED"):
        raise _invariant("PROMPT_WRITES_DISAGREE_WITH_DISPATCH_STATE")
    if refusal_code is not None and dispatch_state not in ("NOT_ATTEMPTED", "CONFIRMED_NOT_SENT"):
        raise _invariant("REFUSAL_DISAGREES_WITH_DISPATCH_STATE")
    if dispatch_state == "CONFIRMED_NOT_SENT" and refusal_code != "PROMPT_REFUSED_BY_RUNTIME":
        raise _invariant("CONFIRMED_NOT_SENT_REQUIRES_PROMPT_REFUSED_BY_RUNTIME")

    expected_agrees = (
        runtime_shape == declared_shape
        and runtime_reasoning == "TRUE"
        and runtime_thinking == EXPECTED_THINKING_LEVEL
    )
    if payload["manipulation_check_agrees"] is not expected_agrees:
        raise _invariant("MANIPULATION_CHECK_DISAGREES_WITH_PROJECTION")
    if dispatch_state != "NOT_ATTEMPTED" and payload["manipulation_check_agrees"] is not True:
        raise _invariant("DISPATCH_WITHOUT_AGREEING_MANIPULATION_CHECK")

    _require_activity_family_consistency(
        payload,
        available=activity_available,
        capture_basis=capture_basis,
        count_keys=_OBS1_COUNT_KEYS,
        extra_false_bool="runtime_reported_unidentified_tool_call_id_seen",
    )
    if capture_basis == CAPTURE_BASIS_AGENT_SETTLED and payload["runtime_wait_outcome"] != "SETTLED":
        raise _invariant("SETTLED_BASIS_REQUIRES_SETTLED_WAIT_OUTCOME")

    if not broker_available:
        for key in _BROKER_COUNT_KEYS:
            if payload[key] != 0:
                raise _invariant("UNAVAILABLE_BROKER_FAMILY_CARRIES_COUNTS")
    if payload["broker_recorded_edited_path_count"] > payload["broker_recorded_edit_operation_count"]:
        raise _invariant("EDITED_PATHS_EXCEED_EDIT_OPERATIONS")

    computed_closed, computed_steps = compute_lifecycle_closure(payload)
    if payload["lifecycle_all_closed"] is not computed_closed:
        raise _invariant("LIFECYCLE_ALL_CLOSED_DISAGREES_WITH_COMPONENTS")
    if failure_steps != computed_steps:
        raise _invariant("LIFECYCLE_FAILURE_STEPS_DISAGREE_WITH_COMPONENTS")

    if verification_attempted:
        if not (
            payload["runtime_exit_observed"]
            and payload["runtime_transport_eof_observed"]
            and payload["broker_state_closed"]
            and payload["generated_config_scrub_verified"]
            and payload["extension_binding_scrub_verified"]
        ):
            raise _invariant("VERIFICATION_ATTEMPTED_WITHOUT_PROVEN_CLOSURE")
    elif skip_reason is None:
        raise _invariant("VERIFICATION_NOT_ATTEMPTED_WITHOUT_SKIP_REASON")

    if changed and not frozenset(changed) <= CFG1_T1_FILES:  # pragma: no cover - list check
        raise _invariant("CHANGED_PATHS_OUTSIDE_FIXTURE")

    if payload["run_classification"] != classify_cfg1_run(payload):
        raise _invariant("RUN_CLASSIFICATION_NOT_REPRODUCIBLE")


def _require_activity_family_consistency(
    payload: Mapping[str, Any],
    *,
    available: bool,
    capture_basis: str | None,
    count_keys: tuple[str, ...],
    extra_false_bool: str,
) -> None:
    """OBS1 re-validation branches on availability (Sec. 22.3, clarified FU2).

    When the family IS available, the validator reconstructs an exact
    :class:`~qualification.runtime_activity.RuntimeToolActivitySnapshot` from
    the record's own retained fields and requires that construction to succeed
    unmodified -- re-establishing every OBS1 invariant rather than re-stating a
    subset of them here.

    When it is NOT available, no snapshot is constructed at all: there is no
    genuine observation to reconstruct, and fabricating an "available" one
    merely to validate an unavailable observation would be a lie. The
    unavailable branch instead requires a null capture basis, every count zero,
    and the unidentified-id flag false.
    """
    from qualification.runtime_activity import (
        ActivityRecordInvariantError,
        RuntimeToolActivitySnapshot,
    )

    if not available:
        if capture_basis is not None:
            raise _invariant("UNAVAILABLE_ACTIVITY_CARRIES_CAPTURE_BASIS")
        for key in count_keys:
            if payload[key] != 0:
                raise _invariant("UNAVAILABLE_ACTIVITY_CARRIES_COUNTS")
        if payload[extra_false_bool] is not False:
            raise _invariant("UNAVAILABLE_ACTIVITY_CARRIES_UNIDENTIFIED_FLAG")
        return

    if capture_basis is None:
        raise _invariant("AVAILABLE_ACTIVITY_WITHOUT_CAPTURE_BASIS")
    if payload["activity_unavailable_reason"] is not None:
        raise _invariant("AVAILABLE_ACTIVITY_CARRIES_UNAVAILABLE_REASON")
    try:
        RuntimeToolActivitySnapshot(
            capture_basis=capture_basis,
            tool_execution_start_events=payload["runtime_reported_tool_execution_start_events"],
            tool_execution_end_events=payload["runtime_reported_tool_execution_end_events"],
            distinct_tool_call_ids=payload["runtime_reported_distinct_tool_call_ids"],
            unidentified_tool_call_id_seen=payload[
                "runtime_reported_unidentified_tool_call_id_seen"
            ],
            aido_read_call_ids=payload["runtime_reported_aido_read_call_ids"],
            aido_read_end_observed=payload["runtime_reported_aido_read_end_observed"],
            aido_read_error_results=payload["runtime_reported_aido_read_error_results"],
            aido_edit_call_ids=payload["runtime_reported_aido_edit_call_ids"],
            aido_edit_end_observed=payload["runtime_reported_aido_edit_end_observed"],
            aido_edit_error_results=payload["runtime_reported_aido_edit_error_results"],
            unexpected_tool_call_ids=payload["runtime_reported_unexpected_tool_call_ids"],
            unexpected_tool_end_observed=payload["runtime_reported_unexpected_tool_end_observed"],
            unexpected_tool_error_results=payload["runtime_reported_unexpected_tool_error_results"],
        )
    except ActivityRecordInvariantError as exc:
        raise _invariant("OBS1_SNAPSHOT_INVARIANT_VIOLATED") from exc


# ---------------------------------------------------------------------------
# Sec. 22.4.1 -- the REFUSAL-record validator
# ---------------------------------------------------------------------------

CFG1_REFUSAL_RECORD_KEYS: frozenset[str] = frozenset(
    {
        "experiment",
        "record_version",
        "record_kind",
        "stage_id",
        "stage_execution_id",
        "run_ordinal",
        "arm_id",
        "record_filename",
        "refused_record_kind",
        "finding_count",
        "finding_categories",
        "lifecycle_all_closed",
    }
)


def _require_valid_cfg1_refusal_payload(payload: Mapping[str, Any]) -> None:
    """The closed ``pi-harness-cfg1-refusal.v1`` schema.

    Structurally parallel to the run-record validator but over its own,
    smaller, closed schema -- and independently implemented, never a wrapper
    with the run-record checks skipped (Sec. 22.4.3).
    """
    if type(payload) is not dict:
        raise _schema("NOT_A_DICT")
    _require_exact_keys(payload, CFG1_REFUSAL_RECORD_KEYS)

    _require_literal(payload, "experiment", PACKAGE_ID)
    _require_literal(payload, "record_version", REFUSAL_RECORD_VERSION)
    _require_literal(payload, "record_kind", REFUSAL_RECORD_KIND)

    stage_id = _require_enum(payload, "stage_id", STAGE_IDS)
    _require_stage_execution_id(payload)
    ordinals = declared_ordinals(stage_id)
    run_ordinal = _require_int(
        payload, "run_ordinal", minimum=ordinals[0], maximum=ordinals[-1]
    )
    arm_id = _require_enum(payload, "arm_id", STAGE_ARMS[stage_id])
    record_filename = _require_str(payload, "record_filename")
    _require_enum(payload, "refused_record_kind", REFUSABLE_RECORD_KINDS)

    finding_count = _require_int(payload, "finding_count", minimum=1)
    categories = _require_sorted_unique_subset(payload, "finding_categories", FINDING_CATEGORIES)
    _require_bool(payload, "lifecycle_all_closed")

    if arm_id != _schedule_arm_for(stage_id, run_ordinal):
        raise _invariant("ARM_DISAGREES_WITH_SCHEDULE")
    if record_filename != _run_record_filename(stage_id, run_ordinal, arm_id):
        raise _invariant("RECORD_FILENAME_DISAGREES_WITH_DERIVATION")
    if not categories:
        raise _invariant("REFUSAL_WITHOUT_FINDING_CATEGORIES")
    if len(categories) > finding_count:
        raise _invariant("FINDING_COUNT_BELOW_CATEGORY_COUNT")


# ---------------------------------------------------------------------------
# Sec. 22.4.2 -- the STAGE-CLOSURE-record validator
# ---------------------------------------------------------------------------

CFG1_STAGE_CLOSURE_RECORD_KEYS: frozenset[str] = frozenset(
    {
        "experiment",
        "record_version",
        "record_kind",
        "stage_id",
        "stage_execution_id",
        "record_filename",
        "ordinal_status",
        "halted_after_ordinal",
        "halt_reason_code",
    }
)


def _require_valid_cfg1_stage_closure_payload(payload: Mapping[str, Any]) -> None:
    """The closed ``pi-harness-cfg1-stage-closure.v1`` schema.

    **Validation proves coherence, never provenance** (Sec. 22.4.2, Finding 5).
    A hand-crafted payload could satisfy every check here while describing a
    stage execution that never happened. The stronger live guarantee is the
    conjunction Sec. 16.3.8.3 defines: valid schema PLUS a genuine sealed
    ``CFG1StageClosureDecision`` PLUS an ACTIVE, matching stage-output
    authority PLUS a payload the writer itself derived from that decision.

    For four of the six halt codes this validator enforces closed-set
    membership ONLY, and must not pretend otherwise: ``PRE_DISPATCH_REFUSAL``,
    ``LIFECYCLE_CLOSURE_UNPROVEN``, ``RUN_SCOPED_REGISTRY_NOT_EMPTY`` and
    ``RUN_RECORD_SELF_VALIDATION_FAILED`` depend on facts no durable payload
    carries, so it has no mechanism to check their relationship to
    ``ordinal_status`` at all.
    """
    if type(payload) is not dict:
        raise _schema("NOT_A_DICT")
    _require_exact_keys(payload, CFG1_STAGE_CLOSURE_RECORD_KEYS)

    _require_literal(payload, "experiment", PACKAGE_ID)
    _require_literal(payload, "record_version", STAGE_CLOSURE_RECORD_VERSION)
    _require_literal(payload, "record_kind", STAGE_CLOSURE_RECORD_KIND)

    stage_id = _require_enum(payload, "stage_id", STAGE_IDS)
    _require_stage_execution_id(payload)
    record_filename = _require_str(payload, "record_filename")

    ordinals = declared_ordinals(stage_id)
    status = _get(payload, "ordinal_status")
    if type(status) is not dict:
        raise _schema("BAD_ORDINAL_STATUS")
    expected_keys = frozenset(str(ordinal) for ordinal in ordinals)
    if frozenset(status) != expected_keys:
        raise _schema("CLOSED_KEY_SET_VIOLATION_ORDINAL_STATUS")
    for value in status.values():
        if type(value) is not str or value not in ORDINAL_STATUS_VALUES:
            raise _schema("BAD_ORDINAL_STATUS_VALUE")

    halted_after = _get(payload, "halted_after_ordinal")
    if halted_after is not None:
        if type(halted_after) is not int:
            raise _schema("BAD_HALTED_AFTER_ORDINAL")
        if halted_after not in ordinals:
            raise _schema("OUT_OF_RANGE_HALTED_AFTER_ORDINAL")
    halt_reason_code = _require_optional_enum(payload, "halt_reason_code", HALT_REASON_CODES)

    # -- cross-field invariants ---------------------------------------------
    if record_filename != _stage_closure_record_filename(stage_id):
        raise _invariant("RECORD_FILENAME_DISAGREES_WITH_DERIVATION")

    if (halted_after is None) != (halt_reason_code is None):
        raise _invariant("HALT_METADATA_PARTIALLY_PRESENT")

    for ordinal in ordinals:
        value = status[str(ordinal)]
        should_be_not_executed = halted_after is not None and ordinal > halted_after
        if should_be_not_executed and value != ORDINAL_NOT_EXECUTED:
            raise _invariant("POST_HALT_ORDINAL_NOT_MARKED_NOT_EXECUTED")
        if not should_be_not_executed and value == ORDINAL_NOT_EXECUTED:
            raise _invariant("NOT_EXECUTED_OUTSIDE_POST_HALT_RANGE")

    for ordinal in ordinals:
        value = status[str(ordinal)]
        if value in (EMISSION_COLLISION, EMISSION_FAILED):
            if halted_after != ordinal:
                raise _invariant("FAILED_ORDINAL_IS_NOT_THE_HALT_POINT")
            expected_code = (
                HALT_RUN_RECORD_EMISSION_COLLISION
                if value == EMISSION_COLLISION
                else HALT_RUN_RECORD_EMISSION_FAILED
            )
            if halt_reason_code != expected_code:
                raise _invariant("HALT_CODE_DISAGREES_WITH_EMISSION_OUTCOME")

    if halted_after is None:
        # Sec. 19.1's admission rule, restated as a schema invariant a reader
        # can verify from an archived record alone.
        for ordinal in ordinals:
            if status[str(ordinal)] not in (EMISSION_RECORD_EMITTED, EMISSION_EVIDENCE_REFUSED):
                raise _invariant("SUCCESSFUL_STAGE_CARRIES_NON_ADMITTING_STATUS")


# ---------------------------------------------------------------------------
# Sec. 22.4.3 -- discriminator dispatch for the read-only run-artifact verifier
# ---------------------------------------------------------------------------

#: ``(record_version, record_kind) -> validator``. Both members of a pair must
#: match: a mixed or contradictory pairing dispatches to NOTHING and is refused
#: with zero validator calls (T-82).
_RUN_PATH_DISCRIMINATORS: dict[tuple[str, str], Any] = {
    (RUN_RECORD_VERSION, RUN_RECORD_KIND): _require_valid_cfg1_run_payload,
    (REFUSAL_RECORD_VERSION, REFUSAL_RECORD_KIND): _require_valid_cfg1_refusal_payload,
}


def _dispatch_run_path_validator(parsed: Mapping[str, Any]):
    """The one legitimate-occupant dispatch for a scheduled RUN path.

    A run path may genuinely hold exactly two kinds: the run record itself, or
    the bounded, non-recursive refusal record written at that SAME path when
    the primary record's own ``PRE_CREATE`` emission failed. Treating a valid
    refusal artifact as invalid merely because it is not the run kind would be
    wrong -- it is one of two legitimate occupants, not a third, unrecognized
    one. Returns ``None`` for anything else, and no validator is invoked.
    """
    key = (parsed.get("record_version"), parsed.get("record_kind"))
    return _RUN_PATH_DISCRIMINATORS.get(key)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Payload construction -- the same schedule derivation every consumer uses
# ---------------------------------------------------------------------------


def build_cfg1_run_payload(
    *, stage_id: str, stage_execution_id: str, run_ordinal: int, observations: Mapping[str, Any]
) -> dict[str, Any]:
    """Assemble one run record from L28's now-immutable facts.

    ``arm_id`` and ``(block, position)`` come from the SAME
    ``_schedule_arm_for`` / ``_schedule_block_position`` callables the writer,
    the validator and the artifact-binding verifier invoke -- so a
    correctly-behaving pipeline's payload already agrees with the writer's
    step-7 binding by construction. That binding remains the ENFORCEMENT
    boundary, not merely a sanity check on a value nothing else could get wrong.

    ``run_classification`` is recomputed here from the assembled snapshot by
    the same pure function the validator re-runs, so an assembled value can
    never disagree with its own inputs.
    """
    if type(observations) is not dict:
        raise _schema("OBSERVATIONS_NOT_A_DICT")
    if frozenset(observations) != CFG1_RUN_OBSERVATION_KEYS:
        raise _schema("CLOSED_KEY_SET_VIOLATION_OBSERVATIONS")

    arm_id = _schedule_arm_for(stage_id, run_ordinal)
    block, position = _schedule_block_position(stage_id, run_ordinal)

    payload: dict[str, Any] = {
        "experiment": PACKAGE_ID,
        "record_version": RUN_RECORD_VERSION,
        "record_kind": RUN_RECORD_KIND,
        "scoring_authority": False,
        "qualification_credit": False,
        "is_review_packet": False,
        "reviewer_invoked": False,
        "claim_scope": CLAIM_SCOPE,
        "stage_id": stage_id,
        "stage_execution_id": stage_execution_id,
        "run_ordinal": run_ordinal,
        "block": block,
        "position": position,
        "arm_id": arm_id,
        "record_filename": _run_record_filename(stage_id, run_ordinal, arm_id),
        "declared_compat_shape": ARM_SHAPE[arm_id],
        "models_json_redacted_sha256": ARM_REDACTED_DIGEST[arm_id],
        "settings_json_sha256": PINNED_SETTINGS_SHA256,
        "model_id": CFG1_MODEL_ID,
        "provider_id": PROVIDER_ID,
        "backend_gateway_class": BACKEND_GATEWAY_CLASS,
        "fixture_task_id": CFG1_TASK_ID,
        "fixture_revision": CFG1_T1_REVISION,
    }
    payload.update(ARM_EFFECTIVE[arm_id])
    payload.update(dict(observations))
    payload["run_classification"] = classify_cfg1_run(payload)
    return payload


def build_cfg1_refusal_payload(
    *,
    stage_id: str,
    stage_execution_id: str,
    run_ordinal: int,
    finding_count: int,
    finding_categories: tuple[str, ...],
    lifecycle_all_closed: bool,
) -> dict[str, Any]:
    """Build a refusal record FRESHLY, from authority and schedule truth only.

    There is deliberately no parameter through which the rejected payload's own
    fields could reach this record's identity: the caller supplies bounded
    finding-category facts and one already-finalized lifecycle bool, and
    nothing else (Sec. 16.3.8.2, T-77).
    """
    arm_id = _schedule_arm_for(stage_id, run_ordinal)
    return {
        "experiment": PACKAGE_ID,
        "record_version": REFUSAL_RECORD_VERSION,
        "record_kind": REFUSAL_RECORD_KIND,
        "stage_id": stage_id,
        "stage_execution_id": stage_execution_id,
        "run_ordinal": run_ordinal,
        "arm_id": arm_id,
        "record_filename": _run_record_filename(stage_id, run_ordinal, arm_id),
        "refused_record_kind": RUN_RECORD_VERSION,
        "finding_count": finding_count,
        "finding_categories": sorted(set(finding_categories)),
        "lifecycle_all_closed": lifecycle_all_closed,
    }
