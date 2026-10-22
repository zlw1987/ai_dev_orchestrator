"""DL-1 — the deterministic transition validator (roadmap §15).

Ordinary deterministic code: no model, no I/O, no clock. Its inputs are the
persisted run snapshot, the step's issued contract, AIDO-computed facts, and a
typed transition *request*. A request names an **event**, never a target state;
the target is chosen here by fixed rules, so no role output can name the state
it wants.

Two outcomes, kept distinct:

- **refusal** (:class:`TransitionRefused`): the request is invalid, stale,
  out of order, a duplicate conflict, or mis-bound. Nothing changes;
- **an authorized transition**, which may itself be an escalation to
  ``HUMAN_REQUIRED`` when the inputs are valid but do not support progress.

The rules that must not exist (roadmap §15.1) do not: a reviewer verdict only
records a fact and moves REVIEWING to ACCEPTANCE, and a Planner recommendation
reaches COMPLETE only together with an AIDO-observed ``verified`` outcome, an
``approve`` verdict when review is required, and a bound human acceptance when
the contract requires one. Any other combination escalates (§15.4).

Persisting an authorized transition is the store's job; this module only
decides.
"""

from __future__ import annotations

import hashlib
from enum import Enum
from typing import Annotated, Literal

from pydantic import Field, StrictInt, field_validator, model_validator

from ai_dev_orchestrator.control_plane.models import (
    IN_FLIGHT_STEP_STATES,
    MAX_RATIONALE_CHARS,
    TERMINAL_PROJECT_STATES,
    TERMINAL_STEP_STATES,
    HumanStepAcceptance,
    ImplementationReport,
    PlannerDecision,
    PlannerRecommendation,
    ProjectRun,
    ProjectState,
    ReviewProposal,
    ReviewVerdict,
    StepContract,
    StepRun,
    StepState,
    VerificationObservation,
    VerificationOutcome,
    _Strict,
    _text,
    canonical_json_bytes,
    is_hex32,
)


class StepEvent(str, Enum):
    MARK_READY = "mark_ready"
    BEGIN_ATTEMPT = "begin_attempt"
    IMPLEMENTATION_RETURNED = "implementation_returned"
    VERIFICATION_OBSERVED = "verification_observed"
    REVIEW_OBSERVED = "review_observed"
    DECIDE_ACCEPTANCE = "decide_acceptance"
    ESCALATE = "escalate"
    RECOVER_INTERRUPTED = "recover_interrupted"


class ProjectEvent(str, Enum):
    ESCALATE = "escalate"
    REQUEST_COMPLETE = "request_complete"


class RefusalCode(str, Enum):
    STALE_STATE_VERSION = "stale_state_version"
    OUT_OF_ORDER = "out_of_order"
    TERMINAL_STATE = "terminal_state"
    PROJECT_NOT_ACTIVE = "project_not_active"
    CONTRACT_MISMATCH = "contract_mismatch"
    BINDING_MISMATCH = "binding_mismatch"
    DEPENDENCIES_INCOMPLETE = "dependencies_incomplete"
    HUMAN_ACCEPTANCE_MISSING = "human_acceptance_missing"
    DUPLICATE_REQUEST_CONFLICT = "duplicate_request_conflict"
    INVALID_REQUEST = "invalid_request"
    UNSUPPORTED_IN_DL1 = "unsupported_in_dl1"


class TransitionRefused(Exception):
    """The request was refused and no state changed."""

    def __init__(self, code: RefusalCode, message: str) -> None:
        super().__init__(f"{code.value}: {message}")
        self.code = code


# The payload each step event requires. Every other payload must be absent.
_STEP_EVENT_PAYLOAD: dict[StepEvent, str | None] = {
    StepEvent.MARK_READY: None,
    StepEvent.BEGIN_ATTEMPT: None,
    StepEvent.IMPLEMENTATION_RETURNED: "implementation",
    StepEvent.VERIFICATION_OBSERVED: "verification",
    StepEvent.REVIEW_OBSERVED: "review",
    StepEvent.DECIDE_ACCEPTANCE: "planner_decision",
    StepEvent.ESCALATE: "reason",
    StepEvent.RECOVER_INTERRUPTED: "reason",
}
_PAYLOAD_FIELDS = ("implementation", "verification", "review", "planner_decision", "reason")


