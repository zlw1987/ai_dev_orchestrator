"""DL-2 — the offline single-Step inner loop (roadmap §16, M6).

:class:`StepInnerLoop` drives one recorded Step Run through implementation,
verification, review when its contract requires it, and the Planner's decision,
using injected role ports and DL-1's store. It is a driver and nothing else:

- **It never chooses a state.** Every change is a
  :class:`~ai_dev_orchestrator.control_plane.transitions.StepTransitionRequest`
  applied through :meth:`ControlPlaneStore.apply_step_transition`, so DL-1's
  validator decides every target state, and every read the loop acts on is the
  store's authoritative, re-proven read.
- **Role outputs are inputs.** A port's return value is accepted only if it is
  exactly the expected model, re-validates through that class, and is bound to
  the step's current contract digest and attempt. Anything else is a role
  failure. Implementer claims are carried in the request but never consulted.
- **At most one dispatch per persisted intent.** A port is called only when
  this ``run()`` call's own, non-duplicate transition produced the exact
  in-flight ``(state, state_version)`` the authoritative read now shows, and
  that permission is spent before the call. An in-flight step this call did not
  produce — left by an earlier call, an earlier session, a crash, or a replayed
  receipt — is never resumed or re-run: it is moved to RECOVERY_REQUIRED with
  DL-1's existing ``recover_interrupted`` event.
- **A replay is a receipt.** Request ids are derived from the step, the
  expected version and the event, so re-sending a recorded request returns its
  receipt. Once a receipt comes back, this call dispatches no role again.
- **Failures stop at a boundary.** A role that raises, or returns an unusable or
  mis-bound output, while the step is EXECUTING, VERIFYING or REVIEWING leaves
  its requested effect unproven, so the step goes to RECOVERY_REQUIRED. A
  Planner failure at ACCEPTANCE goes to HUMAN_REQUIRED via ``escalate``. Neither
  is retried. A ``BaseException`` (a simulated crash) is not caught: the step
  keeps its persisted in-flight state, which ``recover()`` turns into
  RECOVERY_REQUIRED on the next session.
- **No human acceptance source.** The loop never supplies a
  :class:`~ai_dev_orchestrator.control_plane.models.HumanStepAcceptance`. A step
  whose contract requires one escalates to HUMAN_REQUIRED instead of completing.

Offline only. Nothing here calls a model, launches a process, opens a socket,
reads an environment variable, or touches a workspace, and no CLI command
reaches it. Verification provenance, human-approval provenance, policy-issuance
provenance and workspace containment remain unproven hard gates before any real
adapter is wired (DL-4); see ``docs/DL2_OFFLINE_INNER_LOOP.md``.
"""

from __future__ import annotations

import hashlib
from enum import Enum
from typing import Literal

from pydantic import BaseModel

from ai_dev_orchestrator.control_plane.models import (
    IN_FLIGHT_STEP_STATES,
    TERMINAL_STEP_STATES,
    ExecutionPlan,
    ImplementationReport,
    PlannerDecision,
    ProjectContract,
    ProjectRun,
    ProjectState,
    ReviewProposal,
    StepContract,
    StepRun,
    StepState,
    VerificationObservation,
    _Strict,
)
from ai_dev_orchestrator.control_plane.ports import RolePorts
from ai_dev_orchestrator.control_plane.store import (
    _PROJECT_IDENTITY,
    _STEP_IDENTITY,
    AppliedTransition,
    ControlPlaneStore,
)
from ai_dev_orchestrator.control_plane.transitions import (
    RefusalCode,
    StepEvent,
    StepTransitionRequest,
    TransitionRefused,
)

Role = Literal["implementer", "verifier", "reviewer", "planner"]
DispatchResult = Literal["valid", "raised", "malformed", "misbound"]
InnerLoopCause = Literal[
    "role_raised",
    "role_output_malformed",
    "role_output_misbound",
    "result_not_recorded",
    "human_acceptance_unavailable",
    "in_flight_not_dispatched_here",
    "project_not_active",
    "replayed_receipt",
]

