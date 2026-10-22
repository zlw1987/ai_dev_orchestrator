"""DL-1 — typed control-plane contracts, runs, decisions and role proposals.

This module is the data half of the DL-1 offline control-plane foundation (the
M5A subset described in ``docs/AIDO_RUNTIME_HARNESS_ROADMAP.md`` §10–§15). It
holds schemas and identity rules only.

What this module deliberately cannot do:

- **No execution.** Nothing here runs a command, launches a process, opens a
  socket, calls a model, reads an environment variable, or touches a workspace.
  Path-like and command-like text is never interpreted.
- **No authority by construction.** Building a model here authorizes nothing.
  The only authority path is :mod:`ai_dev_orchestrator.control_plane.transitions`
  (the deterministic validator) applied through
  :mod:`ai_dev_orchestrator.control_plane.store` (which persists before it
  reports).

The authority layers (roadmap §10) map onto the types like this:

```text
ProjectContract        human-authoritative; carries an exact-phrase approval
                       bound to the content digest; AIDO never edits it
ExecutionPlan          AIDO-controlled, versioned by content digest, chained
                       to its predecessor; binds one ProjectContract
StepContract           derived per step, versioned by content digest; binds one
                       ProjectContract and one ExecutionPlan; issued only by
                       AIDO (``issue_step_contract``), never by a role
Role proposals         StepContractProposal, PlannerDecision, TestProposal,
                       ImplementationReport, ReviewProposal — inputs only
```

Every model is ``extra="forbid"`` and frozen, so a role output carrying a field
such as ``next_state``, ``authoritative`` or ``max_attempts`` is rejected rather
than stripped. Identity is a SHA-256 over canonical JSON, on the
``task_revision`` precedent: a contract change that leaves its identity unchanged
is impossible.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    field_validator,
    model_validator,
)

PROJECT_CONTRACT_SCHEMA_VERSION = "project-contract.v1"
EXECUTION_PLAN_SCHEMA_VERSION = "execution-plan.v1"
STEP_CONTRACT_SCHEMA_VERSION = "step-contract.v1"

# The exact sentences a human must write. Compared with ``==``: a paraphrase, a
# different case, or extra whitespace is not approval (the PlanApproval rule).
REQUIRED_PROJECT_CONTRACT_APPROVAL_TEXT = (
    "I approve this project contract for AIDO execution"
)
REQUIRED_STEP_ACCEPTANCE_APPROVAL_TEXT = "I approve accepting this step attempt"

# A step contract's verification authority names project configuration. It is
# never a command string, and the plan's ``required_verification`` prose never
# becomes one (roadmap §14.3).
VERIFICATION_AUTHORITY_PROJECT_CONFIG = "project_config.controlled_verification"

MAX_TEXT_CHARS = 4_000
MAX_RATIONALE_CHARS = 2_000
MAX_REF_CHARS = 200
MAX_ITEMS = 50
MAX_EVIDENCE_REFS = 20
MAX_PLAN_STEPS = 50
#: The largest attempt budget AIDO will issue to one step contract.
MAX_STEP_ATTEMPTS = 5

_SLUG = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_HEX32 = re.compile(r"^[0-9a-f]{32}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")

# Mirrors of shipped vocabularies. They are restated, not imported, because the
# shipped modules import the writer, the verification runner and httpx, and
# this package must stay free of every executing module. Tests pin each mirror
# to its source so the two cannot drift.
VerificationOutcome = Literal["verified", "verification-failed", "workspace-state-untrusted"]
ReviewVerdict = Literal["approve", "changes_requested", "needs_human_review"]


class StepState(str, Enum):
    """Step lifecycle (roadmap §12.3). Names are DL-1's, not frozen."""

    PLANNED = "PLANNED"
    READY = "READY"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    REVIEWING = "REVIEWING"
    ACCEPTANCE = "ACCEPTANCE"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    HUMAN_REQUIRED = "HUMAN_REQUIRED"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"


#: No DL-1 rule leaves these states. A human resolution of HUMAN_REQUIRED and a
#: re-proof out of RECOVERY_REQUIRED are later, separately authorized work.
TERMINAL_STEP_STATES = frozenset(
    {
        StepState.COMPLETE,
        StepState.FAILED,
        StepState.HUMAN_REQUIRED,
        StepState.RECOVERY_REQUIRED,
    }
)