def _request_id(value: str) -> str:
    if not is_hex32(value):
        raise ValueError("request_id must be 32 lowercase hexadecimal characters.")
    return value


class StepTransitionRequest(_Strict):
    """One requested step event, its idempotency key and its version guard.

    ``request_id`` is AIDO's idempotency key: replaying the identical request
    returns the recorded result, and reusing the key for a different request is
    refused. ``expected_state_version`` must equal the persisted version, so a
    request built against a superseded snapshot is refused as stale.
    """

    request_id: str
    expected_state_version: Annotated[StrictInt, Field(ge=0)]
    event: StepEvent
    implementation: ImplementationReport | None = None
    verification: VerificationObservation | None = None
    review: ReviewProposal | None = None
    planner_decision: PlannerDecision | None = None
    human_acceptance: HumanStepAcceptance | None = None
    reason: str | None = None

    @field_validator("request_id")
    @classmethod
    def _id(cls, value: str) -> str:
        return _request_id(value)

    @field_validator("reason")
    @classmethod
    def _reason(cls, value: str | None) -> str | None:
        return None if value is None else _text(value, "reason", MAX_RATIONALE_CHARS)

    @model_validator(mode="after")
    def _payload_matches_event(self) -> StepTransitionRequest:
        required = _STEP_EVENT_PAYLOAD[self.event]
        for name in _PAYLOAD_FIELDS:
            present = getattr(self, name) is not None
            if name == required and not present:
                raise ValueError(f"event {self.event.value} requires {name}.")
            if name != required and present:
                raise ValueError(f"event {self.event.value} does not accept {name}.")
        if self.human_acceptance is not None and self.event is not StepEvent.DECIDE_ACCEPTANCE:
            raise ValueError("human_acceptance is accepted only with decide_acceptance.")
        return self

    @property
    def request_sha256(self) -> str:
        return hashlib.sha256(canonical_json_bytes(self.model_dump(mode="json"))).hexdigest()


class ProjectTransitionRequest(_Strict):
    request_id: str
    expected_state_version: Annotated[StrictInt, Field(ge=0)]
    event: ProjectEvent
    reason: str

    @field_validator("request_id")
    @classmethod
    def _id(cls, value: str) -> str:
        return _request_id(value)

    @field_validator("reason")
    @classmethod
    def _reason(cls, value: str) -> str:
        return _text(value, "reason", MAX_RATIONALE_CHARS)

    @property
    def request_sha256(self) -> str:
        return hashlib.sha256(canonical_json_bytes(self.model_dump(mode="json"))).hexdigest()


class StepTransition(_Strict):
    """An authorized step transition, not yet persisted.

    ``rule`` names the fixed rule that chose ``to_state``. ``project_effect`` is
    the project state the store must move the project to in the same database
    transaction, when the step outcome concerns the whole project.
    """

    from_state: StepState
    to_state: StepState
    from_version: int
    to_version: int
    attempt: int
    verification_outcome: VerificationOutcome | None
    review_verdict: ReviewVerdict | None
    rule: str
    project_effect: Literal[ProjectState.HUMAN_REQUIRED, ProjectState.RECOVERY_REQUIRED] | None = None


class ProjectTransition(_Strict):
    from_state: ProjectState
    to_state: ProjectState
    from_version: int
    to_version: int
    rule: str


def _check_binding(payload: object | None, contract: StepContract, step: StepRun) -> None:
    if payload is None:
        return
    if payload.step_contract_sha256 != contract.sha256 or payload.attempt != step.attempt:
        raise TransitionRefused(
            RefusalCode.BINDING_MISMATCH,
            "the role output is bound to a different step contract or attempt.",
        )