_FAILURE_CAUSE: dict[str, InnerLoopCause] = {
    "raised": "role_raised",
    "malformed": "role_output_malformed",
    "misbound": "role_output_misbound",
}


class InnerLoopStop(str, Enum):
    """Why :meth:`StepInnerLoop.run` returned.

    The first four mirror the step's final authoritative state. The rest
    describe a non-terminal step the loop stopped advancing.
    """

    STEP_COMPLETE = "step_complete"
    STEP_FAILED = "step_failed"
    STEP_HUMAN_REQUIRED = "step_human_required"
    STEP_RECOVERY_REQUIRED = "step_recovery_required"
    PROJECT_NOT_ACTIVE = "project_not_active"
    STEP_NOT_READY = "step_not_ready"
    TRANSITION_REFUSED = "transition_refused"
    REPLAYED_RECEIPT = "replayed_receipt"
    ITERATION_BOUND_REACHED = "iteration_bound_reached"


_TERMINAL_STOP = {
    StepState.COMPLETE: InnerLoopStop.STEP_COMPLETE,
    StepState.FAILED: InnerLoopStop.STEP_FAILED,
    StepState.HUMAN_REQUIRED: InnerLoopStop.STEP_HUMAN_REQUIRED,
    StepState.RECOVERY_REQUIRED: InnerLoopStop.STEP_RECOVERY_REQUIRED,
}


class InnerLoopInputError(Exception):
    """The caller's objects do not describe one recorded step. Nothing was
    written and no role was called."""


class RoleDispatch(_Strict):
    """One role call: which role, for which attempt, authorized by which
    persisted step version, and whether its output was usable."""

    role: Role
    attempt: int
    step_state_version: int
    result: DispatchResult


class InnerLoopOutcome(_Strict):
    """The loop's result. ``step_run`` and ``project_run`` are the store's
    authoritative reads taken after the last transition, never a role's
    account or a transition receipt."""

    stop: InnerLoopStop
    step_run: StepRun
    project_run: ProjectRun
    cause: InnerLoopCause | None = None
    cause_role: Role | None = None
    refusal_code: RefusalCode | None = None
    dispatches: tuple[RoleDispatch, ...] = ()


# The role an in-flight state was entered to request, the output it must
# return, and the event that records that output.
_IN_FLIGHT_ROLES: dict[StepState, tuple[Role, type[BaseModel], StepEvent, str]] = {
    StepState.EXECUTING: (
        "implementer", ImplementationReport, StepEvent.IMPLEMENTATION_RETURNED, "implementation"
    ),
    StepState.VERIFYING: (
        "verifier", VerificationObservation, StepEvent.VERIFICATION_OBSERVED, "verification"
    ),
    StepState.REVIEWING: ("reviewer", ReviewProposal, StepEvent.REVIEW_OBSERVED, "review"),
}

_PORT_METHODS = (
    ("planner", "decide_step"),
    ("implementer", "implement"),
    ("verifier", "verify"),
    ("reviewer", "review"),
)

# One attempt is at most five transitions (begin, implementation, verification,
# review, decision); a final escalation and the closing read add the rest.
_TRANSITIONS_PER_ATTEMPT = 5
_ITERATION_SLACK = 3


def step_request_id(step_run_id: str, expected_state_version: int, event: StepEvent) -> str:
    """The idempotency key DL-2 uses for one step event at one version.

    Deterministic, so the same logical request is the same request: replaying it
    returns DL-1's receipt, and a different request reusing the slot is refused
    as a duplicate conflict.
    """
    material = f"dl2:{step_run_id}:{expected_state_version}:{event.value}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]


def _exact(model_type: type[BaseModel], value: object, name: str):
    """Re-parse a caller object through exactly ``model_type``, or refuse it."""
    if type(value) is not model_type:
        raise InnerLoopInputError(f"{name} must be exactly a {model_type.__name__}.")
    try:
        return model_type.model_validate_json(value.model_dump_json(warnings=False))
    except Exception as exc:  # noqa: BLE001 - any failure means it never validated
        raise InnerLoopInputError(f"{name} does not validate.") from exc


