"""DL-3 — the offline project outer loop (roadmap §16.1, M6C; offline subset).

:class:`ProjectOuterLoop` coordinates the recorded Step Runs of one recorded
Project Run. It schedules, it hands each schedulable step to the accepted DL-2
:class:`~ai_dev_orchestrator.control_plane.inner_loop.StepInnerLoop`, and it
assesses whether the project could complete. It is a coordinator and nothing
else:

- **It reconstructs from the store, never from the caller.** The caller names a
  project run; every object the loop decides with is the store's re-proven read,
  loaded by the run's creation-bound digests, and re-read on every iteration. A
  caller's snapshot is compared for identity and never consulted for state.
- **It schedules by recorded dependencies only.** The only dependency authority
  is ``PlannedStep.depends_on`` in the run's bound Execution Plan (which every
  Step Contract must copy verbatim). Steps are taken in plan order, which is a
  topological order by construction. ``mark_ready`` is the one step event the
  loop applies itself, and DL-1's validator re-proves every dependency's
  COMPLETE before allowing it.
- **DL-2 is the only step executor.** The loop never calls a role port. A READY
  or ACCEPTANCE step is driven by a fresh ``StepInnerLoop``; an in-flight step is
  handed to DL-2 too, which never resumes it and reduces it to
  RECOVERY_REQUIRED. DL-2 is invoked at most once per step per :meth:`run` call.
  Its ``cause``, ``dispatches`` and receipts are recorded for audit and never
  decide anything; the next decision comes from a fresh store read.
- **A blocked step stops the project.** No recorded policy authorizes
  continuing past a FAILED, HUMAN_REQUIRED or RECOVERY_REQUIRED step, so the loop
  schedules nothing further and, while the project is still ACTIVE, records a
  DL-1 ``escalate`` (HUMAN_REQUIRED). Nothing is ever resolved automatically.
- **A run executes only its own plan, and only while no successor is recorded.**
  A run's plan is fixed at creation (DL-1 ``run_bindings``). Recording a later
  version proves its structure and chain, not that anyone authorized it, so a
  recorded plan is not an activated plan. A recorded successor is therefore a
  *pending supersession conflict*: the loop stops scheduling, writes nothing and
  leaves the run's state as it is. It never escalates, invalidates or
  supersedes the run because a successor exists. DL-3 never records, activates
  or substitutes a plan, and never creates a run or a step run.
- **Completion is assessed, not claimed.** :func:`assess_project_completion`
  separates "every recorded step run is COMPLETE", "the plan's work is
  complete", "the Project Contract's acceptance criteria are satisfied" and
  "COMPLETE is authorized". No offline evidence source can prove the last two,
  so they are ``False`` by type, the loop never requests completion, and DL-1's
  ``request_complete`` refusal stays the mechanical backstop.

Offline only. Nothing here calls a model, launches a process, opens a socket,
reads an environment variable, or touches a workspace, and no CLI command
reaches it. The DL-1/DL-2 hard gates (human-approval, verification and
policy-issuance provenance; workspace/store containment) and the role-output
binding gap remain open; see ``docs/DL3_OFFLINE_OUTER_LOOP.md``.
"""

from __future__ import annotations

import hashlib
from enum import Enum
from typing import Literal, NamedTuple

from pydantic import BaseModel

from ai_dev_orchestrator.control_plane.inner_loop import InnerLoopStop, StepInnerLoop
from ai_dev_orchestrator.control_plane.models import (
    IN_FLIGHT_STEP_STATES,
    ExecutionPlan,
    ProjectContract,
    ProjectRun,
    ProjectState,
    StepRun,
    StepState,
    _Strict,
)
from ai_dev_orchestrator.control_plane.ports import RolePorts
from ai_dev_orchestrator.control_plane.store import (
    _PROJECT_IDENTITY,
    ControlPlaneStore,
    StateUntrustedError,
)
from ai_dev_orchestrator.control_plane.transitions import (
    ProjectEvent,
    ProjectTransitionRequest,
    RefusalCode,
    StepEvent,
    StepTransitionRequest,
    TransitionRefused,
)

#: Step states that stop all further scheduling of the project. None of them
#: has a DL-1 exit, so the plan's work can never complete past one.
BLOCKED_STEP_STATES = frozenset(
    {StepState.FAILED, StepState.HUMAN_REQUIRED, StepState.RECOVERY_REQUIRED}
)