def decide_step_transition(
    *,
    step: StepRun,
    contract: StepContract,
    project_state: ProjectState,
    dependencies_complete: bool,
    request: StepTransitionRequest,
) -> StepTransition:
    """Authorize or refuse one step event. Pure and deterministic.

    ``dependencies_complete`` is an AIDO-computed fact (every dependency's step
    run is COMPLETE); it is only consulted for ``mark_ready``.
    """
    if step.step_contract_sha256 != contract.sha256:
        raise TransitionRefused(
            RefusalCode.CONTRACT_MISMATCH, "the supplied contract is not the step's bound contract."
        )
    if request.expected_state_version != step.state_version:
        raise TransitionRefused(
            RefusalCode.STALE_STATE_VERSION,
            f"expected state version {request.expected_state_version}, persisted version is "
            f"{step.state_version}.",
        )
    if step.state in TERMINAL_STEP_STATES:
        raise TransitionRefused(
            RefusalCode.TERMINAL_STATE, f"step is {step.state.value}; no DL-1 rule leaves it."
        )
    authority_reducing = request.event in (StepEvent.ESCALATE, StepEvent.RECOVER_INTERRUPTED)
    if project_state is not ProjectState.ACTIVE and not authority_reducing:
        raise TransitionRefused(
            RefusalCode.PROJECT_NOT_ACTIVE, f"project is {project_state.value}."
        )
    for payload in (
        request.implementation,
        request.verification,
        request.review,
        request.planner_decision,
        request.human_acceptance,
    ):
        _check_binding(payload, contract, step)

    def move(
        to_state: StepState,
        rule: str,
        *,
        attempt: int | None = None,
        verification: VerificationOutcome | None = step.verification_outcome,
        review: ReviewVerdict | None = step.review_verdict,
        project_effect: ProjectState | None = None,
    ) -> StepTransition:
        return StepTransition(
            from_state=step.state,
            to_state=to_state,
            from_version=step.state_version,
            to_version=step.state_version + 1,
            attempt=step.attempt if attempt is None else attempt,
            verification_outcome=verification,
            review_verdict=review,
            rule=rule,
            project_effect=project_effect,
        )

    def require(state: StepState) -> None:
        if step.state is not state:
            raise TransitionRefused(
                RefusalCode.OUT_OF_ORDER,
                f"{request.event.value} requires {state.value}; step is {step.state.value}.",
            )

    event = request.event
    if event is StepEvent.ESCALATE:
        return move(StepState.HUMAN_REQUIRED, "escalated_by_aido")

    if event is StepEvent.RECOVER_INTERRUPTED:
        if step.state not in IN_FLIGHT_STEP_STATES:
            raise TransitionRefused(
                RefusalCode.OUT_OF_ORDER,
                f"recovery applies only to an in-flight step; step is {step.state.value}.",
            )
        return move(
            StepState.RECOVERY_REQUIRED,
            "interrupted_external_effect_unproven",
            project_effect=ProjectState.RECOVERY_REQUIRED,
        )

    if event is StepEvent.MARK_READY:
        require(StepState.PLANNED)
        if not dependencies_complete:
            raise TransitionRefused(
                RefusalCode.DEPENDENCIES_INCOMPLETE, "a dependency step is not COMPLETE."
            )
        return move(StepState.READY, "dependencies_complete")

    if event is StepEvent.BEGIN_ATTEMPT:
        require(StepState.READY)
        if step.attempt >= contract.max_attempts:
            raise TransitionRefused(
                RefusalCode.OUT_OF_ORDER, "the step contract's attempt budget is spent."
            )
        # Persisted before any worker request is issued: the intent is durable
        # first, so an interruption is always visible as an in-flight state.
        return move(
            StepState.EXECUTING,
            "attempt_started",
            attempt=step.attempt + 1,
            verification=None,
            review=None,
        )

    if event is StepEvent.IMPLEMENTATION_RETURNED:
        require(StepState.EXECUTING)
        # The report's claims are deliberately not consulted: verification
        # decides what the change achieved, not the worker's account of it.
        return move(StepState.VERIFYING, "implementation_returned")

    if event is StepEvent.VERIFICATION_OBSERVED:
        require(StepState.VERIFYING)
        outcome = request.verification.outcome
        if outcome == "workspace-state-untrusted":
            # The 5F2D exit-3 class: never repaired, never resumed.
            return move(
                StepState.RECOVERY_REQUIRED,
                "workspace_state_untrusted",
                verification=outcome,
                project_effect=ProjectState.RECOVERY_REQUIRED,
            )
        if outcome == "verified" and contract.review_required:
            return move(StepState.REVIEWING, "verified_review_required", verification=outcome)
        return move(StepState.ACCEPTANCE, "verification_recorded", verification=outcome)

    if event is StepEvent.REVIEW_OBSERVED:
        require(StepState.REVIEWING)
        return move(StepState.ACCEPTANCE, "review_recorded", review=request.review.verdict)

    # DECIDE_ACCEPTANCE
    require(StepState.ACCEPTANCE)
    decision = request.planner_decision
    recommendation = decision.recommendation
    if request.human_acceptance is not None and (
        recommendation is not PlannerRecommendation.RECOMMEND_STEP_ACCEPT
    ):
        raise TransitionRefused(
            RefusalCode.BINDING_MISMATCH,
            "a human acceptance applies only to a RECOMMEND_STEP_ACCEPT decision.",
        )

    if recommendation is PlannerRecommendation.PROJECT_CONTRACT_CONFLICT:
        return move(
            StepState.HUMAN_REQUIRED,
            "project_contract_conflict",
            project_effect=ProjectState.HUMAN_REQUIRED,
        )
    if recommendation is PlannerRecommendation.RECOMMEND_RETRY_IMPLEMENTATION:
        if step.attempt >= contract.max_attempts:
            return move(StepState.FAILED, "attempt_budget_exhausted")
        return move(StepState.READY, "retry_implementation_authorized")
    if recommendation is PlannerRecommendation.RECOMMEND_STEP_ACCEPT:
        if step.verification_outcome != "verified":
            return move(StepState.HUMAN_REQUIRED, "accept_recommended_without_verified_outcome")
        if contract.review_required and step.review_verdict != "approve":
            return move(StepState.HUMAN_REQUIRED, "accept_recommended_without_review_approval")
        if contract.human_acceptance_required and request.human_acceptance is None:
            raise TransitionRefused(
                RefusalCode.HUMAN_ACCEPTANCE_MISSING,
                "the step contract requires a bound human acceptance.",
            )
        return move(StepState.COMPLETE, "acceptance_authorized")
    # RECOMMEND_RETRY_TEST, RECOMMEND_REPLAN, PLAN_CONFLICT, HUMAN_REQUIRED:
    # DL-1 has no Tester execution and no re-plan, so each ends at a human.
    return move(StepState.HUMAN_REQUIRED, f"planner_{recommendation.value.lower()}")


