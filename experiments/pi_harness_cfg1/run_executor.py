"""L1-L28 for one admitted ordinal. Port-mediated, total, and fail-closed.

Design Sec. 16.2 (the step table), Sec. 17 (resource ownership), Sec. 18 (the
partial-failure table), Sec. 20 (evidence-versus-cleanup ordering), Sec. 21
(containment), as corrected by ``PHASE_5F3B_HARNESS_CFG1_L1_BOUNDARY_FU1_DESIGN.md``
(R6) and ``..._OC3_AMEND1_DESIGN.md`` (AMEND1).

**Ports, not imports, at the boundary.** Every live-resource step is reached
through one field of :class:`Cfg1RunPorts`, so the whole state machine is
exercisable offline against synthetic doubles (T-11) without ever launching Pi,
opening a socket, reading a credential, or contacting a model.
:func:`default_cfg1_run_ports` binds the frozen modules for the eventual,
separately-authorized live phase; importing THIS module does not import them.

**FU1 -- the first Node/Pi/JavaScript execution is L14.** L1 runs the ONE
canonical static Pi identity proof (:func:`pi_identity.prove_pi_identity`,
the same function object the pre-consumption gate calls), from scratch. It
starts no process: there is no ``--version`` probe and no port whose genuine
binding executes Node or Pi before L14. L14 re-walks all 20 seams and
re-proves the package-root and ``node.exe`` identities immediately before
``launch()``, with nothing that reads the Pi tree between that proof and
``Popen``.

**Attribution is the executor's own (FU1, R6 Sec. 9).** One monotonic step
cursor is advanced at each step's entry, before its first side effect, and
``refused_at_step`` is always the cursor. An unexpected raise before dispatch
is ``UNEXPECTED_STEP_FAILURE`` at the cursor (REFUSAL mode); after the
dispatch write-ahead, or at L19/L20, it is ``unexpected_failure_step`` and no
refusal (POST_DISPATCH_UNEXPECTED mode). Nothing about an exception is read.

**Closure always runs**, in the fixed order L21->L27, after the first
resource-creating step -- skipping only steps whose resource was never created,
and never skipped because an earlier closure step failed. L27's obligation is
decided by the write-ahead workspace mint state W, never by a path.

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

from . import extension_pins as _extension_pins  # noqa: F401 - audited lineage (G4/G5)
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
from .cfg1_extension import Cfg1ExtensionError
from .cfg1_pi_config import Cfg1PiConfigError
from .fixture import CFG1_T1, CFG1_T1_FILES
from .identity import (
    BASE_URL_ENV_VAR_NAME,
    CFG1_MODEL_ID,
    CREDENTIAL_ENV_VAR_NAME,
    PROVIDER_ID,
    TOOL_ALLOWLIST,
)
from .lifecycle import (
    WORKSPACE_MINT_ATTEMPTED_NO_AUTHORITY,
    WORKSPACE_MINT_AUTHORITY_RETURNED,
    WORKSPACE_MINT_NOT_ATTEMPTED,
)
from .pi_identity import (
    PiProofLeaves,
    genuine_pi_proof_leaves,
    prove_pi_identity,
    reprove_pi_identity_for_launch,
    require_pi_proof_result_shape,
)
from .preflight import base_url_compat_detection_clear
from .run_contract import Cfg1RunAdmission, Cfg1RunOutcome

_STOP_REASON_KEYS = ("stop", "length", "toolUse", "error", "aborted", "other")
_VERIFICATION_COUNT_KEYS = ("passed", "failed", "error")

#: R6 Sec. 9.2: the closed code of an unexpected raise before dispatch.
UNEXPECTED_STEP_FAILURE = "UNEXPECTED_STEP_FAILURE"

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

    **FU1 (AMEND1 AMD-1/AMD-6): there is NO port that executes Node or Pi
    before L14.** The former ``resolve_runtime_identity`` port (genuinely bound
    to ``ar2.launch.resolve_runtime_identity``, which ran ``node cli.js
    --version`` with the inherited environment) is removed, not replaced.
    ``pi_proof_leaves`` supplies ONLY the static proof's leaf effects -- the
    Sec. 7.2 no-follow inspection primitive and a one-handle digest reader --
    and has no field through which a process-creating leaf could be passed.

    **The adapter surface each port must provide**, so the eventual LIVE
    binding has a contract rather than an inference:

    ``pi_proof_leaves``
        a :class:`~pi_harness_cfg1.pi_identity.PiProofLeaves`
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
        run's own ``Cfg1RunWorkspace`` ownership handle, never a bare path; a
        failure raises :class:`~pi_harness_cfg1.cfg1_pi_config.Cfg1PiConfigError`
        carrying ``endpoint_material_outstanding`` (AM-13)
    ``build_broker(capability=...)``
        ``.start()``, ``.token``, ``.pipe_name``, ``.capability_id``,
        ``.diagnostics_counts()`` -> ``{read_operations, edit_operations,
        edited_paths, refusals}``, ``.shutdown_for_cfg1()`` ->
        ``{state_reached, pending_operations_unreaped,
        worker_termination_observed}``
    ``write_extension(workspace=..., broker=...)``
        a :class:`~pi_harness_cfg1.cfg1_extension.GeneratedCfg1Extension`
        carrying ONLY an extension issuance token (AM-9) -- never a path; a
        failure raises :class:`~pi_harness_cfg1.cfg1_extension.Cfg1ExtensionError`
        carrying ``token_material_outstanding``
    ``build_supervisor(identity=..., extension=..., environment=...,
    workspace_root=...)``
        a ``PiRpcSupervisor``-shaped object, constructed with the H2
        expectations bound ONCE from the frozen ``PROVIDER_ID`` /
        ``CFG1_MODEL_ID`` -- the same constants its argv is built from -- and
        providing ``probe_runtime_capabilities()`` (CFG1-L16-FU2).
        ``identity`` is the CFG1 static identity object; ``extension.entry_path``
        comes from a FRESH extension-issuance verification at L14
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
    pi_proof_leaves: PiProofLeaves
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
    """The "nothing has happened yet" v2 observation set. Every field fail-closed.

    A run that refuses at L1 emits exactly this, with P's family and one
    refusal code and step filled in -- never a partially-optimistic record
    that implies observations nobody made. There is no ``pi_observed_version``
    and no ``pi_version_probe_attempted``: nothing before L14 executes Pi
    (AMEND1 AMD-4), and no replacement version field exists.
    """
    observations: dict[str, Any] = {
        "pi_seam_digests_match": False,
        "pi_identity_failure_code": None,
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
        "unexpected_failure_step": None,
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
        # there is nothing whose scrub could be unverified. L9 and L11 each
        # write their fact FALSE ahead of the call that could write sensitive
        # bytes (FU1 AM-13, R6 Sec. 9.2a).
        "generated_config_scrub_verified": True,
        "extension_binding_scrub_verified": True,
        "verification_child_reaped_or_not_started": True,
        "workspace_authority_reproved": False,
        "workspace_removed_verified": False,
        "workspace_residual_file_count": 0,
        # W (R6 Sec. 8): the mint port has not been called.
        "workspace_mint_state": WORKSPACE_MINT_NOT_ATTEMPTED,
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
    """Internal control flow: one closed refusal code.

    ``step`` is retained only as the raising site's own label. What is
    RECORDED is always the executor's step cursor (R6 Sec. 9.1): if the two
    ever disagreed, the cursor would win and the record would fail its own v2
    step/code table rather than lie about how far the run got.
    """

    def __init__(self, code: str, step: str) -> None:
        super().__init__(code)
        self.code = code
        self.step = step


class _Cfg1VerifiedExtension:
    """The extension view L14/L15 hand to a port: an entry path from a FRESH
    extension-issuance verification at that consumption point, and nothing
    else. Never stored; rebuilt at each consumption boundary."""

    __slots__ = ("entry_path",)

    def __init__(self, entry_path: str) -> None:
        object.__setattr__(self, "entry_path", entry_path)

    def __setattr__(self, name: str, value: object) -> None:  # noqa: D105
        raise AttributeError("the verified extension view is immutable")

    def __repr__(self) -> str:  # noqa: D105
        return f"{type(self).__name__}(<bound>)"


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
    #: R6 Sec. 9.1: the ONE step cursor, advanced at each step's entry before
    #: its first side effect, written by nothing else.
    cursor: str = "L1"
    #: R6 Sec. 9.3: set by the dispatch write-ahead, immediately before the one
    #: prompt write. Decides REFUSAL vs POST_DISPATCH_UNEXPECTED for a raise.
    dispatch_attempted: bool = False
    #: AMEND1 Sec. 10: the static identity a passing L1 produced. In memory
    #: only; consumed by L12 and L14; never durable, never rendered.
    pi_identity: Any = None
    #: OC-4 D-3: AIDO's OWN record that it called the side-effecting
    #: ``supervisor.launch()`` boundary. Written by exactly one executor line,
    #: immediately before that call; never reset; never read from a port, a
    #: supervisor or a caller; in memory only -- never an observation, a record
    #: field or a port field. L21 consults ``supervisor.process`` ONLY when this
    #: is true, so a merely-built supervisor's ``process`` claim grants nothing.
    runtime_launch_attempted: bool = False


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
    """Run L1-L28 for one admitted ordinal. TOTAL for every dispatch-phase failure.

    Every failure becomes bounded observation facts. The stage runner owns L0,
    L29 and L30; nothing here sees the stage-output authority, derives an
    output path, writes an artifact, or learns any ordinal's emission status.

    **The three exact modes (R6 Sec. 9.2, B6).** An anticipated refusal, or an
    unexpected raise before the dispatch write-ahead, is REFUSAL mode:
    ``refused_at_step`` = the cursor, with the anticipated code or
    ``UNEXPECTED_STEP_FAILURE``. An unexpected raise after the write-ahead, or
    at L19/L20, is POST_DISPATCH_UNEXPECTED mode: ``unexpected_failure_step`` =
    the cursor and no refusal fields. No exception at all is
    NO_DISPATCH_FAILURE: all three absent.
    """
    observations = _initial_observations()
    state = _RunState()
    try:
        _dispatch_phase(admission, ports=ports, observations=observations, state=state)
    except _PreDispatchRefusal as refusal:
        observations["pre_dispatch_refusal_code"] = refusal.code
        observations["refused_at_step"] = state.cursor
    except Exception:  # noqa: BLE001 - reduced HERE; nothing of it is read or kept
        state.console_codes.append("RUN_STEP_RAISED_UNEXPECTEDLY")
        if state.dispatch_attempted or state.cursor in ("L19", "L20"):
            observations["unexpected_failure_step"] = state.cursor
        else:
            observations["pre_dispatch_refusal_code"] = UNEXPECTED_STEP_FAILURE
            observations["refused_at_step"] = state.cursor

    _closure_phase(ports=ports, observations=observations, state=state)

    from .lifecycle import compute_lifecycle_closure_v2

    closed, failure_steps = compute_lifecycle_closure_v2(observations)
    observations["lifecycle_all_closed"] = closed
    observations["lifecycle_failure_steps"] = list(failure_steps)

    from qualification.safety import ArtifactSafetyContext

    return Cfg1RunOutcome(
        observations=observations,
        safety=state.safety if state.safety is not None else ArtifactSafetyContext.none_declared(),
        live_references_released=True,
        console_codes=tuple(state.console_codes),
    )


def _resolve_git_for_l1(ports: Cfg1RunPorts) -> str:
    """L1's Git resolution, after P's success commit. Unchanged in kind (OC-7).

    ``resolve_git_executable`` resolves by name and launches nothing. A port
    that raises is the anticipated Git-resolution refusal -- the ONLY meaning
    ``(L1, OFFLINE_PREFLIGHT_FAILED, pi_identity_failure_code = null)`` can have
    (AMEND1 R-S3).
    """
    try:
        return ports.git_executable()
    except Exception:  # noqa: BLE001
        raise _PreDispatchRefusal("OFFLINE_PREFLIGHT_FAILED", "L1") from None


def _is_genuine_mint(minted: object) -> bool:
    """R6 Sec. 8: exactly a 2-tuple whose first member is exactly a registered
    ``Cfg1RunWorkspace`` -- registry membership, never a path. A malformed
    return, a foreign type, or a genuine workspace inside a malformed tuple is
    never "extracted" from: W stays ``ATTEMPTED_NO_AUTHORITY``."""
    from . import run_workspace as workspace_module

    return (
        type(minted) is tuple
        and len(minted) == 2
        and type(minted[0]) is workspace_module.Cfg1RunWorkspace
        and workspace_module.workspace_is_registered(minted[0])
    )


def _dispatch_phase(
    admission: Cfg1RunAdmission,
    *,
    ports: Cfg1RunPorts,
    observations: dict[str, Any],
    state: _RunState,
) -> None:
    """L1 through L20. Raises :class:`_PreDispatchRefusal` to transfer to closure."""
    state.cursor = "L1"
    from qualification.safety import ArtifactSafetyContext

    # ---------------- L1 OFFLINE PREFLIGHT: the static Pi identity proof ----
    # The SAME function object the pre-consumption gate calls, run FROM
    # SCRATCH: nothing the gate observed can reach this call. It starts no
    # process and executes no Node, Pi or JavaScript (AMEND1 AMD-1). An
    # anticipated refusal is RETURNED; anything else raises into the catch-all
    # with nothing of P's family committed.
    result = require_pi_proof_result_shape(
        prove_pi_identity(ports.ambient_environ, leaves=ports.pi_proof_leaves)
    )
    # P's family, committed atomically: plain assignments of already-validated
    # values in which nothing can raise.
    identity = result.identity
    failure_code = result.failure_code
    observations["pi_seam_digests_match"] = result.seam_digests_match
    observations["pi_identity_failure_code"] = failure_code
    if failure_code is not None:
        observations["pre_dispatch_refusal_code"] = "OFFLINE_PREFLIGHT_FAILED"
        observations["refused_at_step"] = "L1"
        raise _PreDispatchRefusal("OFFLINE_PREFLIGHT_FAILED", "L1")
    state.pi_identity = identity

    git_executable = _resolve_git_for_l1(ports)

    # ---------------- L2 WORKSPACE MINT + POPULATE ----------------
    state.cursor = "L2"
    from . import run_workspace as workspace_module

    # W write-ahead (R6 Sec. 8): BEFORE the port is invoked, so an exception,
    # a partial tree, a malformed return or a crash inside it can never leave
    # NOT_ATTEMPTED behind. W never moves backwards.
    observations["workspace_mint_state"] = WORKSPACE_MINT_ATTEMPTED_NO_AUTHORITY
    try:
        minted = ports.mint_workspace(git_executable=git_executable)
    except Exception:  # noqa: BLE001 - an orphan root may exist and is NEVER deleted
        state.console_codes.append("WORKSPACE_MINT_PARTIAL")
        raise _PreDispatchRefusal("WORKSPACE_BASELINE_FAILED", "L2") from None
    if not _is_genuine_mint(minted):
        state.console_codes.append("WORKSPACE_MINT_PARTIAL")
        raise _PreDispatchRefusal("WORKSPACE_BASELINE_FAILED", "L2")
    state.workspace, state.built_fixture = minted
    observations["workspace_mint_state"] = WORKSPACE_MINT_AUTHORITY_RETURNED

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
    state.cursor = "L3"
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
    state.cursor = "L4"
    try:
        base_url, credential_value = ports.read_connection()
    except Exception:  # noqa: BLE001
        raise _PreDispatchRefusal("CREDENTIAL_BOUNDARY_FAILED", "L4") from None

    # ---------------- L5 SECRET CONTEXT ----------------
    state.cursor = "L5"
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
    state.cursor = "L6"
    clear = base_url_compat_detection_clear(base_url)
    observations["base_url_compat_detection_clear"] = clear
    if not clear:
        raise _PreDispatchRefusal("BASE_URL_COMPAT_DETECTION_TRIGGERED", "L6")

    # ---------------- L7 ROUTE/MODEL CHECK ----------------
    # Placed BEFORE broker/runtime creation, unlike the frozen qualification
    # controller, so a route refusal creates no live resource at all.
    state.cursor = "L7"
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
    state.cursor = "L8"
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
    state.cursor = "L9"
    # FU1 AM-13 (OC-11): the scrub fact is written FALSE immediately before the
    # one call that can put endpoint bytes on disk (category B, write-ahead).
    observations["generated_config_scrub_verified"] = False
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
    except Exception as exc:  # noqa: BLE001
        # ONE decision (R6 Sec. 9.2c-A, G6): only an EXACT ``False`` of the one
        # closed bool on the EXACT genuine error type proves no endpoint-bearing
        # object this invocation produced is known to remain. Anything else --
        # the bool ``True``, a non-bool, another exception type -- leaves it
        # ``False``. Reading that one bool is not reading the exception.
        if (
            type(exc) is Cfg1PiConfigError
            and getattr(exc, "endpoint_material_outstanding", None) is False
        ):
            observations["generated_config_scrub_verified"] = True
        raise _PreDispatchRefusal("CONFIG_GENERATION_FAILED", "L9") from None

    # ---------------- L10 BROKER CONSTRUCTION ----------------
    state.cursor = "L10"
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
    state.cursor = "L11"
    # FU1 (R6 Sec. 9.2a): written FALSE before the call, so an L11 raise can
    # never leave the shipped initial ``True`` behind.
    observations["extension_binding_scrub_verified"] = False
    try:
        state.extension = ports.write_extension(
            workspace=state.workspace, broker=state.broker
        )
    except Exception as exc:  # noqa: BLE001
        # The same one exact-type/exact-bool decision as L9: only an exact
        # ``False`` of ``token_material_outstanding`` on the exact CFG1-owned
        # type proves no token-bearing object this run wrote remains. It
        # authorizes NO deletion; it only records that a handle-bound action
        # the writer already took discharged the obligation.
        if (
            type(exc) is Cfg1ExtensionError
            and getattr(exc, "token_material_outstanding", None) is False
        ):
            observations["extension_binding_scrub_verified"] = True
        raise _PreDispatchRefusal("EXTENSION_GENERATION_FAILED", "L11") from None

    # ---------------- L12 CHILD ENVIRONMENT ----------------
    state.cursor = "L12"
    try:
        launch_environment = ports.build_environment(
            ambient_environ=ports.ambient_environ,
            node_executable=state.pi_identity.node_executable,
            generated_config=state.generated_config,
            workspace=state.workspace,
            credential_value=credential_value,
            git_executable=git_executable,
        )
    except Exception:  # noqa: BLE001
        raise _PreDispatchRefusal("CHILD_ENVIRONMENT_FAILED", "L12") from None

    # ---------------- L13 BROKER START -> READY ----------------
    state.cursor = "L13"
    try:
        state.broker.start()
    except Exception:  # noqa: BLE001
        observations["broker_resource_created"] = True
        raise _PreDispatchRefusal("BROKER_NOT_READY", "L13") from None
    observations["broker_resource_created"] = True
    observations["broker_reached_ready"] = True

    # ---------------- L14 PI LAUNCH: the FIRST Node/Pi execution ----------
    state.cursor = "L14"
    # (1) Construct the supervisor in memory: the extension entry from a FRESH
    # issuance verification, the argv from the static identity object. This
    # reads no Pi file and starts nothing.
    try:
        verified_extension = _verified_extension_view(state)
        state.supervisor = ports.build_supervisor(
            identity=state.pi_identity,
            extension=verified_extension,
            environment=launch_environment,
            workspace_root=state.workspace.workspace_root,
        )
    except Exception:  # noqa: BLE001
        raise _PreDispatchRefusal("RUNTIME_LAUNCH_FAILED", "L14") from None
    # (2) The sole pre-first-execution proof, in its fixed order: all 20 seams,
    # then the package root vs I_r, then node.exe vs I_n. Any failure -> no
    # launch() call, no process, runtime_created stays false.
    try:
        reproved = reprove_pi_identity_for_launch(
            state.pi_identity, leaves=ports.pi_proof_leaves
        )
    except Exception:  # noqa: BLE001
        reproved = False
    if reproved is not True:
        raise _PreDispatchRefusal("RUNTIME_LAUNCH_FAILED", "L14")
    # (3) launch() -> Popen. NOTHING that reads the Pi tree, resolves a name,
    # or executes anything sits between the re-proof above and this call.
    state.runtime_launch_attempted = True
    try:
        state.supervisor.launch()
    except Exception:  # noqa: BLE001
        # CreateProcess failure is L14 with no process; a process that was
        # created and then failed at start-up surfaces at L15 (AMEND1 Sec. 9).
        if getattr(state.supervisor, "process", None) is not None:
            observations["runtime_created"] = True
        raise _PreDispatchRefusal("RUNTIME_LAUNCH_FAILED", "L14") from None
    observations["runtime_created"] = True
    state.l14_launched_supervisor = state.supervisor

    # ---------------- L15 RPC CORRELATION + H1 ----------------
    state.cursor = "L15"
    try:
        h1 = ports.evaluate_extension_identity(
            supervisor=state.supervisor, extension=_verified_extension_view(state)
        )
    except Exception:  # noqa: BLE001
        raise _PreDispatchRefusal("RUNTIME_CORRELATION_FAILED", "L15") from None
    observations["h1_extension_identity_matched"] = _exact_bool(getattr(h1, "matched", False))
    if not observations["h1_extension_identity_matched"]:
        raise _PreDispatchRefusal("H1_MISMATCH", "L15")

    # ---------------- L16 H2 + MANIPULATION CHECK ----------------
    # CFG1-L16-FU2: the ONE get_state is the AR2 probe's own, on this run's
    # own supervisor; the four facts are reduced before AR2's reasoning drop.
    state.cursor = "L16"
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
    state.cursor = "L17"
    try:
        dispatch_baseline = capture_cfg1_dispatch_baseline(state.supervisor)
    except Exception:  # noqa: BLE001
        raise _PreDispatchRefusal("PRE_DISPATCH_BASELINE_FAILED", "L17") from None

    # ---------------- L18 ONE PROMPT WRITE ----------------
    state.cursor = "L18"
    refusal = _write_one_prompt(state.supervisor, observations=observations, state=state)
    if refusal is not None:
        raise _PreDispatchRefusal(refusal, "L18")

    # ---------------- L19 TURN OBSERVATION ----------------
    state.cursor = "L19"
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
    state.cursor = "L20"
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


def _verified_extension_view(state: _RunState) -> _Cfg1VerifiedExtension:
    """A fresh extension-issuance verification at THIS consumption point.

    The entry path is re-derived from the run's own workspace by the issuance
    module -- never read from a caller-mutable attribute -- and the directory
    and every static child are re-proven (identity and digest) each time.
    """
    from . import extension_issuance

    record = extension_issuance.verify_extension_issuance(
        token=getattr(state.extension, "issuance_token", None), workspace=state.workspace
    )
    return _Cfg1VerifiedExtension(record.entry_path)


def _write_one_prompt(
    supervisor, *, observations: dict[str, Any], state: _RunState
) -> str | None:
    """L18. ONE write, one correlated wait, and never a second attempt.

    "Prompt sent?" here means only whether a prompt write reached Pi's stdin.
    It is never a claim that a model request did or did not occur.

    **Write-ahead (R6 Sec. 9.3, AM-5).** Immediately before ``send_command``
    the truthful "a write may have reached Pi's stdin" state is recorded --
    ``SEND_STATE_INDETERMINATE`` and ``prompt_writes = 1`` -- and it is refined
    to ``CONFIRMED_SENT``/``CONFIRMED_NOT_SENT`` only from a correlated
    response of exactly the expected shape (a ``dict`` whose ``success`` is an
    exact ``bool``). A non-``dict`` response, or any raise after the write
    attempt, leaves the indeterminate state. Returns the refusal code, if any.
    """
    from ar2.supervisor import RunBounds

    command_id = _fresh_command_id()
    observations["dispatch_state"] = "SEND_STATE_INDETERMINATE"
    observations["prompt_writes"] = 1
    state.dispatch_attempted = True
    try:
        supervisor.send_command(
            {"id": command_id, "type": "prompt", "message": CFG1_T1.prompt}
        )
    except Exception:  # noqa: BLE001 - the write itself may have partially landed
        return None
    try:
        _outcome, response = supervisor.await_response(
            command_id, timeout_seconds=RunBounds().startup_deadline_seconds
        )
    except Exception:  # noqa: BLE001
        return None
    if type(response) is not dict:
        return None
    success = response.get("success")
    if success is False:
        # Written to Pi, and Pi itself declined it -- a systematic runtime
        # refusal, never a dispatch to a model.
        observations["dispatch_state"] = "CONFIRMED_NOT_SENT"
        return "PROMPT_REFUSED_BY_RUNTIME"
    if success is True:
        observations["dispatch_state"] = "CONFIRMED_SENT"
    return None


def _fresh_command_id() -> str:
    import secrets

    return secrets.token_hex(8)


def _turn_deadline_seconds() -> float:
    from ar2.supervisor import RunBounds

    return RunBounds().turn_deadline_seconds


def _scrub_generated_config(state: _RunState) -> bool:
    """L24 for ``models.json``: a handle-bound CONTENT scrub (AMEND2, Y6).

    The token comes from the executor's own state and is only a lookup key: it
    must name an ACTIVE config issuance whose run-workspace nonce equals this
    run's genuine workspace. No pathname is opened, re-derived or consulted, no
    path field of any public object is read, and no filesystem re-proof of the
    root is a precondition (AMD2-4). ``True`` only after the retained handle
    scrubbed the exact issued object (truncate -> flush -> ``EndOfFile == 0``)
    and every handle it had to release was released. The issuance is retired
    single-shot; a foreign same-name object is never opened, modified or
    deleted. L24 deletes no name -- L27 alone does namespace cleanup.

    OC-4 (E-8): the token READ is inside the containment. A hostile
    port-returned config object whose ``issuance_token`` accessor raises is an
    unproven scrub -- ``False`` -- and cannot skip the extension scrub or any
    later step.
    """
    from . import config_issuance

    try:
        token = getattr(state.generated_config, "issuance_token", None)
        return (
            config_issuance.scrub_config_issuance(token=token, workspace=state.workspace)
            is True
        )
    except Exception:  # noqa: BLE001 - an unproven scrub is simply False
        return False


def _scrub_extension_binding(state: _RunState) -> bool:
    """L24 for ``ar2_config.ts``: the same handle-bound content scrub.

    The exact counterpart of :func:`_scrub_generated_config` over the extension
    issuance's retained handle to the token-bearing object. Each file is
    scrubbed independently: a ``False`` on one never skips, upgrades or masks
    the other. OC-4 (E-9): the token read is inside the containment.
    """
    from . import extension_issuance

    try:
        token = getattr(state.extension, "issuance_token", None)
        return (
            extension_issuance.scrub_extension_issuance(
                token=token, workspace=state.workspace
            )
            is True
        )
    except Exception:  # noqa: BLE001 - an unproven scrub is simply False
        return False


# ---------------------------------------------------------------------------
# OC-4 -- the L21-L27 closure ladder, total by STEP-LOCAL containment only.
# ---------------------------------------------------------------------------
#
# Every step below owns its own protected region(s): invocation, exact
# container validation, ONE read of each required member into a local, exact
# validation of each local, and only then a commit of already-validated plain
# values (R-REGION / R-COMMIT). Handlers are ``except Exception:`` with no
# bound name and a constant-assignment body (R-HANDLER): nothing about a
# contained exception is read, formatted, kept or chained, and nothing in a
# handler can itself raise. No foreign value is ever compared, truth-tested,
# iterated, hashed or converted before ``type(x) is T`` has established what it
# is (R-PLAIN), and no missing member defaults to a positive value.
#
# There is deliberately NO ``try`` around the closure phase as a whole, or
# around any span that covers more than one obligation (I-8): a raise from
# code that touches only executor-owned values is an implementation defect and
# must still surface as ``RUN_EXECUTOR_RAISED`` at the stage runner.


def _closure_l21_runtime_applicable(
    state: _RunState, observations: dict[str, Any]
) -> bool:
    """D-3: is L21 applicable? Decided by AIDO's own facts, never a port's claim.

    * no supervisor -> not applicable;
    * ``runtime_created`` already true (L14's own record) -> applicable, and
      ``supervisor.process`` is not consulted at all;
    * ``runtime_created`` false and AIDO never called ``launch()`` -> NOT
      applicable, and ``supervisor.process`` is NOT consulted: a process claim
      on a merely-built supervisor is a port-supplied claim and grants no
      cleanup authority;
    * ``runtime_created`` false, AIDO DID call ``launch()`` -> the process is
      probed once: exactly ``None`` means no process is proven (not
      applicable); anything else, or an accessor that raises, means AIDO cannot
      prove none exists, so ``runtime_created`` moves ``False -> True`` (never
      back) and L21 is applicable.
    """
    if state.supervisor is None:
        return False
    if observations["runtime_created"] is True:
        return True
    if state.runtime_launch_attempted is not True:
        return False
    try:
        process_present = getattr(state.supervisor, "process", None) is not None
    except Exception:  # noqa: BLE001 - cannot prove there is no process
        process_present = True
    if process_present:
        observations["runtime_created"] = True
    return process_present


def _closure_l21_runtime(state: _RunState, observations: dict[str, Any]) -> None:
    """L21: the DIRECT child's exit status and both reader EOFs -- nothing more.

    Three independent sub-obligations, each attempted once whenever L21 is
    applicable, whatever the others did. Only ``exit_status_observed`` and
    ``eof`` are ever read; ``text_tail``, ``stdin_close_error`` and
    ``claim_scope`` never are, and no returned container outlives its region.
    """
    if not _closure_l21_runtime_applicable(state, observations):
        return

    exit_observed = False
    try:
        record = state.supervisor.shutdown()
        if type(record) is dict:
            exit_status = record.get("exit_status_observed")
            # ``bool`` is an int subclass: an exit status is an exact int.
            exit_observed = type(exit_status) is int
    except Exception:  # noqa: BLE001
        exit_observed = False
    observations["runtime_exit_observed"] = exit_observed

    stdout_eof = False
    try:
        stdout_state = state.supervisor.stdout_state()
        if type(stdout_state) is dict:
            stdout_eof = stdout_state.get("eof") is True
    except Exception:  # noqa: BLE001
        stdout_eof = False

    stderr_eof = False
    try:
        stderr_state = state.supervisor.stderr_snapshot()
        if type(stderr_state) is dict:
            stderr_eof = stderr_state.get("eof") is True
    except Exception:  # noqa: BLE001
        stderr_eof = False

    # Both reads were attempted above; the conjunction is over exact bools.
    observations["runtime_transport_eof_observed"] = stdout_eof and stderr_eof


def _closure_l22_broker_counts(state: _RunState, observations: dict[str, Any]) -> None:
    """L22: diagnostic counts -- ALL-OR-NOTHING, never lifecycle teardown.

    ``broker_recorded_activity_available`` is true only when every one of the
    four raw facts was an exact non-negative ``int``. When anything is
    malformed the four counts stay ``0`` -- not partial real values beside an
    "unavailable" flag, a state the frozen v2 validator refuses (M-2).
    """
    if state.broker is None:
        return

    available = False
    read_operations = edit_operations = edited_paths = refusals = 0
    try:
        counts = state.broker.diagnostics_counts()
        if type(counts) is dict:
            raw_read = counts.get("read_operations")
            raw_edit = counts.get("edit_operations")
            raw_edited = counts.get("edited_paths")
            raw_refusals = counts.get("refusals")
            if (
                type(raw_read) is int
                and raw_read >= 0
                and type(raw_edit) is int
                and raw_edit >= 0
                and type(raw_edited) is int
                and raw_edited >= 0
                and type(raw_refusals) is int
                and raw_refusals >= 0
            ):
                available = True
                read_operations = raw_read
                edit_operations = raw_edit
                edited_paths = raw_edited
                refusals = raw_refusals
    except Exception:  # noqa: BLE001
        available = False
        read_operations = edit_operations = edited_paths = refusals = 0

    observations["broker_recorded_activity_available"] = available
    observations["broker_recorded_read_operation_count"] = read_operations
    observations["broker_recorded_edit_operation_count"] = edit_operations
    observations["broker_recorded_edited_path_count"] = edited_paths
    observations["broker_recorded_refusal_count"] = refusals


def _closure_l23_broker_shutdown(state: _RunState, observations: dict[str, Any]) -> None:
    """L23: three independent proofs from one exact-``dict`` shutdown record.

    A missing or malformed member fails only its own fact -- and a MISSING
    ``worker_termination_observed`` is unproven, never defaulted true (M-4).
    ``worker_error`` (raw text) is never read.
    """
    if observations["broker_resource_created"] is not True:
        return

    state_closed = False
    pending_zero = False
    worker_terminated = False
    try:
        lifecycle = state.broker.shutdown_for_cfg1()
        if type(lifecycle) is dict:
            state_reached = lifecycle.get("state_reached")
            pending_unreaped = lifecycle.get("pending_operations_unreaped")
            worker_termination = lifecycle.get("worker_termination_observed")
            # Exact ``str`` first, so ``==`` only ever runs ``str.__eq__``.
            state_closed = type(state_reached) is str and state_reached == "CLOSED"
            pending_zero = type(pending_unreaped) is int and pending_unreaped == 0
            worker_terminated = worker_termination is True
    except Exception:  # noqa: BLE001
        state_closed = False
        pending_zero = False
        worker_terminated = False

    observations["broker_state_closed"] = state_closed
    observations["broker_pending_unreaped_zero"] = pending_zero
    observations["broker_worker_terminated_or_absent"] = worker_terminated


def _closure_l24_scrubs(state: _RunState, observations: dict[str, Any]) -> None:
    """L24: the two AMEND2 handle-bound scrubs, each independent of the other.

    Must precede any execution of model-influenced code (L26), which could
    otherwise read the endpoint from models.json or the token from the
    generated extension config. Neither is ever set True from a pathname
    observation (G7), and L27's later success never upgrades either (G5). A run
    that never reached L9 / L11 keeps that step's own value. Each helper is
    itself total, so a False or a raise on one never skips the other.
    """
    if state.generated_config is not None:
        observations["generated_config_scrub_verified"] = _scrub_generated_config(state)
    if state.extension is not None:
        observations["extension_binding_scrub_verified"] = _scrub_extension_binding(state)


def _closure_l25_git_observation_1(
    ports: Cfg1RunPorts, observations: dict[str, Any], state: _RunState
) -> None:
    """L25: an observation, not a closure fact. Locals first, then one commit."""
    from . import run_workspace as workspace_module

    if state.workspace is None:
        return

    try:
        workspace_module.verify_cfg1_run_workspace(state.workspace)
        snapshot = ports.observe_repository(
            workspace_root=state.workspace.workspace_root
        )
        head_before, _tracked = workspace_module.registered_baseline(state.workspace)
        # Sec. 37.4.1 (FU15 Finding B1). The exactness PREDICATE runs over the
        # whole snapshot BEFORE a single field is projected, and a single
        # malformed member drives the entire observation to the already-frozen
        # not-performed shape by raising into the same ``except`` below.
        # Nothing here reduces, coerces or defaults: a reducer's job is to
        # manufacture a plausible value, and that is precisely the defect.
        head, changed_paths, untracked, staged = _exact_repository_snapshot(snapshot)
        head_moved = head != head_before
        changed = sorted(set(changed_paths) & CFG1_T1_FILES)
        cross_check_agrees = _broker_git_cross_check(observations, changed)
    except Exception:  # noqa: BLE001
        observations["git_observation_1_performed"] = False
        return

    # Every value is already a plain local: nothing below can raise, so no
    # partially-performed shape is reachable.
    observations["git_observation_1_performed"] = True
    observations["head_moved"] = head_moved
    observations["changed_tracked_paths"] = changed
    observations["untracked_path_count"] = untracked
    observations["staged_path_count"] = staged
    observations["broker_git_cross_check_agrees"] = cross_check_agrees


def _closure_l26_project_verification(outcome: object) -> dict[str, Any] | None:
    """The all-or-nothing projection of one verification outcome (E-10..E-12).

    Returns plain, already-validated values, or ``None`` when ANY accessor
    raised -- in which case nothing at all is committed and the run takes the
    frozen port-raise shape. ``counts`` must be an exact ``dict``; anything else
    (missing, ``None``, a ``list``, a subclass, a foreign object) is a
    container holding no members, so all three keys take Sec. 37.4.2's
    non-content-bearing refusal sentinel -- never the malformed value itself,
    never a truthiness test, never ``.get`` on a foreign object.
    """
    missing = object()
    try:
        started = getattr(outcome, "started", missing) is True
        completed = getattr(outcome, "completed", missing) is True
        timed_out = getattr(outcome, "timed_out", missing) is True
        output_limit_exceeded = getattr(outcome, "output_limit_exceeded", missing) is True
        passed = getattr(outcome, "passed", missing) is True
        raw_return_code = getattr(outcome, "return_code", missing)
        raw_counts = getattr(outcome, "counts", missing)

        return_code = raw_return_code if type(raw_return_code) is int else None

        # Sec. 37.4.2 (FU15 Finding B2). Verification demonstrably RAN, so Sec.
        # 37.4.1's not-performed shape cannot be reused here, and inventing a
        # new availability flag is exactly the schema growth this phase
        # discourages. A malformed member becomes a fixed sentinel that
        # ``_require_exact_int_mapping`` refuses by construction: the run
        # record fails its OWN validator at L29 step 6.
        projected_counts: dict[str, object] = {}
        counts_all_exact = True
        counts_is_dict = type(raw_counts) is dict
        for key in _VERIFICATION_COUNT_KEYS:
            value = raw_counts.get(key) if counts_is_dict else None
            if type(value) is int and value >= 0:
                projected_counts[key] = value
            else:
                projected_counts[key] = _MALFORMED_VERIFICATION_COUNT
                counts_all_exact = False
    except Exception:  # noqa: BLE001
        return None

    return {
        "started": started,
        "completed": completed,
        "timed_out": timed_out,
        "output_limit_exceeded": output_limit_exceeded,
        "return_code": return_code,
        "counts": projected_counts,
        # CFG1-IMPL-FU2 Finding 3: a malformed count can only ever pull a claim
        # of "passed" back to "not proven passed".
        "passed": passed and counts_all_exact,
    }


def _closure_l26_verification(
    ports: Cfg1RunPorts, observations: dict[str, Any], state: _RunState
) -> None:
    """L26: verification (three regions) and then Git observation #2 (its own).

    Eligibility is unchanged and reads only executor-owned exact bools. When
    verification is attempted, Git observation #2 is attempted whatever the
    verification invocation or projection did.
    """
    closure_proven = (
        observations["runtime_exit_observed"] is True
        and observations["runtime_transport_eof_observed"] is True
        and observations["broker_state_closed"] is True
        and observations["generated_config_scrub_verified"] is True
        and observations["extension_binding_scrub_verified"] is True
    )
    if observations["pre_dispatch_refusal_code"] is not None:
        observations["verification_attempted"] = False
        observations["verification_skip_reason"] = "PRE_DISPATCH_REFUSAL"
        return
    if not closure_proven:
        observations["verification_attempted"] = False
        observations["verification_skip_reason"] = "LIFECYCLE_UNPROVEN"
        return

    observations["verification_attempted"] = True
    observations["verification_skip_reason"] = None

    # (a) invocation
    try:
        outcome = ports.run_verification(
            workspace_root=state.workspace.workspace_root,
            args=CFG1_T1.verification_args,
        )
    except Exception:  # noqa: BLE001
        outcome = None

    # (b)/(c) projection -- nothing is committed unless the whole outcome read
    projected = None if outcome is None else _closure_l26_project_verification(outcome)
    if projected is None:
        # The frozen port-raise shape: every other ``verification_*`` fact
        # stays at its current fail-closed value.
        observations["verification_child_reaped_or_not_started"] = False
    else:
        observations["verification_started"] = projected["started"]
        observations["verification_completed"] = projected["completed"]
        observations["verification_timed_out"] = projected["timed_out"]
        observations["verification_output_limit_exceeded"] = projected[
            "output_limit_exceeded"
        ]
        observations["verification_return_code"] = projected["return_code"]
        observations["verification_counts"] = projected["counts"]
        observations["verification_passed"] = projected["passed"]
        # A child that never yielded an exact-int return code was never reaped
        # (M-5): a malformed non-None code is not a reaped child.
        observations["verification_child_reaped_or_not_started"] = (
            projected["return_code"] is not None
        )

    # (d) Git observation #2 -- its own region, attempted regardless of (a)-(c).
    try:
        snapshot = ports.observe_repository(
            workspace_root=state.workspace.workspace_root
        )
        # Observation #2 reads the SAME snapshot type through the SAME port, so
        # Sec. 37.4.1's own reasoning applies verbatim: the same predicate, the
        # same all-or-nothing disposition, the same not-performed shape.
        _head, changed_paths, _untracked, _staged = _exact_repository_snapshot(snapshot)
        post_verification_changed = sorted(set(changed_paths) & CFG1_T1_FILES)
    except Exception:  # noqa: BLE001
        observations["git_observation_2_performed"] = False
        return
    observations["git_observation_2_performed"] = True
    observations["post_verification_changed_tracked_paths"] = post_verification_changed


def _closure_l27_workspace(observations: dict[str, Any], state: _RunState) -> None:
    """L27: decided by W, never by a path and never by ``refused_at_step``.

    NOT_ATTEMPTED -> nothing to close; ATTEMPTED_NO_AUTHORITY -> nothing is
    ever deleted and the facts stay unproven; AUTHORITY_RETURNED -> the
    existing re-proof and removal, each in its own region. A failure never
    retries, never falls back to a name- or path-based delete, never marks
    removal verified, and never hides a surviving registry entry: that entry is
    what ``minted_workspace_count`` reports to L30.
    """
    from . import run_workspace as workspace_module

    if not (
        observations["workspace_mint_state"] == WORKSPACE_MINT_AUTHORITY_RETURNED
        and state.workspace is not None
    ):
        return

    reproved = False
    try:
        workspace_module.verify_cfg1_run_workspace(state.workspace)
        reproved = True
    except Exception:  # noqa: BLE001
        reproved = False
    observations["workspace_authority_reproved"] = reproved

    if not reproved:
        # Ownership unprovable: the tree is NEVER deleted. A later run must not
        # delete it either -- nothing is ever removed because its name looks
        # expected. A discard that itself raises leaves the registry entry
        # visible to L30; there is no second attempt.
        try:
            workspace_module.discard_cfg1_run_workspace(state.workspace)
        except Exception:  # noqa: BLE001
            pass
        return

    removed_verified = False
    residual_count = 0
    try:
        removal = workspace_module.remove_cfg1_run_workspace(state.workspace)
        if type(removal) is dict:
            removed = removal.get("removed")
            raw_residual = removal.get("residual_file_count")
            # CFG1-IMPL-FU2 Finding 3: a malformed residual count forces
            # ``workspace_removed_verified`` false regardless of ``removed``,
            # and is never laundered into a plausible proven zero.
            residual_exact = type(raw_residual) is int and raw_residual >= 0
            residual_count = raw_residual if residual_exact else 0
            removed_verified = removed is True and residual_exact
    except Exception:  # noqa: BLE001
        removed_verified = False
        residual_count = 0
    observations["workspace_removed_verified"] = removed_verified
    observations["workspace_residual_file_count"] = residual_count


def _closure_phase(
    *, ports: Cfg1RunPorts, observations: dict[str, Any], state: _RunState
) -> None:
    """L21-L27, in the fixed order, skipping only never-created resources.

    A pure sequencer over executor-owned values (OC-4 I-1..I-3, I-8): each step
    is total by its OWN step-local containment, so no step is skipped because an
    earlier one failed, and there is deliberately no ``try`` here. A raise that
    reaches this function is an implementation defect and must still surface as
    ``RUN_EXECUTOR_RAISED``.
    """
    _closure_l21_runtime(state, observations)
    _closure_l22_broker_counts(state, observations)
    _closure_l23_broker_shutdown(state, observations)
    _closure_l24_scrubs(state, observations)
    _closure_l25_git_observation_1(ports, observations, state)
    _closure_l26_verification(ports, observations, state)
    _closure_l27_workspace(observations, state)


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


def default_cfg1_run_ports(*, ambient_environ: Mapping[str, str]) -> Cfg1RunPorts:
    """Bind the frozen modules for the eventual, separately-authorized live run.

    **Calling this does not authorize anything.** ``CFG1-LIVE-S1`` /
    ``CFG1-LIVE-S2`` remain separately required (Sec. 14.1). This exists so the
    live wiring is reviewable now, offline, rather than being invented later.

    ``read_connection`` is the one place an endpoint or credential value is
    ever read, and it happens only when a run reaches L4 -- after every
    non-secret gate has already passed.

    **FU1.** ``pi_proof_leaves`` is the SAME genuine leaf binding the
    pre-consumption gate uses (:func:`pi_identity.genuine_pi_proof_leaves`);
    ``ar2.launch.resolve_runtime_identity`` is no longer imported by CFG1 at
    all, and neither is ``ar2.pi_config.write_disposable_extension`` -- L11 is
    the CFG1-owned transactional writer.
    """
    import os
    import secrets
    from dataclasses import dataclass as _dataclass

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
    from ar2.launch import build_pi_argv
    from ar2.observation import observe_repository
    from ar2.supervisor import PiRpcSupervisor, RunBounds
    from ar2.verification import run_verification

    from . import run_workspace as workspace_module
    from .cfg1_extension import write_cfg1_extension
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
        # environment, a config file, or anything runtime-derived. ``identity``
        # is the CFG1 static identity object: the frozen ``build_pi_argv``
        # reads exactly its ``node_executable`` and ``pi_cli_js`` (Test AG).
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
                (Sec. 21.1), which is L22 in ``_closure_l22_broker_counts``, not here.

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

    def _write_extension(*, workspace, broker):
        """L11 -- the CFG1-owned transactional writer (FU1 AM-9, AM-14).

        The generated ``ar2_config.ts`` is the ONLY place the broker token
        exists on disk; the writer returns only an extension issuance token,
        which L14/L15 re-verify and L24 consumes by identity.
        """
        return write_cfg1_extension(
            workspace,
            pipe_name=broker.pipe_name,
            capability_id=broker.capability_id,
            token=broker.token,
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
        pi_proof_leaves=genuine_pi_proof_leaves(),
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
