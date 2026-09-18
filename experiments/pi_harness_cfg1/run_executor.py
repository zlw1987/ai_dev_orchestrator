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
from .arms import (
    ARM_SHAPE,
    EXPECTED_THINKING_LEVEL,
    RUNTIME_COMPAT_SHAPES,
    RUNTIME_MODEL_REASONING_VALUES,
    RUNTIME_THINKING_LEVELS,
)
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

#: Sec. 37.4.2's fixed, non-content-bearing sentinel for a malformed
#: verification count. It is JSON-serializable (so it reaches the validator
#: rather than dying in canonicalization with the malformed object's own text
#: attached) and it is refused by ``_require_exact_int_mapping`` by
#: construction (so the record fails its own validator). It must never be a
#: number: ``0``, ``-1`` and a string like ``"unknown"`` would each be an
#: invented count wearing a different costume.
_MALFORMED_VERIFICATION_COUNT = None


def _exact_bool(value: object) -> bool:
    """Reduce one raw, port-mediated fact to a bool -- never truthiness-coerced.

    ``bool(x)`` cannot fail: it accepts any object and returns a plausible
    ``True``/``False`` even when ``x`` is a string, a list, or an arbitrary
    object -- which is exactly the "malformed but plausible" repair
    CFG1-IMPL-FU1 Finding 4 forbids for an authority- or admission-bearing
    fact. Only an already-exact ``bool`` survives; every other value becomes
    ``False``, the same fail-closed reduction already applied to
    ``lifecycle_all_closed`` in :mod:`stage_runner`.
    """
    return value if type(value) is bool else False


def _exact_count(value: object) -> int:
    """The same reduction for a non-negative, count-shaped raw fact.

    ``bool`` is explicitly excluded (Python's own ``int`` subclass), and a
    float, numeric string, negative number, or an object with a custom
    ``__int__``/``__index__`` becomes ``0`` -- the field's own documented
    minimum -- rather than a value ``int(...)`` would silently manufacture.

    **Where this is still correct, and where FU15 removed it.** It remains the
    right reduction for a count that feeds no observation claim of its own --
    the broker diagnostics, ``auto_retry_events``, the extension error count,
    and the L27 residual, each of which is separately gated by an availability
    or closure bool. It is NO LONGER applied to a repository count (Sec.
    37.4.1) or to a verification count (Sec. 37.4.2): there, the durable field
    IS the observation, so manufacturing a plausible minimum states something
    nobody observed. Those two families use an exactness predicate and a
    refusal sentinel respectively -- see :func:`_exact_repository_snapshot` and
    :data:`_MALFORMED_VERIFICATION_COUNT`. Do not reintroduce it there.
    """
    return value if (type(value) is int and value >= 0) else 0


class _MalformedRepositorySnapshot(Exception):
    """One L25/L26 repository-snapshot member failed its exactness predicate.

    Carries nothing at all -- no value, no repr, no attribute name. It exists
    only to reach the projection's own ``except`` and take the already-frozen
    not-performed branch, so no malformed object can travel any further.
    """


