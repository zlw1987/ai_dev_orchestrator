"""L1-L28 for one admitted ordinal. Port-mediated, total, and fail-closed.

Design Sec. 16.2 (the step table), Sec. 17 (resource ownership), Sec. 18 (the
partial-failure table), Sec. 20 (evidence-versus-cleanup ordering), Sec. 21
(containment).

**Ports, not imports, at the boundary.** Every live-resource step is reached
through one field of :class:`Cfg1RunPorts`, so the whole state machine is
exercisable offline against synthetic doubles (T-11) without ever launching Pi,
opening a socket, reading a credential, or contacting a model.
:func:`default_cfg1_run_ports` binds the frozen modules for the eventual,
separately-authorized live phase; importing THIS module does not import them.

**Closure always runs**, in the fixed order L21->L27, after the first
resource-creating step -- skipping only steps whose resource was never created,
and never skipped because an earlier closure step failed.

**Every raw value is reduced at the step that catches it** (Sec. 21.1). No
``str(exc)``, ``repr``, traceback, stderr tail, provider body, broker refusal
text or raw event crosses a step boundary. Failures become one closed code.

**Nothing here claims what it cannot observe.** A closed runtime means AIDO saw
the DIRECT child's exit status and both reader EOFs -- never that inference
stopped, that GPU work stopped, or that any descendant died. Verification is a
controlled invocation of repository-controlled code, not a sandbox.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from . import obs1
from .arms import ARM_SHAPE, EXPECTED_THINKING_LEVEL
from .baseline import (
    capture_cfg1_dispatch_baseline,
    map_runtime_wait_outcome_literal,
    map_turn_wait_outcome,
)
from .fixture import CFG1_T1, CFG1_T1_FILES
from .identity import (
    BASE_URL_ENV_VAR_NAME,
    CFG1_MODEL_ID,
    CREDENTIAL_ENV_VAR_NAME,
    PINNED_PI_VERSION,
    PROVIDER_ID,
    TOOL_ALLOWLIST,
)
from .preflight import base_url_compat_detection_clear, verify_pi_seam_digests
from .run_contract import Cfg1RunAdmission, Cfg1RunOutcome

_STOP_REASON_KEYS = ("stop", "length", "toolUse", "error", "aborted", "other")
_VERIFICATION_COUNT_KEYS = ("passed", "failed", "error")


@dataclass(frozen=True)
class Cfg1RunPorts:
    """Every live-resource capability L1-L28 may reach, as one injectable set.

    A port is a capability, never a configuration knob: none of them selects a
    path, an arm, an output location, or a schedule position. The arm comes
    from the admission the stage runner derived from the frozen schedule, and
    nothing here can override it.

    **Workspace OWNERSHIP is deliberately not a port.** ``mint_workspace``
    creates one, but the claim, the re-proof at every consumption boundary, and
    the removal all go straight to :mod:`run_workspace`, unmediated -- a double
    that could stand in for those could authorize the deletion of a tree CFG1
    never created, which is exactly what Sec. 17's "never, by construction"
    list forbids.

    **The adapter surface each port must provide**, so the eventual LIVE
    binding has a contract rather than an inference:

    ``resolve_runtime_identity()``
        ``.node_executable``, ``.pi_cli_js``, ``.pi_package_root``,
        ``.reported_version``
    ``mint_workspace(git_executable=...)``
        ``(Cfg1RunWorkspace, BuiltFixture)`` -- a GENUINE registry mint
    ``observe_repository(workspace_root=...)``
        ``.head``, ``.changed_tracked_paths``, ``.untracked_path_count``,
        ``.staged_path_count``
    ``run_verification(workspace_root=..., args=...)``
        ``.started``, ``.completed``, ``.timed_out``,
        ``.output_limit_exceeded``, ``.return_code``, ``.passed``, ``.counts``
    ``read_connection()``
        ``(base_url, credential_value)`` -- the ONE place either is ever read
    ``observe_route(base_url=..., api_key=..., model_id=...)``
        ``.reachable``, ``.configured_model_served``
    ``write_config(owned_root=..., arm_id=..., base_url=...)``
        a :class:`~pi_harness_cfg1.cfg1_pi_config.GeneratedCfg1Config`, written
        BESIDE the repository child, never inside it
    ``build_broker(capability=...)``
        ``.start()``, ``.token``, ``.pipe_name``, ``.capability_id``,
        ``.diagnostics_counts()`` -> ``{read_operations, edit_operations,
        edited_paths, refusals}``, ``.shutdown_for_cfg1()`` ->
        ``{state_reached, pending_operations_unreaped,
        worker_termination_observed}``
    ``write_extension(owned_root=..., broker=...)``
        ``.entry_path``, ``.extension_dir`` (the directory holding the
        token-bearing ``ar2_config.ts`` L24 scrubs through the FROZEN
        ``scrub_generated_extension_config``), likewise written beside the
        repository child
    ``build_supervisor(identity=..., extension=..., environment=...,
    workspace_root=...)``
        a ``PiRpcSupervisor``-shaped object
    ``evaluate_extension_identity(supervisor=..., extension=...)``
        ``.matched``
    ``evaluate_model_identity(supervisor=...)``
        ``(object with .matched, the raw get_state document)``

    The frozen ``ar2`` handshakes return a bounded DICT carrying a ``passed``
    verdict, so :func:`default_cfg1_run_ports` adapts each to this ``.matched``
    shape rather than restating either evaluation. Only the verdict crosses the
    boundary: the handshake's own diagnostic fields, and the raw ``get_state``
    document's ``baseUrl``, are read past and discarded (Sec. 8.2, Sec. 21.2).
    """

    ambient_environ: Mapping[str, str]
    git_executable: Callable[[], str]
    resolve_runtime_identity: Callable[[], Any]
    mint_workspace: Callable[..., Any]
    observe_repository: Callable[..., Any]
    run_verification: Callable[..., Any]
    read_connection: Callable[[], tuple[str, str]]
    observe_route: Callable[..., Any]
    mint_capability: Callable[..., Any]
    write_config: Callable[..., Any]
    write_extension: Callable[..., Any]
    build_environment: Callable[..., Any]
    build_broker: Callable[..., Any]
    build_supervisor: Callable[..., Any]
    evaluate_extension_identity: Callable[..., Any]
    evaluate_model_identity: Callable[..., Any]


def _initial_observations() -> dict[str, Any]:
    """The "nothing has happened yet" observation set. Every field fail-closed.

    A run that refuses at L1 emits exactly this, with one refusal code and one
    step name filled in -- never a partially-optimistic record that implies
    observations nobody made.
    """
    observations: dict[str, Any] = {
        "pi_observed_version": "UNRECOGNIZED",
        "pi_seam_digests_match": False,
        "base_url_compat_detection_clear": False,
        "route_reachable": False,
        "route_configured_model_served": False,
        "broker_reached_ready": False,
        "h1_extension_identity_matched": False,
        "h2_provider_model_identity_matched": False,
        "runtime_reported_compat_shape": "NOT_OBSERVED",
        "runtime_reported_model_reasoning": "NOT_OBSERVED",
        "runtime_reported_thinking_level": "NOT_OBSERVED",
        "manipulation_check_agrees": False,
        "pre_dispatch_refusal_code": None,
        "refused_at_step": None,
        "dispatch_state": "NOT_ATTEMPTED",
        "prompt_writes": 0,
        "automatic_semantic_retry": False,
        "operator_continuation": False,
        "runtime_wait_outcome": "NOT_OBSERVED",
        "stop_reasons_available": False,
        "stop_reason_counts": {key: 0 for key in _STOP_REASON_KEYS},
        "auto_retry_events": 0,
        "extension_error_count": 0,
        "broker_recorded_activity_available": False,
        "broker_recorded_read_operation_count": 0,
        "broker_recorded_edit_operation_count": 0,
        "broker_recorded_edited_path_count": 0,
        "broker_recorded_refusal_count": 0,
        "runtime_created": False,
        "runtime_exit_observed": False,
        "runtime_transport_eof_observed": False,
        "broker_resource_created": False,
        "broker_state_closed": False,
        "broker_pending_unreaped_zero": False,
        "broker_worker_terminated_or_absent": False,
        # "Not created counts as closed": nothing has been written yet, so
        # there is nothing whose scrub could be unverified.
        "generated_config_scrub_verified": True,
        "extension_binding_scrub_verified": True,
        "verification_child_reaped_or_not_started": True,
        "workspace_authority_reproved": False,
        "workspace_removed_verified": False,
        "workspace_residual_file_count": 0,
        "lifecycle_all_closed": False,
        "lifecycle_failure_steps": [],
        "git_observation_1_performed": False,
        "head_moved": False,
        "changed_tracked_paths": [],
        "untracked_path_count": 0,
        "staged_path_count": 0,
        "broker_git_cross_check_agrees": True,
        "git_observation_2_performed": False,
        "post_verification_changed_tracked_paths": [],
        "verification_attempted": False,
        "verification_skip_reason": "PRE_DISPATCH_REFUSAL",
        "verification_started": False,
        "verification_completed": False,
        "verification_timed_out": False,
        "verification_output_limit_exceeded": False,
        "verification_return_code": None,
        "verification_passed": False,
        "verification_counts": {key: 0 for key in _VERIFICATION_COUNT_KEYS},
    }
    observations.update(obs1.unavailable_activity_fields(None))
    return observations


def project_stop_reasons(events) -> tuple[bool, dict[str, int]]:
    """Bucket ``message_end`` stop reasons. Enum counts only, never text.

    ``stop_reasons_available`` is false when no ``message_end`` record carried
    a ``stopReason`` at all -- which Sec. 12.1 row 10 treats as
    ``INDETERMINATE_PROVIDER``, never as "no provider error occurred". An
    unrecognized literal is bucketed as ``other`` and never retained verbatim.
    """
    counts = {key: 0 for key in _STOP_REASON_KEYS}
    seen = False
    for record in events or ():
        if not isinstance(record, dict) or record.get("type") != "message_end":
            continue
        message = record.get("message")
        if not isinstance(message, dict):
            continue
        reason = message.get("stopReason")
        if reason is None:
            continue
        seen = True
        key = reason if isinstance(reason, str) and reason in counts else "other"
        counts[key] += 1
    return seen, counts


def project_get_state(state: object, *, arm_id: str) -> dict[str, Any]:
    """Sec. 8.2's DECLARED-shape projection. Bounded literals only.

    ``get_state`` serializes the COMPOSED model object, not the request-time
    ``getCompat`` result, so what is observable here is the arm's DECLARED
    shape -- never the effective ``true``/``false`` values, which stay
    source-derived offline facts.

    The model object also carries ``baseUrl``. It is read past and discarded:
    nothing but the three bounded projections below leaves this function.
    """
    projection = {
        "runtime_reported_compat_shape": "NOT_OBSERVED",
        "runtime_reported_model_reasoning": "NOT_OBSERVED",
        "runtime_reported_thinking_level": "NOT_OBSERVED",
        "manipulation_check_agrees": False,
    }
    if not isinstance(state, dict):
        return projection

    model = state.get("model")
    if isinstance(model, dict):
        if "compat" not in model:
            projection["runtime_reported_compat_shape"] = "ABSENT"
        else:
            projection["runtime_reported_compat_shape"] = _classify_compat_object(
                model.get("compat")
            )
        reasoning = model.get("reasoning")
        if reasoning is True:
            projection["runtime_reported_model_reasoning"] = "TRUE"
        elif reasoning is False:
            projection["runtime_reported_model_reasoning"] = "FALSE"
        else:
            projection["runtime_reported_model_reasoning"] = "OTHER"
    else:
        projection["runtime_reported_compat_shape"] = "OTHER"
        projection["runtime_reported_model_reasoning"] = "OTHER"

    if "thinkingLevel" in state:
        level = state.get("thinkingLevel")
        known = ("off", "minimal", "low", "medium", "high", "xhigh", "max")
        projection["runtime_reported_thinking_level"] = (
            level if isinstance(level, str) and level in known else "OTHER"
        )

    projection["manipulation_check_agrees"] = (
        projection["runtime_reported_compat_shape"] == ARM_SHAPE[arm_id]
        and projection["runtime_reported_model_reasoning"] == "TRUE"
        and projection["runtime_reported_thinking_level"] == EXPECTED_THINKING_LEVEL
    )
    return projection


def _classify_compat_object(compat: object) -> str:
    """Exactly the four declared shapes, or ``OTHER``. Never a partial match.

    A key set outside the four, or a value that is not exact JSON ``false``,
    is ``OTHER`` -- the check never demands an explicit ``true`` for an absent
    field, and never accepts a truthy stand-in for ``false``.
    """
    if not isinstance(compat, dict):
        return "OTHER"
    if any(value is not False for value in compat.values()):
        return "OTHER"
    keys = frozenset(compat)
    if keys == frozenset({"supportsDeveloperRole"}):
        return "DEVELOPER_ROLE_FALSE_ONLY"
    if keys == frozenset({"supportsReasoningEffort"}):
        return "REASONING_EFFORT_FALSE_ONLY"
    if keys == frozenset({"supportsDeveloperRole", "supportsReasoningEffort"}):
        return "BOTH_FALSE_ONLY"
    return "OTHER"


class _PreDispatchRefusal(Exception):
    """Internal control flow: one closed refusal code plus its step name."""

    def __init__(self, code: str, step: str) -> None:
        super().__init__(code)
        self.code = code
        self.step = step


@dataclass
class _RunState:
    """Which resources this run actually created. Closure acts only on these."""

    workspace: Any = None
    built_fixture: Any = None
    generated_config: Any = None
    extension: Any = None
    broker: Any = None
    supervisor: Any = None
    capability: Any = None
    safety: Any = None
    console_codes: list[str] = field(default_factory=list)


def execute_cfg1_run(admission: Cfg1RunAdmission, *, ports: Cfg1RunPorts) -> Cfg1RunOutcome:
    """Run L1-L28 for one admitted ordinal. TOTAL: never raises.

    Every failure becomes bounded observation facts. The stage runner owns L0,
    L29 and L30; nothing here sees the stage-output authority, derives an
    output path, writes an artifact, or learns any ordinal's emission status.
    """
    observations = _initial_observations()
    state = _RunState()
    try:
        _dispatch_phase(admission, ports=ports, observations=observations, state=state)
    except _PreDispatchRefusal as refusal:
        observations["pre_dispatch_refusal_code"] = refusal.code
        observations["refused_at_step"] = refusal.step
    except Exception:  # noqa: BLE001 - reduced HERE; no raw text escapes
        observations["pre_dispatch_refusal_code"] = "OFFLINE_PREFLIGHT_FAILED"
        observations["refused_at_step"] = "L1"
        state.console_codes.append("RUN_STEP_RAISED_UNEXPECTEDLY")

    _closure_phase(ports=ports, observations=observations, state=state)

    from .lifecycle import compute_lifecycle_closure

    closed, failure_steps = compute_lifecycle_closure(observations)
    observations["lifecycle_all_closed"] = closed
    observations["lifecycle_failure_steps"] = list(failure_steps)

    from qualification.safety import ArtifactSafetyContext

    return Cfg1RunOutcome(
        observations=observations,
        safety=state.safety if state.safety is not None else ArtifactSafetyContext.none_declared(),
        live_references_released=True,
        console_codes=tuple(state.console_codes),
    )


def _dispatch_phase(
    admission: Cfg1RunAdmission,
    *,
    ports: Cfg1RunPorts,
    observations: dict[str, Any],
    state: _RunState,
) -> None:
    """L1 through L20. Raises :class:`_PreDispatchRefusal` to transfer to closure."""
    from qualification.safety import ArtifactSafetyContext

    # ---------------- L1 OFFLINE PREFLIGHT ----------------
    try:
        identity = ports.resolve_runtime_identity()
    except Exception:  # noqa: BLE001
        raise _PreDispatchRefusal("OFFLINE_PREFLIGHT_FAILED", "L1") from None
    observations["pi_observed_version"] = _bounded_version(
        getattr(identity, "reported_version", None)
    )
    digests_match, _mismatched = verify_pi_seam_digests(identity.pi_package_root)
    observations["pi_seam_digests_match"] = digests_match
    if not digests_match or observations["pi_observed_version"] != PINNED_PI_VERSION:
        # A seam or version mismatch refuses BEFORE any credential read. It
        # means the derivation must be re-reviewed, never that Pi is broken.
        raise _PreDispatchRefusal("OFFLINE_PREFLIGHT_FAILED", "L1")

    try:
        git_executable = ports.git_executable()
    except Exception:  # noqa: BLE001
        raise _PreDispatchRefusal("OFFLINE_PREFLIGHT_FAILED", "L1") from None

    # ---------------- L2 WORKSPACE MINT + POPULATE ----------------
    from . import run_workspace as workspace_module

    try:
        state.workspace, state.built_fixture = ports.mint_workspace(
            git_executable=git_executable
        )
    except Exception:  # noqa: BLE001 - an orphan root may exist and is NEVER deleted
        state.console_codes.append("WORKSPACE_MINT_PARTIAL")
        raise _PreDispatchRefusal("WORKSPACE_BASELINE_FAILED", "L2") from None

    # The claim is SINGLE-USE and binds this one synthetic workspace to this one
    # invocation. Guarded like every other step: a workspace already claimed --
    # by another run, or by a re-entry of this one -- refuses here rather than
    # raising out of the state machine as an unclassified error.
    try:
        workspace_module.claim_cfg1_run_workspace(
            state.workspace, run_id=admission.run_id
        )
    except Exception:  # noqa: BLE001
        raise _PreDispatchRefusal("WORKSPACE_BASELINE_FAILED", "L2") from None

    state.safety = ArtifactSafetyContext(
        workspace_absolute_path=state.workspace.experiment_root
    )

    # ---------------- L3 WORKSPACE BASELINE ----------------
    # Repository-controlled code (AIDO's own fixture only) runs here, BEFORE
    # any credential exists in process memory -- the frozen
    # baseline-before-credential ordering.
    try:
        repo_root = workspace_module.verify_cfg1_run_workspace(state.workspace)
        baseline_verification = ports.run_verification(
            workspace_root=repo_root, args=CFG1_T1.verification_args
        )
    except Exception:  # noqa: BLE001
        raise _PreDispatchRefusal("WORKSPACE_BASELINE_FAILED", "L3") from None
    if getattr(baseline_verification, "return_code", None) is None:
        observations["verification_child_reaped_or_not_started"] = False
        raise _PreDispatchRefusal("WORKSPACE_BASELINE_FAILED", "L3")
    if getattr(baseline_verification, "passed", True):
        # CFG1-T1 declares a seeded failure. A passing baseline means the
        # fixture is not the task this record would claim it ran.
        raise _PreDispatchRefusal("WORKSPACE_BASELINE_FAILED", "L3")

    # ---------------- L4 CREDENTIAL BOUNDARY ----------------
    try:
        base_url, credential_value = ports.read_connection()
    except Exception:  # noqa: BLE001
        raise _PreDispatchRefusal("CREDENTIAL_BOUNDARY_FAILED", "L4") from None

    # ---------------- L5 SECRET CONTEXT ----------------
    try:
        from qualification.i2_secret_context import (
            extract_endpoint_host,
            validate_b300_base_url,
        )

        validate_b300_base_url(base_url)
        endpoint_host = extract_endpoint_host(base_url)
    except Exception:  # noqa: BLE001
        raise _PreDispatchRefusal("SECRET_CONTEXT_FAILED", "L5") from None
    state.safety = ArtifactSafetyContext(
        endpoint_host=endpoint_host,
        api_key=credential_value,
        workspace_absolute_path=state.workspace.experiment_root,
    )

    # ---------------- L6 BASE-URL COMPAT CLASSIFICATION ----------------
    clear = base_url_compat_detection_clear(base_url)
    observations["base_url_compat_detection_clear"] = clear
    if not clear:
        raise _PreDispatchRefusal("BASE_URL_COMPAT_DETECTION_TRIGGERED", "L6")

    # ---------------- L7 ROUTE/MODEL CHECK ----------------
    # Placed BEFORE broker/runtime creation, unlike the frozen qualification
    # controller, so a route refusal creates no live resource at all.
    try:
        route = ports.observe_route(
            base_url=base_url, api_key=credential_value, model_id=CFG1_MODEL_ID
        )
    except Exception:  # noqa: BLE001
        raise _PreDispatchRefusal("ROUTE_UNAVAILABLE", "L7") from None
    observations["route_reachable"] = bool(getattr(route, "reachable", False))
    observations["route_configured_model_served"] = bool(
        getattr(route, "configured_model_served", False)
    )
    if not (observations["route_reachable"] and observations["route_configured_model_served"]):
        raise _PreDispatchRefusal("ROUTE_UNAVAILABLE", "L7")

    # ---------------- L8 CAPABILITY MINT ----------------
    # Two individually genuine objects must also AGREE: a workspace minted for
    # some other run is refused here even though both it and this run are
    # genuine. The claim is single-use, so this can only ever be this run's own.
    if not workspace_module.workspace_is_claimed_by(
        state.workspace, run_id=admission.run_id
    ):
        raise _PreDispatchRefusal("CAPABILITY_MINT_FAILED", "L8")
    try:
        state.capability = ports.mint_capability(
            workspace=state.workspace, git_executable=git_executable
        )
    except Exception:  # noqa: BLE001
        raise _PreDispatchRefusal("CAPABILITY_MINT_FAILED", "L8") from None

    # ---------------- L9 CFG1 CONFIG GENERATION ----------------
    try:
        # The OWNED ROOT, not the repository child. The frozen I2 generator
        # writes beside the repo for the same reason: a config directory
        # created INSIDE the working tree would be Git-visible untracked
        # content, contaminating L25's observation and putting the endpoint
        # somewhere the model's own tools can see.
        state.generated_config = ports.write_config(
            owned_root=state.workspace.experiment_root,
            arm_id=admission.arm_id,
            base_url=base_url,
        )
    except Exception:  # noqa: BLE001
        raise _PreDispatchRefusal("CONFIG_GENERATION_FAILED", "L9") from None
    observations["generated_config_scrub_verified"] = False

    # ---------------- L10 BROKER CONSTRUCTION ----------------
    try:
        state.broker = ports.build_broker(capability=state.capability)
    except Exception:  # noqa: BLE001
        raise _PreDispatchRefusal("BROKER_CONSTRUCTION_FAILED", "L10") from None
    state.safety = ArtifactSafetyContext(
        endpoint_host=endpoint_host,
        api_key=credential_value,
        broker_token=getattr(state.broker, "token", None),
        pipe_name=getattr(state.broker, "pipe_name", None),
        capability_id=getattr(state.broker, "capability_id", None),
        workspace_absolute_path=state.workspace.experiment_root,
    )

    # ---------------- L11 EXTENSION GENERATION ----------------
    try:
        state.extension = ports.write_extension(
            owned_root=state.workspace.experiment_root, broker=state.broker
        )
    except Exception:  # noqa: BLE001
        raise _PreDispatchRefusal("EXTENSION_GENERATION_FAILED", "L11") from None
    observations["extension_binding_scrub_verified"] = False

    # ---------------- L12 CHILD ENVIRONMENT ----------------
    try:
        launch_environment = ports.build_environment(
            ambient_environ=ports.ambient_environ,
            node_executable=identity.node_executable,
            generated_config=state.generated_config,
            credential_value=credential_value,
            git_executable=git_executable,
        )
    except Exception:  # noqa: BLE001
        raise _PreDispatchRefusal("CHILD_ENVIRONMENT_FAILED", "L12") from None

    # ---------------- L13 BROKER START -> READY ----------------
    try:
        state.broker.start()
    except Exception:  # noqa: BLE001
        observations["broker_resource_created"] = True
        raise _PreDispatchRefusal("BROKER_NOT_READY", "L13") from None
    observations["broker_resource_created"] = True
    observations["broker_reached_ready"] = True

    # ---------------- L14 PI LAUNCH ----------------
    try:
        state.supervisor = ports.build_supervisor(
            identity=identity,
            extension=state.extension,
            environment=launch_environment,
            workspace_root=state.workspace.workspace_root,
        )
        state.supervisor.launch()
    except Exception:  # noqa: BLE001
        if getattr(state.supervisor, "process", None) is not None:
            observations["runtime_created"] = True
        raise _PreDispatchRefusal("RUNTIME_LAUNCH_FAILED", "L14") from None
    observations["runtime_created"] = True

    # ---------------- L15 RPC CORRELATION + H1 ----------------
    try:
        h1 = ports.evaluate_extension_identity(
            supervisor=state.supervisor, extension=state.extension
        )
    except Exception:  # noqa: BLE001
        raise _PreDispatchRefusal("RUNTIME_CORRELATION_FAILED", "L15") from None
    observations["h1_extension_identity_matched"] = bool(getattr(h1, "matched", False))
    if not observations["h1_extension_identity_matched"]:
        raise _PreDispatchRefusal("H1_MISMATCH", "L15")

    # ---------------- L16 H2 + MANIPULATION CHECK ----------------
    try:
        h2, state_document = ports.evaluate_model_identity(supervisor=state.supervisor)
    except Exception:  # noqa: BLE001
        raise _PreDispatchRefusal("RUNTIME_CORRELATION_FAILED", "L16") from None
    observations["h2_provider_model_identity_matched"] = bool(getattr(h2, "matched", False))
    observations.update(project_get_state(state_document, arm_id=admission.arm_id))
    if not observations["h2_provider_model_identity_matched"]:
        raise _PreDispatchRefusal("H2_MISMATCH", "L16")
    if not observations["manipulation_check_agrees"]:
        # The prompt is written ONLY to a runtime proven to have loaded this
        # arm's declared shape. A mismatch refuses pre-dispatch and halts the
        # stage; the design is never silently re-read to fit what was observed.
        raise _PreDispatchRefusal("CONFIG_SHAPE_MISMATCH", "L16")

    # ---------------- L17 PRE-DISPATCH BASELINE ----------------
    try:
        dispatch_baseline = capture_cfg1_dispatch_baseline(state.supervisor)
    except Exception:  # noqa: BLE001
        raise _PreDispatchRefusal("PRE_DISPATCH_BASELINE_FAILED", "L17") from None

    # ---------------- L18 ONE PROMPT WRITE ----------------
    dispatch_state, refusal = _write_one_prompt(state.supervisor)
    observations["dispatch_state"] = dispatch_state
    observations["prompt_writes"] = 0 if dispatch_state == "NOT_ATTEMPTED" else 1
    if refusal is not None:
        raise _PreDispatchRefusal(refusal, "L18")

    # ---------------- L19 TURN OBSERVATION ----------------
    try:
        wait_outcome = state.supervisor.await_settled(
            timeout_seconds=_turn_deadline_seconds()
        )
    except Exception:  # noqa: BLE001
        wait_outcome = None
    observations["runtime_wait_outcome"] = map_runtime_wait_outcome_literal(wait_outcome)

    # ---------------- L20 PHI-4 PROJECTION ----------------
    # Runtime facts are frozen into plain values BEFORE the runtime is torn
    # down. Nothing live is retained past this point.
    observations.update(
        obs1.project_cfg1_runtime_activity(
            activity=state.supervisor.activity,
            baseline=dispatch_baseline,
            turn_outcome=map_turn_wait_outcome(wait_outcome),
        )
    )
    try:
        available, counts = project_stop_reasons(state.supervisor.sanitized_events())
    except Exception:  # noqa: BLE001
        available, counts = False, {key: 0 for key in _STOP_REASON_KEYS}
    observations["stop_reasons_available"] = available
    observations["stop_reason_counts"] = counts
    observations["auto_retry_events"] = int(
        getattr(state.supervisor.activity, "auto_retry_events", 0)
    )
    observations["extension_error_count"] = len(
        getattr(state.supervisor.activity, "extension_errors", ()) or ()
    )


def _write_one_prompt(supervisor) -> tuple[str, str | None]:
    """L18. ONE write, one correlated wait, and never a second attempt.

    "Prompt sent?" here means only whether a prompt write reached Pi's stdin.
    It is never a claim that a model request did or did not occur.
    """
    from ar2.supervisor import RunBounds

    command_id = _fresh_command_id()
    try:
        supervisor.send_command(
            {"id": command_id, "type": "prompt", "message": CFG1_T1.prompt}
        )
    except Exception:  # noqa: BLE001 - the write itself may have partially landed
        return "SEND_STATE_INDETERMINATE", None
    try:
        outcome, response = supervisor.await_response(
            command_id, timeout_seconds=RunBounds().startup_deadline_seconds
        )
    except Exception:  # noqa: BLE001
        return "SEND_STATE_INDETERMINATE", None
    if response is None:
        return "SEND_STATE_INDETERMINATE", None
    if response.get("success") is False:
        # Written to Pi, and Pi itself declined it -- a systematic runtime
        # refusal, never a dispatch to a model.
        return "CONFIRMED_NOT_SENT", "PROMPT_REFUSED_BY_RUNTIME"
    return "CONFIRMED_SENT", None


def _fresh_command_id() -> str:
    import secrets

    return secrets.token_hex(8)


def _turn_deadline_seconds() -> float:
    from ar2.supervisor import RunBounds

    return RunBounds().turn_deadline_seconds


def _closure_phase(
    *, ports: Cfg1RunPorts, observations: dict[str, Any], state: _RunState
) -> None:
    """L21-L27, in the fixed order, skipping only never-created resources.

    Never skipped because an earlier closure step failed: each step's own
    outcome is recorded and the ladder continues, exactly as Sec. 18's
    dependency notes require.
    """
    from . import config_issuance
    from . import run_workspace as workspace_module

    # ---------------- L21 RUNTIME TEARDOWN ----------------
    if state.supervisor is not None and getattr(state.supervisor, "process", None) is not None:
        try:
            record = state.supervisor.shutdown()
        except Exception:  # noqa: BLE001
            record = {}
        observations["runtime_exit_observed"] = record.get("exit_status_observed") is not None
        stdout_state = {}
        try:
            stdout_state = state.supervisor.stdout_state()
        except Exception:  # noqa: BLE001
            stdout_state = {}
        stderr_state = {}
        try:
            stderr_state = state.supervisor.stderr_snapshot()
        except Exception:  # noqa: BLE001
            stderr_state = {}
        observations["runtime_transport_eof_observed"] = bool(
            stdout_state.get("eof") and stderr_state.get("eof")
        )

    # ---------------- L22 PHI-5 BROKER COUNTS ----------------
    if state.broker is not None:
        try:
            counts = state.broker.diagnostics_counts()
            observations["broker_recorded_activity_available"] = True
            observations["broker_recorded_read_operation_count"] = int(counts["read_operations"])
            observations["broker_recorded_edit_operation_count"] = int(counts["edit_operations"])
            observations["broker_recorded_edited_path_count"] = int(counts["edited_paths"])
            observations["broker_recorded_refusal_count"] = int(counts["refusals"])
        except Exception:  # noqa: BLE001
            observations["broker_recorded_activity_available"] = False

    # ---------------- L23 BROKER SHUTDOWN ----------------
    if observations["broker_resource_created"]:
        try:
            lifecycle = state.broker.shutdown_for_cfg1()
        except Exception:  # noqa: BLE001
            lifecycle = {}
        observations["broker_state_closed"] = lifecycle.get("state_reached") == "CLOSED"
        observations["broker_pending_unreaped_zero"] = (
            lifecycle.get("pending_operations_unreaped") == 0
        )
        observations["broker_worker_terminated_or_absent"] = bool(
            lifecycle.get("worker_termination_observed", True)
        )

    # ---------------- L24 GENERATED MATERIAL SCRUB ----------------
    # Must precede any execution of model-influenced code (L26), which could
    # otherwise read the endpoint from models.json or the token from the
    # generated extension config.
    owned_root = (
        state.workspace.experiment_root if state.workspace is not None else None
    )
    if state.generated_config is not None:
        observations["generated_config_scrub_verified"] = _verified_unlink(
            state.generated_config.models_path, owned_root=owned_root
        )
        config_issuance.discard_config_issuance(state.generated_config.issuance_token)
    if state.extension is not None:
        observations["extension_binding_scrub_verified"] = _scrub_extension_binding(
            getattr(state.extension, "extension_dir", None), owned_root=owned_root
        )

    # ---------------- L25 GIT OBSERVATION #1 ----------------
    if state.workspace is not None:
        try:
            workspace_module.verify_cfg1_run_workspace(state.workspace)
            snapshot = ports.observe_repository(
                workspace_root=state.workspace.workspace_root
            )
            head_before, _tracked = workspace_module.registered_baseline(state.workspace)
            observations["git_observation_1_performed"] = True
            observations["head_moved"] = getattr(snapshot, "head", head_before) != head_before
            changed = sorted(set(getattr(snapshot, "changed_tracked_paths", ())) & CFG1_T1_FILES)
            observations["changed_tracked_paths"] = changed
            observations["untracked_path_count"] = int(
                getattr(snapshot, "untracked_path_count", 0)
            )
            observations["staged_path_count"] = int(getattr(snapshot, "staged_path_count", 0))
            observations["broker_git_cross_check_agrees"] = _broker_git_cross_check(
                observations, changed
            )
        except Exception:  # noqa: BLE001
            observations["git_observation_1_performed"] = False

    # ---------------- L26 VERIFICATION + GIT OBSERVATION #2 ----------------
    closure_proven = (
        observations["runtime_exit_observed"]
        and observations["runtime_transport_eof_observed"]
        and observations["broker_state_closed"]
        and observations["generated_config_scrub_verified"]
        and observations["extension_binding_scrub_verified"]
    )
    if observations["pre_dispatch_refusal_code"] is not None:
        observations["verification_attempted"] = False
        observations["verification_skip_reason"] = "PRE_DISPATCH_REFUSAL"
    elif not closure_proven:
        observations["verification_attempted"] = False
        observations["verification_skip_reason"] = "LIFECYCLE_UNPROVEN"
    else:
        observations["verification_attempted"] = True
        observations["verification_skip_reason"] = None
        try:
            outcome = ports.run_verification(
                workspace_root=state.workspace.workspace_root,
                args=CFG1_T1.verification_args,
            )
        except Exception:  # noqa: BLE001
            outcome = None
        if outcome is None:
            observations["verification_child_reaped_or_not_started"] = False
        else:
            observations["verification_started"] = bool(getattr(outcome, "started", False))
            observations["verification_completed"] = bool(getattr(outcome, "completed", False))
            observations["verification_timed_out"] = bool(getattr(outcome, "timed_out", False))
            observations["verification_output_limit_exceeded"] = bool(
                getattr(outcome, "output_limit_exceeded", False)
            )
            return_code = getattr(outcome, "return_code", None)
            observations["verification_return_code"] = (
                return_code if type(return_code) is int else None
            )
            observations["verification_passed"] = bool(getattr(outcome, "passed", False))
            raw_counts = getattr(outcome, "counts", {}) or {}
            observations["verification_counts"] = {
                key: int(raw_counts.get(key, 0)) for key in _VERIFICATION_COUNT_KEYS
            }
            # A child that never yielded a return code was never reaped.
            observations["verification_child_reaped_or_not_started"] = return_code is not None
        try:
            snapshot = ports.observe_repository(
                workspace_root=state.workspace.workspace_root
            )
            observations["git_observation_2_performed"] = True
            observations["post_verification_changed_tracked_paths"] = sorted(
                set(getattr(snapshot, "changed_tracked_paths", ())) & CFG1_T1_FILES
            )
        except Exception:  # noqa: BLE001
            observations["git_observation_2_performed"] = False

    # ---------------- L27 WORKSPACE REMOVAL ----------------
    if state.workspace is not None:
        try:
            workspace_module.verify_cfg1_run_workspace(state.workspace)
            observations["workspace_authority_reproved"] = True
        except Exception:  # noqa: BLE001
            observations["workspace_authority_reproved"] = False
        if observations["workspace_authority_reproved"]:
            try:
                removal = workspace_module.remove_cfg1_run_workspace(state.workspace)
                observations["workspace_removed_verified"] = bool(removal.get("removed"))
                observations["workspace_residual_file_count"] = int(
                    removal.get("residual_file_count", 0)
                )
            except Exception:  # noqa: BLE001
                observations["workspace_removed_verified"] = False
        else:
            # Ownership unprovable: the tree is NEVER deleted. A later run must
            # not delete it either -- nothing is ever removed because its name
            # looks expected.
            workspace_module.discard_cfg1_run_workspace(state.workspace)


def _broker_git_cross_check(observations: Mapping[str, Any], changed: list[str]) -> bool:
    """D-4's input: does the broker's own edit account agree with Git's truth?

    Diagnostic only, in both directions: the broker's counts are AIDO-authored,
    and Git is the authority. Disagreement never "corrects" either side -- it
    routes the run to indeterminate.
    """
    broker_edits = int(observations["broker_recorded_edited_path_count"])
    if broker_edits == 0 and changed:
        return False
    if broker_edits > 0 and not changed:
        return False
    return True


def _scrub_extension_binding(extension_dir: object, *, owned_root: object) -> bool:
    """L24's extension scrub: the FROZEN verified scrubber, contained first.

    Sec. 7.4 lists ``ar2.pi_config.scrub_generated_extension_config`` among the
    modules CFG1 reuses UNMODIFIED, so CFG1 consumes it rather than
    substituting an equivalent of its own -- it already removes the one
    token-bearing generated file and VERIFIES the removal by stat.

    CFG1 adds exactly one thing in front of it: a canonical containment proof
    that the directory lies inside this run's own owned root. The frozen
    scrubber takes a bare path, as it always has; proving ownership before
    handing it one is this package's own responsibility, not an edit to it.
    """
    import os

    if type(extension_dir) is not str or not extension_dir:
        return True
    if type(owned_root) is not str or not owned_root:
        return False
    try:
        resolved = os.path.realpath(extension_dir)
        resolved_root = os.path.realpath(owned_root)
        if os.path.commonpath([resolved, resolved_root]) != resolved_root:
            return False
        if resolved == resolved_root:
            return False
    except (OSError, ValueError):
        return False

    from ar2.pi_config import scrub_generated_extension_config

    try:
        result = scrub_generated_extension_config(resolved)
    except OSError:
        return False
    return bool(result.get("generated_binding_file_removed"))


def _verified_unlink(path: object, *, owned_root: object) -> bool:
    """Unlink one generated file and VERIFY absence. Never assumes removal.

    **Contained, not merely named.** The path must lie inside the run's own
    owned workspace root, proven by canonical containment rather than by a
    prefix comparison on the raw strings. A cleanup helper that unlinked
    whatever path it was handed is exactly the "cleanup functions accepting
    bare identifiers" shape this design refuses everywhere else -- and the two
    call sites already hold the owned root, so there is no cost to proving it.

    Returns ``True`` when nothing remains at the path afterwards, which is also
    the correct answer when the file was never written.
    """
    import os

    if type(path) is not str or not path:
        return True
    if type(owned_root) is not str or not owned_root:
        return False
    try:
        resolved = os.path.realpath(path)
        resolved_root = os.path.realpath(owned_root)
        if os.path.commonpath([resolved, resolved_root]) != resolved_root:
            return False
        if resolved == resolved_root:
            return False
        if os.path.exists(resolved):
            os.unlink(resolved)
    except (OSError, ValueError):
        return False
    return not os.path.exists(resolved)


def _bounded_version(value: object) -> str:
    """A bounded version literal, or the closed ``UNRECOGNIZED``."""
    import re

    if type(value) is str and re.fullmatch(r"[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}", value):
        return value
    return "UNRECOGNIZED"


def default_cfg1_run_ports(*, ambient_environ: Mapping[str, str]) -> Cfg1RunPorts:
    """Bind the frozen modules for the eventual, separately-authorized live run.

    **Calling this does not authorize anything.** ``CFG1-LIVE-S1`` /
    ``CFG1-LIVE-S2`` remain separately required (Sec. 14.1). This exists so the
    live wiring is reviewable now, offline, rather than being invented later.

    ``read_connection`` is the one place an endpoint or credential value is
    ever read, and it happens only when a run reaches L4 -- after every
    non-secret gate has already passed.
    """
    import os
    import secrets
    from dataclasses import dataclass as _dataclass
    from pathlib import Path

    from ar2.broker import (
        TRIGGER_AIDO_TEARDOWN,
        BrokerBinding,
        BrokerDiagnostics,
        BrokerRequestHandler,
        BrokerServer,
        RunState,
    )
    from ar2.capability import CapDefinitions, mint_capability
    from ar2.handshakes import evaluate_extension_identity, evaluate_model_identity
    from ar2.launch import build_pi_argv, resolve_runtime_identity
    from ar2.observation import observe_repository
    from ar2.pi_config import write_disposable_extension
    from ar2.supervisor import PiRpcSupervisor, RunBounds
    from ar2.verification import run_verification

    from . import run_workspace as workspace_module
    from .cfg1_pi_config import write_cfg1_pi_config
    from .environment import build_cfg1_child_environment

    def _git_executable() -> str:
        from ai_dev_orchestrator.workspace.git_adapter import resolve_git_executable

        return resolve_git_executable(workspace_root=os.getcwd())

    def _read_connection() -> tuple[str, str]:
        base_url = os.environ.get(BASE_URL_ENV_VAR_NAME)
        credential = os.environ.get(CREDENTIAL_ENV_VAR_NAME)
        if not base_url or not credential:
            raise RuntimeError("cfg1 connection values are unavailable")
        return base_url, credential

    def _observe_route(*, base_url: str, api_key: str, model_id: str):
        from qualification.i2_b300_route_observation import (
            observe_b300_route_serves_model,
        )

        # Keyword-only, exactly as the frozen observer declares it. It issues
        # ONE authenticated, non-inference `GET /models` -- no retry, no
        # fallback endpoint, no fallback model, no second request of any kind.
        return observe_b300_route_serves_model(
            base_url=base_url, api_key=api_key, model_id=model_id
        )

    def _mint_capability(*, workspace, git_executable: str):
        from ai_dev_orchestrator.workspace.git_adapter import (
            parse_ls_files_stage,
            run_fixed_git_operation,
        )

        result = run_fixed_git_operation(
            "ls_files_stage",
            git_executable=git_executable,
            workspace_root=workspace.workspace_root,
        )
        manifest = tuple(sorted(entry.path for entry in parse_ls_files_stage(result.stdout)))
        return mint_capability(
            authority=workspace_module.registered_authority(workspace),
            tracked_manifest=manifest,
            protected_patterns=CFG1_T1.protected_patterns,
            verification_witness_paths=CFG1_T1.verification_witness_paths,
            caps=CapDefinitions(),
        )

    def _build_supervisor(*, identity, extension, environment, workspace_root: str):
        return PiRpcSupervisor(
            argv=build_pi_argv(
                identity,
                extension_entry=extension.entry_path,
                tool_allowlist=TOOL_ALLOWLIST,
                provider=PROVIDER_ID,
                model=CFG1_MODEL_ID,
            ),
            cwd=workspace_root,
            environment=environment.as_launch_snapshot(),
            bounds=RunBounds(),
        )

    def _build_broker(*, capability):
        """Compose the frozen broker exactly as AR2 does, plus two adapters.

        One instance per run. ``start()`` is never called twice, the pipe name
        is never used as a lookup key, and the two adapter methods exist only
        so L22 and L23 read BOUNDED facts -- counts, closed state literals and
        bools -- instead of the broker's own diagnostic objects.
        """
        binding = BrokerBinding.mint(capability.capability_id)
        run_state = RunState(caps=capability.caps)
        handler = BrokerRequestHandler(
            sed=capability,
            run_state=run_state,
            binding=binding,
            diagnostics=BrokerDiagnostics(),
        )
        server = BrokerServer(handler)

        @_dataclass
        class _Cfg1BrokerAdapter:
            """The run's own broker handle. Ownership is this object, not a name."""

            server: object
            handler: object
            run_state: object
            token: str
            pipe_name: str
            capability_id: str

            def start(self) -> None:
                self.server.start()

            def diagnostics_counts(self) -> dict:
                """Sec. 16.2 L22: four bounded ints, from their real sources.

                The accepted-operation counts and the distinct edited-path
                count come from ``RunState``'s own consumption accounting --
                the authority the broker itself enforces budgets against --
                rather than from ``BrokerDiagnostics.as_dict()``, whose
                ``accepted``/``refused`` maps are keyed by operation name and
                by ``operation:code``.

                The refusal count sums those ``operation:code`` buckets and
                keeps ONLY the total: the codes and their reason strings are
                bounded diagnostics that never cross into a record (Sec. 21.2).
                """
                consumed = self.run_state.consumed
                diagnostics = self.handler.diagnostics
                return {
                    "read_operations": int(consumed.read_operations),
                    "edit_operations": int(consumed.edit_operations),
                    "edited_paths": len(self.run_state.mutated_paths),
                    "refusals": sum(int(count) for count in diagnostics.refused.values()),
                }

            def shutdown_for_cfg1(self) -> dict:
                lifecycle = self.server.shutdown(TRIGGER_AIDO_TEARDOWN)
                # Bounded literals and bools only. ``worker_error`` is raw text
                # and is deliberately NOT carried across this boundary.
                return {
                    "state_reached": lifecycle.get("state_reached"),
                    "pending_operations_unreaped": int(
                        lifecycle.get("pending_operations_unreaped", 0) or 0
                    ),
                    "worker_termination_observed": bool(
                        lifecycle.get("worker_termination_observed", False)
                    ),
                }

        return _Cfg1BrokerAdapter(
            server=server,
            handler=handler,
            run_state=run_state,
            token=binding.token,
            pipe_name=server.pipe_name,
            capability_id=capability.capability_id,
        )

    def _write_extension(*, owned_root: str, broker):
        """The frozen writer, over the STATIC AR2 extension sources.

        The generated ``ar2_config.ts`` is the ONLY place the broker token
        exists on disk, and it lives inside the run's own owned root -- which
        is what makes L24's verified unlink a complete scrub of it.
        """
        from ar2 import __file__ as _ar2_init

        generated = write_disposable_extension(
            owned_root,
            source_dir=str(Path(_ar2_init).resolve().parent.parent / "extension"),
            experiment_id="pi_harness_cfg1",
            pipe_name=broker.pipe_name,
            capability_id=broker.capability_id,
            token=broker.token,
        )

        @_dataclass(frozen=True)
        class _Cfg1Extension:
            entry_path: str
            extension_dir: str

        return _Cfg1Extension(
            entry_path=generated.extension_entry,
            extension_dir=generated.extension_dir,
        )

    @_dataclass(frozen=True)
    class _HandshakeVerdict:
        """Only the VERDICT crosses the boundary, never the diagnostic fields."""

        matched: bool

    def _evaluate_extension_identity(*, supervisor, extension):
        """H1: correlate ``get_commands`` by an RPC id unique to THIS run."""
        command_id = "h1-" + secrets.token_hex(8)
        supervisor.send_command({"id": command_id, "type": "get_commands"})
        _outcome, response = supervisor.await_response(
            command_id, timeout_seconds=RunBounds().startup_deadline_seconds
        )
        commands = []
        if response and isinstance(response.get("data"), dict):
            commands = response["data"].get("commands") or []
        verdict = evaluate_extension_identity(
            commands, extension_entry=extension.entry_path
        )
        return _HandshakeVerdict(
            matched=bool(response and response.get("success") and verdict.get("passed"))
        )

    def _evaluate_model_identity(*, supervisor):
        """H2: ``get_state``, returning the verdict AND the raw state document.

        The document is handed straight to Sec. 8.2's projection, which retains
        three bounded literals and reads past everything else -- including the
        ``baseUrl`` the composed model object genuinely carries.
        """
        command_id = "h2-" + secrets.token_hex(8)
        supervisor.send_command({"id": command_id, "type": "get_state"})
        _outcome, response = supervisor.await_response(
            command_id, timeout_seconds=RunBounds().startup_deadline_seconds
        )
        verdict = evaluate_model_identity(
            response, expected_provider=PROVIDER_ID, expected_model=CFG1_MODEL_ID
        )
        state_document = {}
        if response and isinstance(response.get("data"), dict):
            state_document = response["data"]
        return _HandshakeVerdict(matched=bool(verdict.get("passed"))), state_document

    return Cfg1RunPorts(
        ambient_environ=ambient_environ,
        git_executable=_git_executable,
        resolve_runtime_identity=lambda: resolve_runtime_identity(
            expected_version=PINNED_PI_VERSION
        ),
        mint_workspace=workspace_module.mint_cfg1_run_workspace,
        observe_repository=lambda *, workspace_root: observe_repository(
            git_executable=_git_executable(), workspace_root=workspace_root
        ),
        run_verification=lambda *, workspace_root, args: run_verification(
            python_executable=_python_executable(), workspace_root=workspace_root, args=args
        ),
        read_connection=_read_connection,
        observe_route=_observe_route,
        mint_capability=_mint_capability,
        write_config=lambda *, owned_root, arm_id, base_url: write_cfg1_pi_config(
            owned_root, arm_id=arm_id, base_url=base_url
        ),
        write_extension=_write_extension,
        build_environment=build_cfg1_child_environment,
        build_broker=_build_broker,
        build_supervisor=_build_supervisor,
        evaluate_extension_identity=_evaluate_extension_identity,
        evaluate_model_identity=_evaluate_model_identity,
    )


def _python_executable() -> str:
    import sys

    return sys.executable