#: States entered *before* an external side effect is requested (worker,
#: verification, review). After an interruption AIDO cannot prove whether that
#: effect happened, so recovery never resumes them (roadmap §12.4).
IN_FLIGHT_STEP_STATES = frozenset(
    {StepState.EXECUTING, StepState.VERIFYING, StepState.REVIEWING}
)


class ProjectState(str, Enum):
    """Project lifecycle. ``COMPLETE`` exists but no DL-1 rule reaches it."""

    ACTIVE = "ACTIVE"
    COMPLETE = "COMPLETE"
    HUMAN_REQUIRED = "HUMAN_REQUIRED"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"


TERMINAL_PROJECT_STATES = frozenset({ProjectState.COMPLETE, ProjectState.HUMAN_REQUIRED})


class PlannerRecommendation(str, Enum):
    """The closed PlannerDecision vocabulary (roadmap §11.1).

    A recommendation is an input to the validator, never a state to enter.
    """

    RECOMMEND_STEP_ACCEPT = "RECOMMEND_STEP_ACCEPT"
    RECOMMEND_RETRY_IMPLEMENTATION = "RECOMMEND_RETRY_IMPLEMENTATION"
    RECOMMEND_RETRY_TEST = "RECOMMEND_RETRY_TEST"
    RECOMMEND_REPLAN = "RECOMMEND_REPLAN"
    PLAN_CONFLICT = "PLAN_CONFLICT"
    PROJECT_CONTRACT_CONFLICT = "PROJECT_CONTRACT_CONFLICT"
    HUMAN_REQUIRED = "HUMAN_REQUIRED"


