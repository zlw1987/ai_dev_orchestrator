"""Payload builders shared by the CFG1 offline suite. Test-only scaffolding.

Nothing here is production code, and nothing here is an authority: these
helpers build PAYLOADS, which every writer then independently validates and
binds to its own authority. A builder that produced something the writer
accepted without checking would defeat the very boundaries this suite exists
to prove.
"""

from __future__ import annotations

from typing import Any

from pi_harness_cfg1 import obs1
from pi_harness_cfg1.records import (
    CFG1_RUN_OBSERVATION_KEYS,
    build_cfg1_run_payload,
)

_STOP_REASON_KEYS = ("stop", "length", "toolUse", "error", "aborted", "other")


def happy_observations(**overrides: Any) -> dict[str, Any]:
    """An L28 observation set for a clean, fully-closed, INACTIVE run.

    INACTIVE, not ACTIVE, is the default because it is the shape Q1/Q2/Q3
    actually produced and the one CFG1 exists to contrast against.
    """
    observations: dict[str, Any] = {
        "pi_observed_version": "0.85.1",
        "pi_seam_digests_match": True,
        "base_url_compat_detection_clear": True,
        "route_reachable": True,
        "route_configured_model_served": True,
        "broker_reached_ready": True,
        "h1_extension_identity_matched": True,
        "h2_provider_model_identity_matched": True,
        "runtime_reported_compat_shape": "ABSENT",
        "runtime_reported_model_reasoning": "TRUE",
        "runtime_reported_thinking_level": "medium",
        "manipulation_check_agrees": True,
        "pre_dispatch_refusal_code": None,
        "refused_at_step": None,
        "dispatch_state": "CONFIRMED_SENT",
        "prompt_writes": 1,
        "automatic_semantic_retry": False,
        "operator_continuation": False,
        "runtime_wait_outcome": "SETTLED",
        "runtime_reported_tool_activity_available": True,
        "runtime_reported_tool_activity_capture_basis": "agent_settled",
        "runtime_reported_tool_execution_start_events": 0,
        "runtime_reported_tool_execution_end_events": 0,
        "runtime_reported_distinct_tool_call_ids": 0,
        "runtime_reported_unidentified_tool_call_id_seen": False,
        "runtime_reported_aido_read_call_ids": 0,
        "runtime_reported_aido_read_end_observed": 0,
        "runtime_reported_aido_read_error_results": 0,
        "runtime_reported_aido_edit_call_ids": 0,
        "runtime_reported_aido_edit_end_observed": 0,
        "runtime_reported_aido_edit_error_results": 0,
        "runtime_reported_unexpected_tool_call_ids": 0,
        "runtime_reported_unexpected_tool_end_observed": 0,
        "runtime_reported_unexpected_tool_error_results": 0,
        "activity_unavailable_reason": None,
        "stop_reasons_available": True,
        "stop_reason_counts": {key: 0 for key in _STOP_REASON_KEYS},
        "auto_retry_events": 0,
        "extension_error_count": 0,
        "broker_recorded_activity_available": True,
        "broker_recorded_read_operation_count": 0,
        "broker_recorded_edit_operation_count": 0,
        "broker_recorded_edited_path_count": 0,
        "broker_recorded_refusal_count": 0,
        "runtime_created": True,
        "runtime_exit_observed": True,
        "runtime_transport_eof_observed": True,
        "broker_resource_created": True,
        "broker_state_closed": True,
        "broker_pending_unreaped_zero": True,
        "broker_worker_terminated_or_absent": True,
        "generated_config_scrub_verified": True,
        "extension_binding_scrub_verified": True,
        "verification_child_reaped_or_not_started": True,
        "workspace_authority_reproved": True,
        "workspace_removed_verified": True,
        "workspace_residual_file_count": 0,
        "lifecycle_all_closed": True,
        "lifecycle_failure_steps": [],
        "git_observation_1_performed": True,
        "head_moved": False,
        "changed_tracked_paths": [],
        "untracked_path_count": 0,
        "staged_path_count": 0,
        "broker_git_cross_check_agrees": True,
        "git_observation_2_performed": True,
        "post_verification_changed_tracked_paths": [],
        "verification_attempted": True,
        "verification_skip_reason": None,
        "verification_started": True,
        "verification_completed": True,
        "verification_timed_out": False,
        "verification_output_limit_exceeded": False,
        "verification_return_code": 1,
        "verification_passed": False,
        "verification_counts": {"passed": 0, "failed": 1, "error": 0},
    }
    observations.update(overrides)
    assert frozenset(observations) == CFG1_RUN_OBSERVATION_KEYS, (
        "the builder and the closed observation key set have drifted apart: "
        f"{frozenset(observations) ^ CFG1_RUN_OBSERVATION_KEYS}"
    )
    return observations


def run_payload(
    *,
    stage_id: str = "S1",
    stage_execution_id: str = "S1-X1",
    run_ordinal: int = 1,
    **observation_overrides: Any,
) -> dict[str, Any]:
    """A fully valid run-record payload for one schedule position."""
    from pi_harness_cfg1.arms import ARM_SHAPE
    from pi_harness_cfg1.schedule import _schedule_arm_for

    arm_id = _schedule_arm_for(stage_id, run_ordinal)
    observation_overrides.setdefault("runtime_reported_compat_shape", ARM_SHAPE[arm_id])
    return build_cfg1_run_payload(
        stage_id=stage_id,
        stage_execution_id=stage_execution_id,
        run_ordinal=run_ordinal,
        observations=happy_observations(**observation_overrides),
    )