#: Audit-log rules under which a step reached HUMAN_REQUIRED because the
#: Planner asked for a different plan. Reported only; never acted on.
_REPLAN_RULES = frozenset({"planner_recommend_replan", "planner_plan_conflict"})

EscalationCode = Literal["step_blocked"]
CompletionBlocker = Literal[
    "project_not_active",
    "plan_supersession_pending",
    "step_run_missing",
    "step_not_complete",
    "step_blocked",
    "acceptance_criteria_unproven",
    "protected_invariants_unproven",
    "integration_gate_unavailable",
]

# One mark_ready and one DL-2 invocation per plan step, a final escalation, and
# the closing reads.
_ITERATION_SLACK = 3
_MAX_LISTED_STEPS = 5


class OuterLoopStop(str, Enum):
    """Why :meth:`ProjectOuterLoop.run` returned. None of these means COMPLETE."""

    PROJECT_NOT_ACTIVE = "project_not_active"
    STEP_BLOCKED = "step_blocked"
    PLAN_SUPERSESSION_PENDING = "plan_supersession_pending"
    PLAN_WORK_COMPLETE = "plan_work_complete_integration_gate_unavailable"
    NO_SCHEDULABLE_STEP = "no_schedulable_step"
    STEP_NOT_SETTLED = "step_not_settled"
    STEP_BUDGET_REACHED = "step_budget_reached"
    TRANSITION_REFUSED = "transition_refused"
    REPLAYED_RECEIPT = "replayed_receipt"
    ITERATION_BOUND_REACHED = "iteration_bound_reached"


class OuterLoopInputError(Exception):
    """The caller's objects do not describe one recorded project run, or the
    run is already being driven. Nothing was written and no step was run."""


class OuterLoopReentryError(OuterLoopInputError):
    """This project run is already being driven by a DL-3 call on this store."""


class ProjectCompletionAssessment(_Strict):
    """What the persisted offline state can and cannot prove about completion.

    The first two levels are computed from the store's re-proven reads. The
    last three are ``False`` **by type**: DL-3 has no project integration
    verification, no project-level acceptance evidence and no human project
    acceptance source, so no value of this model can claim them.
    """

    project_run_id: str
    project_state: ProjectState
    execution_plan_sha256: str
    execution_plan_version: int
    plan_is_latest_recorded: bool
    recorded_step_run_count: int
    #: Level 1: there is at least one recorded step run and every one is COMPLETE.
    all_recorded_step_runs_complete: bool
    #: Level 2: every step of the run's plan has a step run, and each is COMPLETE.
    plan_work_complete: bool
    #: Level 3: never provable offline.
    acceptance_criteria_satisfied: Literal[False] = False
    protected_invariants_satisfied: Literal[False] = False
    #: Level 4: never authorized offline.
    complete_authorized: Literal[False] = False
    missing_step_ids: tuple[str, ...]
    incomplete_step_ids: tuple[str, ...]
    blocked_step_ids: tuple[str, ...]
    blockers: tuple[CompletionBlocker, ...]


class StepInvocation(_Strict):
    """One DL-2 invocation, for audit. ``step_state_after`` is DL-2's
    authoritative read; ``inner_stop`` and the dispatch count never decide."""

    step_id: str
    step_run_id: str
    step_state_before: StepState
    inner_stop: InnerLoopStop
    step_state_after: StepState
    role_dispatch_count: int


class OuterLoopOutcome(_Strict):
    """The loop's result. ``project_run``, ``step_runs`` and ``completion`` are
    the store's authoritative reads taken after the last transition.

    ``replan_recommended_step_ids`` is read from the transition audit log and
    is advisory: the loop acts identically on every blocked step.
    """

    stop: OuterLoopStop
    project_run: ProjectRun
    step_runs: tuple[StepRun, ...]
    completion: ProjectCompletionAssessment
    invocations: tuple[StepInvocation, ...] = ()
    marked_ready: tuple[str, ...] = ()
    escalation: EscalationCode | None = None
    refusal_code: RefusalCode | None = None
    replan_recommended_step_ids: tuple[str, ...] = ()


