"""5F3B-Q1-PRE1 -- per-candidate primary three-task sweep orchestrator.

**OFFLINE WIRING ONLY.** This module runs no Pi/Node process, opens no
socket, calls no model, and reads no real credential -- it composes
:func:`qualification.semantic_controller.run_semantic_task_attempt` three
times, once per frozen corpus task, in the frozen order (Sec. 12.6:
IQ-1 -> IQ-2 -> IQ-3), and then evaluates the accepted hard bar
(:mod:`qualification.hard_bar`) over whatever the three attempts actually
produced. It defines no live adapter, no candidate model, and no route to
B300/vLLM/LiteLLM -- see the module docstring in
:mod:`qualification.semantic_controller` for the identical, already-stated
scope boundary, which applies here unchanged.

Why a separate module from the controller
------------------------------------------

:func:`run_semantic_task_attempt` deliberately owns exactly ONE task
attempt's authority object graph (Sec. "ONE TASK, ONE AUTHORITY OBJECT
GRAPH") and mints its own fresh run correlation id, workspace, broker session
and runtime session on every call -- there is no parameter through which one
call could share state with another. This module is the THIN layer above it
that supplies the missing per-candidate concerns the design's §9/§12.6/§16
sections require and the single-attempt controller intentionally has no
opinion about:

- the fixed IQ-1 -> IQ-2 -> IQ-3 task order;
- a fresh adapter bundle per task (via an injected factory), so a future
  live-adapter phase can mint a genuinely fresh Pi/runtime/broker per task
  rather than reusing one long-lived adapter object across three attempts;
- the maximum-3-prompts-per-candidate accounting;
- evaluating the hard bar ONLY once all three tasks have a result, per
  :func:`qualification.hard_bar.evaluate_hard_bar`'s own precondition -- an
  incomplete 1-task or 2-task partial sweep never reaches a hard-bar verdict
  (Sec. 16's precondition, restated in this phase's own instructions).

Candidate A/B fairness
-----------------------

The identical function, :func:`run_primary_sweep`, drives both candidates.
The ONLY thing that differs between an A call and a B call is the
``candidate`` argument threaded through to
:func:`~qualification.semantic_controller.run_semantic_task_attempt`, which
itself resolves the model id from the single frozen
``qualification.records.CANDIDATE_MODEL_IDS`` mapping. No branch in this
module, or in the controller it calls, is conditioned on which candidate is
running.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

from .corpus import REQUIRED_TASKS, QualificationTask
from .hard_bar import HardBarResult, TaskHardBarFacts, evaluate_hard_bar
from .i2_credentials import ConnectionValues, PreflightGateResult
from .i2b_session import (
    BrokerCreationObservation,
    BrokerCreationRequest,
    BrokerSession,
    BrokerShutdownObservation,
    GetCommandsObservation,
    GetStateObservation,
    ProtocolObservation,
    RuntimeLaunchObservation,
    RuntimeLaunchRequest,
    RuntimeSession,
    RuntimeShutdownObservation,
)
from .records import CANDIDATE_MODEL_IDS
from .semantic_controller import SemanticTaskAttemptResult, run_semantic_task_attempt
from .semantic_session import (
    BrokerActivityObservation,
    FinalReportClaimsObservation,
    SemanticPromptRequest,
    SemanticTurnObservation,
)
from .validity import RunValidity

#: 3 tasks per candidate, exactly 1 semantic prompt per task (Sec. 9).
MAX_SEMANTIC_PROMPTS_PER_CANDIDATE: int = 3


class SweepInputError(ValueError):
    """An AIDO-supplied sweep argument is unusable. Refused before ANYTHING."""


@dataclass(frozen=True)
class TaskAdapterBundle:
    """Every injected adapter :func:`run_semantic_task_attempt` requires, for ONE task.

    A plain data holder -- no behavior, no validation beyond "every field is
    present and callable". Built fresh, per task, by the caller-supplied
    ``build_adapters`` factory in :func:`run_primary_sweep`, so a future live-
    adapter phase can mint a genuinely fresh Pi/runtime/broker per task
    rather than reusing one long-lived adapter object across three attempts.
    """

    non_secret_gates: tuple[Callable[[], PreflightGateResult], ...]
    read_connection: Callable[[], ConnectionValues]
    create_broker: Callable[[BrokerCreationRequest], BrokerCreationObservation]
    launch_runtime: Callable[[RuntimeLaunchRequest], RuntimeLaunchObservation]
    get_commands: Callable[[RuntimeSession], GetCommandsObservation]
    get_state: Callable[[RuntimeSession], GetStateObservation]
    observe_protocol: Callable[[RuntimeSession], ProtocolObservation]
    route_checker: Callable[..., object]
    send_semantic_prompt: Callable[[SemanticPromptRequest], SemanticTurnObservation]
    collect_broker_activity: Callable[[RuntimeSession], BrokerActivityObservation]
    collect_final_report_claims: Callable[[RuntimeSession], FinalReportClaimsObservation]
    shutdown_runtime: Callable[[RuntimeSession], RuntimeShutdownObservation]
    shutdown_broker: Callable[[BrokerSession], BrokerShutdownObservation]

    def __post_init__(self) -> None:
        if not isinstance(self.non_secret_gates, tuple):
            raise SweepInputError("TaskAdapterBundle.non_secret_gates must be a tuple")
        for name in (
            "read_connection", "create_broker", "launch_runtime", "get_commands",
            "get_state", "observe_protocol", "route_checker", "send_semantic_prompt",
            "collect_broker_activity", "collect_final_report_claims",
            "shutdown_runtime", "shutdown_broker",
        ):
            if not callable(getattr(self, name)):
                raise SweepInputError(f"TaskAdapterBundle.{name} must be callable")


@dataclass(frozen=True)
class PrimarySweepResult:
    """One candidate's complete (or partial) primary sweep outcome.

    ``task_results`` is keyed by task id, IN THE FROZEN ORDER
    :data:`~qualification.corpus.REQUIRED_TASKS` declares -- a dict preserves
    insertion order, so iterating it reproduces IQ-1 -> IQ-2 -> IQ-3.
    ``hard_bar_result`` is :data:`~qualification.hard_bar.QualificationState.INCOMPLETE`
    whenever any task lacks a ``VALID``, scoring-eligible result -- it is
    NEVER a partial verdict computed from fewer than three tasks; that
    precondition is :func:`qualification.hard_bar.evaluate_hard_bar`'s own,
    reused unmodified.

    ``total_semantic_prompts_sent`` counts only CONFIRMED-sent prompts
    (5F3B-Q1-PRE1-FU1): a task whose dispatch send-state was mechanically
    ``SEND_STATE_INDETERMINATE`` has ``semantic_prompts_sent = None`` and
    contributes ``0`` here -- this is a conservative resource-budget count
    (never over-claims a prompt was spent), never a claim that the task's
    send-state was confirmed 0. Every such task id is separately named in
    ``indeterminate_dispatch_task_ids`` so the ambiguity is never silently
    dropped.
    """

    candidate: str
    model_id: str
    task_results: dict[str, SemanticTaskAttemptResult]
    total_semantic_prompts_sent: int
    indeterminate_dispatch_task_ids: tuple[str, ...]
    hard_bar_result: HardBarResult

    def __post_init__(self) -> None:
        if self.candidate not in CANDIDATE_MODEL_IDS:
            raise SweepInputError(f"unknown candidate {self.candidate!r}")
        if self.model_id != CANDIDATE_MODEL_IDS[self.candidate]:
            raise SweepInputError(
                f"model_id {self.model_id!r} does not match candidate "
                f"{self.candidate!r}'s frozen pairing {CANDIDATE_MODEL_IDS[self.candidate]!r}"
            )
        if type(self.total_semantic_prompts_sent) is not int or not (
            0 <= self.total_semantic_prompts_sent <= MAX_SEMANTIC_PROMPTS_PER_CANDIDATE
        ):
            raise SweepInputError(
                "PrimarySweepResult.total_semantic_prompts_sent must be in "
                f"[0, {MAX_SEMANTIC_PROMPTS_PER_CANDIDATE}]"
            )
        expected = self.total_semantic_prompts_sent == sum(
            (r.semantic_prompts_sent or 0) for r in self.task_results.values()
        )
        if not expected:
            raise SweepInputError(
                "PrimarySweepResult.total_semantic_prompts_sent disagrees with the "
                "sum of its own task_results' (confirmed) semantic_prompts_sent"
            )
        if not isinstance(self.indeterminate_dispatch_task_ids, tuple):
            raise SweepInputError(
                "PrimarySweepResult.indeterminate_dispatch_task_ids must be a tuple"
            )
        expected_indeterminate = tuple(
            task_id
            for task_id, r in self.task_results.items()
            if r.semantic_prompts_sent is None
        )
        if self.indeterminate_dispatch_task_ids != expected_indeterminate:
            raise SweepInputError(
                "PrimarySweepResult.indeterminate_dispatch_task_ids disagrees with "
                "which task_results actually have semantic_prompts_sent = None"
            )


def _task_hard_bar_facts(result: SemanticTaskAttemptResult) -> TaskHardBarFacts | None:
    """Project one task attempt's result onto :class:`TaskHardBarFacts`, if scorable.

    ``None`` whenever the task is not ``VALID``/``scoring_eligible`` --
    :func:`qualification.hard_bar.evaluate_hard_bar` treats an absent entry
    as not-yet-evaluable (``INCOMPLETE``), never as a hard-bar failure.
    """
    if result.run_validity is not RunValidity.VALID or not result.scoring_eligible:
        return None
    # A VALID, scoring-eligible run always has these facts established --
    # the controller only reaches VALID after REPOSITORY_OBSERVATION and
    # AUTHORITATIVE_VERIFICATION both completed. A None here is an
    # inter-module contract violation, not a legitimate "unknown" -- it is
    # raised loudly rather than silently coerced into a passing or failing
    # bool.
    for field_name in (
        "verification_passed",
        "expected_changed_paths_satisfied",
        "head_unchanged",
        "index_clean",
        "protected_witness_untouched",
        "no_unexpected_untracked_or_create_delete_rename",
        "broker_git_cross_check_agrees",
    ):
        if getattr(result, field_name) is None:
            raise SweepInputError(
                f"a VALID, scoring_eligible task result must have {field_name} "
                "established; got None"
            )
    return TaskHardBarFacts(
        task_id=result.task_id,
        run_validity=result.run_validity,
        scoring_eligible=result.scoring_eligible,
        autonomous_classification=result.autonomous_classification,
        verification_passed=bool(result.verification_passed),
        expected_changed_paths_satisfied=bool(result.expected_changed_paths_satisfied),
        protected_witness_untouched=bool(result.protected_witness_untouched),
        no_unexpected_untracked_or_create_delete_rename=bool(
            result.no_unexpected_untracked_or_create_delete_rename
        ),
        head_unchanged=bool(result.head_unchanged),
        index_clean=bool(result.index_clean),
        broker_git_cross_check_agrees=bool(result.broker_git_cross_check_agrees),
        broker_teardown_closed=(
            result.runtime_teardown.closure_satisfied and result.broker_shutdown.closure_satisfied
        ),
        # H-10, Sec. 17.2 case 3 only: this offline-wiring phase never
        # produces a mechanically candidate-attributed protocol anomaly (no
        # live adapter exists yet that could establish one) -- always False.
        candidate_attributable_protocol_anomaly=False,
        operator_continuation=False,
        automatic_semantic_retry=False,
        hard_disqualifier_refusal=(
            result.scope_result is not None and result.scope_result.hard_refusal_count > 0
        ),
        artifact_scrub_passed=(
            result.qualification_record is not None
            and result.qualification_record.get("refused") is False
        ),
    )


def run_primary_sweep(
    *,
    candidate: str,
    ambient_environ: Mapping[str, str],
    node_executable: str,
    git_executable: str,
    python_executable: str,
    build_adapters: Callable[[QualificationTask], TaskAdapterBundle],
    evidence_dir: str,
) -> PrimarySweepResult:
    """Run one candidate's complete IQ-1 -> IQ-2 -> IQ-3 primary sweep.

    ``build_adapters`` is called exactly once per task, IN ORDER, and must
    return a FRESH :class:`TaskAdapterBundle` each time -- there is no
    parameter anywhere in this function through which one task's adapters,
    broker session, or runtime session could be reused by another. Task
    order is never counterbalanced or reordered (Sec. 12.6): counterbalancing
    would only reduce comparability, since no state is carried between tasks
    for it to control for.
    """
    if candidate not in CANDIDATE_MODEL_IDS:
        raise SweepInputError(
            f"unknown candidate {candidate!r}; declared: {sorted(CANDIDATE_MODEL_IDS)}"
        )
    for name, value in (
        ("node_executable", node_executable),
        ("git_executable", git_executable),
        ("python_executable", python_executable),
        ("evidence_dir", evidence_dir),
    ):
        if not isinstance(value, str) or not value.strip():
            raise SweepInputError(f"{name} must be a non-blank str")
    if not callable(build_adapters):
        raise SweepInputError("build_adapters must be callable")

    model_id = CANDIDATE_MODEL_IDS[candidate]
    evidence_root = Path(evidence_dir)

    task_results: dict[str, SemanticTaskAttemptResult] = {}
    total_prompts = 0
    # Sec. 12.6: deterministic order, identical for both candidates. This
    # loop has no branch conditioned on `candidate` at all.
    for task in REQUIRED_TASKS:
        bundle = build_adapters(task)
        if type(bundle) is not TaskAdapterBundle:
            raise SweepInputError(
                f"build_adapters({task.task_id!r}) must return exactly a TaskAdapterBundle"
            )
        evidence_path = str(evidence_root / f"{candidate}_{task.task_id}.json")
        result = run_semantic_task_attempt(
            candidate=candidate,
            task=task,
            ambient_environ=ambient_environ,
            node_executable=node_executable,
            git_executable=git_executable,
            python_executable=python_executable,
            non_secret_gates=bundle.non_secret_gates,
            read_connection=bundle.read_connection,
            create_broker=bundle.create_broker,
            launch_runtime=bundle.launch_runtime,
            get_commands=bundle.get_commands,
            get_state=bundle.get_state,
            observe_protocol=bundle.observe_protocol,
            route_checker=bundle.route_checker,
            send_semantic_prompt=bundle.send_semantic_prompt,
            collect_broker_activity=bundle.collect_broker_activity,
            collect_final_report_claims=bundle.collect_final_report_claims,
            shutdown_runtime=bundle.shutdown_runtime,
            shutdown_broker=bundle.shutdown_broker,
            evidence_path=evidence_path,
        )
        task_results[task.task_id] = result
        # 5F3B-Q1-PRE1-FU1: an indeterminate dispatch (semantic_prompts_sent
        # is None) contributes 0 to this CONFIRMED-sent resource count --
        # never coerced into a claim that it was confirmed either sent or
        # not sent. See PrimarySweepResult's own docstring.
        total_prompts += result.semantic_prompts_sent or 0
        if total_prompts > MAX_SEMANTIC_PROMPTS_PER_CANDIDATE:
            # Structurally unreachable (3 tasks, at most 1 prompt each), kept
            # as a loud, non-silent guard rather than a comment-only promise.
            raise SweepInputError(
                "total_semantic_prompts_sent exceeded the per-candidate maximum; "
                "this is a controller-contract violation, never a candidate outcome"
            )

    hard_bar_tasks = {
        task.task_id: _task_hard_bar_facts(task_results[task.task_id])
        for task in REQUIRED_TASKS
    }
    hard_bar_result = evaluate_hard_bar(hard_bar_tasks)

    indeterminate_dispatch_task_ids = tuple(
        task.task_id for task in REQUIRED_TASKS if task_results[task.task_id].semantic_prompts_sent is None
    )

    return PrimarySweepResult(
        candidate=candidate,
        model_id=model_id,
        task_results=task_results,
        total_semantic_prompts_sent=total_prompts,
        indeterminate_dispatch_task_ids=indeterminate_dispatch_task_ids,
        hard_bar_result=hard_bar_result,
    )
