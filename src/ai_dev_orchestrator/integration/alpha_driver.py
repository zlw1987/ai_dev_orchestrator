"""DL-4B S7 — the non-model Alpha driver, run as the authority identity A.

The driver connects S0–S6 into one human-supervised Alpha. It holds no
authority of its own: it opens an integration session (S0's proof), reads what
the store has recorded, and calls the accepted store APIs and the DL-3 outer
loop, which keep every check they had. It never launches, runs, sends or signs
anything, and it never executes an X-side command; it **presents** them.

```text
status              recover() any recorded run, then report the stage and the next
                    action. Nothing else is written
request-approval    issue the challenge the current stage needs (contract, activation,
                    exact diff, or step acceptance after publishing the bundle), and
                    present it with its subject re-derived by the driver
record-approval     consume the attestation O placed in the inbox through the
                    stage's own store API
run                 the attempt invocation: DL-3 → DL-2 over the session's ports.
                    The human runs the two frozen X commands while A waits; the
                    driver announces each one. Ends held, at a human, or in recovery
decline-acceptance  the human declines a held acceptance: ESCALATE → HUMAN_REQUIRED
```

**The stage is derived, every time, from the store.** Each invocation reads
the Alpha definition O placed in the inbox, the store's re-proven inventory
(:meth:`~.integration_store.IntegrationStore.alpha_inventory`) and, once a
project run exists, the run after DL-1 ``recover()``. A verb that is not the
stage's next authorized action is refused with nothing written. No caller says
which stage it is, which run, which challenge, or whether a command
succeeded. A record the definition does not describe (another contract, plan,
approval or run) refuses everything.

**Durability is the store's.** An approval is recorded once (a replay is the
store's receipt); a project and step run are created only when the store holds
none; an interrupted attempt is reduced by ``recover()`` to
RECOVERY_REQUIRED and never resumed; a held decision is never re-planned
(DL-2 S6); a completion is applied once (the held ticket and challenge are
consumed with it).

Nothing here imports a model client, a harness, Git, ``subprocess``, a socket or
the CLI (static test). The production entry point (:func:`main`) takes only a
state root and a verb, requires an isolated interpreter, and opens
:func:`~.integration_session.open_integration_session`, which has no
injection point. See ``docs/DL4B_S7_ALPHA_DRIVER.md``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from ai_dev_orchestrator.control_plane.attestation_v2 import (
    ATTESTATION_NAMESPACE,
    ATTESTATION_STATEMENT_SCHEMA_VERSION,
    ApprovalChallengeV2,
    ApprovalSubjectKindV2,
    HumanAttestationV2,
    utc_text,
)
from ai_dev_orchestrator.control_plane.authority import AuthorityRefusedError, DispatchTicket, ExecutionPolicy
from ai_dev_orchestrator.control_plane.containment import AidoStateRoot, ContainmentError
from ai_dev_orchestrator.control_plane.contracts import ContractRefusedError, issue_step_contract
from ai_dev_orchestrator.control_plane.integration_records import (
    WriteScopeV1,
    exact_diff_approval_subject_v1_sha256,
    plan_activation_subject_v2_sha256,
    write_scopes_sha256,
)
from ai_dev_orchestrator.control_plane.models import (
    REQUIRED_PROJECT_CONTRACT_APPROVAL_TEXT,
    REQUIRED_STEP_ACCEPTANCE_APPROVAL_TEXT,
    ExecutionPlan,
    HumanStepAcceptance,
    PlannedStep,
    ProjectContract,
    ProjectContractApproval,
    ProjectContractContent,
    ProjectRun,
    ProjectState,
    StepContractProposal,
    StepRun,
    StepState,
)
from ai_dev_orchestrator.control_plane.outer_loop import OuterLoopInputError, ProjectOuterLoop
from ai_dev_orchestrator.control_plane.ports import RolePorts
from ai_dev_orchestrator.control_plane.store import RecoveryReport, StoreError
from ai_dev_orchestrator.control_plane.transitions import StepEvent, StepTransitionRequest, TransitionRefused
from ai_dev_orchestrator.integration import exchange
from ai_dev_orchestrator.integration.claim_receiver import CLAIM_WAIT_SECONDS, COMPLETE_NAME, STDOUT_NAME
from ai_dev_orchestrator.integration.integration_session import IntegrationSession, open_integration_session
from ai_dev_orchestrator.integration.integration_store import (
    AlphaInventory,
    IntegrationStore,
    OperatorDocument,
    RecordedExactDiffApproval,
)

REPORT_SCHEMA_VERSION = "alpha-driver-report.v1"
DEFINITION_SCHEMA_VERSION = "alpha-definition.v1"
#: The fixed inbox names O places the driver's inputs under (FD-14: O adds
#: files to the inbox; A reads them; X has no access).
DEFINITION_NAME = "alpha-definition.json"
ATTESTATION_NAMES = {
    ApprovalSubjectKindV2.PROJECT_CONTRACT: "attestation-project-contract.json",
    ApprovalSubjectKindV2.PLAN_ACTIVATION: "attestation-plan-activation.json",
    ApprovalSubjectKindV2.EXACT_DIFF_APPROVAL: "attestation-exact-diff-approval.json",
    ApprovalSubjectKindV2.STEP_ACCEPTANCE: "attestation-step-acceptance.json",
}
#: The frozen X-side commands, exactly as the human types them (unchanged).
CLI_NAME = "ai-dev-orchestrator"
WRITE_COMMAND = ("l2-apply-approved-file-edit", "--apply-approved-plan", "--write-approved-file")
REVIEW_COMMAND = ("l2-review-approved-file-edit", "--verify-approved-file-edit", "--real-reviewer")
DECLINE_REASON = "The human operator declined the held acceptance decision."

VERBS = ("status", "request-approval", "record-approval", "run", "decline-acceptance")


class AlphaStage(str, Enum):
    """Where the Alpha is, as derived from the store."""

    CONTRACT_APPROVAL = "contract_approval"
    PLAN_ACTIVATION = "plan_activation"
    EXACT_DIFF_APPROVAL = "exact_diff_approval"
    ATTEMPT = "attempt"
    DECISION = "decision"
    ACCEPTANCE = "acceptance"
    COMPLETE = "complete"
    HUMAN_REQUIRED = "human_required"
    RECOVERY_REQUIRED = "recovery_required"
    FAILED = "failed"
    UNTRUSTED = "untrusted"
    UNKNOWN = "unknown"


class DriverOutcome(str, Enum):
    """What the invocation ended at. Only the store's state decides it."""

    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    READY_TO_RUN = "READY_TO_RUN"
    AWAITING_HUMAN_ACCEPTANCE = "AWAITING_HUMAN_ACCEPTANCE"
    COMPLETE = "COMPLETE"
    HUMAN_REQUIRED = "HUMAN_REQUIRED"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    REFUSED = "REFUSED"