def active_observation_overrides() -> dict[str, Any]:
    """Observation deltas that make a run genuinely ``ACTIVE``.

    One read call, one non-error end, and the one matching broker operation --
    the smallest shape that satisfies every OBS1 cross-field invariant AND
    every Sec. 12.2 disagreement predicate simultaneously.
    """
    return {
        "runtime_reported_tool_execution_start_events": 1,
        "runtime_reported_tool_execution_end_events": 1,
        "runtime_reported_distinct_tool_call_ids": 1,
        "runtime_reported_aido_read_call_ids": 1,
        "runtime_reported_aido_read_end_observed": 1,
        "broker_recorded_read_operation_count": 1,
    }


def unavailable_activity_overrides(reason: str = "PROJECTION_REFUSED") -> dict[str, Any]:
    """Observation deltas for a bounded OBS1 projection failure."""
    return dict(obs1.unavailable_activity_fields(reason))


def pre_dispatch_refusal_overrides(code: str, step: str) -> dict[str, Any]:
    """Observation deltas for a run refused BEFORE the one prompt write.

    A refused run observed nothing after its refusal step, so every downstream
    family is fail-closed: no dispatch, no turn outcome, no activity projection
    (there was no dispatch to project), no broker counts, no verification. The
    ``activity_unavailable_reason`` stays ``None`` -- no projection was ever
    attempted, so none was refused, and claiming otherwise would be a lie about
    what happened.
    """
    overrides: dict[str, Any] = {
        "pre_dispatch_refusal_code": code,
        "refused_at_step": step,
        "dispatch_state": "NOT_ATTEMPTED",
        "prompt_writes": 0,
        "runtime_wait_outcome": "NOT_OBSERVED",
        "stop_reasons_available": False,
        "broker_recorded_activity_available": False,
        "verification_attempted": False,
        "verification_skip_reason": "PRE_DISPATCH_REFUSAL",
        "verification_started": False,
        "verification_completed": False,
        "verification_return_code": None,
        "verification_passed": False,
        "verification_counts": {"passed": 0, "failed": 0, "error": 0},
        "git_observation_2_performed": False,
    }
    overrides.update(obs1.unavailable_activity_fields(None))
    return overrides


def refusal_payload(
    *,
    stage_id: str = "S1",
    stage_execution_id: str = "S1-X1",
    run_ordinal: int = 1,
    finding_count: int = 1,
    finding_categories: tuple[str, ...] = ("SCRUB_NEEDLE_MATCH",),
    lifecycle_all_closed: bool = True,
) -> dict[str, Any]:
    from pi_harness_cfg1.records import build_cfg1_refusal_payload

    return build_cfg1_refusal_payload(
        stage_id=stage_id,
        stage_execution_id=stage_execution_id,
        run_ordinal=run_ordinal,
        finding_count=finding_count,
        finding_categories=finding_categories,
        lifecycle_all_closed=lifecycle_all_closed,
    )


def stage_closure_payload(
    *,
    stage_id: str = "S1",
    stage_execution_id: str = "S1-X1",
    ordinal_status: dict[str, str] | None = None,
    halted_after_ordinal: int | None = None,
    halt_reason_code: str | None = None,
) -> dict[str, Any]:
    """A stage-closure PAYLOAD, for validator-level tests only.

    The writer never accepts one of these: it builds its own from a genuine
    sealed decision. This exists so the schema can be exercised directly,
    which is exactly the separation Sec. 22.4.2 draws between coherence
    (checkable here) and provenance (not).
    """
    from pi_harness_cfg1 import (
        PACKAGE_ID,
        STAGE_CLOSURE_RECORD_KIND,
        STAGE_CLOSURE_RECORD_VERSION,
    )
    from pi_harness_cfg1.records import _stage_closure_record_filename
    from pi_harness_cfg1.schedule import declared_ordinals

    if ordinal_status is None:
        ordinal_status = {
            str(ordinal): "RECORD_EMITTED" for ordinal in declared_ordinals(stage_id)
        }
    return {
        "experiment": PACKAGE_ID,
        "record_version": STAGE_CLOSURE_RECORD_VERSION,
        "record_kind": STAGE_CLOSURE_RECORD_KIND,
        "stage_id": stage_id,
        "stage_execution_id": stage_execution_id,
        "record_filename": _stage_closure_record_filename(stage_id),
        "ordinal_status": ordinal_status,
        "halted_after_ordinal": halted_after_ordinal,
        "halt_reason_code": halt_reason_code,
    }


def synthetic_run_executor(
    *, observations_for=None, live_references_released: bool = True
):
    """A total, synthetic stand-in for L1-L28. No Pi, no broker, no workspace.

    ``observations_for(admission) -> dict`` lets one test give different
    ordinals different outcomes; the default gives every ordinal the clean,
    fully-closed INACTIVE shape.
    """
    from qualification.safety import ArtifactSafetyContext

    from pi_harness_cfg1.run_contract import Cfg1RunOutcome

    def _executor(admission):
        if observations_for is None:
            observations = happy_observations(
                runtime_reported_compat_shape=_shape_for(admission)
            )
        else:
            observations = observations_for(admission)
        return Cfg1RunOutcome(
            observations=observations,
            safety=ArtifactSafetyContext.none_declared(),
            live_references_released=live_references_released,
        )

    return _executor


def _shape_for(admission) -> str:
    from pi_harness_cfg1.arms import ARM_SHAPE

    return ARM_SHAPE[admission.arm_id]
