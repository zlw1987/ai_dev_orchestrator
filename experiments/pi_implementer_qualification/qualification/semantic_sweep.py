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
from types import MappingProxyType
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
    SemanticPromptDispatchObservation,
    SemanticPromptDispatchState,
    SemanticPromptRequest,
    SemanticTurnObservation,
    SemanticTurnRequest,
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
    dispatch_semantic_prompt: Callable[
        [SemanticPromptRequest], SemanticPromptDispatchObservation
    ]
    observe_semantic_turn: Callable[[SemanticTurnRequest], SemanticTurnObservation]
    collect_broker_activity: Callable[[RuntimeSession], BrokerActivityObservation]
    collect_final_report_claims: Callable[[RuntimeSession], FinalReportClaimsObservation]
    shutdown_runtime: Callable[[RuntimeSession], RuntimeShutdownObservation]
    shutdown_broker: Callable[[BrokerSession], BrokerShutdownObservation]

    def __post_init__(self) -> None:
        if not isinstance(self.non_secret_gates, tuple):
            raise SweepInputError("TaskAdapterBundle.non_secret_gates must be a tuple")
        for name in (
            "read_connection", "create_broker", "launch_runtime", "get_commands",
            "get_state", "observe_protocol", "route_checker",
            "dispatch_semantic_prompt", "observe_semantic_turn",
            "collect_broker_activity", "collect_final_report_claims",
            "shutdown_runtime", "shutdown_broker",
        ):
            if not callable(getattr(self, name)):
                raise SweepInputError(f"TaskAdapterBundle.{name} must be callable")


#: A task the sweep deliberately never invoked, because it stopped first
#: (DESIGN-FU1 Sec. 3.J). Distinct from every task-attempt outcome: nothing
#: was minted, nothing was dispatched, and -- per Sec. 3.F, whose "exactly
#: one artifact" rule is scoped to INVOKED attempts -- no artifact exists
#: for it, because there was no attempt to record.
NOT_ATTEMPTED = "NOT_ATTEMPTED"


