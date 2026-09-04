"""Offline tests for :mod:`qualification.semantic_sweep` (5F3B-Q1-PRE1)."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from qualification.corpus import IQ1_CORRECT_ROUNDING, IQ2_TASK, REQUIRED_TASKS
from qualification.hard_bar import QualificationState
from qualification.i2_credentials import ConnectionValues, PreflightGateResult
from qualification.i2_route import route_descriptor_for_candidate
from qualification.i2b_session import (
    CATEGORY_B_SENTINEL_COMMAND_NAME,
    BrokerCreationObservation,
    BrokerCreationRequest,
    BrokerSession,
    BrokerShutdownObservation,
    GetCommandsObservation,
    GetStateObservation,
    ObservedCommand,
    ProtocolObservation,
    RuntimeLaunchObservation,
    RuntimeLaunchRequest,
    RuntimeSession,
    RuntimeShutdownObservation,
)
from qualification.outcomes import AutonomousClassification
from qualification.report_accuracy import ReportClaims
from qualification.semantic_session import (
    BrokerActivityObservation,
    FinalReportClaimsObservation,
    SemanticDispatchEvidenceCode,
    SemanticPromptDispatchObservation,
    SemanticPromptDispatchState,
    SemanticPromptRequest,
    SemanticTurnObservation,
    SemanticTurnOutcome,
    SemanticTurnRequest,
)
from qualification.semantic_sweep import (
    MAX_SEMANTIC_PROMPTS_PER_CANDIDATE,
    SweepInputError,
    TaskAdapterBundle,
    run_primary_sweep,
)

_IQ2_PARSE_CORRECT = (
    "\"\"\"Parse a raw sensor reading string into (value, unit).\"\"\"\n\n\n"
    "def parse_reading(reading):\n"
    "    text = reading.strip()\n"
    "    unit = text[-1]\n"
    "    number_text = text[:-1]\n"
    "    return float(number_text), unit\n"
)
_IQ2_CONVERT_CORRECT = (
    "\"\"\"Convert Celsius to Fahrenheit, rounded to one decimal.\"\"\"\n\n\n"
    "def to_fahrenheit(celsius):\n"
    "    return round(celsius * 9.0 / 5.0 + 32.0, 1)\n"
)

_REPAIRS = {
    "IQ-1": ({"money/rounding.py": IQ1_CORRECT_ROUNDING}, frozenset({"money/rounding.py"})),
    "IQ-2": (
        {"units/parse.py": _IQ2_PARSE_CORRECT, "units/convert.py": _IQ2_CONVERT_CORRECT},
        frozenset({"units/parse.py", "units/convert.py"}),
    ),
    "IQ-3": ({}, frozenset()),
}


@pytest.fixture(scope="module")
def git_executable() -> str:
    """AIDO's OWN accepted Git resolution (5F3B-LIVE1-C1-P12a).

    The semantic attempt's fixture-population checkpoint requires EXACT
    STRING EQUALITY with ``resolve_git_executable``'s return value, so this
    fixture must BE that value -- never another spelling of the same target.
    """
    from ai_dev_orchestrator.workspace.git_adapter import resolve_git_executable

    exe = shutil.which("git")
    assert exe, "git must be on PATH to build synthetic fixtures"
    return resolve_git_executable(workspace_root=str(Path(__file__).resolve().parents[1]))


def _make_build_adapters(
    candidate: str,
    *,
    correct: bool,
    fresh_calls: list,
    indeterminate_task_ids: frozenset = frozenset(),
):
    """A ``build_adapters`` factory that always produces a "happy path" bundle
    for the task it is called with, capturing one call record per task so
    tests can prove freshness/order.

    ``indeterminate_task_ids`` (5F3B-Q1-PRE1-FU1): any task id named here
    gets a ``send_semantic_prompt`` double that RAISES -- a dispatch AIDO
    cannot mechanically establish as sent -- so sweep-level tests can prove
    ``PrimarySweepResult`` handles a per-task indeterminate dispatch
    truthfully.
    """
    route_descriptor = route_descriptor_for_candidate(candidate)

    def build_adapters(task) -> TaskAdapterBundle:
        fresh_calls.append(task.task_id)
        workspace_root_holder: dict[str, str | None] = {"root": None}
        repairs, edited = _REPAIRS[task.task_id]

        def non_secret_gates():
            return (lambda: PreflightGateResult(name="ok", passed=True),)

        def read_connection():
            return ConnectionValues(base_url="https://b300.example.invalid", api_key="synthetic-test-key")

        def create_broker(request: BrokerCreationRequest):
            return BrokerCreationObservation(
                session=BrokerSession(
                    run_id=request.run_id,
                    session_id=f"bsess-{task.task_id}",
                    pipe_name="\\\\.\\pipe\\test",
                    capability_id="cap-1",
                    broker_token="tok-1",
                    reached_ready=True,
                ),
                start_attempted=True,
                resource_created=True,
            )

        def launch_runtime(request: RuntimeLaunchRequest):
            workspace_root_holder["root"] = request.workspace_root
            return RuntimeLaunchObservation(
                session=RuntimeSession(
                    run_id=request.run_id,
                    broker_session_id=request.broker_session.session_id,
                    runtime_session_id=f"rsess-{task.task_id}",
                ),
                launch_shape_valid=True,
                required_flags_accepted=True,
                lf_jsonl_correlation_succeeded=True,
                observed_pi_version="0.84.4",
                resource_created=True,
            )

        def get_commands(session):
            return GetCommandsObservation(
                runtime_session_id=session.runtime_session_id,
                call_succeeded=True,
                response_shape_understood=True,
                sentinel_name_matched=True,
                sentinel_source_is_extension=True,
                sentinel_path_resolves_to_expected_entry=True,
                noncontradictory_source_origin=True,
                malformed_source_metadata=False,
                reported_source_kind="cli",
                commands=(
                    ObservedCommand(
                        name=CATEGORY_B_SENTINEL_COMMAND_NAME,
                        source="extension",
                        source_info_present=True,
                        source_info_well_formed=True,
                        source_info_source="cli",
                    ),
                ),
            )

        def get_state(session):
            return GetStateObservation(
                runtime_session_id=session.runtime_session_id,
                call_succeeded=True,
                response_shape_understood=True,
                reported_provider=route_descriptor.provider_id,
                reported_model=route_descriptor.model_id,
            )

        def observe_protocol(session):
            return ProtocolObservation(
                runtime_session_id=session.runtime_session_id,
                protocol_violation_observed=False,
                extension_error_observed=False,
            )

        def route_checker(base_url, *, model_id):
            return SimpleNamespace(reachable=True, configured_model_served=True)

        def dispatch_semantic_prompt(request: SemanticPromptRequest):
            if task.task_id in indeterminate_task_ids:
                raise RuntimeError("synthetic: dispatch send-state unknown")
            return SemanticPromptDispatchObservation(
                run_id=request.run_id,
                runtime_session_id=request.runtime_session.runtime_session_id,
                task_id=request.task_id,
                task_revision=request.task_revision,
                dispatch_state=SemanticPromptDispatchState.CONFIRMED_SENT,
                dispatch_evidence_code=(
                    SemanticDispatchEvidenceCode.PROMPT_RESPONSE_ACCEPTED
                ),
            )

        def observe_semantic_turn(request: SemanticTurnRequest):
            return SemanticTurnObservation(
                runtime_session_id=request.runtime_session.runtime_session_id,
                turn_outcome=SemanticTurnOutcome.SETTLED,
            )

        def collect_broker_activity(session):
            if correct and workspace_root_holder["root"] is not None:
                repo_root = Path(workspace_root_holder["root"])
                for relative, body in repairs.items():
                    (repo_root / relative).write_text(body, encoding="utf-8", newline="\n")
            return BrokerActivityObservation(
                runtime_session_id=session.runtime_session_id,
                call_succeeded=True,
                read_operation_count=1,
                edit_operation_count=len(edited) if correct else 0,
                edited_paths=edited if correct else frozenset(),
                refusals=(),
            )

        def collect_final_report_claims(session):
            return FinalReportClaimsObservation(
                runtime_session_id=session.runtime_session_id,
                claims=ReportClaims(
                    claimed_changed_paths=edited if correct else frozenset(),
                    claimed_no_change=not edited,
                    claimed_done=True,
                    claimed_ran_tests=False,
                ),
            )

        def shutdown_runtime(session):
            return RuntimeShutdownObservation(
                runtime_session_id=session.runtime_session_id,
                shutdown_call_returned=True,
                orchestrator_direct_child_reported_exit=True,
            )

        def shutdown_broker(session):
            return BrokerShutdownObservation(session_id=session.session_id, reached_closed=True)

        return TaskAdapterBundle(
            non_secret_gates=non_secret_gates(),
            read_connection=read_connection,
            create_broker=create_broker,
            launch_runtime=launch_runtime,
            get_commands=get_commands,
            get_state=get_state,
            observe_protocol=observe_protocol,
            route_checker=route_checker,
            dispatch_semantic_prompt=dispatch_semantic_prompt,
            observe_semantic_turn=observe_semantic_turn,
            collect_broker_activity=collect_broker_activity,
            collect_final_report_claims=collect_final_report_claims,
            shutdown_runtime=shutdown_runtime,
            shutdown_broker=shutdown_broker,
        )

    return build_adapters


def _run_sweep(
    candidate: str,
    git_executable: str,
    tmp_path: Path,
    *,
    correct: bool,
    indeterminate_task_ids: frozenset = frozenset(),
):
    fresh_calls: list[str] = []
    build_adapters = _make_build_adapters(
        candidate,
        correct=correct,
        fresh_calls=fresh_calls,
        indeterminate_task_ids=indeterminate_task_ids,
    )
    result = run_primary_sweep(
        candidate=candidate,
        ambient_environ={},
        node_executable=sys.executable,
        git_executable=git_executable,
        python_executable=sys.executable,
        build_adapters=build_adapters,
        evidence_dir=str(tmp_path),
    )
    return result, fresh_calls


def test_full_three_task_sweep_qualifies_a_correct_candidate(
    git_executable: str, tmp_path: Path
) -> None:
    result, fresh_calls = _run_sweep("A", git_executable, tmp_path, correct=True)
    assert fresh_calls == ["IQ-1", "IQ-2", "IQ-3"]
    assert result.confirmed_semantic_prompts_sent == 3
    assert result.semantic_dispatch_attempts == 3
    assert result.not_attempted_task_ids == ()
    assert result.hard_bar_result.qualification_state is QualificationState.AUTONOMOUS_QUALIFIED
    for task_id, task_result in result.task_results.items():
        assert task_result.autonomous_classification is AutonomousClassification.AUTONOMOUS_PASS


def test_incomplete_sweep_never_reaches_a_hard_bar_verdict(
    git_executable: str, tmp_path: Path
) -> None:
    # A candidate that fails every task never gets NOT_QUALIFIED confused
    # with an incomplete run; this test instead proves the converse: a
    # sweep that never ran all three tasks is INCOMPLETE, never a verdict.
    from qualification.hard_bar import HardBarResult, evaluate_hard_bar

    partial = {"IQ-1": None, "IQ-2": None}
    result = evaluate_hard_bar(partial)
    assert result.qualification_state is QualificationState.INCOMPLETE
    assert result.missing_or_ineligible_tasks


def test_two_task_partial_sweep_is_incomplete_not_scored() -> None:
    from qualification.hard_bar import evaluate_hard_bar

    result = evaluate_hard_bar({"IQ-1": None, "IQ-2": None, "IQ-3": None})
    assert result.qualification_state is QualificationState.INCOMPLETE


def test_candidate_a_and_b_run_the_identical_task_order(
    git_executable: str, tmp_path: Path
) -> None:
    (tmp_path / "a").mkdir(exist_ok=True)
    (tmp_path / "b").mkdir(exist_ok=True)
    _, calls_a = _run_sweep("A", git_executable, tmp_path / "a", correct=True)
    _, calls_b = _run_sweep("B", git_executable, tmp_path / "b", correct=True)
    assert calls_a == calls_b == ["IQ-1", "IQ-2", "IQ-3"]


def test_no_state_reused_between_tasks(git_executable: str, tmp_path: Path) -> None:
    result, _ = _run_sweep("A", git_executable, tmp_path, correct=True)
    workspace_roots = set()
    for task_result in result.task_results.values():
        # Every task's evidence path is distinct and every task's own
        # gate_statuses is a fresh mapping -- prove no two tasks' evidence
        # collapsed into the same file.
        assert task_result.qualification_record["path"] not in workspace_roots
        workspace_roots.add(task_result.qualification_record["path"])
    assert len(workspace_roots) == 3


def test_max_semantic_prompts_per_candidate_is_three(
    git_executable: str, tmp_path: Path
) -> None:
    result, _ = _run_sweep("A", git_executable, tmp_path, correct=True)
    assert result.confirmed_semantic_prompts_sent <= MAX_SEMANTIC_PROMPTS_PER_CANDIDATE
    assert result.semantic_dispatch_attempts <= MAX_SEMANTIC_PROMPTS_PER_CANDIDATE


def test_unknown_candidate_refused(git_executable: str, tmp_path: Path) -> None:
    with pytest.raises(SweepInputError):
        run_primary_sweep(
            candidate="C",
            ambient_environ={},
            node_executable=sys.executable,
            git_executable=git_executable,
            python_executable=sys.executable,
            build_adapters=lambda task: (_ for _ in ()).throw(AssertionError("unreachable")),
            evidence_dir=str(tmp_path),
        )


def test_build_adapters_must_return_exact_bundle_type(
    git_executable: str, tmp_path: Path
) -> None:
    with pytest.raises(SweepInputError):
        run_primary_sweep(
            candidate="A",
            ambient_environ={},
            node_executable=sys.executable,
            git_executable=git_executable,
            python_executable=sys.executable,
            build_adapters=lambda task: object(),
            evidence_dir=str(tmp_path),
        )


# ===========================================================================
# 5F3B-Q1-PRE1-FU2 -- sweep-level indeterminate dispatch STOPS the sweep
#
# DESIGN-FU1 Sec. 3.J supersedes FU1's "keep going" behavior these tests
# previously asserted. Continuing after an ambiguous attempt would spend
# one-shot attempts against uncharacterised infrastructure, launch a fresh
# runtime/broker while a possibly-live turn may still be running, and make
# the three-prompt budget unprovable (confirmed 0, possible 1) -- all for a
# verdict that is already fixed at INCOMPLETE.
# ===========================================================================


def test_indeterminate_iq1_stops_the_sweep_immediately(
    git_executable: str, tmp_path: Path
) -> None:
    result, fresh_calls = _run_sweep(
        "A", git_executable, tmp_path, correct=True, indeterminate_task_ids=frozenset({"IQ-1"})
    )
    # IQ-2 and IQ-3 are never invoked -- `build_adapters` is not even called
    # for them, so no runtime, broker, workspace or dispatch exists.
    assert fresh_calls == ["IQ-1"]
    assert tuple(result.task_results) == ("IQ-1",)
    assert result.not_attempted_task_ids == ("IQ-2", "IQ-3")
    assert result.indeterminate_dispatch_task_ids == ("IQ-1",)
    # The CONFIRMED count never claims the unknown prompt, and the dispatch
    # budget counts the attempt that was actually made.
    assert result.confirmed_semantic_prompts_sent == 0
    assert result.semantic_dispatch_attempts == 1
    assert result.hard_bar_result.qualification_state is QualificationState.INCOMPLETE
    assert "IQ-2" in result.hard_bar_result.missing_or_ineligible_tasks
    assert "IQ-3" in result.hard_bar_result.missing_or_ineligible_tasks


def test_indeterminate_mid_sweep_keeps_earlier_confirmed_prompts(
    git_executable: str, tmp_path: Path
) -> None:
    result, fresh_calls = _run_sweep(
        "A", git_executable, tmp_path, correct=True, indeterminate_task_ids=frozenset({"IQ-2"})
    )
    assert fresh_calls == ["IQ-1", "IQ-2"]
    assert result.not_attempted_task_ids == ("IQ-3",)
    assert result.confirmed_semantic_prompts_sent == 1
    assert result.semantic_dispatch_attempts == 2
    assert result.indeterminate_dispatch_task_ids == ("IQ-2",)
    assert result.hard_bar_result.qualification_state is QualificationState.INCOMPLETE


def test_not_attempted_tasks_leave_no_artifact(git_executable: str, tmp_path: Path) -> None:
    """Sec. 3.F's "exactly one artifact per attempt" rule is scoped to
    INVOKED attempts: a task the sweep never started has no attempt, so it
    correctly has nothing on disk."""
    result, _ = _run_sweep(
        "A", git_executable, tmp_path, correct=True, indeterminate_task_ids=frozenset({"IQ-1"})
    )
    assert (tmp_path / "A_IQ-1.json").exists()
    for task_id in result.not_attempted_task_ids:
        assert not (tmp_path / f"A_{task_id}.json").exists()


def test_indeterminate_attempt_still_leaves_its_own_artifact(
    git_executable: str, tmp_path: Path
) -> None:
    import json

    result, _ = _run_sweep(
        "A", git_executable, tmp_path, correct=True, indeterminate_task_ids=frozenset({"IQ-1"})
    )
    payload = json.loads((tmp_path / "A_IQ-1.json").read_text(encoding="utf-8"))
    assert payload["record_version"] == "pi-implementer-qualification-attempt.v1"
    assert "semantic_prompts_sent" not in payload
    assert result.task_results["IQ-1"].qualification_record is None
    assert result.task_results["IQ-1"].attempt_record is not None


def test_no_replacement_or_retry_after_an_indeterminate_attempt(
    git_executable: str, tmp_path: Path
) -> None:
    """Sec. 3.H: no automatic retry, ever -- not immediately, not after a
    delay, not with a fresh session for the same task within the same
    sweep."""
    fresh_calls: list[str] = []
    build_adapters = _make_build_adapters(
        "A", correct=True, fresh_calls=fresh_calls, indeterminate_task_ids=frozenset({"IQ-1"})
    )
    seen: list[str] = []

    def counting_build_adapters(task):
        seen.append(task.task_id)
        return build_adapters(task)

    result = run_primary_sweep(
        candidate="A",
        ambient_environ={},
        node_executable=sys.executable,
        git_executable=git_executable,
        python_executable=sys.executable,
        build_adapters=counting_build_adapters,
        evidence_dir=str(tmp_path),
    )
    assert seen == ["IQ-1"]
    assert seen.count("IQ-1") == 1
    assert result.semantic_dispatch_attempts == 1


def test_zero_task_indeterminate_dispatch_has_empty_tuple(
    git_executable: str, tmp_path: Path
) -> None:
    result, _ = _run_sweep("A", git_executable, tmp_path, correct=True)
    assert result.indeterminate_dispatch_task_ids == ()
    assert result.not_attempted_task_ids == ()


@pytest.mark.parametrize("candidate", ["A", "B"])
def test_candidate_a_and_b_indeterminate_dispatch_sweep_semantics_are_identical(
    git_executable: str, tmp_path: Path, candidate: str
) -> None:
    (tmp_path / candidate).mkdir(exist_ok=True)
    result, fresh_calls = _run_sweep(
        candidate,
        git_executable,
        tmp_path / candidate,
        correct=True,
        indeterminate_task_ids=frozenset({"IQ-1"}),
    )
    assert fresh_calls == ["IQ-1"]
    assert result.task_results["IQ-1"].semantic_prompts_sent is None
    assert result.indeterminate_dispatch_task_ids == ("IQ-1",)
    assert result.not_attempted_task_ids == ("IQ-2", "IQ-3")
    assert result.confirmed_semantic_prompts_sent == 0
    assert result.semantic_dispatch_attempts == 1
    assert result.candidate == candidate