_APPROVAL_KIND = {
    AlphaStage.CONTRACT_APPROVAL: ApprovalSubjectKindV2.PROJECT_CONTRACT,
    AlphaStage.PLAN_ACTIVATION: ApprovalSubjectKindV2.PLAN_ACTIVATION,
    AlphaStage.EXACT_DIFF_APPROVAL: ApprovalSubjectKindV2.EXACT_DIFF_APPROVAL,
    AlphaStage.ACCEPTANCE: ApprovalSubjectKindV2.STEP_ACCEPTANCE,
}
_OUTCOME = {
    AlphaStage.CONTRACT_APPROVAL: DriverOutcome.APPROVAL_REQUIRED,
    AlphaStage.PLAN_ACTIVATION: DriverOutcome.APPROVAL_REQUIRED,
    AlphaStage.EXACT_DIFF_APPROVAL: DriverOutcome.APPROVAL_REQUIRED,
    AlphaStage.ATTEMPT: DriverOutcome.READY_TO_RUN,
    AlphaStage.DECISION: DriverOutcome.READY_TO_RUN,
    AlphaStage.ACCEPTANCE: DriverOutcome.AWAITING_HUMAN_ACCEPTANCE,
    AlphaStage.COMPLETE: DriverOutcome.COMPLETE,
    AlphaStage.HUMAN_REQUIRED: DriverOutcome.HUMAN_REQUIRED,
    AlphaStage.RECOVERY_REQUIRED: DriverOutcome.RECOVERY_REQUIRED,
    AlphaStage.FAILED: DriverOutcome.HUMAN_REQUIRED,
    AlphaStage.UNTRUSTED: DriverOutcome.HUMAN_REQUIRED,
}
_TERMINAL_STEP = {
    StepState.COMPLETE: AlphaStage.COMPLETE,
    StepState.HUMAN_REQUIRED: AlphaStage.HUMAN_REQUIRED,
    StepState.RECOVERY_REQUIRED: AlphaStage.RECOVERY_REQUIRED,
    StepState.FAILED: AlphaStage.FAILED,
}
#: Stages at which the Alpha has ended; nothing more is ever run.
_ENDED = frozenset({AlphaStage.COMPLETE, AlphaStage.HUMAN_REQUIRED, AlphaStage.RECOVERY_REQUIRED,
                    AlphaStage.FAILED, AlphaStage.UNTRUSTED})
_EXIT_CODES = {
    DriverOutcome.APPROVAL_REQUIRED: 0, DriverOutcome.READY_TO_RUN: 0,
    DriverOutcome.AWAITING_HUMAN_ACCEPTANCE: 0, DriverOutcome.COMPLETE: 0,
    DriverOutcome.REFUSED: 1, DriverOutcome.HUMAN_REQUIRED: 2, DriverOutcome.RECOVERY_REQUIRED: 3,
}


# =============================================================================
# the Alpha definition (O's input; not authority)
# =============================================================================