@dataclass(frozen=True)
class PrimarySweepResult:
    """One candidate's complete (or deliberately stopped) primary sweep outcome.

    ``task_results`` is keyed by task id, IN THE FROZEN ORDER
    :data:`~qualification.corpus.REQUIRED_TASKS` declares, and holds ONLY
    the tasks the sweep actually invoked. ``hard_bar_result`` is
    :data:`~qualification.hard_bar.QualificationState.INCOMPLETE` whenever
    any task lacks a ``VALID``, scoring-eligible result -- it is NEVER a
    partial verdict computed from fewer than three tasks; that precondition
    is :func:`qualification.hard_bar.evaluate_hard_bar`'s own, reused
    unmodified.

    **The two counts are deliberately DISTINCT and must never be collapsed**
    (5F3B-Q1-PRE1-FU2 / DESIGN-FU1 Sec. 4):

    ``confirmed_semantic_prompts_sent``
        The honest CONFIRMED count. A task whose dispatch send state was
        mechanically ``SEND_STATE_INDETERMINATE`` contributes ``0`` -- and
        that ``0`` is a statement about what AIDO could PROVE, never a claim
        that the task's send state was confirmed zero. FU1 named this
        ``total_semantic_prompts_sent``, which reads as though the actual
        number of accepted prompts were known; it is renamed, not aliased,
        because the misleading name is exactly the defect.

    ``semantic_dispatch_attempts``
        How many times phase 1 was entered. An indeterminate task
        contributes ``1``. **This is the budget the sweep enforces**: without
        it, counting only confirmed prompts would permit a possible fourth
        prompt (three more dispatches after one that may already have
        crossed the boundary).

    Every indeterminate task id is separately named in
    ``indeterminate_dispatch_task_ids``, and every task the sweep never
    invoked in ``not_attempted_task_ids``, so neither the ambiguity nor the
    stop is ever silently dropped.
    """

    candidate: str
    model_id: str
    task_results: Mapping[str, SemanticTaskAttemptResult]
    confirmed_semantic_prompts_sent: int
    semantic_dispatch_attempts: int
    indeterminate_dispatch_task_ids: tuple[str, ...]
    not_attempted_task_ids: tuple[str, ...]
    hard_bar_result: HardBarResult

    def __post_init__(self) -> None:
        if self.candidate not in CANDIDATE_MODEL_IDS:
            raise SweepInputError(f"unknown candidate {self.candidate!r}")
        if self.model_id != CANDIDATE_MODEL_IDS[self.candidate]:
            raise SweepInputError(
                f"model_id {self.model_id!r} does not match candidate "
                f"{self.candidate!r}'s frozen pairing {CANDIDATE_MODEL_IDS[self.candidate]!r}"
            )
        if not isinstance(self.task_results, Mapping):
            raise SweepInputError("PrimarySweepResult.task_results must be a Mapping")
        for task_id, result in self.task_results.items():
            if type(result) is not SemanticTaskAttemptResult:
                raise SweepInputError(
                    f"PrimarySweepResult.task_results[{task_id!r}] must be exactly a "
                    "SemanticTaskAttemptResult"
                )
            if result.task_id != task_id:
                raise SweepInputError(
                    f"PrimarySweepResult.task_results[{task_id!r}] carries a result for "
                    f"task {result.task_id!r}; a cross-task substitution is refused"
                )
            # 5F3B-Q1-PRE1-FU2A: bind CANDIDATE, never just task identity.
            # Independent review proved an A `PrimarySweepResult` could be
            # built from genuine Candidate B `SemanticTaskAttemptResult`
            # objects (same task ids, foreign candidate/model), which the
            # `task_id` check above never catches.
            if result.candidate != self.candidate or result.model_id != self.model_id:
                raise SweepInputError(
                    f"PrimarySweepResult.task_results[{task_id!r}] belongs to "
                    f"candidate {result.candidate!r}/model {result.model_id!r}, not "
                    f"this sweep's {self.candidate!r}/{self.model_id!r} -- a "
                    "cross-candidate substitution is refused"
                )
        # 5F3B-Q1-PRE1-FU2A: `task_results` must be exactly the frozen prefix
        # of REQUIRED_TASKS the sweep could have actually invoked -- and, if
        # a dispatch was indeterminate, it must be the LAST attempted task
        # (the sweep stops immediately after one; DESIGN-FU1 Sec. 3.J).
        # Neither was previously checked: `IQ-2` present without `IQ-1`,
        # `IQ-1` + `IQ-3` without `IQ-2`, or a determinate result AFTER an
        # indeterminate one all passed silently before.
        present_ids = [task.task_id for task in REQUIRED_TASKS if task.task_id in self.task_results]
        expected_prefix = [task.task_id for task in REQUIRED_TASKS[: len(present_ids)]]
        if present_ids != expected_prefix:
            raise SweepInputError(
                "PrimarySweepResult.task_results must form an exact frozen prefix "
                f"of REQUIRED_TASKS ({[task.task_id for task in REQUIRED_TASKS]!r}); "
                f"got {present_ids!r}"
            )
        indeterminate_positions = [
            index
            for index, task_id in enumerate(present_ids)
            if self.task_results[task_id].dispatch_state
            is SemanticPromptDispatchState.SEND_STATE_INDETERMINATE
        ]
        if len(indeterminate_positions) > 1:
            raise SweepInputError(
                "PrimarySweepResult.task_results carries more than one "
                "indeterminate dispatch; at most one is ever possible per sweep"
            )
        if indeterminate_positions and indeterminate_positions[0] != len(present_ids) - 1:
            raise SweepInputError(
                "PrimarySweepResult: an indeterminate dispatch must be the LAST "
                "attempted task -- the sweep stops immediately after one, so no "
                "task_result may follow it"
            )
        # Fix the canonical (REQUIRED_TASKS) order structurally, so a
        # caller-supplied mapping's own insertion order can never be an
        # externally observable fact about this result.
        object.__setattr__(
            self,
            "task_results",
            {task_id: self.task_results[task_id] for task_id in present_ids},
        )
        for name in ("confirmed_semantic_prompts_sent", "semantic_dispatch_attempts"):
            value = getattr(self, name)
            if type(value) is not int or not (
                0 <= value <= MAX_SEMANTIC_PROMPTS_PER_CANDIDATE
            ):
                raise SweepInputError(
                    f"PrimarySweepResult.{name} must be in "
                    f"[0, {MAX_SEMANTIC_PROMPTS_PER_CANDIDATE}]"
                )
        if self.confirmed_semantic_prompts_sent != sum(
            (r.semantic_prompts_sent or 0) for r in self.task_results.values()
        ):
            raise SweepInputError(
                "PrimarySweepResult.confirmed_semantic_prompts_sent disagrees with the "
                "sum of its own task_results' confirmed semantic_prompts_sent"
            )
        if self.semantic_dispatch_attempts != sum(
            1 for r in self.task_results.values() if r.semantic_dispatch_attempted
        ):
            raise SweepInputError(
                "PrimarySweepResult.semantic_dispatch_attempts disagrees with how many "
                "of its own task_results actually entered phase 1"
            )
        if self.confirmed_semantic_prompts_sent > self.semantic_dispatch_attempts:
            raise SweepInputError(
                "PrimarySweepResult: more prompts were counted as confirmed-sent than "
                "dispatches were ever attempted"
            )
        for name in ("indeterminate_dispatch_task_ids", "not_attempted_task_ids"):
            if not isinstance(getattr(self, name), tuple):
                raise SweepInputError(f"PrimarySweepResult.{name} must be a tuple")
        expected_indeterminate = tuple(
            task_id
            for task_id, r in self.task_results.items()
            if r.dispatch_state is SemanticPromptDispatchState.SEND_STATE_INDETERMINATE
        )
        if self.indeterminate_dispatch_task_ids != expected_indeterminate:
            raise SweepInputError(
                "PrimarySweepResult.indeterminate_dispatch_task_ids disagrees with "
                "which task_results actually had an indeterminate dispatch"
            )
        expected_not_attempted = tuple(
            task.task_id for task in REQUIRED_TASKS if task.task_id not in self.task_results
        )
        if self.not_attempted_task_ids != expected_not_attempted:
            raise SweepInputError(
                "PrimarySweepResult.not_attempted_task_ids disagrees with which "
                "required tasks are missing from task_results"
            )
        # 5F3B-Q1-PRE1-FU2A: `hard_bar_result` must be MECHANICALLY DERIVED
        # from this same, already-validated `task_results` -- never a
        # caller-supplied, independently-convenient value. Independent
        # review proved a `PrimarySweepResult` could be constructed with a
        # genuine completed task_results set paired with a fabricated
        # `HardBarResult` (`__post_init__` never re-derived/bound it). One
        # source of truth: re-run the identical projection/evaluator this
        # module's own `run_primary_sweep` uses, and refuse any disagreement
        # rather than silently repairing it.
        freshly_derived_hard_bar_tasks = {
            task.task_id: (
                _task_hard_bar_facts(self.task_results[task.task_id])
                if task.task_id in self.task_results
                else None
            )
            for task in REQUIRED_TASKS
        }
        freshly_derived_hard_bar_result = evaluate_hard_bar(freshly_derived_hard_bar_tasks)
        if freshly_derived_hard_bar_result != self.hard_bar_result:
            raise SweepInputError(
                "PrimarySweepResult.hard_bar_result disagrees with the hard bar "
                "freshly derived from this result's own task_results -- a caller "
                "cannot supply the verdict independently of its inputs"
            )
        # DESIGN-FU1 Sec. 9.4: `task_results` was a plain, mutable dict, so a
        # caller could replace, add, or delete an entry AFTER `hard_bar_result`
        # had already been computed from it -- permanently, undetectably
        # disagreeing with the object a reader can still inspect. Copy first,
        # then wrap: a proxy over a caller-held dict would still reflect that
        # caller's later mutations.
        object.__setattr__(self, "task_results", MappingProxyType(dict(self.task_results)))