def decide_integrity_escalation(step: StepRun) -> StepTransition:
    """The one rule for a step whose persisted state cannot be trusted.

    It takes no request and checks no version, because the inputs a request
    would be validated against are exactly what is in doubt. It can only ever
    reduce authority: whatever the step claims to be, it becomes HUMAN_REQUIRED,
    including a claimed COMPLETE the transition log does not explain.
    """
    return StepTransition(
        from_state=step.state,
        to_state=StepState.HUMAN_REQUIRED,
        from_version=step.state_version,
        to_version=step.state_version + 1,
        attempt=step.attempt,
        verification_outcome=step.verification_outcome,
        review_verdict=step.review_verdict,
        rule="state_integrity_failed",
    )


def decide_project_transition(
    *, project: ProjectRun, request: ProjectTransitionRequest
) -> ProjectTransition:
    """Authorize or refuse one project event. Pure and deterministic."""
    if request.expected_state_version != project.state_version:
        raise TransitionRefused(
            RefusalCode.STALE_STATE_VERSION,
            f"expected state version {request.expected_state_version}, persisted version is "
            f"{project.state_version}.",
        )
    if project.state in TERMINAL_PROJECT_STATES:
        raise TransitionRefused(
            RefusalCode.TERMINAL_STATE, f"project is {project.state.value}."
        )
    if request.event is ProjectEvent.REQUEST_COMPLETE:
        # Every step COMPLETE does not imply the project is (roadmap §20). The
        # integration gate does not exist in DL-1, so nothing can complete one.
        raise TransitionRefused(
            RefusalCode.UNSUPPORTED_IN_DL1,
            "project completion requires the project integration gate, which DL-1 does not "
            "implement.",
        )
    return ProjectTransition(
        from_state=project.state,
        to_state=ProjectState.HUMAN_REQUIRED,
        from_version=project.state_version,
        to_version=project.state_version + 1,
        rule="escalated_by_aido",
    )


# How severe each project state is when a step outcome propagates upward. A
# propagation never lowers severity.
_PROJECT_SEVERITY = {
    ProjectState.ACTIVE: 0,
    ProjectState.RECOVERY_REQUIRED: 1,
    ProjectState.HUMAN_REQUIRED: 2,
    ProjectState.COMPLETE: 3,
}


def propagated_project_state(current: ProjectState, effect: ProjectState) -> ProjectState | None:
    """The project state a step's ``project_effect`` produces, or ``None`` if
    the project already is at least that severe."""
    if _PROJECT_SEVERITY[effect] > _PROJECT_SEVERITY[current]:
        return effect
    return None