class AlphaDefinitionV1(BaseModel):
    """``alpha-definition.v1``: the one-step Alpha O defines, placed in the
    inbox. It is never authority. Everything the store records from it is
    bound by a human signature over a subject the driver presents, and the
    store re-validates every value (FD-8a's Alpha profile, the scope, the
    config, the artifact)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["alpha-definition.v1"]
    project_contract: ProjectContractContent
    step: PlannedStep
    execution_policy: ExecutionPolicy
    write_scope: WriteScopeV1
    step_contract_proposal: StepContractProposal
    approved_diff_name: str
    project_config_name: str

    @model_validator(mode="after")
    def _consistent(self) -> AlphaDefinitionV1:
        if not self.step.step_id == self.write_scope.step_id == self.step_contract_proposal.step_id:
            raise ValueError("the step, the write scope and the step contract proposal name different steps.")
        if self.step.depends_on:
            raise ValueError("the Alpha's one step depends on nothing.")
        reserved = {DEFINITION_NAME, *ATTESTATION_NAMES.values()}
        names = (self.approved_diff_name, self.project_config_name)
        if len(set(names)) != 2 or set(names) & reserved:
            raise ValueError("the artifact and config inbox names are distinct and not the driver's own names.")
        return self

    def plan_for(self, contract: ProjectContract) -> ExecutionPlan:
        """The one execution plan this definition activates under ``contract``."""
        return ExecutionPlan(schema_version="execution-plan.v1", project_id=contract.project_id,
                             project_contract_sha256=contract.sha256, plan_version=1,
                             supersedes_sha256=None, steps=(self.step,))


def parse_definition(data: bytes) -> AlphaDefinitionV1:
    """Strictly parse ``alpha-definition.v1`` bytes: one UTF-8 JSON object
    with no duplicate keys. Raises :class:`ValueError`."""
    def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        keys = [key for key, _ in pairs]
        if len(keys) != len(set(keys)):
            raise ValueError("the definition repeats a key.")
        return dict(pairs)

    if type(data) is not bytes:
        raise ValueError("the definition is bytes.")
    try:
        document = json.loads(data.decode("utf-8"), object_pairs_hook=no_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"the definition is not one UTF-8 JSON object ({type(exc).__name__}).") from None
    if type(document) is not dict:
        raise ValueError("the definition is not one JSON object.")
    try:
        return AlphaDefinitionV1.model_validate_json(json.dumps(document), strict=True)
    except ValidationError as exc:
        raise ValueError(f"the definition does not validate ({exc.error_count()} errors).") from None


def contract_for(content: ProjectContractContent, attestation: HumanAttestationV2) -> ProjectContract:
    """The Project Contract a human's contract attestation approves: the
    content, with exactly the attested approver and time."""
    return ProjectContract(content=content, approval=ProjectContractApproval(
        approved_by=attestation.approver_id, approved_at=attestation.attested_at,
        approval_text=REQUIRED_PROJECT_CONTRACT_APPROVAL_TEXT, source="manual",
        contract_sha256=content.sha256,
    ))


# =============================================================================
# the report
# =============================================================================


@dataclass(frozen=True)
class DriverReport:
    """What one invocation did and what comes next. A presentation for the
    human, never an input to AIDO (no API reads it back)."""

    verb: str
    outcome: DriverOutcome
    stage: AlphaStage
    state_root_id: str | None = None
    identity_boundary_sha256: str | None = None
    production: bool | None = None
    refusal: dict | None = None
    run: dict | None = None
    challenge: ApprovalChallengeV2 | None = None
    subject: dict | None = None
    statement_template: dict | None = None
    attestation_inbox_name: str | None = None
    held: dict | None = None
    announced_x_actions: tuple[dict, ...] = ()
    dl3_stop: str | None = None
    recovery: dict | None = None
    next_actions: tuple[dict, ...] = ()

    def document(self) -> dict:
        return {
            "schema_version": REPORT_SCHEMA_VERSION,
            "verb": self.verb,
            "outcome": self.outcome.value,
            "stage": self.stage.value,
            "state_root_id": self.state_root_id,
            "identity_boundary_sha256": self.identity_boundary_sha256,
            "production": self.production,
            "refusal": self.refusal,
            "run": self.run,
            "challenge": None if self.challenge is None else self.challenge.model_dump(mode="json"),
            "subject": self.subject,
            "statement_template": self.statement_template,
            "attestation_inbox_name": self.attestation_inbox_name,
            "held": self.held,
            "announced_x_actions": list(self.announced_x_actions),
            "dl3_stop": self.dl3_stop,
            "recovery": self.recovery,
            "next_actions": list(self.next_actions),
        }

    def to_json(self) -> str:
        return json.dumps(self.document(), indent=2, sort_keys=True, ensure_ascii=True)

    @property
    def exit_code(self) -> int:
        return _EXIT_CODES[self.outcome]


#: What a verb reports as a refusal rather than raising: every refusal the
#: store, the containment checks and the models raise, and an unreadable file.
#: A BaseException (a crash) is never caught.
_REFUSALS = (AuthorityRefusedError, TransitionRefused, StoreError, ContainmentError, ContractRefusedError,
             ValueError, OSError)


class _Refusal(Exception):
    """This invocation is not authorized now, or an input refused. Nothing
    the driver itself would have written was written."""

    def __init__(self, category: str, detail: str) -> None:
        self.category = category
        self.detail = detail
        super().__init__(f"{category}: {detail}")


@dataclass
class _Context:
    """The stage, derived from re-proven reads. Rebuilt for every decision."""

    definition: AlphaDefinitionV1
    inventory: AlphaInventory
    stage: AlphaStage
    contract: ProjectContract | None = None
    plan: ExecutionPlan | None = None
    approval: RecordedExactDiffApproval | None = None
    project: ProjectRun | None = None
    step: StepRun | None = None
    held: Any = None
    recovery: RecoveryReport | None = None


def _action(actor: str, action: str, **details: Any) -> dict:
    return {"actor": actor, "action": action, **details}


def _x_action(paths: Any, role: str, ticket_id: str) -> dict:
    """The exact X-side step for one dispatch: the frozen command, unchanged,
    with stdout redirected byte for byte by ``cmd.exe`` into the ticket's
    outbox, then the empty completion marker."""
    handoff, outbox = exchange.ticket_directories(paths.exchange_root, ticket_id)
    command, *flags = WRITE_COMMAND if role == "implementer" else REVIEW_COMMAND
    config = f"{handoff}\\{exchange.HANDOFF_CONFIG_NAME}"
    artifact = f"{handoff}\\{exchange.HANDOFF_ARTIFACT_NAME}"
    stdout, marker = f"{outbox}\\{STDOUT_NAME}", f"{outbox}\\{COMPLETE_NAME}"
    argv = (CLI_NAME, command, "--project-config", config, "--approved-diff-proposal", artifact, *flags)
    return _action(
        "X", "run_frozen_write_command" if role == "implementer" else "run_frozen_review_command",
        role=role, ticket_id=ticket_id, handoff_directory=handoff, outbox_directory=outbox, argv=list(argv),
        cmd_exe_lines=[
            " ".join(f'"{a}"' if " " in a or "\\" in a else a for a in argv) + f' > "{stdout}"',
            f'type nul > "{marker}"',
        ],
        shell="cmd.exe in X's own interactive session (never PowerShell 5.1 '>', which writes UTF-16)",
        reviewer_environment="this console only" if role == "verifier" else "none",
        a_waits_seconds=CLAIM_WAIT_SECONDS,
        claim_classification="execution claim: refused or labeled, never proof",
    )


class _AnnouncedImplementer:
    """DL-2's implementer port: announce the X step, then the session's own
    write handoff adapter, unchanged. The announcement is display only."""

    __slots__ = ("_port", "_announce")

    def __init__(self, port: Any, announce: Callable[[str, object], None]) -> None:
        self._port, self._announce = port, announce

    def implement(self, *, step_contract, attempt, dispatch):
        self._announce("implementer", dispatch)
        return self._port.implement(step_contract=step_contract, attempt=attempt, dispatch=dispatch)


class _AnnouncedVerifier:
    """DL-2's verifier port: announce the X step, then the session's own
    execution claim adapter, unchanged."""

    __slots__ = ("_port", "_announce")

    def __init__(self, port: Any, announce: Callable[[str, object], None]) -> None:
        self._port, self._announce = port, announce

    def verify(self, *, step_contract, attempt, dispatch):
        self._announce("verifier", dispatch)
        return self._port.verify(step_contract=step_contract, attempt=attempt, dispatch=dispatch)


class _NoTester:
    """The Alpha has no tester role; DL-2 never dispatches one."""

    def propose_tests(self, **kwargs: Any):
        raise AuthorityRefusedError("the Alpha has no tester role.")


def _request_id(*parts: object) -> str:
    material = ":".join(str(part) for part in ("dl4b-s7", *parts))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]


# =============================================================================
# the driver
# =============================================================================


class AlphaDriver:
    """The A-side driver over one open integration session.

    It keeps nothing between invocations, and nothing it remembers within one
    decides anything: every verb re-derives the stage from the store first.
    ``announce`` receives each X-side step the attempt hands off (display only;
    the default prints nothing).
    """

    def __init__(self, session: IntegrationSession, *,
                 announce: Callable[[dict], None] | None = None) -> None:
        if type(session) is not IntegrationSession:
            raise TypeError("the Alpha driver runs over an IntegrationSession.")
        if announce is not None and not callable(announce):
            raise TypeError("announce must be callable.")
        self._session = session
        self._store: IntegrationStore = session.store
        self._announce_to = announce
        self._announced: list[dict] = []
        self._paths: Any = None

    # --- verbs --------------------------------------------------------------

    def status(self) -> DriverReport:
        """The stage and the next action. Writes nothing except what DL-1's
        ``recover()`` writes for an interrupted run."""
        return self._invoke("status", None)

    def request_approval(self) -> DriverReport:
        """Issue and present the challenge the current stage needs."""
        return self._invoke("request-approval", self._request_approval)

    def record_approval(self) -> DriverReport:
        """Consume the stage's attestation from the inbox through the stage's
        own store API."""
        return self._invoke("record-approval", self._record_approval)

    def run(self) -> DriverReport:
        """The attempt (or the decision at ACCEPTANCE): DL-3 → DL-2."""
        return self._invoke("run", self._run)

    def decline_acceptance(self) -> DriverReport:
        """The human declines the held acceptance decision."""
        return self._invoke("decline-acceptance", self._decline)

    def invoke(self, verb: str) -> DriverReport:
        if type(verb) is not str or verb not in VERBS:
            raise ValueError(f"verb must be one of {', '.join(VERBS)}.")
        return {
            "status": self.status, "request-approval": self.request_approval,
            "record-approval": self.record_approval, "run": self.run,
            "decline-acceptance": self.decline_acceptance,
        }[verb]()

    # --- the frame every verb runs in -----------------------------------------

    def _invoke(self, verb: str, body: Callable[[_Context], dict | None] | None) -> DriverReport:
        """Derive the stage, run ``body`` against it, then derive it again
        from the store for the report. ``status`` has no body. A refusal of the
        driver's own is raised before the body changes any lifecycle state, so
        it reports the stage it was derived at; any other failure re-derives."""
        self._announced = []
        try:
            ctx = self._derive()
        except _Refusal as refusal:
            return self._refused(verb, refusal, None)
        except _REFUSALS as exc:
            return self._refused(verb, _Refusal(_category(exc), str(exc)), None)
        if body is None:
            return self._report(verb, ctx)
        try:
            extra = body(ctx) or {}
        except _Refusal as refusal:
            return self._refused(verb, refusal, ctx)
        except (*_REFUSALS, OuterLoopInputError) as exc:
            return self._refused(verb, _Refusal(_category(exc), str(exc)), self._rederive(), before=ctx.stage)
        after = self._rederive()
        if after is None:
            return self._refused(verb, _Refusal("state_unreadable", "the store could not be re-read."), None)
        return self._report(verb, after, **extra)

    def _rederive(self) -> _Context | None:
        try:
            return self._derive()
        except (_Refusal, *_REFUSALS):
            return None

    # --- deriving the stage ----------------------------------------------------

    def _inbox(self, name: str, category: str) -> OperatorDocument:
        """An operator document, or a refusal naming it. A boundary failure
        (a subclass) is not an unreadable document: it propagates."""
        try:
            return self._store.read_inbox_document(name)
        except AuthorityRefusedError as exc:
            if type(exc) is not AuthorityRefusedError:
                raise
            raise _Refusal(category, str(exc)) from None

    def _definition(self) -> AlphaDefinitionV1:
        data = self._inbox(DEFINITION_NAME, "definition_unreadable").content
        try:
            return parse_definition(data)
        except ValueError as exc:
            raise _Refusal("definition_invalid", str(exc)) from None

    def _derive(self) -> _Context:
        store = self._store
        definition = self._definition()
        inventory = store.alpha_inventory()
        self._paths = inventory.boundary.paths
        ctx = _Context(definition=definition, inventory=inventory, stage=AlphaStage.UNKNOWN)

        content = definition.project_contract
        if [c for c in inventory.project_contracts if c.sha256 != content.sha256]:
            raise _Refusal("foreign_record",
                           "the state root records a project contract this definition does not describe.")
        ctx.contract = inventory.project_contracts[0] if inventory.project_contracts else None
        if ctx.contract is None:
            if inventory.execution_plans or inventory.exact_diff_approvals or inventory.project_run_ids:
                raise _Refusal("foreign_record",
                               "the state root records work under no approved contract of this definition.")
            ctx.stage = AlphaStage.CONTRACT_APPROVAL
            return ctx

        expected = definition.plan_for(ctx.contract)
        if [p for p in inventory.execution_plans if p.sha256 != expected.sha256]:
            raise _Refusal("foreign_record",
                           "the state root records an execution plan this definition does not describe.")
        if not inventory.execution_plans:
            if inventory.exact_diff_approvals or inventory.project_run_ids:
                raise _Refusal("foreign_record", "the state root records work under no activated plan.")
            ctx.stage = AlphaStage.PLAN_ACTIVATION
            return ctx
        ctx.plan = expected

        step_id = definition.step.step_id
        for approval in inventory.exact_diff_approvals:
            if (approval.execution_plan_sha256, approval.step_id) != (expected.sha256, step_id):
                raise _Refusal("foreign_record", "the state root records an exact-diff approval for another step.")
        ctx.approval = inventory.exact_diff_approvals[0] if inventory.exact_diff_approvals else None

        if len(inventory.project_run_ids) > 1:
            raise _Refusal("foreign_record", "the state root records more than one project run; the Alpha has one.")
        if not inventory.project_run_ids:
            if ctx.approval is None:
                ctx.stage = AlphaStage.EXACT_DIFF_APPROVAL
            elif ctx.approval.spent:
                ctx.stage = AlphaStage.UNTRUSTED  # a spent approval with no run explains nothing
            else:
                ctx.stage = AlphaStage.ATTEMPT
            return ctx

        run_id = inventory.project_run_ids[0]
        ctx.recovery = store.recover(run_id)
        if not ctx.recovery.integrity_ok:
            ctx.stage = AlphaStage.UNTRUSTED
            return ctx
        ctx.project = store.get_project_run(run_id)
        if (ctx.project.project_contract_sha256, ctx.project.execution_plan_sha256) != (
            ctx.contract.sha256, expected.sha256
        ):
            raise _Refusal("foreign_record", "the recorded project run is not this definition's run.")
        steps = store.list_step_runs(run_id)
        if len(steps) > 1:
            raise _Refusal("foreign_record", "the recorded project run has more than the Alpha's one step.")
        ctx.step = steps[0] if steps else None
        if ctx.step is not None and ctx.step.step_contract_sha256 != self._step_contract(ctx).sha256:
            raise _Refusal("foreign_record", "the recorded step run is not this definition's step contract.")

        step = ctx.step
        if step is not None and step.state in _TERMINAL_STEP:
            ctx.stage = _TERMINAL_STEP[step.state]
        elif ctx.project.state is not ProjectState.ACTIVE:
            ctx.stage = AlphaStage.HUMAN_REQUIRED
        elif step is None or step.state in (StepState.PLANNED, StepState.READY):
            if step is not None and step.attempt != 0:
                ctx.stage = AlphaStage.UNTRUSTED
            elif ctx.approval is None:
                ctx.stage = AlphaStage.EXACT_DIFF_APPROVAL
            elif ctx.approval.spent:
                ctx.stage = AlphaStage.UNTRUSTED
            else:
                ctx.stage = AlphaStage.ATTEMPT
        elif step.state is StepState.ACCEPTANCE:
            ctx.held = store.held_acceptance_decision(step.step_run_id, expected_state_version=step.state_version)
            ctx.stage = AlphaStage.DECISION if ctx.held is None else AlphaStage.ACCEPTANCE
        else:
            # In flight after recover() is impossible; never resume it.
            ctx.stage = AlphaStage.RECOVERY_REQUIRED
        return ctx

    def _step_contract(self, ctx: _Context):
        policy = ctx.definition.execution_policy
        return issue_step_contract(ctx.definition.step_contract_proposal, project_contract=ctx.contract,
                                   execution_plan=ctx.plan, review_required=policy.review_required,
                                   human_acceptance_required=policy.human_acceptance_required,
                                   max_attempts=policy.max_attempts)

    # --- request-approval -------------------------------------------------------

    def _request_approval(self, ctx: _Context) -> dict:
        kind = _APPROVAL_KIND.get(ctx.stage)
        if kind is None:
            raise _Refusal("no_pending_approval", f"no human approval is pending at stage {ctx.stage.value}.")
        store, definition = self._store, ctx.definition
        if kind is ApprovalSubjectKindV2.PROJECT_CONTRACT:
            challenge = store.request_project_contract_approval(definition.project_contract)
            subject, expected = {
                "kind": kind.value,
                "project_contract_content": definition.project_contract.model_dump(mode="json"),
                "project_contract_sha256": definition.project_contract.sha256,
            }, definition.project_contract.sha256
        elif kind is ApprovalSubjectKindV2.PLAN_ACTIVATION:
            plan = definition.plan_for(ctx.contract)
            challenge = store.request_plan_activation(execution_plan=plan, execution_policy=definition.execution_policy,
                                                      write_scopes=(definition.write_scope,))
            subject, expected = self._activation_subject(ctx.contract, plan, definition)
        elif kind is ApprovalSubjectKindV2.EXACT_DIFF_APPROVAL:
            challenge = store.request_exact_diff_approval(
                execution_plan_sha256=ctx.plan.sha256, step_id=definition.step.step_id,
                artifact_name=definition.approved_diff_name, config_name=definition.project_config_name)
            subject, expected = self._exact_diff_subject(ctx, definition)
        else:
            # The store publishes (or re-verifies) the bundle in published/
            # before it issues the challenge; the bundle is then re-read.
            challenge = store.request_step_acceptance(ctx.step.step_run_id)
            bundle = store.held_acceptance_bundle(ctx.step.step_run_id)
            subject, expected = {
                "kind": kind.value,
                "bundle_name": bundle.name,
                "bundle_sha256": bundle.sha256,
                "published_directory": self._paths.published,
                "published_files": [name for name, _ in bundle.files],
                "step_acceptance_subject_v2": bundle.subject.model_dump(mode="json"),
                "step_acceptance_subject_sha256": bundle.subject.sha256,
                "decline": "run decline-acceptance instead of signing; nothing is signed to decline",
            }, bundle.subject.sha256
        if challenge.subject_kind is not kind or challenge.subject_sha256 != expected:
            raise _Refusal("subject_unconfirmed",
                           "the driver's re-derived subject is not the challenge's subject; do not sign it.")
        if kind is ApprovalSubjectKindV2.STEP_ACCEPTANCE:
            # Not recomputed here: the v2 subject binds digests of the store's
            # re-proven records. What is confirmed is that the challenge names
            # exactly the subject of the bundle O reads in published/.
            subject["subject_sha256_matches_published_bundle"] = expected
        else:
            subject["subject_sha256_recomputed_by_driver"] = expected
        return {"challenge": challenge, "subject": subject,
                "statement_template": self._statement_template(challenge),
                "attestation_inbox_name": ATTESTATION_NAMES[kind]}

    def _activation_subject(self, contract: ProjectContract, plan: ExecutionPlan,
                            definition: AlphaDefinitionV1) -> tuple[dict, str]:
        workspace = self._session.state_root.authorize_target_workspace(self._paths.clone)
        scope = definition.write_scope
        values = dict(
            project_contract_sha256=contract.sha256, execution_plan_sha256=plan.sha256,
            execution_policy_sha256=definition.execution_policy.sha256, target_workspace_sha256=workspace.sha256,
            write_scopes_sha256=write_scopes_sha256((scope,)), project_config_sha256=scope.project_config_sha256,
            identity_boundary_sha256=self._session.boundary_sha256,
        )
        subject = {
            "kind": ApprovalSubjectKindV2.PLAN_ACTIVATION.value,
            "execution_plan": plan.model_dump(mode="json"),
            "execution_policy": definition.execution_policy.model_dump(mode="json"),
            "write_scope": scope.model_dump(mode="json"),
            "target_workspace": self._paths.clone,
            **values,
        }
        return subject, plan_activation_subject_v2_sha256(**values)

    def _exact_diff_subject(self, ctx: _Context, definition: AlphaDefinitionV1) -> tuple[dict, str]:
        activation, activation_sha256 = self._activation_subject(ctx.contract, ctx.plan, definition)
        artifact = self._inbox(definition.approved_diff_name, "artifact_unreadable")
        config = self._inbox(definition.project_config_name, "config_unreadable")
        values = dict(
            plan_activation_subject_sha256=activation_sha256, execution_plan_sha256=ctx.plan.sha256,
            step_id=definition.step.step_id, write_scope_sha256=definition.write_scope.sha256,
            approved_diff_artifact_sha256=artifact.sha256,
        )
        subject = {
            "kind": ApprovalSubjectKindV2.EXACT_DIFF_APPROVAL.value,
            "write_scope": definition.write_scope.model_dump(mode="json"),
            "approved_diff_inbox_name": definition.approved_diff_name,
            "project_config_inbox_name": definition.project_config_name,
            "project_config_sha256": config.sha256,
            "approval_time_rule": "attested_at must equal the artifact's DiffEditApproval approved_at exactly",
            **values,
        }
        return subject, exact_diff_approval_subject_v1_sha256(**values)

    def _statement_template(self, challenge: ApprovalChallengeV2) -> dict:
        """``attestation-statement.v1`` with O's three fields left open. O's
        helper (:mod:`.alpha_operator`) fills them; the verifier rebuilds the
        statement itself, so this template is never authority."""
        return {
            "schema_version": ATTESTATION_STATEMENT_SCHEMA_VERSION,
            "namespace": ATTESTATION_NAMESPACE,
            "state_root_id": self._session.state_root.root_id,
            "challenge_id": challenge.challenge_id,
            "subject_kind": challenge.subject_kind.value,
            "subject_sha256": challenge.subject_sha256,
            "approver_id": None,
            "key_fingerprint_sha256": None,
            "attested_at": None,
            "expires_at": utc_text(challenge.expires_at),
            "approval_text": challenge.required_approval_text,
        }

    # --- record-approval --------------------------------------------------------

    def _attestation(self, kind: ApprovalSubjectKindV2) -> HumanAttestationV2:
        name = ATTESTATION_NAMES[kind]
        data = self._inbox(name, "attestation_unreadable").content
        try:
            attestation = HumanAttestationV2.model_validate_json(data)
        except ValidationError as exc:
            raise _Refusal("attestation_invalid", f"inbox/{name} is not a human-attestation.v2 "
                                                  f"({exc.error_count()} errors).") from None
        if attestation.subject_kind is not kind:
            raise _Refusal("attestation_kind_mismatch", f"inbox/{name} answers a {attestation.subject_kind.value} "
                                                        f"challenge, not {kind.value}.")
        return attestation

    def _record_approval(self, ctx: _Context) -> None:
        kind = _APPROVAL_KIND.get(ctx.stage)
        if kind is None:
            raise _Refusal("no_pending_approval", f"no human approval is pending at stage {ctx.stage.value}.")
        attestation = self._attestation(kind)
        store, definition = self._store, ctx.definition
        if kind is ApprovalSubjectKindV2.PROJECT_CONTRACT:
            store.record_approved_project_contract(contract_for(definition.project_contract, attestation), attestation)
        elif kind is ApprovalSubjectKindV2.PLAN_ACTIVATION:
            store.issue_execution_plan(definition.plan_for(ctx.contract), execution_policy=definition.execution_policy,
                                       write_scopes=(definition.write_scope,), attestation=attestation)
        elif kind is ApprovalSubjectKindV2.EXACT_DIFF_APPROVAL:
            store.record_exact_diff_approval(attestation)
        else:
            self._complete(ctx, attestation)

    def _complete(self, ctx: _Context, attestation: HumanAttestationV2) -> None:
        """DECIDE_ACCEPTANCE over the held decision with the signed v2
        acceptance (S6). The store re-proves the hold, the envelope, the
        bundle and the signature, and consumes the held ticket and the
        challenge with COMPLETE."""
        step, held = ctx.step, ctx.held
        acceptance = HumanStepAcceptance(
            step_contract_sha256=step.step_contract_sha256, attempt=step.attempt,
            approved_by=attestation.approver_id, approved_at=attestation.attested_at,
            approval_text=REQUIRED_STEP_ACCEPTANCE_APPROVAL_TEXT, source="manual",
        )
        request = StepTransitionRequest(
            request_id=_request_id(step.step_run_id, step.state_version, "accept", attestation.sha256),
            expected_state_version=step.state_version, event=StepEvent.DECIDE_ACCEPTANCE,
            planner_decision=held.envelope.output, human_acceptance=acceptance,
        )
        self._store.apply_step_transition(step.step_run_id, request, role_output=held.envelope,
                                          human_attestation=attestation)
        return None

    # --- run and decline --------------------------------------------------------

    def _run(self, ctx: _Context) -> dict:
        if ctx.stage not in (AlphaStage.ATTEMPT, AlphaStage.DECISION):
            raise _Refusal("not_runnable", f"nothing may be run at stage {ctx.stage.value}.")
        store = self._store
        if ctx.stage is AlphaStage.ATTEMPT:
            contract = store.issue_authorized_step_contract(ctx.definition.step_contract_proposal,
                                                            execution_plan_sha256=ctx.plan.sha256)
            if ctx.project is None:
                ctx.project = store.create_project_run(project_contract_sha256=ctx.contract.sha256,
                                                       execution_plan_sha256=ctx.plan.sha256)
            if ctx.step is None:
                store.create_step_run(project_run_id=ctx.project.project_run_id,
                                      step_contract_sha256=contract.sha256)
        return {"dl3_stop": self._outer_loop(ctx)}

    def _decline(self, ctx: _Context) -> None:
        if ctx.stage is not AlphaStage.ACCEPTANCE:
            raise _Refusal("nothing_to_decline", f"no held acceptance exists at stage {ctx.stage.value}.")
        step = ctx.step
        request = StepTransitionRequest(
            request_id=_request_id(step.step_run_id, step.state_version, "decline"),
            expected_state_version=step.state_version, event=StepEvent.ESCALATE, reason=DECLINE_REASON,
        )
        self._store.apply_step_transition(step.step_run_id, request)
        return None

    def _outer_loop(self, ctx: _Context) -> str:
        store, session = self._store, self._session
        ports = RolePorts(planner=session.planner, tester=_NoTester(),
                          implementer=_AnnouncedImplementer(session.implementer, self._announce),
                          verifier=_AnnouncedVerifier(session.verifier, self._announce),
                          reviewer=session.reviewer)
        project = store.get_project_run(ctx.project.project_run_id)
        outcome = ProjectOuterLoop(store, ports).run(project_run=project, project_contract=ctx.contract,
                                                     execution_plan=ctx.plan)
        return outcome.stop.value

    def _announce(self, role: str, dispatch: object) -> None:
        if type(dispatch) is not DispatchTicket:
            return  # the adapter refuses it; there is nothing to present
        action = _x_action(self._paths, role, dispatch.ticket_id)
        self._announced.append(action)
        if self._announce_to is not None:
            self._announce_to(action)

    # --- reports -----------------------------------------------------------------

    def _base(self, ctx: _Context | None) -> dict:
        session = self._session
        base: dict[str, Any] = {"state_root_id": session.state_root.root_id,
                                "identity_boundary_sha256": session.boundary_sha256,
                                "production": session.is_production,
                                "announced_x_actions": tuple(self._announced)}
        if ctx is None:
            return base
        if ctx.project is not None:
            base["run"] = {
                "project_run_id": ctx.project.project_run_id,
                "project_state": ctx.project.state.value,
                "step_run_id": None if ctx.step is None else ctx.step.step_run_id,
                "step_state": None if ctx.step is None else ctx.step.state.value,
                "step_state_version": None if ctx.step is None else ctx.step.state_version,
                "attempt": None if ctx.step is None else ctx.step.attempt,
            }
        if ctx.held is not None:
            base["held"] = {"ticket_id": ctx.held.ticket_id, "envelope_sha256": ctx.held.envelope_sha256,
                            "subject_sha256": ctx.held.subject_sha256, "held_at": ctx.held.held_at.isoformat(),
                            "recommendation": ctx.held.envelope.output.recommendation.value}
        if ctx.recovery is not None:
            base["recovery"] = {"integrity_ok": ctx.recovery.integrity_ok,
                                "integrity_issues": list(ctx.recovery.integrity_issues),
                                "recovered_step_run_ids": list(ctx.recovery.recovered_step_run_ids),
                                "escalated_step_run_ids": list(ctx.recovery.escalated_step_run_ids)}
        return base

    def _report(self, verb: str, ctx: _Context, **extra: Any) -> DriverReport:
        return DriverReport(verb=verb, outcome=_OUTCOME[ctx.stage], stage=ctx.stage,
                            next_actions=_next_actions(ctx.stage, verb, bool(extra.get("challenge"))),
                            **{**self._base(ctx), **extra})

    def _refused(self, verb: str, refusal: _Refusal, ctx: _Context | None, *,
                 before: AlphaStage | None = None) -> DriverReport:
        """A refused invocation. If the failure itself moved the Alpha into an
        ended stage (an attempt reduced to recovery, an untrusted run
        escalated), the outcome is that stage's; the refusal is kept."""
        stage = AlphaStage.UNKNOWN if ctx is None else ctx.stage
        outcome = DriverOutcome.REFUSED
        if ctx is not None and before is not None and stage is not before and stage in _ENDED:
            outcome = _OUTCOME[stage]
        actions = (_action("O", "inspect", detail="the invocation was refused and changed nothing the driver "
                                                  "would have written; no retry is automatic"),)
        if ctx is not None:
            actions += _next_actions(stage, verb, False)
        return DriverReport(verb=verb, outcome=outcome, stage=stage,
                            refusal={"category": refusal.category, "detail": refusal.detail},
                            next_actions=actions, **self._base(ctx))