def _task_hard_bar_facts(result: SemanticTaskAttemptResult) -> TaskHardBarFacts | None:
    """Project one task attempt's result onto :class:`TaskHardBarFacts`, if scorable.

    ``None`` whenever the task is not ``VALID``/``scoring_eligible`` --
    :func:`qualification.hard_bar.evaluate_hard_bar` treats an absent entry
    as not-yet-evaluable (``INCOMPLETE``), never as a hard-bar failure.
    """
    # 5F3B-Q1-PRE1-FU2A-FU1: `scoring_eligible` is a hard-bar authority
    # fact. `SemanticTaskAttemptResult.__post_init__` now mechanically
    # guarantees it is exact bool, so this is defense-in-depth at THIS
    # authority boundary too -- refused outright, never read through
    # truthiness (`not "no"` is `False`, which would silently treat a
    # forged non-bool as eligible).
    if type(result.scoring_eligible) is not bool:
        raise SweepInputError(
            "a task result's scoring_eligible must be exactly a bool -- a truthy "
            "non-bool is refused, never read through truthiness"
        )
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
        value = getattr(result, field_name)
        if value is None:
            raise SweepInputError(
                f"a VALID, scoring_eligible task result must have {field_name} "
                "established; got None"
            )
        # 5F3B-Q1-PRE1-FU2A: `SemanticTaskAttemptResult.__post_init__` now
        # mechanically guarantees each of these is exact bool when not None
        # (never a truthy non-bool), so this is a defense-in-depth re-check
        # at the hard-bar authority boundary, not the primary guard -- and
        # this value is never truthiness-normalized either way.
        if type(value) is not bool:
            raise SweepInputError(
                f"a VALID, scoring_eligible task result's {field_name} must be "
                "exactly a bool -- a truthy non-bool is refused, never coerced"
            )
    return TaskHardBarFacts(
        task_id=result.task_id,
        run_validity=result.run_validity,
        scoring_eligible=result.scoring_eligible,
        autonomous_classification=result.autonomous_classification,
        verification_passed=result.verification_passed,
        expected_changed_paths_satisfied=result.expected_changed_paths_satisfied,
        protected_witness_untouched=result.protected_witness_untouched,
        no_unexpected_untracked_or_create_delete_rename=(
            result.no_unexpected_untracked_or_create_delete_rename
        ),
        head_unchanged=result.head_unchanged,
        index_clean=result.index_clean,
        broker_git_cross_check_agrees=result.broker_git_cross_check_agrees,
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
        # H-14 reads the NARROW typed projection, not a live reference to
        # the emission dict (DESIGN-FU1 Sec. 9.4.2). `EvidenceEmission` is a
        # frozen dataclass of scalars and a tuple, so this fact can no longer
        # be mutated between attempt-result construction and hard-bar
        # evaluation.
        artifact_scrub_passed=(
            result.evidence_emission is not None
            and result.evidence_emission.refused is False
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
    confirmed_prompts = 0
    dispatch_attempts = 0
    stop_after_indeterminate = False
    # Sec. 12.6: deterministic order, identical for both candidates. This
    # loop has no branch conditioned on `candidate` at all.
    for task in REQUIRED_TASKS:
        if stop_after_indeterminate:
            # 5F3B-Q1-PRE1-FU2 / DESIGN-FU1 Sec. 3.J -- STOP IMMEDIATELY.
            # Four independent reasons, none of them convenience:
            #   1. the verdict is already fixed. `evaluate_hard_bar` requires
            #      all three tasks VALID and scoring-eligible, and an
            #      indeterminate task can never become either -- it has no
            #      `run_validity` at all -- so continuing buys no verdict.
            #   2. continuing spends one-shot attempts against
            #      uncharacterised infrastructure. Sec. 3.G makes the
            #      indeterminate attempt CONSUMED; Sec. 11.5/15.1 put
            #      re-running after an infrastructure failure in the
            #      OPERATOR's hands, under an explicit recorded decision. A
            #      sweep that plows on converts one replaceable task into
            #      three without the operator ever deciding.
            #   3. a possibly-live turn may still be running. An
            #      indeterminate dispatch is exactly the state in which Pi
            #      may be executing the task while AIDO cannot see it, and
            #      the fairness model's "fresh process, fresh repository, no
            #      shared state" guarantee assumes the previous task's
            #      runtime is finished.
            #   4. the budget can no longer be proven: the CONFIRMED count is
            #      0 but the POSSIBLE count is 1, so three more dispatches
            #      would permit a possible total of four.
            # Nothing is invoked for this task, so -- per Sec. 3.F, scoped to
            # INVOKED attempts -- it correctly leaves no artifact.
            continue
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
            dispatch_semantic_prompt=bundle.dispatch_semantic_prompt,
            observe_semantic_turn=bundle.observe_semantic_turn,
            collect_broker_activity=bundle.collect_broker_activity,
            collect_final_report_claims=bundle.collect_final_report_claims,
            shutdown_runtime=bundle.shutdown_runtime,
            shutdown_broker=bundle.shutdown_broker,
            evidence_path=evidence_path,
        )
        task_results[task.task_id] = result
        # An indeterminate dispatch (semantic_prompts_sent is None)
        # contributes 0 to the CONFIRMED count -- never coerced into a claim
        # that it was confirmed either sent or not sent -- and 1 to the
        # dispatch-attempt budget, which is what is actually enforced.
        confirmed_prompts += result.semantic_prompts_sent or 0
        if result.semantic_dispatch_attempted:
            dispatch_attempts += 1
        if dispatch_attempts > MAX_SEMANTIC_PROMPTS_PER_CANDIDATE:
            # Structurally unreachable (3 tasks, at most 1 dispatch each),
            # kept as a loud, non-silent guard rather than a comment-only
            # promise. The budget is enforced on DISPATCH ATTEMPTS, not on a
            # confirmed count that an indeterminate task would understate.
            raise SweepInputError(
                "semantic_dispatch_attempts exceeded the per-candidate maximum; this "
                "is a controller-contract violation, never a candidate outcome"
            )
        if result.dispatch_state is SemanticPromptDispatchState.SEND_STATE_INDETERMINATE:
            stop_after_indeterminate = True

    # Tasks the sweep never invoked have no facts at all; `evaluate_hard_bar`
    # treats an absent/None entry as not-yet-evaluable (INCOMPLETE), never as
    # a hard-bar FAILURE. This local dict is a throwaway consumed before any
    # caller could reach it.
    hard_bar_tasks = {
        task.task_id: (
            _task_hard_bar_facts(task_results[task.task_id])
            if task.task_id in task_results
            else None
        )
        for task in REQUIRED_TASKS
    }
    hard_bar_result = evaluate_hard_bar(hard_bar_tasks)

    indeterminate_dispatch_task_ids = tuple(
        task.task_id
        for task in REQUIRED_TASKS
        if task.task_id in task_results
        and task_results[task.task_id].dispatch_state
        is SemanticPromptDispatchState.SEND_STATE_INDETERMINATE
    )
    not_attempted_task_ids = tuple(
        task.task_id for task in REQUIRED_TASKS if task.task_id not in task_results
    )

    return PrimarySweepResult(
        candidate=candidate,
        model_id=model_id,
        task_results=task_results,
        confirmed_semantic_prompts_sent=confirmed_prompts,
        semantic_dispatch_attempts=dispatch_attempts,
        indeterminate_dispatch_task_ids=indeterminate_dispatch_task_ids,
        not_attempted_task_ids=not_attempted_task_ids,
        hard_bar_result=hard_bar_result,
    )