def outer_request_id(subject_id: str, expected_state_version: int, label: str) -> str:
    """The idempotency key DL-3 uses for one event at one version.

    Deterministic, and in a namespace (``dl3:``) DL-2's keys cannot reach, so
    re-sending a recorded DL-3 request returns its receipt.
    """
    material = f"dl3:{subject_id}:{expected_state_version}:{label}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]


# --- pure decisions ------------------------------------------------------------


def _ordered(plan: ExecutionPlan, steps: tuple[StepRun, ...]) -> list[tuple[str, StepRun | None]]:
    by_step = {step.step_id: step for step in steps}
    return [(planned.step_id, by_step.get(planned.step_id)) for planned in plan.steps]


def _assess(
    project: ProjectRun,
    plan: ExecutionPlan,
    plan_is_latest: bool,
    steps: tuple[StepRun, ...],
) -> ProjectCompletionAssessment:
    ordered = _ordered(plan, steps)
    missing = tuple(step_id for step_id, step in ordered if step is None)
    blocked = tuple(
        step_id for step_id, step in ordered
        if step is not None and step.state in BLOCKED_STEP_STATES
    )
    incomplete = tuple(
        step_id for step_id, step in ordered
        if step is not None and step.state is not StepState.COMPLETE
        and step.state not in BLOCKED_STEP_STATES
    )
    plan_work_complete = not missing and not blocked and not incomplete
    blockers: list[CompletionBlocker] = []
    if project.state is not ProjectState.ACTIVE:
        blockers.append("project_not_active")
    if not plan_is_latest:
        blockers.append("plan_supersession_pending")
    if missing:
        blockers.append("step_run_missing")
    if incomplete:
        blockers.append("step_not_complete")
    if blocked:
        blockers.append("step_blocked")
    blockers += [
        "acceptance_criteria_unproven",
        "protected_invariants_unproven",
        "integration_gate_unavailable",
    ]
    return ProjectCompletionAssessment(
        project_run_id=project.project_run_id,
        project_state=project.state,
        execution_plan_sha256=plan.sha256,
        execution_plan_version=plan.plan_version,
        plan_is_latest_recorded=plan_is_latest,
        recorded_step_run_count=len(steps),
        all_recorded_step_runs_complete=bool(steps)
        and all(step.state is StepState.COMPLETE for step in steps),
        plan_work_complete=plan_work_complete,
        missing_step_ids=missing,
        incomplete_step_ids=incomplete,
        blocked_step_ids=blocked,
        blockers=tuple(blockers),
    )


class _Action(NamedTuple):
    kind: Literal["stop", "escalate", "mark_ready", "inner_loop"]
    stop: OuterLoopStop | None = None
    step: StepRun | None = None
    escalation: EscalationCode | None = None