def _category(exc: Exception) -> str:
    category = getattr(exc, "category", None)
    if category is not None:
        return f"{type(exc).__name__}:{getattr(category, 'value', category)}"
    return type(exc).__name__


def _next_actions(stage: AlphaStage, verb: str, issued: bool) -> tuple[dict, ...]:
    kind = _APPROVAL_KIND.get(stage)
    if kind is not None and stage is not AlphaStage.ACCEPTANCE:
        steps = () if issued else (_action("A", "request-approval"),)
        return steps + (
            _action("O", "review_subject_and_sign", kind=kind.value,
                    detail="review the presented subject; prepare the statement with alpha_operator; sign it "
                           "with the security key; place the attestation in the inbox"),
            _action("O", "place_attestation", inbox_name=ATTESTATION_NAMES[kind]),
            _action("A", "record-approval"),
        )
    if stage is AlphaStage.ACCEPTANCE:
        steps = () if issued else (_action("A", "request-approval",
                                           detail="publishes the acceptance bundle and issues the challenge"),)
        return steps + (
            _action("O", "inspect_bundle", detail="read the bundle in published/: aido_observed facts versus "
                                                  "execution_claims; the model's verdict is not permission"),
            _action("O", "accept_or_decline",
                    detail="to accept: sign the step-acceptance statement and place "
                           f"{ATTESTATION_NAMES[ApprovalSubjectKindV2.STEP_ACCEPTANCE]}, then A record-approval; "
                           "to decline: A decline-acceptance (nothing is signed)"),
        )
    if stage in (AlphaStage.ATTEMPT, AlphaStage.DECISION):
        return (_action("A", "run", detail="the long attempt invocation; it announces each X step and waits for "
                                           "its completion marker"),)
    if stage is AlphaStage.COMPLETE:
        return (_action("O", "close_out", detail="archive the state root; an administrator disables X"),)
    if stage in (AlphaStage.HUMAN_REQUIRED, AlphaStage.RECOVERY_REQUIRED, AlphaStage.FAILED, AlphaStage.UNTRUSTED):
        return (_action("O", "inspect", detail="the Alpha has ended: no retry, repair, rollback or cleanup "
                                               "(E-10); inspect the clone and the store as they are"),)
    return ()