def _exact_repository_snapshot(snapshot: object) -> tuple[str, tuple, int, int]:
    """Sec. 37.4.1's exactness PREDICATE -- all-or-nothing, never a reducer.

    Runs over the WHOLE snapshot before any field is projected, and raises if
    any single member is malformed. The difference from a reducer is the whole
    point of Finding B1: ``_exact_count`` turned a malformed
    ``untracked_path_count`` into the durable integer ``0`` while
    ``git_observation_1_performed`` stayed ``true`` -- an invented observation.
    ``getattr(snapshot, "changed_tracked_paths", ())`` and
    ``getattr(snapshot, "head", head_before)`` did the same, one becoming a
    durable "nothing changed" and the other a durable ``head_moved = false``.

    An OBSERVED exact zero is unaffected and still records as performed with
    ``0`` -- a change that made observed zeros unrepresentable would be a
    different falsehood, not a fix (T-159).

    This is the shape FU2 already accepted one family over:
    ``broker_recorded_activity_available`` is exactly "every one of the raw
    facts was an exact non-negative int", and ``git_observation_1_performed``
    is the repository family's already-frozen equivalent -- so no schema field,
    no record kind and no new availability flag is added, and Sec. 12.2's D-4
    predicate already gates on ``git_observation_1_performed is True``.
    """
    missing = object()

    head = getattr(snapshot, "head", missing)
    if type(head) is not str:
        raise _MalformedRepositorySnapshot

    changed = getattr(snapshot, "changed_tracked_paths", missing)
    # A str is iterable and would silently decompose into characters, so the
    # exact container types are named rather than "anything iterable".
    if type(changed) not in (tuple, list):
        raise _MalformedRepositorySnapshot
    changed = tuple(changed)
    for member in changed:
        if type(member) is not str:
            raise _MalformedRepositorySnapshot

    counts = []
    for name in ("untracked_path_count", "staged_path_count"):
        value = getattr(snapshot, name, missing)
        # ``type(...) is int`` refuses bool (an int subclass), float, a numeric
        # string, and any object with ``__int__``/``__index__``; the range
        # check refuses a negative. Nothing is coerced, defaulted or repaired.
        if type(value) is not int or value < 0:
            raise _MalformedRepositorySnapshot
        counts.append(value)

    return head, changed, counts[0], counts[1]


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
    ``write_config(workspace=..., arm_id=..., base_url=...)``
        a :class:`~pi_harness_cfg1.cfg1_pi_config.GeneratedCfg1Config`, written
        BESIDE the repository child, never inside it -- ``workspace`` is the
        run's own ``Cfg1RunWorkspace`` ownership handle, never a bare path
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
        a ``PiRpcSupervisor``-shaped object, constructed with the H2
        expectations bound ONCE from the frozen ``PROVIDER_ID`` /
        ``CFG1_MODEL_ID`` -- the same constants its argv is built from -- and
        providing ``probe_runtime_capabilities()`` (CFG1-L16-FU2)
    ``evaluate_extension_identity(supervisor=..., extension=...)``
        ``.matched``

    The frozen ``ar2`` H1 handshake returns a bounded DICT carrying a
    ``passed`` verdict, so :func:`default_cfg1_run_ports` adapts it to this
    ``.matched`` shape rather than restating the evaluation. Only the verdict
    crosses the boundary (Sec. 21.2).

    **There is deliberately no H2 / ``get_state`` port** (CFG1-L16-FU2,
    R-CFG1-2). L16 calls the one parameterless AR2 probe directly on the run
    state's OWN supervisor -- the object L14 launched -- and receives exactly
    one ``bool`` and three closed literals. No state document, response, facts
    or verdict can enter L16 through a port, because no port supplies one.
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
    #: The exact object L14 built and launched. L16 refuses any other.
    l14_launched_supervisor: Any = None
    capability: Any = None
    safety: Any = None
    console_codes: list[str] = field(default_factory=list)