def _next_action(
    *,
    project: ProjectRun,
    plan: ExecutionPlan,
    plan_is_latest: bool,
    steps: tuple[StepRun, ...],
    invoked: frozenset[str],
    marked: frozenset[str],
    budget_left: int,
) -> _Action:
    """The one thing to do next, from proven state alone. Pure and deterministic.

    ``invoked`` and ``marked`` are the step runs this call already handed to
    DL-2 or marked READY: a step is never acted on twice in one call, so a step
    that does not settle stops the loop instead of spinning it.
    """
    ordered = _ordered(plan, steps)
    present = [step for _, step in ordered if step is not None]

    # An in-flight step was entered by some other call or session (the
    # re-entry guard means never by a live DL-3 call for this project). DL-2 is
    # the one place that decides what happens to it: it is never resumed, only
    # reduced to RECOVERY_REQUIRED. That is authority-reducing and dispatches
    # nothing, so it comes first, whatever the project's state, rather than
    # leave an unproven in-flight state stranded behind an escalation.
    for step in present:
        if step.state in IN_FLIGHT_STEP_STATES:
            if step.step_run_id in invoked:
                return _Action("stop", OuterLoopStop.STEP_NOT_SETTLED, step)
            return _Action("inner_loop", step=step)
    if project.state is not ProjectState.ACTIVE:
        return _Action("stop", OuterLoopStop.PROJECT_NOT_ACTIVE)
    # A blocked step is a reason to escalate that does not depend on the plan
    # chain, so it keeps its escalation whether or not a successor is recorded.
    if any(step.state in BLOCKED_STEP_STATES for step in present):
        return _Action("escalate", OuterLoopStop.STEP_BLOCKED, escalation="step_blocked")
    # A recorded successor is not an activated one: nothing authorized it to
    # replace this run's plan, and nothing authorizes ignoring it. Stop before
    # any scheduling, and write nothing, so the run's lifecycle is unchanged.
    if not plan_is_latest:
        return _Action("stop", OuterLoopStop.PLAN_SUPERSESSION_PENDING)

    # Resume work already scheduled before starting new work.
    for step in present:
        if step.state in (StepState.READY, StepState.ACCEPTANCE):
            if step.step_run_id in invoked:
                return _Action("stop", OuterLoopStop.STEP_NOT_SETTLED, step)
            if budget_left <= 0:
                return _Action("stop", OuterLoopStop.STEP_BUDGET_REACHED, step)
            return _Action("inner_loop", step=step)

    by_id = dict(ordered)
    states = {step_id: (step.state if step else None) for step_id, step in ordered}
    for planned in plan.steps:
        step = by_id[planned.step_id]
        if step is None or step.state is not StepState.PLANNED:
            continue
        if not all(states.get(dep) is StepState.COMPLETE for dep in planned.depends_on):
            continue
        if step.step_run_id in marked:
            return _Action("stop", OuterLoopStop.STEP_NOT_SETTLED, step)
        if budget_left <= 0:
            return _Action("stop", OuterLoopStop.STEP_BUDGET_REACHED, step)
        return _Action("mark_ready", step=step)

    if all(state is StepState.COMPLETE for state in states.values()):
        return _Action("stop", OuterLoopStop.PLAN_WORK_COMPLETE)
    return _Action("stop", OuterLoopStop.NO_SCHEDULABLE_STEP)


# --- store-backed reads --------------------------------------------------------


def _plan_is_latest(store: ControlPlaneStore, project: ProjectRun) -> bool:
    plans = store.list_execution_plans(project.project_contract_sha256)
    index = project.execution_plan_version - 1
    if index >= len(plans) or plans[index].sha256 != project.execution_plan_sha256:
        raise StateUntrustedError(
            "the project run's plan is not in its project contract's recorded plan chain."
        )
    return len(plans) == project.execution_plan_version


def assess_project_completion(
    store: ControlPlaneStore, project_run_id: str
) -> ProjectCompletionAssessment:
    """Assess completion from the store's re-proven reads only.

    It takes no snapshot, flag or role output, so nothing a caller or a role
    asserts can raise any level. It writes nothing, and it never authorizes
    COMPLETE (see :class:`ProjectCompletionAssessment`).
    """
    if not isinstance(store, ControlPlaneStore):
        raise OuterLoopInputError("store must be a ControlPlaneStore.")
    project = store.get_project_run(project_run_id)
    steps = store.list_step_runs(project_run_id)
    plan = store.get_execution_plan(project.execution_plan_sha256)
    return _assess(project, plan, _plan_is_latest(store, project), steps)


def _exact(model_type: type[BaseModel], value: object, name: str):
    """Re-parse a caller object through exactly ``model_type``, or refuse it."""
    if type(value) is not model_type:
        raise OuterLoopInputError(f"{name} must be exactly a {model_type.__name__}.")
    try:
        return model_type.model_validate_json(value.model_dump_json(warnings=False))
    except Exception as exc:  # noqa: BLE001 - any failure means it never validated
        raise OuterLoopInputError(f"{name} does not validate.") from exc


# Project runs being driven right now, per store. Held only for the duration of
# one run() call, so a port that re-enters DL-3 for the same project is refused
# before it reads or writes anything.
_DRIVING: set[tuple[int, str]] = set()