# =============================================================================
# the production entry point
# =============================================================================


def _isolated() -> bool:
    flags = sys.flags
    return bool(flags.isolated or (flags.ignore_environment and flags.no_user_site and flags.safe_path))


def main(argv: list[str] | None = None) -> int:
    """``python -I -m ai_dev_orchestrator.integration.alpha_driver --state-root <dir> <verb>``.

    Production only: the session is :func:`open_integration_session` (S0's
    live proof; no injection point). The report is printed to stdout as JSON,
    each announced X step as it happens. The exit code is 0 for
    APPROVAL_REQUIRED, READY_TO_RUN, AWAITING_HUMAN_ACCEPTANCE and COMPLETE,
    1 for REFUSED, 2 for HUMAN_REQUIRED and 3 for RECOVERY_REQUIRED.
    """
    parser = argparse.ArgumentParser(prog="alpha_driver", description="DL-4B S7 non-model Alpha driver (A).")
    parser.add_argument("--state-root", required=True)
    parser.add_argument("verb", choices=VERBS)
    args = parser.parse_args(argv)

    def emit(document: dict) -> None:
        sys.stdout.write(json.dumps(document, indent=2, sort_keys=True, ensure_ascii=True) + "\n\n")
        sys.stdout.flush()

    def refused(category: str, detail: str) -> int:
        report = DriverReport(verb=args.verb, outcome=DriverOutcome.REFUSED, stage=AlphaStage.UNKNOWN,
                              refusal={"category": category, "detail": detail})
        emit(report.document())
        return report.exit_code

    if not _isolated():
        return refused("interpreter_not_isolated", "A runs Python only with -I (S0 §8 item 1).")
    try:
        root = AidoStateRoot.open(args.state_root)
        session = open_integration_session(root)
    except (AuthorityRefusedError, StoreError, ContainmentError, OSError, ValueError) as exc:
        return refused(_category(exc), str(exc))
    with session:
        report = AlphaDriver(session, announce=emit).invoke(args.verb)
    emit(report.document())
    return report.exit_code


if __name__ == "__main__":  # pragma: no cover - the production launch
    raise SystemExit(main())