def observe_l16_runtime_capabilities(state: _RunState, *, arm_id: str) -> dict[str, Any]:
    """Sec. 8.2's four L16 facts, from the run's OWN supervisor. Raises on refusal.

    CFG1-L16-FU2 (R-CFG1-1..3). This replaces the former state-document
    projection. There is deliberately NO parameter through which facts, a
    literal, a verdict, a response, a state document, or any supervisor other
    than the run state's own can enter: the facts are obtained HERE, by calling
    the one parameterless AR2 probe on ``state.supervisor`` -- which must be the
    identical object L14 launched -- and are type-checked and returned in the
    same function. ``arm_id`` selects only which frozen declared shape the
    unchanged manipulation predicate compares against.

    The probe reduces the ONE AIDO-minted, correlated ``get_state`` response
    to one ``bool`` and three closed literals BEFORE AR2's reasoning drop
    removes ``data.model.reasoning`` (the defect this replaces could never
    observe it). The facts stay ``runtime_reported_*`` UNTRUSTED CLAIMS.

    A probe that raises, a supervisor that is not the L14 object, and a return
    that is not exactly ``(bool, str, str, str)`` drawn from the closed domains
    all refuse with the EXISTING ``RUNTIME_CORRELATION_FAILED`` at ``L16``;
    nothing raw is formatted or retained.
    """
    supervisor = state.supervisor
    if supervisor is None or supervisor is not state.l14_launched_supervisor:
        raise _PreDispatchRefusal("RUNTIME_CORRELATION_FAILED", "L16")
    try:
        result = supervisor.probe_runtime_capabilities()
    except Exception:  # noqa: BLE001 - reduced HERE; no raw text escapes
        raise _PreDispatchRefusal("RUNTIME_CORRELATION_FAILED", "L16") from None
    if type(result) is not tuple or len(result) != 4:
        raise _PreDispatchRefusal("RUNTIME_CORRELATION_FAILED", "L16")
    h2, reasoning, compat_shape, thinking_level = result
    if not (
        type(h2) is bool
        and type(reasoning) is str
        and reasoning in RUNTIME_MODEL_REASONING_VALUES
        and type(compat_shape) is str
        and compat_shape in RUNTIME_COMPAT_SHAPES
        and type(thinking_level) is str
        and thinking_level in RUNTIME_THINKING_LEVELS
    ):
        raise _PreDispatchRefusal("RUNTIME_CORRELATION_FAILED", "L16")
    return {
        "h2_provider_model_identity_matched": h2,
        "runtime_reported_compat_shape": compat_shape,
        "runtime_reported_model_reasoning": reasoning,
        "runtime_reported_thinking_level": thinking_level,
        # The frozen predicate, unchanged.
        "manipulation_check_agrees": (
            compat_shape == ARM_SHAPE[arm_id]
            and reasoning == "TRUE"
            and thinking_level == EXPECTED_THINKING_LEVEL
        ),
    }


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
    observations["route_reachable"] = _exact_bool(getattr(route, "reachable", False))
    observations["route_configured_model_served"] = _exact_bool(
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
            workspace=state.workspace,
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
            workspace=state.workspace,
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
    state.l14_launched_supervisor = state.supervisor

    # ---------------- L15 RPC CORRELATION + H1 ----------------
    try:
        h1 = ports.evaluate_extension_identity(
            supervisor=state.supervisor, extension=state.extension
        )
    except Exception:  # noqa: BLE001
        raise _PreDispatchRefusal("RUNTIME_CORRELATION_FAILED", "L15") from None
    observations["h1_extension_identity_matched"] = _exact_bool(getattr(h1, "matched", False))
    if not observations["h1_extension_identity_matched"]:
        raise _PreDispatchRefusal("H1_MISMATCH", "L15")

    # ---------------- L16 H2 + MANIPULATION CHECK ----------------
    # CFG1-L16-FU2: the ONE get_state is the AR2 probe's own, on this run's
    # own supervisor; the four facts are reduced before AR2's reasoning drop.
    observations.update(
        observe_l16_runtime_capabilities(state, arm_id=admission.arm_id)
    )
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
    raw_auto_retry_events = getattr(state.supervisor.activity, "auto_retry_events", 0)
    auto_retry_events_exact = type(raw_auto_retry_events) is int and raw_auto_retry_events >= 0
    observations["auto_retry_events"] = _exact_count(raw_auto_retry_events)
    # CFG1-IMPL-FU2 Finding 3: a malformed raw ``auto_retry_events`` must not
    # be laundered into a plausible "0 retries happened" that lets
    # `classify_cfg1_run` row 10 fall through as if no retry evidence problem
    # existed. Reusing `stop_reasons_available` -- the sibling "is this run's
    # provider-activity evidence trustworthy" flag already gating that same
    # row -- routes a malformed count to the existing
    # ``INDETERMINATE_PROVIDER`` classification rather than inventing a new
    # field for it.
    observations["stop_reasons_available"] = available and auto_retry_events_exact
    observations["stop_reason_counts"] = counts
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
        observations["runtime_transport_eof_observed"] = _exact_bool(
            stdout_state.get("eof")
        ) and _exact_bool(stderr_state.get("eof"))

    # ---------------- L22 PHI-5 BROKER COUNTS ----------------
    if state.broker is not None:
        try:
            counts = state.broker.diagnostics_counts()
            raw_read = counts["read_operations"]
            raw_edit = counts["edit_operations"]
            raw_edited = counts["edited_paths"]
            raw_refusals = counts["refusals"]
            # CFG1-IMPL-FU2 Finding 3: "available" must mean every one of the
            # four raw facts was an exact, non-negative int -- not merely that
            # the dict access itself did not raise. A dict that came back with
            # a malformed VALUE (as opposed to a missing key or an exception)
            # must not read as available while silently reporting a
            # manufactured ``0`` for the field that was actually malformed;
            # `classify_cfg1_run` row 5 routes on this exact flag.
            observations["broker_recorded_activity_available"] = all(
                type(value) is int and value >= 0
                for value in (raw_read, raw_edit, raw_edited, raw_refusals)
            )
            observations["broker_recorded_read_operation_count"] = _exact_count(raw_read)
            observations["broker_recorded_edit_operation_count"] = _exact_count(raw_edit)
            observations["broker_recorded_edited_path_count"] = _exact_count(raw_edited)
            observations["broker_recorded_refusal_count"] = _exact_count(raw_refusals)
        except Exception:  # noqa: BLE001
            observations["broker_recorded_activity_available"] = False

    # ---------------- L23 BROKER SHUTDOWN ----------------
    if observations["broker_resource_created"]:
        try:
            lifecycle = state.broker.shutdown_for_cfg1()
        except Exception:  # noqa: BLE001
            lifecycle = {}
        observations["broker_state_closed"] = lifecycle.get("state_reached") == "CLOSED"
        pending_unreaped = lifecycle.get("pending_operations_unreaped")
        observations["broker_pending_unreaped_zero"] = (
            type(pending_unreaped) is int and pending_unreaped == 0
        )
        observations["broker_worker_terminated_or_absent"] = _exact_bool(
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
        # CFG1-IMPL-FU2 Finding 2: the scrub target is the VERIFIED issuance
        # record's own ``models_path``, never ``state.generated_config.
        # models_path`` -- that object is a caller-mutable plain attribute
        # holder, and a genuine ``issuance_token`` paired with a substituted
        # ``models_path`` must not be able to steer L24 into unlinking an
        # arbitrary path. A token that fails re-verification (already
        # discarded, workspace mismatch, redirected, digest mismatch) yields
        # no scrub target at all rather than falling back to the unverified
        # field, and the scrub is reported unverified.
        try:
            issuance_record = config_issuance.verify_config_issuance(
                token=state.generated_config.issuance_token, workspace=state.workspace
            )
        except config_issuance.ConfigIssuanceError:
            issuance_record = None
        if issuance_record is None:
            observations["generated_config_scrub_verified"] = False
        else:
            observations["generated_config_scrub_verified"] = _verified_unlink(
                issuance_record.models_path,
                owned_root=owned_root,
                expected_identity=issuance_record.models_identity,
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
            # Sec. 37.4.1 (FU15 Finding B1). The exactness PREDICATE runs over
            # the whole snapshot BEFORE a single field is projected, and a
            # single malformed member drives the entire observation to the
            # already-frozen not-performed shape by raising into the same
            # ``except`` below. Nothing here reduces, coerces or defaults: a
            # reducer's job is to manufacture a plausible value, and that is
            # precisely the defect -- a durable `0` presented as an observed
            # count, or a durable empty list meaning "nothing changed", or a
            # missing head meaning "HEAD did not move".
            head, changed_paths, untracked, staged = _exact_repository_snapshot(snapshot)
            observations["git_observation_1_performed"] = True
            observations["head_moved"] = head != head_before
            changed = sorted(set(changed_paths) & CFG1_T1_FILES)
            observations["changed_tracked_paths"] = changed
            observations["untracked_path_count"] = untracked
            observations["staged_path_count"] = staged
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
            observations["verification_started"] = _exact_bool(getattr(outcome, "started", False))
            observations["verification_completed"] = _exact_bool(
                getattr(outcome, "completed", False)
            )
            observations["verification_timed_out"] = _exact_bool(
                getattr(outcome, "timed_out", False)
            )
            observations["verification_output_limit_exceeded"] = _exact_bool(
                getattr(outcome, "output_limit_exceeded", False)
            )
            return_code = getattr(outcome, "return_code", None)
            observations["verification_return_code"] = (
                return_code if type(return_code) is int else None
            )
            raw_counts = getattr(outcome, "counts", {}) or {}
            # Sec. 37.4.2 (FU15 Finding B2). Verification demonstrably RAN, so
            # Sec. 37.4.1's not-performed shape cannot be reused here -- that
            # would replace one false statement with another -- and inventing a
            # new availability flag is exactly the schema growth this phase
            # discourages. So a malformed member becomes a fixed,
            # NON-CONTENT-BEARING sentinel that `_require_exact_int_mapping`
            # refuses by construction: the run record fails its OWN validator
            # at L29 step 6, taking the already-frozen Sec. 18 row 15 path --
            # refusal record with `RECORD_INVARIANT`, `EVIDENCE_REFUSED` if
            # that artifact was written, and an unconditional stage halt. No
            # count is invented, and no `verification_passed: true` survives.
            #
            # The sentinel is deliberately NOT the malformed value itself:
            # substituting a fixed `None` keeps the containment guarantee that
            # no foreign object reaches a payload, a serializer, or a console
            # sink, while still guaranteeing refusal (T-161).
            projected_counts: dict[str, object] = {}
            verification_counts_all_exact = True
            for key in _VERIFICATION_COUNT_KEYS:
                value = raw_counts.get(key, _MALFORMED_VERIFICATION_COUNT)
                if type(value) is int and value >= 0:
                    projected_counts[key] = value
                else:
                    projected_counts[key] = _MALFORMED_VERIFICATION_COUNT
                    verification_counts_all_exact = False
            observations["verification_counts"] = projected_counts
            # CFG1-IMPL-FU2 Finding 3: a malformed verification count must
            # never STRENGTHEN a passing verification claim. Folding
            # verification_counts' own exactness into `verification_passed`
            # means a malformed count can only ever pull a claim of "passed"
            # back to "not proven passed" -- it can never turn a genuine
            # failure into a false pass either, since `passed` is already
            # ANDed here rather than substituted.
            observations["verification_passed"] = (
                _exact_bool(getattr(outcome, "passed", False))
                and verification_counts_all_exact
            )
            # A child that never yielded a return code was never reaped.
            observations["verification_child_reaped_or_not_started"] = return_code is not None
        try:
            snapshot = ports.observe_repository(
                workspace_root=state.workspace.workspace_root
            )
            # Observation #2 reads the SAME snapshot type through the SAME
            # port, so Sec. 37.4.1's own reasoning applies verbatim: a
            # missing or malformed ``changed_tracked_paths`` must not become a
            # durable "nothing changed" while ``git_observation_2_performed``
            # stays true. The same predicate, the same all-or-nothing
            # disposition, and the same already-frozen not-performed shape --
            # no schema field and no new flag.
            _head, changed_paths, _untracked, _staged = _exact_repository_snapshot(
                snapshot
            )
            observations["git_observation_2_performed"] = True
            observations["post_verification_changed_tracked_paths"] = sorted(
                set(changed_paths) & CFG1_T1_FILES
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
                raw_residual = removal.get("residual_file_count", 0)
                residual_exact = type(raw_residual) is int and raw_residual >= 0
                observations["workspace_residual_file_count"] = _exact_count(raw_residual)
                # CFG1-IMPL-FU2 Finding 3: `compute_lifecycle_closure` treats
                # `workspace_residual_file_count == 0` (with `type(...) is
                # int`, always true after `_exact_count`) as one half of L27's
                # closure proof. A malformed raw residual count laundered to
                # `0` would satisfy that check despite the true residual state
                # being UNKNOWN, not proven zero -- so a malformed residual
                # count forces `workspace_removed_verified` false regardless
                # of the frozen remover's own `removed` flag, which is the
                # OTHER half of the same closure proof and already gates L27.
                observations["workspace_removed_verified"] = (
                    _exact_bool(removal.get("removed")) and residual_exact
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
    broker_edits = _exact_count(observations["broker_recorded_edited_path_count"])
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
    return _exact_bool(result.get("generated_binding_file_removed"))


def _verified_unlink(
    path: object, *, owned_root: object, expected_identity: object = None
) -> bool:
    """L24's PRECISE child authority. Identity-bound, never name-bound.

    **Contained, not merely named.** The path must lie inside the run's own
    owned workspace root, proven by canonical containment rather than by a
    prefix comparison on the raw strings. A cleanup helper that unlinked
    whatever path it was handed is exactly the "cleanup functions accepting
    bare identifiers" shape this design refuses everywhere else -- and the call
    site already holds the owned root, so there is no cost to proving it.

    **Sec. 37.3.2a, and why containment alone is not enough (FU15).** L27's
    namespace teardown may truthfully remove a descendant CFG1 did not create,
    because it re-proves authority over the whole owned root. An individual
    sensitive-file operation may not: "somewhere inside the root, under the
    right name" would let a same-name replacement planted between issuance and
    L24 be deleted as though it were the generated file. So when the caller
    supplies the identity the issuance record bound, the target is re-opened
    without following a redirect, ``os.stat(fd)`` is compared against that
    identity, and disposal happens THROUGH THAT SAME HANDLE. A mismatch deletes
    nothing at all and reports the scrub unverified; there is no pathname
    fallback, and the identity check is never skipped once bound.

    Returns ``True`` when nothing the issuance authorized remains, which is
    also the correct answer when the file was never written.
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
    except (OSError, ValueError):
        return False

    if expected_identity is not None:
        from . import win_config_authority as win

        return win.identity_bound_unlink(path, expected_identity=expected_identity)

    try:
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
    from ar2.handshakes import evaluate_extension_identity
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
        # R-40: the argv's provider/model and the probe's H2 expectations come
        # from the SAME frozen module constants -- never a literal, the
        # environment, a config file, or anything runtime-derived.
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
            expected_provider=PROVIDER_ID,
            expected_model=CFG1_MODEL_ID,
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
                """Sec. 16.2 L22: four RAW facts, from their real sources.

                CFG1-IMPL-FU2 Finding 3: this adapter must NOT reduce
                ``read_operations``/``edit_operations``/``refusals`` with
                ``_exact_count`` here -- doing so would launder a malformed
                frozen-broker value into a manufactured, plausible ``0``
                BEFORE L22's own exact-type check ever sees it, defeating the
                very check that is supposed to catch it (the same class of
                defect the adapter's ``pending_operations_unreaped`` field
                had). Every raw value is reduced at the step that catches it
                (Sec. 21.1), which is L22 in ``_closure_phase``, not here.

                ``edited_paths`` is exempt: ``len(...)`` on a real ``list``
                object is unconditionally an exact, non-negative ``int`` by
                construction, so there is nothing to launder.

                The refusal count sums those ``operation:code`` buckets and
                keeps ONLY the total -- but the sum itself is reported ONLY
                when every individual bucket is already an exact, non-negative
                int; if any bucket is malformed the raw, unsummed value list is
                returned instead, which is itself not an ``int`` and therefore
                fails L22's exact-type check rather than silently contributing
                a partial, manufactured total.
                """
                consumed = self.run_state.consumed
                diagnostics = self.handler.diagnostics
                refusal_values = list(diagnostics.refused.values())
                refusals_all_exact = all(
                    type(value) is int and value >= 0 for value in refusal_values
                )
                return {
                    "read_operations": consumed.read_operations,
                    "edit_operations": consumed.edit_operations,
                    "edited_paths": len(self.run_state.mutated_paths),
                    "refusals": sum(refusal_values) if refusals_all_exact else refusal_values,
                }

            def shutdown_for_cfg1(self) -> dict:
                lifecycle = self.server.shutdown(TRIGGER_AIDO_TEARDOWN)
                # Bounded literals only. ``worker_error`` is raw text and is
                # deliberately NOT carried across this boundary.
                #
                # CFG1-IMPL-FU2 Finding 3: ``pending_operations_unreaped`` is
                # returned RAW -- never pre-reduced with ``_exact_count`` --
                # because L23's own consumption check
                # (``type(pending_unreaped) is int and pending_unreaped == 0``)
                # is exactly the exact-type-and-value proof this design relies
                # on to tell an OBSERVED exact zero apart from a malformed
                # value. Reducing it here first would manufacture a plausible
                # ``0`` that check could no longer tell apart from the real
                # thing -- the defect this correction closes. There is
                # deliberately no ``.get(..., 0)`` default either: a MISSING
                # key becomes ``None``, which the same check also correctly
                # treats as not-proven-zero, rather than a manufactured zero
                # for an absent fact.
                #
                # ``worker_termination_observed`` keeps its existing
                # ``_exact_bool`` reduction here: unlike a count whose
                # observed-zero and malformed-defaulted-zero are otherwise
                # indistinguishable, ``_exact_bool``'s only two outcomes are
                # "proven true" and "not proven true" -- and "not proven true"
                # is already the correct, fail-closed answer for a malformed
                # value, so pre-reducing it here does not launder anything.
                return {
                    "state_reached": lifecycle.get("state_reached"),
                    "pending_operations_unreaped": lifecycle.get(
                        "pending_operations_unreaped"
                    ),
                    "worker_termination_observed": _exact_bool(
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
            matched=bool(response)
            and _exact_bool(response.get("success"))
            and _exact_bool(verdict.get("passed"))
        )

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
        write_config=lambda *, workspace, arm_id, base_url: write_cfg1_pi_config(
            workspace, arm_id=arm_id, base_url=base_url
        ),
        write_extension=_write_extension,
        build_environment=build_cfg1_child_environment,
        build_broker=_build_broker,
        build_supervisor=_build_supervisor,
        evaluate_extension_identity=_evaluate_extension_identity,
    )


def _python_executable() -> str:
    import sys

    return sys.executable


# ---------------------------------------------------------------------------
# CFG1-IMPL-FU1 Finding 1 -- the genuine executor, mint-registry-unforgeable
# ---------------------------------------------------------------------------
#
# CFG1-IMPL-FU2 Finding 1 correction: FU1's registry stored only TOKEN
# MEMBERSHIP (``token -> True``), so a genuine token copied onto a
# ``Cfg1GenuineRunExecutor`` built with a SUBSTITUTED ``call`` still passed
# both ``__post_init__`` and ``invoke``'s re-check -- neither ever compared
# the presented callable against the one this module actually minted for that
# token. The registry now binds ``token -> the exact callable object minted
# for it``, and every check below is an IDENTITY comparison (``is``, never
# ``==``) against that record, re-read fresh at construction AND at every
# ``invoke`` call. A token whose recorded callable does not match the
# instance's own ``call`` -- whether because the instance was hand-built with
# a substituted callable, or because ``call`` was reassigned after mint via
# ``object.__setattr__`` (frozen only blocks ordinary attribute assignment,
# never that), or because the instance was rebuilt via ``dataclasses.replace``
# -- is refused, never invoked.

#: token -> the exact callable minted for it. Process-local, in-memory only,
#: never persisted, never an evidence field.
_GENUINE_RUN_EXECUTOR_MINTED: dict[str, Callable[[Cfg1RunAdmission], Cfg1RunOutcome]] = {}

_GENUINE_RUN_EXECUTOR_TOKEN_BYTES = 16


class Cfg1GenuineRunExecutorError(Exception):
    """A genuine run-executor binding could not be established or re-proven."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(f"cfg1 genuine run executor refused: {reason_code}")
        self.reason_code = reason_code


def _genuine_executor_binding_holds(token: object, call: object) -> bool:
    """The ONE mechanical proof: this exact token maps to this exact callable.

    An identity comparison, never equality: two distinct callables that
    happen to compare equal (or a mock configured to do so) must not pass.
    """
    if type(token) is not str or token not in _GENUINE_RUN_EXECUTOR_MINTED:
        return False
    return _GENUINE_RUN_EXECUTOR_MINTED[token] is call


@dataclass(frozen=True)
class Cfg1GenuineRunExecutor:
    """The ONE unforgeable handle to the genuine, mechanically-bound L1-L28
    executor. Valid by construction and unforgeable by API.

    ``bind_genuine_cfg1_run_executor`` is the ONLY supported path to a genuine
    instance: ``__post_init__`` refuses any instance whose ``(token, call)``
    pair does not match the mint registry EXACTLY -- by identity, not merely
    by the token's membership -- so a caller cannot construct one pairing a
    genuine token with a substitute callable of its own (CFG1-IMPL-FU2
    Finding 1). The bound callable is ``field(repr=False)`` and is invoked
    only through :meth:`invoke`, never exposed as a bare attribute a caller
    could detach and pass elsewhere.
    """

    token: str = field(repr=False)
    call: object = field(repr=False)

    def __post_init__(self) -> None:
        if not _genuine_executor_binding_holds(self.token, self.call):
            raise Cfg1GenuineRunExecutorError("EXECUTOR_BINDING_UNPROVEN")

    def invoke(self, admission: Cfg1RunAdmission) -> Cfg1RunOutcome:
        """Re-proves ``(token, call)`` still matches the mint, THEN invokes.

        Re-checked on EVERY call, not merely at construction -- so a ``call``
        reassigned after mint via ``object.__setattr__`` (which ``frozen=True``
        does not prevent) is caught here even when it slipped past
        ``__post_init__`` at a time it was still genuine.
        """
        if not _genuine_executor_binding_holds(self.token, self.call):
            raise Cfg1GenuineRunExecutorError("EXECUTOR_BINDING_UNPROVEN")
        return self.call(admission)

    def __repr__(self) -> str:  # noqa: D105 - the bound callable is never rendered
        return f"{type(self).__name__}(<bound>)"


def bind_genuine_cfg1_run_executor() -> Cfg1GenuineRunExecutor:
    """Mint the ONE genuine, mechanically-bound L1-L28 executor handle.

    Closes over :func:`execute_cfg1_run` and
    ``default_cfg1_run_ports(ambient_environ=os.environ)`` itself -- there is
    no parameter here through which a caller could substitute ports, an
    outcome, or the underlying execute function. Calling this does not
    authorize anything by itself (``CFG1-LIVE-S1``/``-LIVE-S2`` remain
    separately required, Sec. 14.1); it exists so :func:`stage_runner.
    run_cfg1_stage` can bind the genuine executor mechanically, with nothing
    left for a caller holding only a stage-output authority to substitute
    (CFG1-IMPL-FU1 Finding 1, CFG1-IMPL-FU2 Finding 1).
    """
    import os
    import secrets

    ports = default_cfg1_run_ports(ambient_environ=os.environ)

    def _call(admission: Cfg1RunAdmission) -> Cfg1RunOutcome:
        return execute_cfg1_run(admission, ports=ports)

    token = secrets.token_hex(_GENUINE_RUN_EXECUTOR_TOKEN_BYTES)
    if token in _GENUINE_RUN_EXECUTOR_MINTED:  # pragma: no cover - a 128-bit collision
        raise Cfg1GenuineRunExecutorError("EXECUTOR_TOKEN_ALREADY_REGISTERED")
    _GENUINE_RUN_EXECUTOR_MINTED[token] = _call
    return Cfg1GenuineRunExecutor(token=token, call=_call)