def _role_output(
    model_type: type[BaseModel], value: object, contract: StepContract, attempt: int
) -> tuple[BaseModel | None, DispatchResult]:
    """The re-validated, bound copy of a role output, or why there is none."""
    if type(value) is not model_type:
        return None, "malformed"
    try:
        copy = model_type.model_validate_json(value.model_dump_json(warnings=False))
    except Exception:  # noqa: BLE001 - any failure means it never validated
        return None, "malformed"
    if copy.step_contract_sha256 != contract.sha256 or copy.attempt != attempt:
        return None, "misbound"
    return copy, "valid"


class StepInnerLoop:
    """Drive one Step Run with injected role ports. See the module docstring.

    The instance holds only the store and the ports. Dispatch permission lives
    inside one :meth:`run` call and never outlives it, so neither a new
    instance nor a second ``run()`` on this one can resume an in-flight step.
    """

    def __init__(self, store: ControlPlaneStore, ports: RolePorts) -> None:
        if not isinstance(store, ControlPlaneStore):
            raise InnerLoopInputError("store must be a ControlPlaneStore.")
        if not isinstance(ports, RolePorts):
            raise InnerLoopInputError("ports must be a RolePorts.")
        for role, method in _PORT_METHODS:
            if not callable(getattr(getattr(ports, role), method, None)):
                raise InnerLoopInputError(f"the {role} port has no callable {method}().")
        self._store = store
        self._ports = ports

    def run(
        self,
        *,
        project_run: ProjectRun,
        step_run: StepRun,
        project_contract: ProjectContract,
        execution_plan: ExecutionPlan,
        step_contract: StepContract,
    ) -> InnerLoopOutcome:
        """Advance the step until it is terminal or cannot be advanced.

        Raises :class:`InnerLoopInputError` before reading any state as
        authority when the objects do not describe one recorded step, and lets
        the store's :class:`~ai_dev_orchestrator.control_plane.store.RecoveryRequiredError`
        and :class:`~ai_dev_orchestrator.control_plane.store.StateUntrustedError`
        propagate unchanged: a run this session has not re-proven is not
        consumed.
        """
        project_run_id, step_run_id, contract = self._bind(
            project_run, step_run, project_contract, execution_plan, step_contract
        )
        return _Run(self._store, self._ports, project_run_id, step_run_id, contract).drive()

    def _bind(
        self,
        project_run: object,
        step_run: object,
        project_contract: object,
        execution_plan: object,
        step_contract: object,
    ) -> tuple[str, str, StepContract]:
        supplied_project = _exact(ProjectRun, project_run, "project_run")
        supplied_step = _exact(StepRun, step_run, "step_run")
        supplied_pc = _exact(ProjectContract, project_contract, "project_contract")
        supplied_plan = _exact(ExecutionPlan, execution_plan, "execution_plan")
        supplied_contract = _exact(StepContract, step_contract, "step_contract")

        # The store's reads re-prove each run and enforce the recovery gate.
        project = self._store.get_project_run(supplied_project.project_run_id)
        step = self._store.get_step_run(supplied_step.step_run_id)
        if step.project_run_id != project.project_run_id:
            raise InnerLoopInputError("step_run belongs to another project run.")
        # Identity must match; a supplied run's state fields are never consulted.
        for name in _PROJECT_IDENTITY:
            if getattr(supplied_project, name) != getattr(project, name):
                raise InnerLoopInputError(f"project_run.{name} is not the recorded run's.")
        for name in _STEP_IDENTITY:
            if getattr(supplied_step, name) != getattr(step, name):
                raise InnerLoopInputError(f"step_run.{name} is not the recorded run's.")
        if supplied_pc.sha256 != project.project_contract_sha256:
            raise InnerLoopInputError("project_contract is not the project run's contract.")
        if supplied_plan.sha256 != project.execution_plan_sha256:
            raise InnerLoopInputError("execution_plan is not the project run's plan.")
        if supplied_contract.sha256 != step.step_contract_sha256:
            raise InnerLoopInputError("step_contract is not the step run's contract.")
        return (
            project.project_run_id,
            step.step_run_id,
            self._store.get_step_contract(step.step_contract_sha256),
        )