class ProjectOuterLoop:
    """Drive one Project Run's recorded steps. See the module docstring.

    The instance holds only the store and the ports, which it passes to each
    fresh ``StepInnerLoop``. Nothing it learns in one :meth:`run` call carries
    into the next.
    """

    def __init__(self, store: ControlPlaneStore, ports: RolePorts) -> None:
        if not isinstance(store, ControlPlaneStore):
            raise OuterLoopInputError("store must be a ControlPlaneStore.")
        if not isinstance(ports, RolePorts):
            raise OuterLoopInputError("ports must be a RolePorts.")
        # DL-2 checks the ports' methods; construct one now so a bad port set is
        # refused before any run.
        StepInnerLoop(store, ports)
        self._store = store
        self._ports = ports

    def run(
        self,
        *,
        project_run: ProjectRun,
        project_contract: ProjectContract,
        execution_plan: ExecutionPlan,
        max_steps: int | None = None,
    ) -> OuterLoopOutcome:
        """Schedule and drive the project until nothing further may be done.

        ``max_steps`` optionally lowers how many READY or ACCEPTANCE steps are
        handed to DL-2 in this call; it can never raise the bound, which is one
        DL-2 invocation per plan step. Raises :class:`OuterLoopInputError`
        before any write when the objects do not describe one recorded run, and
        lets DL-1's ``RecoveryRequiredError`` / ``StateUntrustedError``
        propagate unchanged.
        """
        if max_steps is not None and (type(max_steps) is not int or max_steps < 1):
            raise OuterLoopInputError("max_steps must be a positive int or None.")
        supplied_project = _exact(ProjectRun, project_run, "project_run")
        supplied_pc = _exact(ProjectContract, project_contract, "project_contract")
        supplied_plan = _exact(ExecutionPlan, execution_plan, "execution_plan")
        key = (id(self._store), supplied_project.project_run_id)
        if key in _DRIVING:
            raise OuterLoopReentryError("this project run is already being driven by DL-3.")
        _DRIVING.add(key)
        try:
            project = self._store.get_project_run(supplied_project.project_run_id)
            for name in _PROJECT_IDENTITY:
                if getattr(supplied_project, name) != getattr(project, name):
                    raise OuterLoopInputError(f"project_run.{name} is not the recorded run's.")
            if supplied_pc.sha256 != project.project_contract_sha256:
                raise OuterLoopInputError("project_contract is not the project run's contract.")
            if supplied_plan.sha256 != project.execution_plan_sha256:
                raise OuterLoopInputError("execution_plan is not the project run's plan.")
            return _Drive(self._store, self._ports, project.project_run_id, max_steps).drive()
        finally:
            _DRIVING.discard(key)