def canonical_json_bytes(data: Any) -> bytes:
    """Serialize JSON-ready data canonically: sorted keys, no spaces, UTF-8."""
    return json.dumps(
        data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def model_sha256(model: BaseModel) -> str:
    """The content identity of a model: SHA-256 over its canonical JSON."""
    return hashlib.sha256(canonical_json_bytes(model.model_dump(mode="json"))).hexdigest()


def _text(value: str, field_name: str, max_chars: int = MAX_TEXT_CHARS) -> str:
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty or whitespace-only.")
    if len(value) > max_chars:
        raise ValueError(f"{field_name} must be at most {max_chars} characters.")
    return value


def _texts(
    values: tuple[str, ...], field_name: str, *, required: bool, max_chars: int = MAX_TEXT_CHARS
) -> tuple[str, ...]:
    if required and not values:
        raise ValueError(f"{field_name} must contain at least one item.")
    if len(values) > MAX_ITEMS:
        raise ValueError(f"{field_name} must contain at most {MAX_ITEMS} items.")
    for item in values:
        _text(item, f"{field_name} item", max_chars)
    if len(set(values)) != len(values):
        raise ValueError(f"{field_name} must not contain duplicates.")
    return values


def _slug(value: str, field_name: str) -> str:
    if not _SLUG.fullmatch(value):
        raise ValueError(
            f"{field_name} must be 1-64 characters of lowercase ASCII letters, digits, "
            "'.', '_' or '-', starting with a letter or digit."
        )
    return value


def _hex64(value: str, field_name: str) -> str:
    if not _HEX64.fullmatch(value):
        raise ValueError(f"{field_name} must be 64 lowercase hexadecimal characters.")
    return value


def _aware(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must carry a UTC offset.")
    return value


class _Strict(BaseModel):
    """Frozen, and rejects unknown fields so forged extras fail loudly."""

    model_config = ConfigDict(extra="forbid", frozen=True)


Sha256 = Annotated[str, Field(min_length=64, max_length=64)]
PositiveInt = Annotated[StrictInt, Field(ge=1)]


# --- Project Contract (human-authoritative, AIDO-immutable) -----------------


class ProjectContractContent(_Strict):
    """The human-authored product intent. Its digest is the contract identity."""

    schema_version: Literal["project-contract.v1"]
    project_id: str
    goal: str
    requirements: tuple[str, ...]
    protected_invariants: tuple[str, ...] = ()
    acceptance_criteria: tuple[str, ...]
    human_decision_boundaries: tuple[str, ...] = ()

    @field_validator("project_id")
    @classmethod
    def _project_id(cls, value: str) -> str:
        return _slug(value, "project_id")

    @field_validator("goal")
    @classmethod
    def _goal(cls, value: str) -> str:
        return _text(value, "goal")

    @field_validator("requirements", "acceptance_criteria")
    @classmethod
    def _required_lists(cls, value: tuple[str, ...], info) -> tuple[str, ...]:
        return _texts(value, info.field_name, required=True)

    @field_validator("protected_invariants", "human_decision_boundaries")
    @classmethod
    def _optional_lists(cls, value: tuple[str, ...], info) -> tuple[str, ...]:
        return _texts(value, info.field_name, required=False)

    @property
    def sha256(self) -> str:
        return model_sha256(self)


class ProjectContractApproval(_Strict):
    """A human's approval of exactly one contract content digest.

    Every field is required: there is no approval by omission. A model never
    writes this block, and neither does AIDO; writing it is the human act.
    """

    approved_by: str
    approved_at: datetime
    approval_text: str
    source: Literal["manual"]
    contract_sha256: Sha256

    @field_validator("approved_by")
    @classmethod
    def _approved_by(cls, value: str) -> str:
        return _text(value, "approved_by", MAX_REF_CHARS)

    @field_validator("approved_at")
    @classmethod
    def _approved_at(cls, value: datetime) -> datetime:
        return _aware(value, "approved_at")

    @field_validator("approval_text")
    @classmethod
    def _approval_text(cls, value: str) -> str:
        if value != REQUIRED_PROJECT_CONTRACT_APPROVAL_TEXT:
            raise ValueError(
                "approval_text must match the required approval phrase exactly; "
                "a paraphrase is not approval."
            )
        return value

    @field_validator("contract_sha256")
    @classmethod
    def _contract_sha256(cls, value: str) -> str:
        return _hex64(value, "contract_sha256")


class ProjectContract(_Strict):
    """Approved content. The approval must name this content's digest exactly."""

    content: ProjectContractContent
    approval: ProjectContractApproval

    @model_validator(mode="after")
    def _approval_binds_content(self) -> ProjectContract:
        if self.approval.contract_sha256 != self.content.sha256:
            raise ValueError(
                "approval.contract_sha256 does not match the contract content; the "
                "approval belongs to a different contract."
            )
        return self

    @property
    def sha256(self) -> str:
        """The contract identity: the digest of the approved content."""
        return self.content.sha256

    @property
    def project_id(self) -> str:
        return self.content.project_id


# --- Execution Plan (AIDO-controlled, versioned) ----------------------------


class PlannedStep(_Strict):
    step_id: str
    objective: str
    depends_on: tuple[str, ...] = ()

    @field_validator("step_id")
    @classmethod
    def _step_id(cls, value: str) -> str:
        return _slug(value, "step_id")

    @field_validator("objective")
    @classmethod
    def _objective(cls, value: str) -> str:
        return _text(value, "objective")

    @field_validator("depends_on")
    @classmethod
    def _depends_on(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for item in value:
            _slug(item, "depends_on item")
        if len(set(value)) != len(value):
            raise ValueError("depends_on must not contain duplicates.")
        return value


class ExecutionPlan(_Strict):
    """One version of the plan. Version N names version N-1's digest.

    A step may depend only on steps listed *before* it, so every valid plan is
    acyclic by construction and no cycle detection is needed.
    """

    schema_version: Literal["execution-plan.v1"]
    project_id: str
    project_contract_sha256: Sha256
    plan_version: PositiveInt
    supersedes_sha256: Sha256 | None = None
    steps: tuple[PlannedStep, ...]

    @field_validator("project_id")
    @classmethod
    def _project_id(cls, value: str) -> str:
        return _slug(value, "project_id")

    @field_validator("project_contract_sha256", "supersedes_sha256")
    @classmethod
    def _digests(cls, value: str | None, info) -> str | None:
        return None if value is None else _hex64(value, info.field_name)

    @model_validator(mode="after")
    def _shape(self) -> ExecutionPlan:
        if (self.plan_version == 1) != (self.supersedes_sha256 is None):
            raise ValueError(
                "supersedes_sha256 must be absent for plan_version 1 and present for "
                "every later version."
            )
        if not self.steps:
            raise ValueError("steps must contain at least one step.")
        if len(self.steps) > MAX_PLAN_STEPS:
            raise ValueError(f"steps must contain at most {MAX_PLAN_STEPS} steps.")
        seen: set[str] = set()
        for step in self.steps:
            if step.step_id in seen:
                raise ValueError(f"step_id {step.step_id!r} appears more than once.")
            for dependency in step.depends_on:
                if dependency not in seen:
                    raise ValueError(
                        f"step {step.step_id!r} depends on {dependency!r}, which is not "
                        "an earlier step in this plan."
                    )
            seen.add(step.step_id)
        return self

    @property
    def sha256(self) -> str:
        return model_sha256(self)

    def step(self, step_id: str) -> PlannedStep | None:
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None


# --- Step Contract (derived, versioned, AIDO-issued) ------------------------


class StepContract(_Strict):
    """The AIDO-issued statement of one unit of work and what makes it done.

    ``objective`` and ``depends_on`` are copied from the plan, the requirements
    and invariants come from a validated Planner proposal, and every policy
    field (review, human acceptance, attempt budget, verification authority) is
    set by AIDO. :func:`ai_dev_orchestrator.control_plane.contracts.validate_step_contract`
    is the single place those rules are checked, and the store re-runs it
    before persisting any contract, however it was built.
    """

    schema_version: Literal["step-contract.v1"]
    project_id: str
    project_contract_sha256: Sha256
    execution_plan_sha256: Sha256
    execution_plan_version: PositiveInt
    step_id: str
    step_contract_version: PositiveInt
    supersedes_sha256: Sha256 | None = None
    objective: str
    depends_on: tuple[str, ...] = ()
    requirements: tuple[str, ...]
    protected_invariants: tuple[str, ...] = ()
    verification_authority: Literal["project_config.controlled_verification"]
    review_required: StrictBool
    human_acceptance_required: StrictBool
    max_attempts: Annotated[StrictInt, Field(ge=1, le=MAX_STEP_ATTEMPTS)]

    @field_validator("project_id", "step_id")
    @classmethod
    def _slugs(cls, value: str, info) -> str:
        return _slug(value, info.field_name)

    @field_validator("project_contract_sha256", "execution_plan_sha256", "supersedes_sha256")
    @classmethod
    def _digests(cls, value: str | None, info) -> str | None:
        return None if value is None else _hex64(value, info.field_name)

    @field_validator("objective")
    @classmethod
    def _objective(cls, value: str) -> str:
        return _text(value, "objective")

    @field_validator("requirements")
    @classmethod
    def _requirements(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _texts(value, "requirements", required=True)

    @field_validator("protected_invariants")
    @classmethod
    def _invariants(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _texts(value, "protected_invariants", required=False)

    @model_validator(mode="after")
    def _version_chain(self) -> StepContract:
        if (self.step_contract_version == 1) != (self.supersedes_sha256 is None):
            raise ValueError(
                "supersedes_sha256 must be absent for step_contract_version 1 and "
                "present for every later version."
            )
        return self

    @property
    def sha256(self) -> str:
        return model_sha256(self)


# --- Role proposals (inputs only, never authority) --------------------------


class _BoundToAttempt(_Strict):
    """A role output naming the exact contract and attempt it was produced for.

    The validator refuses one whose binding differs from the step's current
    contract and attempt, so a stale or misrouted output cannot be replayed.
    """

    step_contract_sha256: Sha256
    attempt: PositiveInt

    @field_validator("step_contract_sha256")
    @classmethod
    def _contract(cls, value: str) -> str:
        return _hex64(value, "step_contract_sha256")


class StepContractProposal(_Strict):
    """A Planner's proposed step contract content. Never a contract by itself.

    There is no field for any policy value: a proposal naming ``max_attempts``,
    ``review_required`` or a verification command is rejected as an extra.
    """

    step_id: str
    requirements: tuple[str, ...]
    protected_invariants: tuple[str, ...] = ()

    @field_validator("step_id")
    @classmethod
    def _step_id(cls, value: str) -> str:
        return _slug(value, "step_id")

    @field_validator("requirements")
    @classmethod
    def _requirements(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _texts(value, "requirements", required=True)

    @field_validator("protected_invariants")
    @classmethod
    def _invariants(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _texts(value, "protected_invariants", required=False)


class PlannerDecision(_BoundToAttempt):
    """A Planner's structured judgment (roadmap §11.1).

    It carries a recommendation, a bounded user-visible rationale, and evidence
    references. It never names a state to enter, and it carries no private
    reasoning: there is no field for either.
    """

    recommendation: PlannerRecommendation
    rationale: str
    evidence_refs: tuple[str, ...] = ()

    @field_validator("rationale")
    @classmethod
    def _rationale(cls, value: str) -> str:
        return _text(value, "rationale", MAX_RATIONALE_CHARS)

    @field_validator("evidence_refs")
    @classmethod
    def _refs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) > MAX_EVIDENCE_REFS:
            raise ValueError(f"evidence_refs must contain at most {MAX_EVIDENCE_REFS} items.")
        return _texts(value, "evidence_refs", required=False, max_chars=MAX_REF_CHARS)


class TestProposal(_BoundToAttempt):
    """A Tester's proposed test. There is no authority field, and DL-1 has no
    issuer: a proposed test cannot become authoritative here (roadmap §17.3)."""

    __test__ = False  # not a pytest test class

    test_path: str
    description: str

    @field_validator("test_path")
    @classmethod
    def _path(cls, value: str) -> str:
        return _text(value, "test_path", MAX_REF_CHARS)

    @field_validator("description")
    @classmethod
    def _description(cls, value: str) -> str:
        return _text(value, "description")


class ImplementationReport(_BoundToAttempt):
    """What an Implementer says it did. Its claims are advisory and are never
    used to decide a transition; verification facts are (roadmap §19.2)."""

    summary: str
    claims: tuple[str, ...] = ()

    @field_validator("summary")
    @classmethod
    def _summary(cls, value: str) -> str:
        return _text(value, "summary")

    @field_validator("claims")
    @classmethod
    def _claims(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _texts(value, "claims", required=False)


class VerificationObservation(_BoundToAttempt):
    """An AIDO-observed verification fact and the digest of its evidence.

    This is the one input the validator treats as authoritative, so only AIDO's
    own deterministic verification may produce it. No DL-1 code does; DL-2 is
    expected to adapt the shipped 5F2D ``verification-result.v1`` outcome.
    """

    outcome: VerificationOutcome
    evidence_sha256: Sha256

    @field_validator("evidence_sha256")
    @classmethod
    def _evidence(cls, value: str) -> str:
        return _hex64(value, "evidence_sha256")


class ReviewProposal(_BoundToAttempt):
    """A Reviewer verdict: advisory, recorded as a fact, never a transition."""

    verdict: ReviewVerdict
    evidence_sha256: Sha256

    @field_validator("evidence_sha256")
    @classmethod
    def _evidence(cls, value: str) -> str:
        return _hex64(value, "evidence_sha256")


class HumanStepAcceptance(_BoundToAttempt):
    """A human's exact-phrase acceptance of one step attempt."""

    approved_by: str
    approved_at: datetime
    approval_text: str
    source: Literal["manual"]

    @field_validator("approved_by")
    @classmethod
    def _approved_by(cls, value: str) -> str:
        return _text(value, "approved_by", MAX_REF_CHARS)

    @field_validator("approved_at")
    @classmethod
    def _approved_at(cls, value: datetime) -> datetime:
        return _aware(value, "approved_at")

    @field_validator("approval_text")
    @classmethod
    def _approval_text(cls, value: str) -> str:
        if value != REQUIRED_STEP_ACCEPTANCE_APPROVAL_TEXT:
            raise ValueError(
                "approval_text must match the required approval phrase exactly; "
                "a paraphrase is not approval."
            )
        return value


# --- Runs (persisted snapshots; the store is their only writer) -------------


class ProjectRun(_Strict):
    project_run_id: str
    project_id: str
    project_contract_sha256: Sha256
    execution_plan_sha256: Sha256
    execution_plan_version: PositiveInt
    state: ProjectState
    state_version: Annotated[StrictInt, Field(ge=0)]

    @field_validator("project_run_id")
    @classmethod
    def _run_id(cls, value: str) -> str:
        if not _HEX32.fullmatch(value):
            raise ValueError("project_run_id must be 32 lowercase hexadecimal characters.")
        return value


class StepRun(_Strict):
    step_run_id: str
    project_run_id: str
    step_id: str
    step_contract_sha256: Sha256
    state: StepState
    state_version: Annotated[StrictInt, Field(ge=0)]
    attempt: Annotated[StrictInt, Field(ge=0, le=MAX_STEP_ATTEMPTS)]
    verification_outcome: VerificationOutcome | None = None
    review_verdict: ReviewVerdict | None = None

    @field_validator("step_run_id", "project_run_id")
    @classmethod
    def _run_ids(cls, value: str, info) -> str:
        if not _HEX32.fullmatch(value):
            raise ValueError(f"{info.field_name} must be 32 lowercase hexadecimal characters.")
        return value


def is_hex32(value: object) -> bool:
    return isinstance(value, str) and _HEX32.fullmatch(value) is not None