class _Run:
    """The state of one :meth:`StepInnerLoop.run` call."""

    def __init__(
        self,
        store: ControlPlaneStore,
        ports: RolePorts,
        project_run_id: str,
        step_run_id: str,
        contract: StepContract,
    ) -> None:
        self.store = store
        self.ports = ports
        self.project_run_id = project_run_id
        self.step_run_id = step_run_id
        self.contract = contract
        self.dispatches: list[RoleDispatch] = []
        self.cause: InnerLoopCause | None = None
        self.cause_role: Role | None = None
        self.refusal_code: RefusalCode | None = None
        # The one in-flight (state, version) this call produced and may still
        # dispatch for. Cleared before the port is called.
        self.owned: tuple[StepState, int] | None = None
        # Set once a receipt comes back: no role is dispatched after it.
        self.receipt_seen = False
        self.attempts_begun = 0

    def drive(self) -> InnerLoopOutcome:
        halt: InnerLoopStop | None = None
        bound = _TRANSITIONS_PER_ATTEMPT * self.contract.max_attempts + _ITERATION_SLACK
        for _ in range(bound):
            step = self.store.get_step_run(self.step_run_id)
            project = self.store.get_project_run(self.project_run_id)
            if step.state in TERMINAL_STEP_STATES:
                break
            if step.state in IN_FLIGHT_STEP_STATES:
                self._in_flight(step, project)
                continue
            if project.state is not ProjectState.ACTIVE:
                halt = InnerLoopStop.PROJECT_NOT_ACTIVE
                break
            if self.receipt_seen:
                halt = InnerLoopStop.REPLAYED_RECEIPT
                break
            if step.state is StepState.PLANNED:
                halt = InnerLoopStop.STEP_NOT_READY
                break
            if step.state is StepState.READY:
                halt = self._begin_attempt(step)
            else:
                halt = self._decide(step)
            if halt is not None:
                break
        else:
            halt = InnerLoopStop.ITERATION_BOUND_REACHED
        return self._outcome(halt)

    # --- states ----------------------------------------------------------

    def _in_flight(self, step: StepRun, project: ProjectRun) -> None:
        if self.owned != (step.state, step.state_version):
            self._note("in_flight_not_dispatched_here")
            self._reduce(step, "the step was in flight without a dispatch by this DL-2 call")
            return
        self.owned = None
        if project.state is not ProjectState.ACTIVE:
            self._note("project_not_active")
            self._reduce(step, "the project left ACTIVE before the role was dispatched")
            return
        role, model_type, event, field = _IN_FLIGHT_ROLES[step.state]
        output, result = self._dispatch(role, model_type, step)
        if output is None:
            self._note(_FAILURE_CAUSE[result], role)
            self._reduce(step, f"the {role} {result}; its requested effect is unproven")
            return
        applied = self._apply(step, event, **{field: output})
        if applied is None:
            # Refused: the next read sees an in-flight step this call no longer
            # owns, and reduces it. The role is not called again.
            self._note("result_not_recorded", role)
            return
        if not applied.duplicate and StepState(applied.record.to_state) in IN_FLIGHT_STEP_STATES:
            self.owned = (StepState(applied.record.to_state), applied.record.to_version)

    def _begin_attempt(self, step: StepRun) -> InnerLoopStop | None:
        if self.attempts_begun >= self.contract.max_attempts:
            return InnerLoopStop.ITERATION_BOUND_REACHED
        applied = self._apply(step, StepEvent.BEGIN_ATTEMPT)
        if applied is None:
            return InnerLoopStop.TRANSITION_REFUSED
        if not applied.duplicate:
            self.attempts_begun += 1
            self.owned = (StepState(applied.record.to_state), applied.record.to_version)
        return None

    def _decide(self, step: StepRun) -> InnerLoopStop | None:
        decision, result = self._dispatch("planner", PlannerDecision, step)
        if decision is None:
            self._note(_FAILURE_CAUSE[result], "planner")
            return self._escalate(step, f"the planner {result}; no decision was recorded")
        try:
            applied = self.store.apply_step_transition(
                self.step_run_id, self._request(step, StepEvent.DECIDE_ACCEPTANCE,
                                                planner_decision=decision)
            )
        except TransitionRefused as exc:
            self.refusal_code = exc.code
            if exc.code is RefusalCode.HUMAN_ACCEPTANCE_MISSING:
                self._note("human_acceptance_unavailable", "planner")
                return self._escalate(
                    step, "the step contract requires human acceptance and DL-2 has no source "
                    "of one"
                )
            return InnerLoopStop.TRANSITION_REFUSED
        self._receipt(applied)
        return None

    # --- mechanics -------------------------------------------------------

    def _dispatch(
        self, role: Role, model_type: type[BaseModel], step: StepRun
    ) -> tuple[BaseModel | None, DispatchResult]:
        try:
            value = self._call_port(role, step)
        except Exception:  # noqa: BLE001 - a BaseException is a crash and propagates
            output, result = None, "raised"
        else:
            output, result = _role_output(model_type, value, self.contract, step.attempt)
        self.dispatches.append(RoleDispatch(
            role=role, attempt=step.attempt, step_state_version=step.state_version, result=result
        ))
        return output, result

    def _call_port(self, role: Role, step: StepRun) -> object:
        # Ports get fresh copies of the store's contract and snapshot, never the
        # store and never an object this call later decides with: a "frozen"
        # model can still be changed with object.__setattr__.
        contract = StepContract.model_validate_json(self.contract.model_dump_json())
        attempt = step.attempt
        if role == "planner":
            snapshot = StepRun.model_validate_json(step.model_dump_json())
            return self.ports.planner.decide_step(step_contract=contract, step_run=snapshot)
        if role == "implementer":
            return self.ports.implementer.implement(step_contract=contract, attempt=attempt)
        if role == "verifier":
            return self.ports.verifier.verify(step_contract=contract, attempt=attempt)
        return self.ports.reviewer.review(step_contract=contract, attempt=attempt)

    def _request(self, step: StepRun, event: StepEvent, **payload) -> StepTransitionRequest:
        return StepTransitionRequest(
            request_id=step_request_id(self.step_run_id, step.state_version, event),
            expected_state_version=step.state_version,
            event=event,
            **payload,
        )

    def _apply(self, step: StepRun, event: StepEvent, **payload) -> AppliedTransition | None:
        try:
            applied = self.store.apply_step_transition(
                self.step_run_id, self._request(step, event, **payload)
            )
        except TransitionRefused as exc:
            self.refusal_code = exc.code
            return None
        self._receipt(applied)
        return applied

    def _receipt(self, applied: AppliedTransition) -> None:
        if applied.duplicate:
            self.receipt_seen = True
            self.owned = None
            self._note("replayed_receipt")

    def _reduce(self, step: StepRun, reason: str) -> None:
        """Move an in-flight step to RECOVERY_REQUIRED; never resume it."""
        self._apply(step, StepEvent.RECOVER_INTERRUPTED, reason=f"DL-2: {reason}.")

    def _escalate(self, step: StepRun, reason: str) -> InnerLoopStop | None:
        if self._apply(step, StepEvent.ESCALATE, reason=f"DL-2: {reason}.") is None:
            return InnerLoopStop.TRANSITION_REFUSED
        return None

    def _note(self, cause: InnerLoopCause, role: Role | None = None) -> None:
        if self.cause is None:
            self.cause, self.cause_role = cause, role

    def _outcome(self, halt: InnerLoopStop | None) -> InnerLoopOutcome:
        step = self.store.get_step_run(self.step_run_id)
        project = self.store.get_project_run(self.project_run_id)
        if step.state in _TERMINAL_STOP:
            stop = _TERMINAL_STOP[step.state]
        elif project.state is not ProjectState.ACTIVE:
            stop = InnerLoopStop.PROJECT_NOT_ACTIVE
        else:
            # A non-terminal step is only left behind by an explicit halt.
            stop = halt or InnerLoopStop.ITERATION_BOUND_REACHED
        return InnerLoopOutcome(
            stop=stop,
            step_run=step,
            project_run=project,
            cause=self.cause,
            cause_role=self.cause_role,
            refusal_code=self.refusal_code,
            dispatches=tuple(self.dispatches),
        )