class _Drive:
    """The state of one :meth:`ProjectOuterLoop.run` call."""

    def __init__(
        self,
        store: ControlPlaneStore,
        ports: RolePorts,
        project_run_id: str,
        max_steps: int | None,
    ) -> None:
        self.store = store
        self.ports = ports
        self.project_run_id = project_run_id
        self.max_steps = max_steps
        self.invoked: set[str] = set()
        self.marked: set[str] = set()
        self.steps_run = 0
        self.invocations: list[StepInvocation] = []
        self.marked_ready: list[str] = []
        self.escalation: EscalationCode | None = None
        self.refusal_code: RefusalCode | None = None

    def drive(self) -> OuterLoopOutcome:
        project = self.store.get_project_run(self.project_run_id)
        plan_steps = len(self.store.get_execution_plan(project.execution_plan_sha256).steps)
        budget = plan_steps if self.max_steps is None else min(self.max_steps, plan_steps)
        halt: OuterLoopStop | None = None
        for _ in range(2 * plan_steps + _ITERATION_SLACK):
            # Every decision is taken from fresh, re-proven reads.
            project = self.store.get_project_run(self.project_run_id)
            steps = self.store.list_step_runs(self.project_run_id)
            plan = self.store.get_execution_plan(project.execution_plan_sha256)
            action = _next_action(
                project=project,
                plan=plan,
                plan_is_latest=_plan_is_latest(self.store, project),
                steps=steps,
                invoked=frozenset(self.invoked),
                marked=frozenset(self.marked),
                budget_left=budget - self.steps_run,
            )
            if action.kind == "stop":
                halt = action.stop
                break
            if action.kind == "escalate":
                halt = self._escalate(project, steps, action)
                break
            if action.kind == "mark_ready":
                halt = self._mark_ready(action.step)
            else:
                halt = self._inner_loop(project, plan, action.step)
            if halt is not None:
                break
        else:
            halt = OuterLoopStop.ITERATION_BOUND_REACHED
        return self._outcome(halt)

    # --- actions ----------------------------------------------------------

    def _mark_ready(self, step: StepRun) -> OuterLoopStop | None:
        self.marked.add(step.step_run_id)
        request = StepTransitionRequest(
            request_id=outer_request_id(step.step_run_id, step.state_version, "mark_ready"),
            expected_state_version=step.state_version,
            event=StepEvent.MARK_READY,
        )
        try:
            applied = self.store.apply_step_transition(step.step_run_id, request)
        except TransitionRefused as exc:
            self.refusal_code = exc.code
            return OuterLoopStop.TRANSITION_REFUSED
        if applied.duplicate:
            # A receipt is not permission to schedule.
            return OuterLoopStop.REPLAYED_RECEIPT
        self.marked_ready.append(step.step_id)
        return None

    def _inner_loop(
        self, project: ProjectRun, plan: ExecutionPlan, step: StepRun
    ) -> OuterLoopStop | None:
        self.invoked.add(step.step_run_id)
        if step.state not in IN_FLIGHT_STEP_STATES:
            self.steps_run += 1
        outcome = StepInnerLoop(self.store, self.ports).run(
            project_run=project,
            step_run=step,
            project_contract=self.store.get_project_contract(project.project_contract_sha256),
            execution_plan=plan,
            step_contract=self.store.get_step_contract(step.step_contract_sha256),
        )
        if (
            outcome.step_run.step_run_id != step.step_run_id
            or outcome.project_run.project_run_id != self.project_run_id
        ):
            raise StateUntrustedError("DL-2 reported on a different step or project run.")
        self.invocations.append(StepInvocation(
            step_id=step.step_id,
            step_run_id=step.step_run_id,
            step_state_before=step.state,
            inner_stop=outcome.stop,
            step_state_after=outcome.step_run.state,
            role_dispatch_count=len(outcome.dispatches),
        ))
        return None

    def _escalate(
        self, project: ProjectRun, steps: tuple[StepRun, ...], action: _Action
    ) -> OuterLoopStop:
        code = action.escalation
        blocked = [s for s in steps if s.state in BLOCKED_STEP_STATES]
        listed = ", ".join(f"{s.step_id}={s.state.value}" for s in blocked[:_MAX_LISTED_STEPS])
        if len(blocked) > _MAX_LISTED_STEPS:
            listed += f" and {len(blocked) - _MAX_LISTED_STEPS} more"
        reason = (
            f"DL-3: blocked step run(s) {listed}; no recorded policy authorizes further "
            "scheduling or completion."
        )
        request = ProjectTransitionRequest(
            request_id=outer_request_id(
                self.project_run_id, project.state_version, f"escalate:{code}"
            ),
            expected_state_version=project.state_version,
            event=ProjectEvent.ESCALATE,
            reason=reason,
        )
        try:
            applied = self.store.apply_project_transition(self.project_run_id, request)
        except TransitionRefused as exc:
            self.refusal_code = exc.code
            return OuterLoopStop.TRANSITION_REFUSED
        if applied.duplicate:
            return OuterLoopStop.REPLAYED_RECEIPT
        self.escalation = code
        return action.stop

    # --- result -----------------------------------------------------------

    def _outcome(self, halt: OuterLoopStop) -> OuterLoopOutcome:
        project = self.store.get_project_run(self.project_run_id)
        steps = self.store.list_step_runs(self.project_run_id)
        plan = self.store.get_execution_plan(project.execution_plan_sha256)
        completion = _assess(project, plan, _plan_is_latest(self.store, project), steps)
        stop = halt
        if project.state is not ProjectState.ACTIVE and halt is not OuterLoopStop.STEP_BLOCKED:
            stop = OuterLoopStop.PROJECT_NOT_ACTIVE
        replan = tuple(
            step.step_id
            for step in steps
            if step.state is StepState.HUMAN_REQUIRED
            and (log := self.store.transitions_for(step.step_run_id))
            and log[-1].rule in _REPLAN_RULES
        )
        return OuterLoopOutcome(
            stop=stop,
            project_run=project,
            step_runs=steps,
            completion=completion,
            invocations=tuple(self.invocations),
            marked_ready=tuple(self.marked_ready),
            escalation=self.escalation,
            refusal_code=self.refusal_code,
            replan_recommended_step_ids=replan,
        )
