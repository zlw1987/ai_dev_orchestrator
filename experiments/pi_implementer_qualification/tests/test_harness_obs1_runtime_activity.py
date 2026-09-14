"""Offline regressions for 5F3B-HARNESS-OBS1 -- the durable runtime-activity
companion artifact.

Design authority: ``docs/PHASE_5F3B_HARNESS_OBS1_RUNTIME_ACTIVITY_COMPANION_DESIGN.md``
Sec. 17 (FU1/FU2/FU3/FU4) and
``docs/PHASE_5F3B_HARNESS_OBS1_CONTRACT_A1_PHASE2_OBSERVATION_AMENDMENT.md``.

**Wholly offline.** No model call, no network, no socket, no credential, no
Pi launch. Every input is a synthetic dict or a synthetic file under pytest
``tmp_path``; the only real subprocess anywhere is the fixed, read-only Git
observation the frozen controller already performs against a synthetic
disposable fixture repository.

Design Sec. 17 lists 74 numbered items as the MINIMUM specification. Several
are consolidated here into single adversarial tests where that gives stronger
evidence than a shallow one-assert-per-number split; the item numbers each
test discharges are named in its docstring so the mapping stays mechanical.
"""

from __future__ import annotations

import dataclasses
import hashlib
import inspect
import json
import os
import re
import sys
from pathlib import Path

import pytest

import qualification.runtime_activity as ra
from qualification import (
    ACTIVITY_RECORD_VERSION,
    QUALIFICATION_POLICY_REVISION,
    RECORD_VERSION,
)
from qualification.corpus import IQ1_CORRECT_ROUNDING, IQ1_TASK, TASKS_BY_ID
from qualification.records import CANDIDATE_MODEL_IDS, build_qualification_record, emit_or_refuse
from qualification.runtime_activity import (
    ACTIVITY_RECORD_KIND,
    ActivityRecordInvariantError,
    AttemptIdentity,
    MAX_ACTIVITY_TOOL_COUNT,
    PrimaryArtifactUnavailableError,
    RuntimeActivityCompanionDisposition,
    RuntimeToolActivitySnapshot,
    UnboundPrimaryError,
    emit_activity_companion_or_refuse,
    project_runtime_tool_activity,
    verify_activity_companion_binding,
)
from qualification.safety import ArtifactSafetyContext, EvidencePathCollisionError
from qualification.semantic_session import (
    BrokerActivityObservation,
    SemanticTurnObservation,
    SemanticTurnOutcome,
    SemanticTurnRequest,
)

from test_semantic_controller import Harness  # noqa: E402  (sibling test module)

_QUALIFICATION_DIR = Path(ra.__file__).resolve().parent
_NONE = ArtifactSafetyContext.none_declared()


# ===========================================================================
# helpers -- every one of them synthetic, under tmp_path
# ===========================================================================


def _frozen_route_provenance(candidate: str) -> dict:
    from qualification.i2_route import route_descriptor_for_candidate

    descriptor = route_descriptor_for_candidate(candidate)
    return {
        "model_id": descriptor.model_id,
        "provider_route": descriptor.provider_id,
        "backend_gateway_class": descriptor.backend_gateway_class,
    }


def _identity(candidate: str = "A", task_id: str = "IQ-1") -> AttemptIdentity:
    return AttemptIdentity(
        candidate=candidate,
        model_id=CANDIDATE_MODEL_IDS[candidate],
        task_id=task_id,
        task_revision=TASKS_BY_ID[task_id].task_revision,
    )


def _primary_payload(candidate: str = "A", task_id: str = "IQ-1") -> dict:
    return build_qualification_record(
        candidate=candidate,
        model_id=CANDIDATE_MODEL_IDS[candidate],
        task_id=task_id,
        task_revision=TASKS_BY_ID[task_id].task_revision,
        semantic_prompts_sent=1,
        infrastructure_refusal=False,
        run_validity="VALID",
        scoring_eligible=True,
        autonomous_classification="AUTONOMOUS_FAIL",
        diagnostic_subclassification="PREMATURE_SETTLE",
        operator_continuation=False,
        automatic_semantic_retry=False,
        pi_runtime={
            "observed_version": "0.84.4",
            "compatibility_facts": {},
            "compatibility_gate_passed": True,
        },
        route_provenance={
            "model_id": CANDIDATE_MODEL_IDS[candidate],
            "provider_route": "synthetic-provider",
            "backend_gateway_class": "synthetic-gateway",
        },
        verification={"attempted": False},
        scope_result={"synthetic": True},
        report_accuracy={"synthetic": True},
    )


def _write_primary(tmp_path: Path, candidate: str = "A", task_id: str = "IQ-1") -> str:
    path = str(tmp_path / f"{candidate}_{task_id}.json")
    emit_or_refuse(_primary_payload(candidate, task_id), path=path, safety=_NONE)
    return path


def _write_raw(tmp_path: Path, name: str, text: str) -> str:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8", newline="\n")
    return str(path)


def _facts(**overrides) -> dict:
    base = {
        "runtime_reported_tool_activity_available": True,
        "runtime_reported_tool_activity_capture_basis": "agent_settled",
        "runtime_reported_tool_execution_start_events": 3,
        "runtime_reported_tool_execution_end_events": 3,
        "runtime_reported_distinct_tool_call_ids": 3,
        "runtime_reported_unidentified_tool_call_id_seen": False,
        "runtime_reported_aido_read_call_ids": 2,
        "runtime_reported_aido_read_end_observed": 2,
        "runtime_reported_aido_read_error_results": 1,
        "runtime_reported_aido_edit_call_ids": 1,
        "runtime_reported_aido_edit_end_observed": 1,
        "runtime_reported_aido_edit_error_results": 0,
        "runtime_reported_unexpected_tool_call_ids": 0,
        "runtime_reported_unexpected_tool_end_observed": 0,
        "runtime_reported_unexpected_tool_error_results": 0,
        "broker_recorded_activity_available": True,
        "broker_recorded_read_operation_count": 2,
        "broker_recorded_edit_operation_count": 1,
        "broker_recorded_edited_path_count": 1,
        "broker_recorded_refusal_count": 0,
    }
    base.update(overrides)
    return base


def _snapshot(**overrides) -> RuntimeToolActivitySnapshot:
    base = {
        "capture_basis": "agent_settled",
        "tool_execution_start_events": 1,
        "tool_execution_end_events": 1,
        "distinct_tool_call_ids": 1,
        "unidentified_tool_call_id_seen": False,
        "aido_read_call_ids": 1,
        "aido_read_end_observed": 1,
        "aido_read_error_results": 0,
        "aido_edit_call_ids": 0,
        "aido_edit_end_observed": 0,
        "aido_edit_error_results": 0,
        "unexpected_tool_call_ids": 0,
        "unexpected_tool_end_observed": 0,
        "unexpected_tool_error_results": 0,
    }
    base.update(overrides)
    return RuntimeToolActivitySnapshot(**base)


class _Activity:
    """The two fields ``project_runtime_tool_activity`` reads, and nothing else."""

    def __init__(self, event_type_counts, tool_calls):
        self.event_type_counts = event_type_counts
        self.tool_calls = tool_calls


class _Baseline:
    """The two ``_DispatchBaseline`` fields the projection reads."""

    def __init__(self, agent_loop_event_counts, pre_dispatch_tool_call_ids):
        self.agent_loop_event_counts = agent_loop_event_counts
        self.pre_dispatch_tool_call_ids = pre_dispatch_tool_call_ids


# ===========================================================================
# Sec. 17 items 1-4, 70-73 -- FROZEN-CONTRACT PRESERVATION
# ===========================================================================


def test_the_four_semantic_ports_and_the_bundle_are_untouched() -> None:
    """Items 1-2. Names, count, parameter lists, and the bundle's member set."""
    from qualification.semantic_live_adapters import LiveSemanticAdapters
    from qualification.semantic_sweep import TaskAdapterBundle

    expected_ports = {
        "dispatch_semantic_prompt": ["self", "request"],
        "observe_semantic_turn": ["self", "request"],
        "collect_broker_activity": ["self", "session"],
        "collect_final_report_claims": ["self", "session"],
    }
    for name, params in expected_ports.items():
        assert list(inspect.signature(getattr(LiveSemanticAdapters, name)).parameters) == params

    # EXACTLY four semantic ports -- no fifth, under any name.
    assert {
        member
        for member in dir(LiveSemanticAdapters)
        if member.startswith(("dispatch_semantic", "observe_semantic", "collect_"))
        and callable(getattr(LiveSemanticAdapters, member))
    } == set(expected_ports)

    assert {f.name for f in dataclasses.fields(TaskAdapterBundle)} == {
        "non_secret_gates",
        "read_connection",
        "create_broker",
        "launch_runtime",
        "get_commands",
        "get_state",
        "observe_protocol",
        "route_checker",
        "dispatch_semantic_prompt",
        "observe_semantic_turn",
        "collect_broker_activity",
        "collect_final_report_claims",
        "shutdown_runtime",
        "shutdown_broker",
    }
    assert inspect.signature(LiveSemanticAdapters.__init__).parameters.keys() == {
        "self",
        "task",
        "environ_reader",
    }


def test_gate_topology_and_failure_enums_are_untouched() -> None:
    """Items 3-4. No new gate, no new failure code, no fingerprint entry."""
    from qualification.i2b_controller import CategoryBFailureCode
    from qualification.semantic_controller import (
        CLOSURE_GATES,
        GATING_POST_PROMPT_GATES,
        NON_GATING_POST_PROMPT_GATES,
        POST_PROMPT_GATES,
        SemanticFailureCode,
        SemanticGateName,
        _authorized_facts_fingerprint,
    )

    assert {g.value for g in SemanticGateName} == {
        "non_secret_preflight",
        "connection_values",
        "secret_context",
        "route_descriptor",
        "route_check",
        "identity_binding",
        "child_environment",
        "pi_config_generation",
        "workspace_authority",
        "workspace_baseline",
        "run_correlation",
        "broker_ready",
        "broker_session",
        "rpc_launch_shape",
        "required_launch_flags",
        "lf_jsonl_correlation",
        "runtime_launch",
        "pi_version_observed",
        "get_commands",
        "get_state",
        "h1_extension_identity",
        "h2_provider_model_identity",
        "extension_command_namespace",
        "protocol_integrity",
        "semantic_prompt_dispatch",
        "turn_completion",
        "broker_activity",
        "repository_observation",
        "authoritative_verification",
        "final_report_claims",
        "runtime_teardown",
        "broker_shutdown",
        "generated_config_cleanup",
        "semantic_workspace_removal",
        "evidence_safety",
    }
    assert POST_PROMPT_GATES == (
        SemanticGateName.SEMANTIC_PROMPT_DISPATCH,
        SemanticGateName.TURN_COMPLETION,
        SemanticGateName.BROKER_ACTIVITY,
        SemanticGateName.REPOSITORY_OBSERVATION,
        SemanticGateName.AUTHORITATIVE_VERIFICATION,
        SemanticGateName.FINAL_REPORT_CLAIMS,
    )
    assert set(GATING_POST_PROMPT_GATES) | set(NON_GATING_POST_PROMPT_GATES) == set(
        POST_PROMPT_GATES
    )
    assert not set(GATING_POST_PROMPT_GATES) & set(NON_GATING_POST_PROMPT_GATES)
    assert CLOSURE_GATES == (
        SemanticGateName.RUNTIME_TEARDOWN,
        SemanticGateName.BROKER_SHUTDOWN,
        SemanticGateName.GENERATED_CONFIG_CLEANUP,
        SemanticGateName.SEMANTIC_WORKSPACE_REMOVAL,
        SemanticGateName.EVIDENCE_SAFETY,
    )
    for enum in (SemanticFailureCode, CategoryBFailureCode):
        for member in enum:
            for token in ("RUNTIME_ACTIVITY", "COMPANION", "TOOL_ACTIVITY", "ACTIVITY_SNAPSHOT"):
                assert token not in member.name, member

    # The companion disposition is NOT a fingerprint input: the fingerprint's
    # own parameter list is a closed, named set that never mentions it.
    assert "runtime_activity" not in str(
        inspect.signature(_authorized_facts_fingerprint)
    )
    assert "companion" not in str(inspect.signature(_authorized_facts_fingerprint))


def test_no_scoring_module_imports_any_companion_symbol() -> None:
    """Item 71. Source-level: the companion is unreachable from scoring."""
    for name in (
        "hard_bar.py",
        "ranking.py",
        "validity.py",
        "outcomes.py",
        "records.py",
        "lineage.py",
        "safety.py",
        "scope.py",
        "corpus.py",
        "refusal_projection.py",
        "semantic_sweep.py",
    ):
        source = (_QUALIFICATION_DIR / name).read_text(encoding="utf-8")
        assert "runtime_activity" not in source, name
        assert "RuntimeActivityCompanionDisposition" not in source, name
        assert "RuntimeToolActivitySnapshot" not in source, name


def test_pinned_versions_and_policy_revision_are_unmoved() -> None:
    """Item 70, plus the companion's own separate lineage."""
    assert RECORD_VERSION == "pi-implementer-qualification.v2"
    assert QUALIFICATION_POLICY_REVISION == (
        "aido-implementer-role-capability-qualification-policy.r1"
    )
    assert ACTIVITY_RECORD_VERSION == "pi-implementer-qualification-activity.v1"
    assert ACTIVITY_RECORD_KIND != "qualification run record"


def test_lineage_refuses_a_companion_handed_where_a_run_record_was_claimed(
    tmp_path: Path,
) -> None:
    """Item 73. No edit to ``lineage.py`` was needed to get this."""
    from qualification.lineage import LineageBindingError, _require_run_record_shape

    primary = _write_primary(tmp_path)
    emit_activity_companion_or_refuse(
        _facts(), bound_primary_path=primary, identity=_identity(), safety=_NONE
    )
    companion = json.loads(
        (tmp_path / "A_IQ-1.activity.json").read_text(encoding="utf-8")
    )
    with pytest.raises(LineageBindingError):
        _require_run_record_shape(companion, context="companion")


def test_the_duplicated_values_agree_with_their_declaration_sites() -> None:
    """Sec. 9.1 / Sec. 7 / Sec. 3: every duplicated-as-a-VALUE literal agrees."""
    from ar2.pi_config import TOOL_ALLOWLIST as AR2_ALLOWLIST
    from ar2.supervisor import RunBounds
    from qualification import semantic_session
    from qualification.i2b_live_adapters import TOOL_ALLOWLIST as I2B_ALLOWLIST
    from qualification.records import RECORD_KIND
    from qualification.safety import build_refusal_record
    from qualification.semantic_attempt import ATTEMPT_RECORD_KIND

    assert ra.TOOL_ALLOWLIST == tuple(AR2_ALLOWLIST) == tuple(I2B_ALLOWLIST)
    assert ra.ATTEMPT_RECORD_KIND == ATTEMPT_RECORD_KIND
    assert (
        ra.REFUSAL_RECORD_KIND
        == build_refusal_record(
            refused_record_kind="x", finding_count=0, finding_categories=[]
        )["record_kind"]
    )
    assert ra._KNOWN_PRIMARY_RECORD_KINDS == frozenset(
        {RECORD_KIND, ATTEMPT_RECORD_KIND, ra.REFUSAL_RECORD_KIND}
    )
    assert ra._MAX_READ_OPERATIONS == semantic_session._MAX_READ_OPERATIONS
    assert ra._MAX_EDIT_OPERATIONS == semantic_session._MAX_EDIT_OPERATIONS
    assert ra._MAX_REFUSAL_EVENTS == semantic_session._MAX_REFUSAL_EVENTS
    # Imported, never duplicated: Sec. 9.2 withdrew the arbitrary 4096.
    assert MAX_ACTIVITY_TOOL_COUNT == RunBounds().max_events
    assert "4096" not in (_QUALIFICATION_DIR / "runtime_activity.py").read_text(
        encoding="utf-8"
    )


# ===========================================================================
# Sec. 17 items 5-6, 49 -- THE CONTRACT-A1 OBSERVATION AMENDMENT
# ===========================================================================


def test_turn_observation_default_and_exact_type_rules() -> None:
    """Items 5-6 plus CONTRACT-A1 Sec. 6's exact-type rule."""
    from qualification.i2b_session import ObservationError

    plain = SemanticTurnObservation(
        runtime_session_id="rsess-1", turn_outcome=SemanticTurnOutcome.SETTLED
    )
    assert plain.tool_activity is None
    assert plain.agent_settled and not plain.deadline_reached

    class _Subclass(RuntimeToolActivitySnapshot):
        pass

    for bad in (
        {"capture_basis": "agent_settled"},  # a Mapping shaped like a snapshot
        _Subclass(**dataclasses.asdict(_snapshot())),  # an exact subclass
        "agent_settled",
        0,
        True,
    ):
        with pytest.raises(ObservationError):
            SemanticTurnObservation(
                runtime_session_id="rsess-1",
                turn_outcome=SemanticTurnOutcome.SETTLED,
                tool_activity=bad,
            )


def test_require_turn_matches_request_is_unaffected_by_the_new_field(
    git_executable: str,
) -> None:
    """Item 6 / CONTRACT-A1 Sec. 5, proven both ways."""
    from qualification.i2b_session import RuntimeSession
    from qualification.semantic_session import (
        SemanticDispatchEvidenceCode,
        SemanticPromptDispatchObservation,
        SemanticPromptDispatchState,
        require_turn_matches_request,
    )

    session = RuntimeSession(
        run_id="run-1", broker_session_id="bsess-1", runtime_session_id="rsess-1"
    )
    dispatch = SemanticPromptDispatchObservation(
        run_id="run-1",
        runtime_session_id="rsess-1",
        task_id="IQ-1",
        task_revision=TASKS_BY_ID["IQ-1"].task_revision,
        dispatch_state=SemanticPromptDispatchState.CONFIRMED_SENT,
        dispatch_evidence_code=SemanticDispatchEvidenceCode.PROMPT_RESPONSE_ACCEPTED,
    )
    request = SemanticTurnRequest(
        run_id="run-1",
        runtime_session=session,
        task_id="IQ-1",
        task_revision=TASKS_BY_ID["IQ-1"].task_revision,
        dispatch=dispatch,
    )
    populated = SemanticTurnObservation(
        runtime_session_id="rsess-1",
        turn_outcome=SemanticTurnOutcome.SETTLED,
        tool_activity=_snapshot(),
    )
    assert require_turn_matches_request(populated, request) is True
    # Item 28: a FOREIGN session still refuses, on the pre-existing check
    # alone, however well-formed its tool_activity happens to be.
    foreign = SemanticTurnObservation(
        runtime_session_id="rsess-999",
        turn_outcome=SemanticTurnOutcome.SETTLED,
        tool_activity=_snapshot(),
    )
    assert require_turn_matches_request(foreign, request) is False


def test_mutating_the_source_tool_calls_after_projection_changes_nothing() -> None:
    """Item 49. The snapshot retains no live reference, at any depth."""
    entry = {"toolName": "aido_read", "isError": False}
    tool_calls = {"c1": entry}
    activity = _Activity({"tool_execution_start": 1, "tool_execution_end": 1}, tool_calls)
    baseline = _Baseline(
        {"tool_execution_start": 0, "tool_execution_end": 0}, frozenset()
    )
    snapshot = project_runtime_tool_activity(
        activity, baseline, turn_outcome=SemanticTurnOutcome.SETTLED
    )
    observation = SemanticTurnObservation(
        runtime_session_id="rsess-1",
        turn_outcome=SemanticTurnOutcome.SETTLED,
        tool_activity=snapshot,
    )
    before = dataclasses.asdict(snapshot)

    tool_calls["c2"] = {"toolName": "shell", "isError": True}
    tool_calls["c3"] = {"toolName": "aido_edit"}
    entry["toolName"] = "something_else"
    entry["isError"] = True
    activity.event_type_counts["tool_execution_start"] = 999

    assert dataclasses.asdict(observation.tool_activity) == before
    assert observation.tool_activity is snapshot
    with pytest.raises(dataclasses.FrozenInstanceError):
        snapshot.distinct_tool_call_ids = 42  # type: ignore[misc]


# ===========================================================================
# Sec. 17 items 7-11, 22-23 -- PER-DISPATCH CORRELATION AND VOCABULARY
# ===========================================================================


def test_pre_dispatch_entries_and_counts_are_excluded_mechanically() -> None:
    """Items 7-8 together: an entry present BEFORE the baseline is excluded
    even though it is still in ``tool_calls``, and event totals are a DELTA."""
    activity = _Activity(
        {"tool_execution_start": 8, "tool_execution_end": 6, "agent_end": 2},
        {
            "old-1": {"toolName": "aido_edit", "isError": True},
            "new-1": {"toolName": "aido_read", "isError": False},
            "new-2": {"toolName": "aido_read"},
        },
    )
    baseline = _Baseline(
        {"tool_execution_start": 5, "tool_execution_end": 4},
        frozenset({"old-1"}),
    )
    snapshot = project_runtime_tool_activity(
        activity, baseline, turn_outcome=SemanticTurnOutcome.SETTLED
    )
    assert snapshot.tool_execution_start_events == 3
    assert snapshot.tool_execution_end_events == 2
    assert snapshot.distinct_tool_call_ids == 2
    assert snapshot.aido_read_call_ids == 2
    assert snapshot.aido_read_end_observed == 1
    assert snapshot.aido_edit_call_ids == 0  # the pre-dispatch entry, excluded
    assert snapshot.aido_edit_error_results == 0
    assert "old-1" in activity.tool_calls  # still present; simply not projected


def test_the_real_port_carries_a_correlated_snapshot_out_of_phase_two() -> None:
    """Sec. 4.2, end-to-end through the REAL ``observe_semantic_turn`` port.

    The pre-dispatch entry is planted BEFORE phase 1 runs, so the baseline
    genuinely captures it; the post-dispatch entries arrive after. The
    returned observation is exactly a ``SemanticTurnObservation``, its
    completion semantics are untouched, and its snapshot counts only THIS
    dispatch's activity.
    """
    from ar2.supervisor import RUNTIME_SETTLED
    from test_semantic_live_adapters import (
        _adapter_with_transport,
        _confirmed_sent,
        _turn_request,
    )

    adapters, session, supervisor = _adapter_with_transport()
    supervisor.activity.tool_calls["leftover"] = {"toolName": "aido_edit", "isError": True}
    supervisor.activity.event_type_counts["tool_execution_start"] = 4
    supervisor.activity.event_type_counts["tool_execution_end"] = 4

    dispatch_observation, _ = _confirmed_sent(adapters, session)

    supervisor.activity.tool_calls["call-a"] = {"toolName": "aido_read", "isError": False}
    supervisor.activity.tool_calls["call-b"] = {"toolName": "aido_edit", "isError": True}
    supervisor.activity.tool_calls[""] = {"toolName": "shell"}
    supervisor.activity.event_type_counts["tool_execution_start"] = 7
    supervisor.activity.event_type_counts["tool_execution_end"] = 6
    supervisor.await_settled_outcome = RUNTIME_SETTLED

    observation = adapters.observe_semantic_turn(
        _turn_request(adapters, session, dispatch_observation)
    )
    assert type(observation) is SemanticTurnObservation
    assert observation.turn_outcome is SemanticTurnOutcome.SETTLED
    assert observation.agent_end_observed is False

    snapshot = observation.tool_activity
    assert type(snapshot) is RuntimeToolActivitySnapshot
    assert snapshot.capture_basis == "agent_settled"
    assert snapshot.tool_execution_start_events == 3  # 7 - 4, never the absolute
    assert snapshot.tool_execution_end_events == 2  # 6 - 4
    assert snapshot.distinct_tool_call_ids == 3  # "leftover" excluded
    assert snapshot.aido_read_call_ids == 1
    assert snapshot.aido_edit_call_ids == 1
    assert snapshot.aido_edit_error_results == 1
    assert snapshot.unexpected_tool_call_ids == 1
    assert snapshot.unidentified_tool_call_id_seen is True


def test_the_real_dispatch_baseline_snapshots_pre_dispatch_call_ids() -> None:
    """Item 7, against the REAL ``_DispatchBaseline.capture``."""
    from qualification.semantic_live_adapters import _DispatchBaseline

    names = {f.name for f in dataclasses.fields(_DispatchBaseline)}
    assert "pre_dispatch_tool_call_ids" in names

    class _Supervisor:
        def __init__(self):
            self.activity = _Activity({"tool_execution_start": 4}, {"pre-a": {}, "pre-b": {}})
            self.activity.unmatched_response_ids = []
            self.activity.agent_end_count = 0
            self.activity.settled = False

        def stdout_state(self):
            return {"records_ingested": 7}

    supervisor = _Supervisor()
    baseline = _DispatchBaseline.capture(supervisor)
    assert baseline.pre_dispatch_tool_call_ids == frozenset({"pre-a", "pre-b"})
    assert isinstance(baseline.pre_dispatch_tool_call_ids, frozenset)
    # Captured by VALUE: a later mutation cannot retroactively widen it.
    supervisor.activity.tool_calls["post-a"] = {}
    assert baseline.pre_dispatch_tool_call_ids == frozenset({"pre-a", "pre-b"})


@pytest.mark.parametrize(
    "outcome,expected",
    [
        (SemanticTurnOutcome.SETTLED, "agent_settled"),
        (SemanticTurnOutcome.DEADLINE_REACHED, "wait_ended_before_settled"),
        (SemanticTurnOutcome.OBSERVATION_FAILED, "wait_ended_before_settled"),
    ],
)
def test_capture_basis_records_which_completeness_proof_applied(outcome, expected) -> None:
    """Items 9-10. Sec. 5.3's Part-A/Part-B distinction, never guessed."""
    snapshot = project_runtime_tool_activity(
        _Activity({}, {}),
        _Baseline({}, frozenset()),
        turn_outcome=outcome,
    )
    assert snapshot.capture_basis == expected


def test_unexpected_tool_names_collapse_to_the_bounded_category(tmp_path: Path) -> None:
    """Items 22-23. Exact, case-sensitive matching; the literal never retained."""

    class _EqualStr(str):
        def __eq__(self, other):  # noqa: D105
            return True

        def __hash__(self):  # noqa: D105
            return hash("aido_read")

    hostile_names = [
        "shell",
        "AIDO_READ",
        " aido_read",
        "aido_read2",
        "aido_edit ",
        None,
        123,
        _EqualStr("aido_read"),
    ]
    tool_calls = {f"c{i}": {"toolName": name} for i, name in enumerate(hostile_names)}
    snapshot = project_runtime_tool_activity(
        _Activity(
            {"tool_execution_start": len(hostile_names)},
            tool_calls,
        ),
        _Baseline({}, frozenset()),
        turn_outcome=SemanticTurnOutcome.SETTLED,
    )
    assert snapshot.unexpected_tool_call_ids == len(hostile_names)
    assert snapshot.aido_read_call_ids == 0
    assert snapshot.aido_edit_call_ids == 0

    primary = _write_primary(tmp_path)
    emit_activity_companion_or_refuse(
        _facts(
            runtime_reported_tool_execution_start_events=len(hostile_names),
            runtime_reported_tool_execution_end_events=0,
            runtime_reported_distinct_tool_call_ids=len(hostile_names),
            runtime_reported_aido_read_call_ids=0,
            runtime_reported_aido_read_end_observed=0,
            runtime_reported_aido_read_error_results=0,
            runtime_reported_aido_edit_call_ids=0,
            runtime_reported_aido_edit_end_observed=0,
            runtime_reported_unexpected_tool_call_ids=len(hostile_names),
        ),
        bound_primary_path=primary,
        identity=_identity(),
        safety=_NONE,
    )
    emitted = (tmp_path / "A_IQ-1.activity.json").read_text(encoding="utf-8")
    for literal in ("shell", "AIDO_READ", "aido_read2", "123"):
        assert literal not in emitted, literal
    assert "unexpected_tool_call_ids" in emitted


def test_the_empty_tool_call_id_collapse_is_recorded_as_a_flag() -> None:
    """Sec. 6.4: the FACT of a collapse, never a reconstructed count."""
    snapshot = project_runtime_tool_activity(
        _Activity(
            {"tool_execution_start": 4, "tool_execution_end": 1},
            {"": {"toolName": "aido_read", "isError": True}, "c1": {"toolName": "aido_edit"}},
        ),
        _Baseline({}, frozenset()),
        turn_outcome=SemanticTurnOutcome.SETTLED,
    )
    assert snapshot.unidentified_tool_call_id_seen is True
    assert snapshot.distinct_tool_call_ids == 2
    assert snapshot.aido_read_error_results == 1


# ===========================================================================
# Sec. 17 items 12-18, 24-27 -- CROSS-FIELD INVARIANTS AND COUNT INTEGRITY
# ===========================================================================


@pytest.mark.parametrize(
    "overrides",
    [
        # item 13 -- ends > call ids, each category independently
        {"runtime_reported_aido_read_end_observed": 3},
        {"runtime_reported_aido_edit_end_observed": 2},
        {
            "runtime_reported_unexpected_tool_call_ids": 0,
            "runtime_reported_unexpected_tool_end_observed": 1,
        },
        # item 14 -- error results > ends, each category independently
        {"runtime_reported_aido_read_error_results": 3},
        {
            "runtime_reported_aido_edit_end_observed": 0,
            "runtime_reported_aido_edit_error_results": 1,
        },
        # item 15 -- the partition identity
        {"runtime_reported_distinct_tool_call_ids": 4},
        {"runtime_reported_aido_read_call_ids": 1},
        # item 16 -- the collapse bound
        {
            "runtime_reported_tool_execution_start_events": 1,
            "runtime_reported_tool_execution_end_events": 1,
        },
        # item 18 -- the proven broker inequality
        {"broker_recorded_edited_path_count": 2},
        # item 24 -- bool where a count belongs
        {"runtime_reported_distinct_tool_call_ids": True},
        {"broker_recorded_read_operation_count": False},
        # item 25 -- negative
        {"runtime_reported_aido_read_error_results": -1},
        {"broker_recorded_refusal_count": -1},
        # item 26 -- over the runtime cap, refused not clamped
        {
            "runtime_reported_tool_execution_start_events": MAX_ACTIVITY_TOOL_COUNT + 1,
        },
        # item 27 -- over a broker cap
        {"broker_recorded_read_operation_count": 33},
        {"broker_recorded_edit_operation_count": 17},
        {"broker_recorded_refusal_count": 257},
        # a float that happens to be integral is refused, never coerced
        {"broker_recorded_read_operation_count": 2.0},
        # a non-bool availability flag
        {"runtime_reported_tool_activity_available": "yes"},
        # an unknown capture basis
        {"runtime_reported_tool_activity_capture_basis": "probably_settled"},
    ],
)
def test_every_malformed_or_impossible_fact_set_refuses(
    tmp_path: Path, overrides: dict
) -> None:
    """Items 13-16, 18, 24-27. Refused outright -- never clamped, coerced or
    silently corrected -- and nothing is written."""
    primary = _write_primary(tmp_path)
    before = Path(primary).read_bytes()
    with pytest.raises(ActivityRecordInvariantError):
        emit_activity_companion_or_refuse(
            _facts(**overrides),
            bound_primary_path=primary,
            identity=_identity(),
            safety=_NONE,
        )
    assert Path(primary).read_bytes() == before
    assert not (tmp_path / "A_IQ-1.activity.json").exists()


@pytest.mark.parametrize(
    "overrides",
    [
        {"runtime_reported_distinct_tool_call_ids": 1},
        {"runtime_reported_unidentified_tool_call_id_seen": True},
        {"runtime_reported_tool_activity_capture_basis": "agent_settled"},
        {"runtime_reported_aido_edit_call_ids": 1},
    ],
)
def test_an_unavailable_runtime_family_must_be_exactly_zeroed(
    tmp_path: Path, overrides: dict
) -> None:
    """Item 12. Sec. 6.1's implication chain, every link."""
    primary = _write_primary(tmp_path)
    zeroed = _facts(
        runtime_reported_tool_activity_available=False,
        **{k: v for k, v in ra._RUNTIME_ZERO_FACTS.items()},
    )
    zeroed.update(overrides)
    with pytest.raises(ActivityRecordInvariantError):
        emit_activity_companion_or_refuse(
            zeroed, bound_primary_path=primary, identity=_identity(), safety=_NONE
        )
    assert not (tmp_path / "A_IQ-1.activity.json").exists()


def test_an_unavailable_broker_family_must_be_exactly_zeroed(tmp_path: Path) -> None:
    """Item 12's broker half."""
    primary = _write_primary(tmp_path)
    with pytest.raises(ActivityRecordInvariantError):
        emit_activity_companion_or_refuse(
            _facts(broker_recorded_activity_available=False),
            bound_primary_path=primary,
            identity=_identity(),
            safety=_NONE,
        )


def test_the_declined_invariants_were_not_silently_reintroduced() -> None:
    """Item 17. Sec. 6.4 DECLINES these; nothing may quietly assert them."""
    source = (_QUALIFICATION_DIR / "runtime_activity.py").read_text(encoding="utf-8")
    # No equality is ever asserted between distinct ids and START events alone.
    assert "distinct_tool_call_ids != " not in source.replace(
        "aido_read_call_ids + aido_edit_call_ids + unexpected_tool_call_ids\n        != distinct_tool_call_ids",
        "",
    )
    assert "read_operation_count ==" not in source
    assert "read_operation_count >" not in source
    assert "refusal_count >" not in source
    assert "refusal_count ==" not in source
    # The ONE broker inequality Sec. 6.5 proves, and only that one.
    assert (
        source.count('record["broker_recorded_edited_path_count"]')
        == 1
    )


def test_the_snapshot_itself_enforces_the_same_invariants() -> None:
    """Sec. 6.6: the builder and the gate check INDEPENDENTLY, both re-derived."""
    for bad in (
        {"aido_read_end_observed": 5},
        {"aido_read_error_results": 5},
        {"distinct_tool_call_ids": 9},
        {"tool_execution_start_events": 0, "tool_execution_end_events": 0},
        {"aido_read_call_ids": True},
        {"aido_read_call_ids": -1, "distinct_tool_call_ids": -1},
        {"capture_basis": "settled"},
        {"unidentified_tool_call_id_seen": 1},
    ):
        with pytest.raises(ActivityRecordInvariantError):
            _snapshot(**bad)


# ===========================================================================
# Sec. 17 items 19-21 -- CONTENT PROHIBITION
# ===========================================================================


def test_no_raw_tool_content_or_reasoning_can_reach_the_companion(
    tmp_path: Path,
) -> None:
    """Items 19-20. The guarantee is the CLOSED SCHEMA: there is no free-text
    field for any of this to occupy, even when it is present upstream."""
    needles = (
        "SECRETARGUMENTBODY",
        "SECRETRESULTBODY",
        "SECRETASSISTANTTEXT",
        "SECRETREASONING",
    )
    tool_calls = {
        "c1": {
            "toolName": "aido_read",
            "isError": False,
            "arguments": {"path": needles[0]},
            "input": needles[0],
            "parameters": needles[0],
            "result": needles[1],
            "output": needles[1],
            "content": needles[2],
            "text": needles[2],
            "reasoning": needles[3],
            "reasoningContent": needles[3],
            "thinking": needles[3],
            "redacted_thinking": needles[3],
        }
    }
    snapshot = project_runtime_tool_activity(
        _Activity({"tool_execution_start": 1, "tool_execution_end": 1}, tool_calls),
        _Baseline({}, frozenset()),
        turn_outcome=SemanticTurnOutcome.SETTLED,
    )
    assert snapshot.aido_read_call_ids == 1
    for value in dataclasses.asdict(snapshot).values():
        assert type(value) in (int, bool, str)
        if isinstance(value, str):
            assert value in ("agent_settled", "wait_ended_before_settled")

    primary = _write_primary(tmp_path)
    emit_activity_companion_or_refuse(
        _facts(
            runtime_reported_tool_execution_start_events=1,
            runtime_reported_tool_execution_end_events=1,
            runtime_reported_distinct_tool_call_ids=1,
            runtime_reported_aido_read_call_ids=1,
            runtime_reported_aido_read_end_observed=1,
            runtime_reported_aido_read_error_results=0,
            runtime_reported_aido_edit_call_ids=0,
            runtime_reported_aido_edit_end_observed=0,
        ),
        bound_primary_path=primary,
        identity=_identity(),
        safety=_NONE,
    )
    emitted = (tmp_path / "A_IQ-1.activity.json").read_text(encoding="utf-8")
    for needle in needles:
        assert needle not in emitted
    for forbidden_key in (
        "arguments",
        "result",
        "output",
        "reasoning",
        "thinking",
        "final_assistant_text",
        "usage",
        "changed_paths",
        "edited_paths",
        "runtime_session_id",
        "run_id",
        "capability_id",
        "pipe_name",
        "broker_token",
        "attempt_authority_token",
        "path",
    ):
        assert f'"{forbidden_key}"' not in emitted, forbidden_key


def test_declared_sensitive_values_are_caught_by_the_shared_scrub(
    tmp_path: Path,
) -> None:
    """Item 21. A poisoned companion refuses through the SAME choke point, and
    a durable bounded refusal record is written in its place."""
    primary = _write_primary(tmp_path)
    poisoned = ArtifactSafetyContext(
        endpoint_host="b300.example.invalid",
        api_key=CANDIDATE_MODEL_IDS["A"],  # appears in every companion, never in a refusal
        broker_token="tok-1",
        pipe_name="\\\\.\\pipe\\test-pipe",
        capability_id="cap-1",
        workspace_absolute_path=str(tmp_path),
    )
    emission = emit_activity_companion_or_refuse(
        _facts(), bound_primary_path=primary, identity=_identity(), safety=poisoned
    )
    assert emission["refused"] is True
    written = json.loads((tmp_path / "A_IQ-1.activity.json").read_text(encoding="utf-8"))
    assert written["record_kind"] == "artifact emission refusal"
    assert written["refused_record_kind"] == ACTIVITY_RECORD_KIND
    assert written["candidate_artifact_not_emitted"] is True
    assert "api_key_value_present" in written["finding_categories"]

    # And a CLEAN companion, with nothing declared, passes the same scrub.
    clean_primary = _write_primary(tmp_path, task_id="IQ-2")
    clean = emit_activity_companion_or_refuse(
        _facts(), bound_primary_path=clean_primary, identity=_identity(task_id="IQ-2"), safety=_NONE
    )
    assert clean["refused"] is False


# ===========================================================================
# Sec. 17 items 33-37 -- THE CLOSED proposed_facts KEY SET
# ===========================================================================


@pytest.mark.parametrize(
    "extra",
    [
        {"bound_primary_sha256": "0" * 64},
        {"bound_primary_filename": "B_IQ-2.json"},
        {"bound_primary_record_kind": "qualification run record"},
        {
            "bound_primary_sha256": "0" * 64,
            "bound_primary_filename": "B_IQ-2.json",
            "bound_primary_record_kind": "qualification run record",
        },
        {"candidate": "B"},
        {"model_id": "minimax-m2.7"},
        {"task_id": "IQ-3"},
        {"task_revision": "IQ-3@deadbeefdeadbeef"},
        {"candidate": "B", "model_id": "minimax-m2.7", "task_id": "IQ-3"},
        {"path": "anywhere.json"},
        {"activity_path": "anywhere.activity.json"},
        {"bound_primary_path": "anywhere.json"},
        {"experiment": "something_else"},
        {"record_kind": "qualification run record"},
        {"record_version": "pi-implementer-qualification.v2"},
        {"qualification_policy_revision": "forged.r2"},
        {"scoring_authority": True},
        {"claim_scope": "this artifact is authoritative"},
        {"run_validity": "VALID"},
        {"scoring_eligible": True},
        {"autonomous_classification": "AUTONOMOUS_PASS"},
        {"diagnostic_subclassification": "NONE"},
        {"gate_statuses": {}},
        {"failed_gate": None},
        {"is_review_packet": True},
        {"reviewer_invoked": True},
        # item 36 -- an UNRECOGNIZED key that is not reserved at all
        {"runtime_reported_aido_reed_call_ids": 1},
    ],
)
def test_a_reserved_or_unknown_proposed_facts_key_refuses_before_any_io(
    tmp_path: Path, extra: dict
) -> None:
    """Items 33-36. The refusal is a BOUNDED
    ``ActivityRecordInvariantError`` -- explicitly NOT a Python
    duplicate-keyword ``TypeError`` from a later ``**``-expansion, and it
    happens before ``bound_primary_path`` is ever opened."""
    missing_primary = str(tmp_path / "A_IQ-1.json")
    with pytest.raises(ActivityRecordInvariantError) as caught:
        emit_activity_companion_or_refuse(
            _facts(**extra),
            bound_primary_path=missing_primary,
            identity=_identity(),
            safety=_NONE,
        )
    assert not isinstance(caught.value, TypeError)
    # Proven to have refused BEFORE the read: the primary does not even exist,
    # yet the failure is the key-set refusal, never PrimaryArtifactUnavailableError.
    assert not Path(missing_primary).exists()
    assert not (tmp_path / "A_IQ-1.activity.json").exists()


def test_a_missing_observational_key_refuses_just_as_readily(tmp_path: Path) -> None:
    """Item 37. Exact-set equality catches omission as readily as addition."""
    primary = _write_primary(tmp_path)
    for dropped in sorted(ra._ALLOWED_PROPOSED_FACTS_KEYS):
        facts = _facts()
        del facts[dropped]
        with pytest.raises(ActivityRecordInvariantError):
            emit_activity_companion_or_refuse(
                facts, bound_primary_path=primary, identity=_identity(), safety=_NONE
            )
    assert not (tmp_path / "A_IQ-1.activity.json").exists()


def test_a_non_mapping_proposed_facts_refuses_boundedly(tmp_path: Path) -> None:
    """POST-CODE ADVERSARIAL REGRESSION. ``set(proposed_facts)`` on an object
    that is not iterable at all raised an UNCONTROLLED ``TypeError`` out of
    the emission boundary -- indistinguishable, to a reader of the traceback,
    from exactly the duplicate-keyword ``TypeError`` FU3 Finding 1 forbids as
    a refusal mechanism. It is now the module's own bounded refusal."""
    primary = _write_primary(tmp_path)

    class _NotIterable:
        pass

    for facts in (_NotIterable(), 7, None, object()):
        with pytest.raises(ActivityRecordInvariantError) as caught:
            emit_activity_companion_or_refuse(
                facts, bound_primary_path=primary, identity=_identity(), safety=_NONE
            )
        assert not isinstance(caught.value, TypeError)
        assert caught.value.__cause__ is None
    # A list of the right strings is still a key-set refusal, not a crash.
    with pytest.raises(ActivityRecordInvariantError):
        emit_activity_companion_or_refuse(
            list(ra._ALLOWED_PROPOSED_FACTS_KEYS),
            bound_primary_path=primary,
            identity=_identity(),
            safety=_NONE,
        )
    assert not (tmp_path / "A_IQ-1.activity.json").exists()


def test_a_lookalike_broker_observation_is_refused_never_read_as_unavailable() -> None:
    """POST-CODE ADVERSARIAL REGRESSION. A ``BrokerActivityObservation``
    SUBCLASS used to be silently recorded as ``broker_recorded_activity_available:
    false`` -- a claim AIDO had not established. It is refused, exactly as a
    runtime-snapshot lookalike already was."""

    class _Lookalike(BrokerActivityObservation):
        pass

    observation = SemanticTurnObservation(
        runtime_session_id="rsess-1", turn_outcome=SemanticTurnOutcome.SETTLED
    )
    with pytest.raises(ActivityRecordInvariantError):
        ra._build_proposed_facts(
            observation,
            _Lookalike(runtime_session_id="rsess-1", call_succeeded=True),
        )
    # `None` remains a legitimate "never collected", and is NOT a refusal.
    assert ra._build_proposed_facts(observation, None)[
        "broker_recorded_activity_available"
    ] is False


def test_the_written_object_is_exactly_the_object_the_final_gate_inspected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """POST-CODE ADVERSARIAL REGRESSION -- no post-validation mutation window.

    ``_require_valid_activity_payload`` returns the CANONICAL dict it
    inspected, and that exact object is what reaches the shared writer. Proven
    by object identity, so nothing can change shape between the last check and
    the write (the gap ``records._canonicalize_or_refuse`` closes for the
    primary artifact, closed here the same way)."""
    primary = _write_primary(tmp_path)
    observed: dict = {}

    real_gate = ra._require_valid_activity_payload
    real_emit = ra.emit_evidence_or_refuse

    def gate_spy(payload, *, bound_primary_path):
        result = real_gate(payload, bound_primary_path=bound_primary_path)
        observed["gate_returned"] = id(result)
        return result

    def emit_spy(payload, *, path, safety, record_kind):
        observed["written"] = id(payload)
        observed["written_type"] = type(payload)
        return real_emit(payload, path=path, safety=safety, record_kind=record_kind)

    monkeypatch.setattr(ra, "_require_valid_activity_payload", gate_spy)
    monkeypatch.setattr(ra, "emit_evidence_or_refuse", emit_spy)
    emit_activity_companion_or_refuse(
        _facts(), bound_primary_path=primary, identity=_identity(), safety=_NONE
    )
    assert observed["written"] == observed["gate_returned"]
    assert observed["written_type"] is dict  # an ORDINARY dict, never a subclass


@pytest.mark.parametrize(
    "content",
    [b"", b"\xff\xfe\x00garbage", b"   ", b"null", b"123", b'"a string"'],
)
def test_degenerate_primary_content_is_unbound_not_unavailable(
    tmp_path: Path, content: bytes
) -> None:
    """POST-CODE ADVERSARIAL REGRESSION. A zero-byte, non-UTF8, or
    non-object-JSON primary is READ successfully -- so it is
    ``UnboundPrimaryError``, never the read-failure type."""
    path = tmp_path / "A_IQ-1.json"
    path.write_bytes(content)
    with pytest.raises(UnboundPrimaryError):
        emit_activity_companion_or_refuse(
            _facts(), bound_primary_path=str(path), identity=_identity(), safety=_NONE
        )


def test_a_directory_as_the_bound_primary_is_a_read_failure(tmp_path: Path) -> None:
    """POST-CODE ADVERSARIAL REGRESSION. The read cannot succeed, so it is the
    read-failure type -- never a content claim about a file that was opened.

    **5F3B-HARNESS-OBS1-IMPL-FU3.** ``tmp_path`` itself has no ``.json``
    extension, so since Finding 1's fix moved ``_derive_activity_path`` to
    run BEFORE the read, a bare ``str(tmp_path)`` is now correctly refused
    EARLIER, by the path-SHAPE gate, as ``ActivityRecordInvariantError`` --
    it never reaches ``open()`` at all, which is proven directly below. To
    keep proving the ORIGINAL claim this test names (a validly ``<name>.json``
    -shaped path whose primary open/read itself still fails becomes
    ``PrimaryArtifactUnavailableError``, never a content claim), a directory
    is created whose own name carries the required ``.json`` suffix, so it
    passes the shape gate and fails only at the read.
    """
    with pytest.raises(ActivityRecordInvariantError):
        emit_activity_companion_or_refuse(
            _facts(), bound_primary_path=str(tmp_path), identity=_identity(), safety=_NONE
        )

    json_shaped_dir = tmp_path / "A_IQ-1.json"
    json_shaped_dir.mkdir()
    with pytest.raises(PrimaryArtifactUnavailableError):
        emit_activity_companion_or_refuse(
            _facts(),
            bound_primary_path=str(json_shaped_dir),
            identity=_identity(),
            safety=_NONE,
        )


def test_a_bypass_constructed_snapshot_is_still_caught_at_the_payload_gate(
    tmp_path: Path,
) -> None:
    """POST-CODE ADVERSARIAL REGRESSION. ``__post_init__`` is not the only
    line of defence: a snapshot minted through ``object.__new__`` (skipping
    every one of its own checks) carrying ``True`` where a count belongs is
    still refused, independently, at the emission boundary's own gate -- the
    Sec. 6.6 "builder and gate check INDEPENDENTLY" discipline, proven."""
    primary = _write_primary(tmp_path)
    forged = object.__new__(RuntimeToolActivitySnapshot)
    fields = dataclasses.asdict(_snapshot())
    fields.update(
        tool_execution_start_events=True,
        distinct_tool_call_ids=True,
        aido_read_call_ids=True,
    )
    for name, value in fields.items():
        object.__setattr__(forged, name, value)

    observation = object.__new__(SemanticTurnObservation)
    for name, value in {
        "runtime_session_id": "rsess-1",
        "turn_outcome": SemanticTurnOutcome.SETTLED,
        "agent_end_observed": False,
        "tool_activity": forged,
    }.items():
        object.__setattr__(observation, name, value)

    with pytest.raises(ActivityRecordInvariantError):
        emit_activity_companion_or_refuse(
            ra._build_proposed_facts(observation, None),
            bound_primary_path=primary,
            identity=_identity(),
            safety=_NONE,
        )
    assert not (tmp_path / "A_IQ-1.activity.json").exists()


def test_a_companion_can_never_be_bound_as_though_it_were_a_primary(
    tmp_path: Path,
) -> None:
    """POST-CODE ADVERSARIAL REGRESSION. Primary/companion path confusion is
    closed at BOTH gates: ``_derive_activity_path`` refuses a
    ``*.activity.json`` input outright (Sec. 11.1), and -- independently --
    the companion's own ``record_kind`` is none of the three bindable kinds.

    **5F3B-HARNESS-OBS1-IMPL-FU3.** Since ``_derive_activity_path`` now runs
    BEFORE any primary read (Finding 1's fix), the PATH-SHAPE gate is the one
    that actually fires for ``emit_activity_companion_or_refuse`` here -- the
    file is never even opened, so the record-kind gate is never reached for
    this particular input. Before FU3, the read happened first, so this same
    call raised ``UnboundPrimaryError`` from the record-kind check instead;
    that was never a distinct security property, only an accident of the old
    ordering, and the shape gate closing it EARLIER (before any I/O) is
    strictly stronger. The record-kind gate's OWN independent closure of the
    identical confusion, for an input that somehow bypassed the path-shape
    gate, is proven separately below without going through the emission
    boundary at all.
    """
    primary = _write_primary(tmp_path)
    emit_activity_companion_or_refuse(
        _facts(), bound_primary_path=primary, identity=_identity(), safety=_NONE
    )
    companion = str(tmp_path / "A_IQ-1.activity.json")
    with pytest.raises(ActivityRecordInvariantError):
        emit_activity_companion_or_refuse(
            _facts(), bound_primary_path=companion, identity=_identity(), safety=_NONE
        )
    with pytest.raises(ActivityRecordInvariantError):
        ra._derive_activity_path(companion)

    # The record-kind gate's OWN independent closure, proven directly against
    # `_require_known_kind_or_raise` so it is not merely inferred from the
    # path-shape gate having fired first above.
    companion_bytes = Path(companion).read_bytes()
    companion_record = ra._parse_json_object_or_raise(companion_bytes)
    with pytest.raises(UnboundPrimaryError):
        ra._require_known_kind_or_raise(companion_record)

    assert not (tmp_path / "A_IQ-1.activity.activity.json").exists()


def test_an_attempt_that_wrote_nothing_gets_no_companion(
    git_executable: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sec. 11.4. A ``SAFETY_CONTEXT_UNPROVABLE`` refusal leaves NO durable
    artifact, so there is nothing to bind -- and an unbound companion would be
    strictly worse than none."""
    import qualification.semantic_controller as controller
    from qualification.semantic_controller import SemanticSafetyContextError

    harness = Harness("A", git_executable)
    monkeypatch.setattr(
        controller,
        "build_run_safety_context",
        lambda **kwargs: (_ for _ in ()).throw(
            SemanticSafetyContextError("UNEXPECTED_CREDENTIAL_MECHANISM")
        ),
    )
    evidence_path = str(tmp_path / "A_IQ-1.json")
    result = harness.run(IQ1_TASK, evidence_path)
    assert result.evidence_emission is None
    assert (
        result.runtime_activity_companion
        is RuntimeActivityCompanionDisposition.UNAVAILABLE_NO_PRIMARY
    )
    assert sorted(p.name for p in tmp_path.iterdir()) == []


def test_the_emission_boundary_has_no_output_path_parameter() -> None:
    """Item 44. There is NO signature shape through which a caller could
    supply an independently chosen destination."""
    signature = inspect.signature(emit_activity_companion_or_refuse)
    assert list(signature.parameters) == [
        "proposed_facts",
        "bound_primary_path",
        "identity",
        "safety",
    ]
    for forbidden in ("path", "activity_path", "record", "digest", "filename"):
        assert forbidden not in signature.parameters


# ===========================================================================
# Sec. 17 items 38-41 -- THE CANONICAL-SNAPSHOT TOCTOU ATTACK
# ===========================================================================


class _HostileFacts(dict):
    """Honest to the FIRST enumeration, hostile to the canonicalizing one.

    ``set(proposed_facts)`` walks ``__iter__``; ``json.dumps(..., sort_keys=True)``
    walks ``PyMapping_Items`` -> ``items()``. A ``dict`` subclass can therefore
    report one key set to the preliminary check at step (1) and a DIFFERENT,
    smuggling one to canonicalization at step (9a). That gap is exactly what
    the step-(9b) recheck on the canonical snapshot closes.
    """

    def __init__(self, base: dict, smuggled_key: str, smuggled_value):
        super().__init__({**base, smuggled_key: smuggled_value})
        self._smuggled_key = smuggled_key
        self._sealed = False
        self.reads_after_seal: list[str] = []

    def seal(self) -> None:
        self._sealed = True

    def _note(self, how: str) -> None:
        if self._sealed:
            self.reads_after_seal.append(how)

    def __iter__(self):
        self._note("__iter__")
        return iter([k for k in dict.keys(self) if k != self._smuggled_key])

    def keys(self):
        self._note("keys")
        return [k for k in dict.keys(self) if k != self._smuggled_key]

    def items(self):
        self._note("items")
        return dict.items(self)

    def __getitem__(self, key):
        self._note(f"__getitem__:{key}")
        return dict.__getitem__(self, key)

    def get(self, key, default=None):
        self._note(f"get:{key}")
        return dict.get(self, key, default)


@pytest.mark.parametrize(
    "smuggled_key",
    ["bound_primary_sha256", "bound_primary_filename", "bound_primary_record_kind", "candidate"],
)
def test_a_hostile_mapping_that_changes_shape_between_reads_fails_closed(
    tmp_path: Path, smuggled_key: str
) -> None:
    """Item 38, stated exactly, plus item 39's never-consulted-again property.

    Asserts, mechanically, in one test:
      * the preliminary check at step (1) PASSES (the disguise works against
        that check alone -- which is exactly why it cannot be the authority);
      * canonicalization at step (9a) DOES produce the smuggled key;
      * the recheck at step (9b), against the CANONICAL snapshot, REFUSES;
      * no ``TypeError`` is ever raised;
      * the primary artifact is byte-for-byte unchanged;
      * no file exists at the companion's derived path;
      * the original object is never read again after canonicalization.
    """
    primary = _write_primary(tmp_path)
    before = Path(primary).read_bytes()
    hostile = _HostileFacts(_facts(), smuggled_key, "forged-value")

    # The disguise genuinely works against the preliminary enumeration...
    assert set(hostile) == ra._ALLOWED_PROPOSED_FACTS_KEYS
    # ...and genuinely fails to survive canonicalization.
    canonical = json.loads(json.dumps(hostile, ensure_ascii=True, sort_keys=True))
    assert smuggled_key in canonical

    with pytest.raises(ActivityRecordInvariantError) as caught:
        emit_activity_companion_or_refuse(
            hostile, bound_primary_path=primary, identity=_identity(), safety=_NONE
        )
    assert not isinstance(caught.value, TypeError)
    assert "canonical" in str(caught.value)
    assert Path(primary).read_bytes() == before
    assert not (tmp_path / "A_IQ-1.activity.json").exists()


def test_the_original_proposed_facts_object_is_never_read_after_canonicalization(
    tmp_path: Path,
) -> None:
    """Item 39, proven rather than stated: the instance records every access,
    and NONE occurs after canonicalization has completed."""
    primary = _write_primary(tmp_path)

    class _SealingFacts(_HostileFacts):
        def items(self):
            result = super().items()
            # Canonicalization has now walked this object for the last time.
            self.seal()
            return result

    hostile = _SealingFacts(_facts(), "bound_primary_sha256", "forged")
    with pytest.raises(ActivityRecordInvariantError):
        emit_activity_companion_or_refuse(
            hostile, bound_primary_path=primary, identity=_identity(), safety=_NONE
        )
    assert hostile.reads_after_seal == []

    # ...and the same on the SUCCESS path, where execution continues all the
    # way through the builder, the gate and the writer.
    class _SealingDict(dict):
        """Honest at every enumeration; it only RECORDS who reads it, and
        seals itself once canonicalization has walked it for the last time."""

        def __init__(self, base):
            super().__init__(base)
            self._sealed = False
            self.reads_after_seal: list[str] = []

        def _note(self, how):
            if self._sealed:
                self.reads_after_seal.append(how)

        def __iter__(self):
            self._note("__iter__")
            return dict.__iter__(self)

        def keys(self):
            self._note("keys")
            return dict.keys(self)

        def __getitem__(self, key):
            self._note(f"__getitem__:{key}")
            return dict.__getitem__(self, key)

        def get(self, key, default=None):
            self._note(f"get:{key}")
            return dict.get(self, key, default)

        def items(self):
            result = dict.items(self)
            self._sealed = True
            return result

    clean = _SealingDict(_facts())
    emission = emit_activity_companion_or_refuse(
        clean, bound_primary_path=primary, identity=_identity(), safety=_NONE
    )
    assert emission["refused"] is False
    assert clean.reads_after_seal == []


def test_a_caller_mutating_its_own_dict_afterwards_cannot_change_the_artifact(
    tmp_path: Path,
) -> None:
    """Item 40. The canonical snapshot is an independent, ordinary dict."""

    class _Subdict(dict):
        pass

    primary = _write_primary(tmp_path)
    facts = _Subdict(_facts())
    emit_activity_companion_or_refuse(
        facts, bound_primary_path=primary, identity=_identity(), safety=_NONE
    )
    emitted = (tmp_path / "A_IQ-1.activity.json").read_bytes()
    facts["runtime_reported_distinct_tool_call_ids"] = 999
    facts["bound_primary_sha256"] = "0" * 64
    assert (tmp_path / "A_IQ-1.activity.json").read_bytes() == emitted


def test_an_unserializable_facts_shape_refuses_without_raw_exception_text(
    tmp_path: Path,
) -> None:
    """Item 41. No raw ``TypeError``/``ValueError``/``RecursionError`` escapes,
    and the message names nothing about what made the value unserializable."""
    primary = _write_primary(tmp_path)

    class _Unprintable:
        def __repr__(self):  # pragma: no cover - must never be called
            raise AssertionError("the unserializable value was stringified")

    recursive: dict = {}
    recursive["self"] = recursive
    for value in (object(), _Unprintable(), recursive, {1: "a", "b": 2}):
        with pytest.raises(ActivityRecordInvariantError) as caught:
            emit_activity_companion_or_refuse(
                _facts(runtime_reported_distinct_tool_call_ids=value),
                bound_primary_path=primary,
                identity=_identity(),
                safety=_NONE,
            )
        assert not isinstance(caught.value, (TypeError, RecursionError))
        assert caught.value.__cause__ is None  # `from None`, deliberately
        assert "JSON-serializable" in str(caught.value)
    assert not (tmp_path / "A_IQ-1.activity.json").exists()


# ===========================================================================
# Sec. 17 items 29-32, 42-48, 50-51 -- BINDING
# ===========================================================================


def test_each_call_recomputes_binding_from_its_own_primary(tmp_path: Path) -> None:
    """Item 43. Positive proof of per-call recomputation."""
    p1 = _write_primary(tmp_path, task_id="IQ-1")
    p2 = _write_primary(tmp_path, task_id="IQ-2")
    emit_activity_companion_or_refuse(
        _facts(), bound_primary_path=p1, identity=_identity(task_id="IQ-1"), safety=_NONE
    )
    emit_activity_companion_or_refuse(
        _facts(), bound_primary_path=p2, identity=_identity(task_id="IQ-2"), safety=_NONE
    )
    c1 = json.loads((tmp_path / "A_IQ-1.activity.json").read_text(encoding="utf-8"))
    c2 = json.loads((tmp_path / "A_IQ-2.activity.json").read_text(encoding="utf-8"))
    assert c1["bound_primary_sha256"] != c2["bound_primary_sha256"]
    assert c1["bound_primary_filename"] == "A_IQ-1.json"
    assert c2["bound_primary_filename"] == "A_IQ-2.json"
    assert c1["bound_primary_sha256"] == hashlib.sha256(Path(p1).read_bytes()).hexdigest()
    assert c2["bound_primary_sha256"] == hashlib.sha256(Path(p2).read_bytes()).hexdigest()
    assert c1["bound_primary_identity_cross_check_performed"] is True


@pytest.mark.parametrize(
    "forged",
    [
        {"bound_primary_sha256": "0" * 64},
        {"bound_primary_filename": "B_IQ-2.json"},
        {"bound_primary_record_kind": ra.ATTEMPT_RECORD_KIND},
        {"bound_primary_identity_cross_check_performed": False},
        {"candidate": "B", "model_id": "minimax-m2.7"},
        {"record_version": "pi-implementer-qualification.v2"},
        {"record_kind": "qualification run record"},
        {"scoring_authority": True},
        {"qualification_policy_revision": "forged.r9"},
        {"claim_scope": "this artifact IS authority"},
        {"trust_namespaces": {}},
    ],
)
def test_the_internal_gate_refuses_a_hand_built_self_consistent_payload(
    tmp_path: Path, forged: dict
) -> None:
    """Item 42. The consumption boundary is tested DIRECTLY, with a payload
    that never went through ``build_activity_companion_record`` or
    ``proposed_facts`` -- internally self-consistent, and still refused."""
    primary = _write_primary(tmp_path)
    genuine = ra.build_activity_companion_record(
        bound_primary_path=primary,
        candidate="A",
        model_id=CANDIDATE_MODEL_IDS["A"],
        task_id="IQ-1",
        task_revision=TASKS_BY_ID["IQ-1"].task_revision,
        bound_primary_filename=os.path.basename(primary),
        bound_primary_sha256=hashlib.sha256(Path(primary).read_bytes()).hexdigest(),
        bound_primary_record_kind="qualification run record",
        bound_primary_identity_cross_check_performed=True,
        **_facts(),
    )
    hand_built = dict(genuine)
    hand_built.update(forged)
    with pytest.raises(ActivityRecordInvariantError):
        ra._require_valid_activity_payload(hand_built, bound_primary_path=primary)


def test_a_hand_built_payload_with_an_extra_or_missing_key_refuses(
    tmp_path: Path,
) -> None:
    """Item 42's key-set half, at the wider full-payload key set."""
    primary = _write_primary(tmp_path)
    genuine = ra.build_activity_companion_record(
        bound_primary_path=primary,
        candidate="A",
        model_id=CANDIDATE_MODEL_IDS["A"],
        task_id="IQ-1",
        task_revision=TASKS_BY_ID["IQ-1"].task_revision,
        bound_primary_filename=os.path.basename(primary),
        bound_primary_sha256=hashlib.sha256(Path(primary).read_bytes()).hexdigest(),
        bound_primary_record_kind="qualification run record",
        bound_primary_identity_cross_check_performed=True,
        **_facts(),
    )
    with pytest.raises(ActivityRecordInvariantError):
        ra._require_valid_activity_payload(
            {**genuine, "surprise": 1}, bound_primary_path=primary
        )
    dropped = dict(genuine)
    del dropped["claim_scope"]
    with pytest.raises(ActivityRecordInvariantError):
        ra._require_valid_activity_payload(dropped, bound_primary_path=primary)


@pytest.mark.parametrize(
    "wrong",
    [
        {"candidate": "B", "model_id": "minimax-m2.7"},
        {"task_id": "IQ-2", "task_revision": TASKS_BY_ID["IQ-2"].task_revision},
    ],
)
def test_an_identity_mismatch_against_the_bound_file_refuses(
    tmp_path: Path, wrong: dict
) -> None:
    """Items 29, 46. The bound file's OWN declared identity is cross-checked."""
    primary = _write_primary(tmp_path, candidate="A", task_id="IQ-1")
    identity = AttemptIdentity(
        candidate=wrong.get("candidate", "A"),
        model_id=wrong.get("model_id", CANDIDATE_MODEL_IDS["A"]),
        task_id=wrong.get("task_id", "IQ-1"),
        task_revision=wrong.get("task_revision", TASKS_BY_ID["IQ-1"].task_revision),
    )
    with pytest.raises(ActivityRecordInvariantError):
        emit_activity_companion_or_refuse(
            _facts(), bound_primary_path=primary, identity=identity, safety=_NONE
        )


def test_attempt_identity_itself_refuses_an_impossible_tuple() -> None:
    """Items 29-30. A candidate/model mismatch, and a revision that merely
    shares the task's id prefix, are both refused at construction."""
    with pytest.raises(ActivityRecordInvariantError):
        AttemptIdentity(
            candidate="A", model_id="minimax-m2.7", task_id="IQ-1",
            task_revision=TASKS_BY_ID["IQ-1"].task_revision,
        )
    with pytest.raises(ActivityRecordInvariantError):
        AttemptIdentity(
            candidate="A", model_id=CANDIDATE_MODEL_IDS["A"], task_id="IQ-1",
            task_revision="IQ-1@0000000000000000",
        )
    with pytest.raises(ActivityRecordInvariantError):
        AttemptIdentity(
            candidate="Z", model_id="whatever", task_id="IQ-1",
            task_revision=TASKS_BY_ID["IQ-1"].task_revision,
        )

    class _EqStr(str):
        def __eq__(self, other):  # noqa: D105
            return True

        def __hash__(self):  # noqa: D105
            return hash(str(self))

    with pytest.raises(ActivityRecordInvariantError):
        AttemptIdentity(
            candidate=_EqStr("A"), model_id=CANDIDATE_MODEL_IDS["A"], task_id="IQ-1",
            task_revision=TASKS_BY_ID["IQ-1"].task_revision,
        )


def test_an_unbindable_primary_is_unbound_never_unavailable(tmp_path: Path) -> None:
    """Item 31 / item 61. Read succeeded; the CONTENT disqualifies it."""
    for name, text in (
        ("A_IQ-1.json", "this is not json at all"),
        ("A_IQ-2.json", '["a", "json", "array"]'),
        ("A_IQ-3.json", json.dumps({"record_kind": "something else entirely"})),
        ("C_IQ-1.json", json.dumps({"no_record_kind": True})),
        ("C_IQ-2.json", json.dumps({"record_kind": 7})),
    ):
        path = _write_raw(tmp_path, name, text)
        with pytest.raises(UnboundPrimaryError):
            emit_activity_companion_or_refuse(
                _facts(),
                bound_primary_path=path,
                identity=_identity(task_id=name.split("_")[1].removesuffix(".json")),
                safety=_NONE,
            )


def test_binding_to_an_attempt_record_and_to_a_refusal_record(
    git_executable: str, tmp_path: Path
) -> None:
    """Items 32, 48. Each binds with its own correct kind. The refusal case
    records ``bound_primary_identity_cross_check_performed: False`` and still
    carries THIS attempt's own trusted identity, never one invented from the
    (identity-less) refusal bytes.

    The attempt artifact here is a GENUINE one, produced by driving the frozen
    controller through a real indeterminate dispatch -- never a hand-built dict.
    """
    from qualification.safety import build_refusal_record
    from qualification.semantic_session import SemanticPromptDispatchState

    harness = Harness("A", git_executable)
    harness.dispatch_state = SemanticPromptDispatchState.SEND_STATE_INDETERMINATE
    attempt_path = str(tmp_path / "A_IQ-1.json")
    attempt_result = harness.run(IQ1_TASK, attempt_path)
    assert attempt_result.attempt_record is not None
    # An indeterminate dispatch never reaches phase 2, so the controller itself
    # emitted NO companion -- truthfully, and without inventing a zeroed claim.
    assert (
        attempt_result.runtime_activity_companion
        is RuntimeActivityCompanionDisposition.UNAVAILABLE_NO_TURN_OBSERVATION
    )
    assert not (tmp_path / "A_IQ-1.activity.json").exists()

    emit_activity_companion_or_refuse(
        _facts(), bound_primary_path=attempt_path, identity=_identity(), safety=_NONE
    )
    bound_attempt = json.loads(
        (tmp_path / "A_IQ-1.activity.json").read_text(encoding="utf-8")
    )
    assert bound_attempt["bound_primary_record_kind"] == ra.ATTEMPT_RECORD_KIND
    assert bound_attempt["bound_primary_identity_cross_check_performed"] is True
    assert verify_activity_companion_binding(
        str(tmp_path / "A_IQ-1.activity.json"), attempt_path
    )

    # Item 47: the attempt schema carries all four identity fields, so each
    # mismatch against it is independently refused -- the same cross-check the
    # run-record binding gets, on the other identity-bearing kind.
    for wrong in (
        _identity(candidate="B"),
        _identity(task_id="IQ-2"),
    ):
        with pytest.raises(ActivityRecordInvariantError):
            emit_activity_companion_or_refuse(
                _facts(),
                bound_primary_path=attempt_path,
                identity=wrong,
                safety=_NONE,
            )

    refusal = build_refusal_record(
        refused_record_kind="qualification run record",
        finding_count=1,
        finding_categories=["api_key_value_present"],
    )
    # The refusal artifact carries NO identity at all -- that is the point.
    for field_name in ("candidate", "model_id", "task_id", "task_revision"):
        assert field_name not in refusal
    refusal_path = str(tmp_path / "A_IQ-2.json")
    Path(refusal_path).write_text(
        json.dumps(refusal, indent=2, sort_keys=True) + chr(10),
        encoding="utf-8",
        newline=chr(10),
    )
    emit_activity_companion_or_refuse(
        _facts(),
        bound_primary_path=refusal_path,
        identity=_identity(task_id="IQ-2"),
        safety=_NONE,
    )
    bound_refusal = json.loads(
        (tmp_path / "A_IQ-2.activity.json").read_text(encoding="utf-8")
    )
    assert bound_refusal["bound_primary_record_kind"] == "artifact emission refusal"
    assert bound_refusal["bound_primary_identity_cross_check_performed"] is False
    assert bound_refusal["candidate"] == "A"
    assert bound_refusal["task_id"] == "IQ-2"
    assert bound_refusal["task_revision"] == TASKS_BY_ID["IQ-2"].task_revision
    # Source-level: no code path reads identity off a parsed refusal record.
    source = (_QUALIFICATION_DIR / "runtime_activity.py").read_text(encoding="utf-8")
    assert source.count("_require_identity_matches(bound_record") == 2
    assert "if actual_cross_check:" in source
    assert "if identity_cross_check_performed:" in source


def test_the_companion_path_is_derived_and_validated_without_python_assert() -> None:
    """Items 44-45, plus the ACCEPTED IMPLEMENTATION ERRATUM: the path-shape
    invariant must NOT be a bare ``assert``, so ``python -O`` cannot weaken it."""
    assert ra._derive_activity_path("/x/A_IQ-1.json") == "/x/A_IQ-1.activity.json"
    assert ra._derive_activity_path("/x/A_IQ-1.json") == ra._derive_activity_path(
        "/x/A_IQ-1.json"
    )
    assert ra._derive_activity_path(r"C:\r\A_IQ-1.json") == r"C:\r\A_IQ-1.activity.json"
    assert ra._derive_activity_path("/a/A_IQ-1.json") != ra._derive_activity_path(
        "/b/A_IQ-1.json"
    )
    for bad in (
        "/x/A_IQ-1.txt",
        "/x/A_IQ-1",
        "/x/.json",
        "/x/A_IQ-1.activity.json",  # a companion is never itself a primary
        "",
        "   ",
        None,
        7,
    ):
        with pytest.raises(ActivityRecordInvariantError):
            ra._derive_activity_path(bad)

    source = (_QUALIFICATION_DIR / "runtime_activity.py").read_text(encoding="utf-8")
    assert not re.search(r"^\s*assert\b", source, re.MULTILINE), (
        "the companion module must never use a bare `assert` as an authority "
        "invariant -- `python -O` strips it"
    )


def test_an_existing_companion_path_collides_and_leaves_the_first_untouched(
    tmp_path: Path,
) -> None:
    """Item 50. Exclusive-create, unmodified, through the shared writer."""
    primary = _write_primary(tmp_path)
    emit_activity_companion_or_refuse(
        _facts(), bound_primary_path=primary, identity=_identity(), safety=_NONE
    )
    first = (tmp_path / "A_IQ-1.activity.json").read_bytes()
    with pytest.raises(EvidencePathCollisionError):
        emit_activity_companion_or_refuse(
            _facts(runtime_reported_distinct_tool_call_ids=3),
            bound_primary_path=primary,
            identity=_identity(),
            safety=_NONE,
        )
    assert (tmp_path / "A_IQ-1.activity.json").read_bytes() == first


def test_binding_verification_rereads_and_rehashes_at_call_time(tmp_path: Path) -> None:
    """Item 51. The stored digest is never treated as self-certifying."""
    primary = _write_primary(tmp_path)
    emit_activity_companion_or_refuse(
        _facts(), bound_primary_path=primary, identity=_identity(), safety=_NONE
    )
    companion = str(tmp_path / "A_IQ-1.activity.json")
    assert verify_activity_companion_binding(companion, primary) is True

    Path(primary).write_text(
        json.dumps({**_primary_payload(), "tampered": True}), encoding="utf-8"
    )
    assert verify_activity_companion_binding(companion, primary) is False
    assert verify_activity_companion_binding(companion, str(tmp_path / "missing.json")) is False
    assert verify_activity_companion_binding(str(tmp_path / "missing.activity.json"), primary) is False


# ===========================================================================
# 5F3B-HARNESS-OBS1-IMPL-FU1 -- ADVERSARIAL CLOSURE REGRESSIONS
#
# Three narrow implementation defects, found by independent review against
# the ACTUAL shipped code (not the design):
#   1. verify_activity_companion_binding under-verified (two fields only)
#   2. project_runtime_tool_activity silently mapped ANY non-SETTLED value,
#      including a malformed one, to a plausible durable capture basis
#   3. RuntimeToolActivitySnapshot bounded each of
#      tool_execution_start_events/tool_execution_end_events individually but
#      never their SUM against the one shared total-event ceiling they both
#      draw from
# ===========================================================================


def _write_genuine_companion(
    tmp_path: Path, *, candidate: str = "A", task_id: str = "IQ-1"
) -> tuple[str, str, dict]:
    """A genuine, fully emitted run-record-bound companion, for mutation
    tests. Returns ``(companion_path, primary_path, parsed_companion_dict)``.
    """
    primary_path = _write_primary(tmp_path, candidate=candidate, task_id=task_id)
    emit_activity_companion_or_refuse(
        _facts(),
        bound_primary_path=primary_path,
        identity=_identity(candidate=candidate, task_id=task_id),
        safety=_NONE,
    )
    companion_path = str(tmp_path / f"{candidate}_{task_id}.activity.json")
    companion = json.loads(Path(companion_path).read_text(encoding="utf-8"))
    return companion_path, primary_path, companion


def _write_mutated_companion(tmp_path: Path, name: str, companion: dict) -> str:
    path = tmp_path / name
    path.write_text(json.dumps(companion), encoding="utf-8")
    return str(path)


# -- 1a. verify_activity_companion_binding must catch EVERY declared mutation


def test_verifier_true_for_an_unchanged_genuine_run_record_companion(
    tmp_path: Path,
) -> None:
    companion_path, primary_path, _ = _write_genuine_companion(tmp_path)
    assert verify_activity_companion_binding(companion_path, primary_path) is True


def test_verifier_true_for_an_unchanged_genuine_attempt_companion(
    git_executable: str, tmp_path: Path
) -> None:
    from qualification.semantic_session import SemanticPromptDispatchState

    harness = Harness("A", git_executable)
    harness.dispatch_state = SemanticPromptDispatchState.SEND_STATE_INDETERMINATE
    attempt_path = str(tmp_path / "A_IQ-1.json")
    harness.run(IQ1_TASK, attempt_path)
    emit_activity_companion_or_refuse(
        _facts(), bound_primary_path=attempt_path, identity=_identity(), safety=_NONE
    )
    companion_path = str(tmp_path / "A_IQ-1.activity.json")
    assert verify_activity_companion_binding(companion_path, attempt_path) is True


@pytest.mark.parametrize(
    "mutation",
    [
        # candidate + model_id to another internally-valid pair
        {"candidate": "B", "model_id": CANDIDATE_MODEL_IDS["B"]},
        # task_id + task_revision to another internally-valid pair
        {"task_id": "IQ-2", "task_revision": TASKS_BY_ID["IQ-2"].task_revision},
        {"record_kind": "qualification attempt (indeterminate semantic dispatch)"},
        {"record_version": "pi-implementer-qualification-activity.v2"},
        {"qualification_policy_revision": "forged.r9"},
        {"scoring_authority": True},
        {"claim_scope": "THIS ARTIFACT IS SCORING AUTHORITY"},
        {"bound_primary_record_kind": "qualification attempt (indeterminate semantic dispatch)"},
        {"bound_primary_identity_cross_check_performed": False},
        {"is_review_packet": True},
        {"reviewer_invoked": True},
        {"trust_namespaces": {}},
    ],
    ids=[
        "candidate+model_id",
        "task_id+task_revision",
        "record_kind",
        "record_version",
        "qualification_policy_revision",
        "scoring_authority",
        "claim_scope",
        "bound_primary_record_kind",
        "bound_primary_identity_cross_check_performed",
        "is_review_packet",
        "reviewer_invoked",
        "trust_namespaces",
    ],
)
def test_verifier_false_after_any_declared_field_mutation_run_record(
    tmp_path: Path, mutation: dict
) -> None:
    """The FALSE-POSITIVE this FU1 closes: the ORIGINAL implementation
    checked only ``bound_primary_sha256``/``bound_primary_filename`` and
    would have returned ``True`` for every mutation below, since none of them
    touches either of those two fields."""
    companion_path, primary_path, companion = _write_genuine_companion(tmp_path)
    tampered = {**companion, **mutation}
    tampered_path = _write_mutated_companion(tmp_path, "tampered.activity.json", tampered)
    assert verify_activity_companion_binding(tampered_path, primary_path) is False
    # The genuine companion (written to its OWN separate path) still verifies
    # True -- the attack was checked against an independent tampered copy,
    # never the genuine file itself.
    assert verify_activity_companion_binding(companion_path, primary_path) is True


def test_verifier_false_after_removing_a_required_field(tmp_path: Path) -> None:
    companion_path, primary_path, companion = _write_genuine_companion(tmp_path)
    for dropped in ("candidate", "claim_scope", "runtime_reported_aido_read_call_ids"):
        tampered = dict(companion)
        del tampered[dropped]
        tampered_path = _write_mutated_companion(
            tmp_path, f"missing_{dropped}.activity.json", tampered
        )
        assert verify_activity_companion_binding(tampered_path, primary_path) is False
    # The unmutated genuine pair is unaffected.
    assert verify_activity_companion_binding(companion_path, primary_path) is True


def test_verifier_false_after_adding_an_unknown_field(tmp_path: Path) -> None:
    companion_path, primary_path, companion = _write_genuine_companion(tmp_path)
    tampered = {**companion, "an_unrecognized_extra_field": "surprise"}
    tampered_path = _write_mutated_companion(tmp_path, "extra.activity.json", tampered)
    assert verify_activity_companion_binding(tampered_path, primary_path) is False
    assert verify_activity_companion_binding(companion_path, primary_path) is True


def test_verifier_false_after_digest_mutation(tmp_path: Path) -> None:
    companion_path, primary_path, companion = _write_genuine_companion(tmp_path)
    tampered = {**companion, "bound_primary_sha256": "0" * 64}
    tampered_path = _write_mutated_companion(tmp_path, "digest.activity.json", tampered)
    assert verify_activity_companion_binding(tampered_path, primary_path) is False


def test_verifier_false_after_filename_mutation(tmp_path: Path) -> None:
    companion_path, primary_path, companion = _write_genuine_companion(tmp_path)
    tampered = {**companion, "bound_primary_filename": "B_IQ-9.json"}
    tampered_path = _write_mutated_companion(tmp_path, "filename.activity.json", tampered)
    assert verify_activity_companion_binding(tampered_path, primary_path) is False


def test_verifier_false_after_primary_byte_mutation(tmp_path: Path) -> None:
    companion_path, primary_path, companion = _write_genuine_companion(tmp_path)
    assert verify_activity_companion_binding(companion_path, primary_path) is True
    Path(primary_path).write_bytes(Path(primary_path).read_bytes() + b" ")
    assert verify_activity_companion_binding(companion_path, primary_path) is False


def test_verifier_refusal_bound_companion_preserves_no_identity_semantics(
    tmp_path: Path,
) -> None:
    """The refusal-bound companion carries no bound identity to check --
    ``bound_primary_identity_cross_check_performed`` MUST be ``False``, and the
    verifier must never fabricate a check the refusal bytes cannot support.

    Only the binding facts a refusal artifact CAN actually establish are
    exercised here: digest/filename/kind agreement, the fixed header, the
    closed key set, and the exact-``False`` cross-check flag. A
    candidate/model mismatch on a refusal-bound companion is deliberately NOT
    asserted to be caught -- the frozen design (Sec. 10.5) has nothing in the
    refusal bytes to compare it against, and inventing such a check would
    itself be the prohibited "fabricated identity cross-check".
    """
    from qualification.safety import build_refusal_record

    refusal = build_refusal_record(
        refused_record_kind="qualification run record",
        finding_count=1,
        finding_categories=["api_key_value_present"],
    )
    refusal_path = str(tmp_path / "A_IQ-1.json")
    Path(refusal_path).write_text(
        json.dumps(refusal, indent=2, sort_keys=True) + chr(10),
        encoding="utf-8",
        newline=chr(10),
    )
    emit_activity_companion_or_refuse(
        _facts(), bound_primary_path=refusal_path, identity=_identity(), safety=_NONE
    )
    companion_path = str(tmp_path / "A_IQ-1.activity.json")
    companion = json.loads(Path(companion_path).read_text(encoding="utf-8"))
    assert companion["bound_primary_identity_cross_check_performed"] is False

    # Unchanged -> True.
    assert verify_activity_companion_binding(companion_path, refusal_path) is True

    # Fabricating a cross-check the refusal bytes cannot support -> False.
    forged_flag = {**companion, "bound_primary_identity_cross_check_performed": True}
    forged_path = _write_mutated_companion(tmp_path, "forged_flag.activity.json", forged_flag)
    assert verify_activity_companion_binding(forged_path, refusal_path) is False

    # Digest/filename/kind tampering are still caught for a refusal binding,
    # exactly as for a run/attempt binding.
    for mutation in (
        {"bound_primary_sha256": "0" * 64},
        {"bound_primary_filename": "B_IQ-9.json"},
        {"bound_primary_record_kind": "qualification run record"},
        {"record_kind": "qualification run record"},
        {"scoring_authority": True},
    ):
        tampered = {**companion, **mutation}
        tampered_path = _write_mutated_companion(
            tmp_path, f"refusal_tampered_{len(mutation)}_{id(mutation)}.activity.json", tampered
        )
        assert verify_activity_companion_binding(tampered_path, refusal_path) is False


def test_verifier_false_for_same_file_or_swapped_argument_order(tmp_path: Path) -> None:
    """Post-fix adversarial probe: pointing the verifier at degenerate/attack
    argument shapes -- the same path for both arguments, or the two
    arguments swapped -- must never accidentally verify True."""
    companion_path, primary_path, _ = _write_genuine_companion(tmp_path)
    assert verify_activity_companion_binding(companion_path, companion_path) is False
    assert verify_activity_companion_binding(primary_path, primary_path) is False
    assert verify_activity_companion_binding(primary_path, companion_path) is False
    # The genuine, correctly-ordered call is unaffected.
    assert verify_activity_companion_binding(companion_path, primary_path) is True


def test_verifier_does_not_cross_bind_two_genuine_companions(tmp_path: Path) -> None:
    """A genuine companion for primary A, checked against a DIFFERENT
    genuine primary B, must not verify True merely because both sides are
    individually well-formed."""
    companion_a, primary_a, _ = _write_genuine_companion(tmp_path, task_id="IQ-1")
    _companion_b, primary_b, _ = _write_genuine_companion(tmp_path, task_id="IQ-2")
    assert verify_activity_companion_binding(companion_a, primary_a) is True
    assert verify_activity_companion_binding(companion_a, primary_b) is False


def test_verifier_is_read_only_and_leaks_nothing_on_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """Post-fix adversarial question: can verifier validation mutate or
    write either file, or leak raw JSON/path/exception text?"""
    companion_path, primary_path, companion = _write_genuine_companion(tmp_path)
    tampered = {**companion, "scoring_authority": True}
    tampered_path = _write_mutated_companion(tmp_path, "leak_check.activity.json", tampered)

    before_companion = Path(companion_path).read_bytes()
    before_primary = Path(primary_path).read_bytes()
    before_tampered = Path(tampered_path).read_bytes()
    before_listing = sorted(p.name for p in tmp_path.iterdir())

    result_false = verify_activity_companion_binding(tampered_path, primary_path)
    result_true = verify_activity_companion_binding(companion_path, primary_path)

    assert result_false is False
    assert result_true is True
    assert Path(companion_path).read_bytes() == before_companion
    assert Path(primary_path).read_bytes() == before_primary
    assert Path(tampered_path).read_bytes() == before_tampered
    assert sorted(p.name for p in tmp_path.iterdir()) == before_listing

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


@pytest.mark.parametrize(
    "companion_content",
    [
        b"not json at all",
        b'["a", "json", "array"]',
        b"",
        b"null",
        b'{"candidate": "A"',  # truncated
    ],
)
def test_verifier_false_for_malformed_companion_bytes_never_raises(
    tmp_path: Path, companion_content: bytes
) -> None:
    _companion_path, primary_path, _ = _write_genuine_companion(tmp_path, task_id="IQ-2")
    malformed_path = tmp_path / "malformed.activity.json"
    malformed_path.write_bytes(companion_content)
    assert verify_activity_companion_binding(str(malformed_path), primary_path) is False


# -- 2. project_runtime_tool_activity must fail closed on a malformed outcome


def test_project_runtime_tool_activity_refuses_every_malformed_turn_outcome() -> None:
    activity = _Activity({}, {})
    baseline = _Baseline({}, frozenset())

    class _ForeignEnum:
        SETTLED = "SETTLED"

    class _EqualityForger:
        def __eq__(self, other):  # noqa: D105
            return True

        def __hash__(self):  # noqa: D105
            return hash(SemanticTurnOutcome.SETTLED)

    for bad in (
        "SETTLED",
        "DEADLINE_REACHED",
        "OBSERVATION_FAILED",
        None,
        True,
        False,
        0,
        1,
        object(),
        {},
        {"turn_outcome": "SETTLED"},
        [SemanticTurnOutcome.SETTLED],
        _ForeignEnum(),
        _ForeignEnum.SETTLED,
        _EqualityForger(),
    ):
        with pytest.raises(ActivityRecordInvariantError) as caught:
            project_runtime_tool_activity(activity, baseline, turn_outcome=bad)
        assert not isinstance(caught.value, TypeError)
        # No caller value is ever embedded in the refusal message.
        assert repr(bad) not in str(caught.value)


def test_semantic_turn_outcome_cannot_be_subclassed_with_new_members() -> None:
    """Documents WHY a subclass bypass is structurally impossible: Python
    refuses to subclass an Enum that already defines members at all, so
    ``type(turn_outcome) is SemanticTurnOutcome`` cannot be defeated by a
    same-named subclass member."""
    with pytest.raises(TypeError):

        class _Subclassed(SemanticTurnOutcome):
            EXTRA = "EXTRA"


@pytest.mark.parametrize(
    "outcome,expected",
    [
        (SemanticTurnOutcome.SETTLED, "agent_settled"),
        (SemanticTurnOutcome.DEADLINE_REACHED, "wait_ended_before_settled"),
        (SemanticTurnOutcome.OBSERVATION_FAILED, "wait_ended_before_settled"),
    ],
)
def test_project_runtime_tool_activity_positive_controls_still_hold(
    outcome, expected
) -> None:
    """The three genuine enum members remain fully accepted after the
    exact-type closure -- this fix narrows the input domain, it does not
    change the output mapping for any genuine value."""
    snapshot = project_runtime_tool_activity(
        _Activity({}, {}), _Baseline({}, frozenset()), turn_outcome=outcome
    )
    assert snapshot.capture_basis == expected


def test_a_malformed_turn_outcome_from_the_real_port_never_corrupts_qualification_facts(
    git_executable: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Even in the pathological case where the injected ``observe_semantic_turn``
    port itself raises the new ``ActivityRecordInvariantError`` (e.g. a future
    bug feeding a malformed value into ``project_runtime_tool_activity``
    INSIDE the port), the frozen controller's own pre-existing
    ``except Exception: observed_turn = None`` at TURN_COMPLETION (unchanged
    by this fix) already absorbs it into a truthful ``OBSERVATION_FAILED`` --
    the identical fate a raised ``LiveSemanticAdapterError`` already has.
    Every qualification-facing fact is therefore unaffected by this fix."""
    harness = Harness("A", git_executable)

    def _raising_observe_semantic_turn(request):
        raise ActivityRecordInvariantError("synthetic: malformed turn outcome upstream")

    monkeypatch.setattr(harness, "observe_semantic_turn", _raising_observe_semantic_turn)
    evidence_path = str(tmp_path / "A_IQ-1.json")
    result = harness.run(IQ1_TASK, evidence_path)
    assert result.turn_outcome is SemanticTurnOutcome.OBSERVATION_FAILED
    assert result.semantic_prompts_sent == 1  # Invariant I-1: unaffected
    assert (
        result.runtime_activity_companion
        is RuntimeActivityCompanionDisposition.EMITTED
    )
    companion = json.loads((tmp_path / "A_IQ-1.activity.json").read_text(encoding="utf-8"))
    assert companion["runtime_reported_tool_activity_available"] is False


# -- 3. the impossible total-event-count state


@pytest.mark.parametrize(
    "start_events,end_events,should_refuse",
    [
        (MAX_ACTIVITY_TOOL_COUNT, 1, True),
        (1, MAX_ACTIVITY_TOOL_COUNT, True),
        (MAX_ACTIVITY_TOOL_COUNT, MAX_ACTIVITY_TOOL_COUNT, True),
        (MAX_ACTIVITY_TOOL_COUNT // 2, MAX_ACTIVITY_TOOL_COUNT // 2, False),
        (10, 10, False),
        (0, 0, False),
    ],
)
def test_snapshot_refuses_an_impossible_total_event_sum(
    start_events: int, end_events: int, should_refuse: bool
) -> None:
    kwargs = dict(
        capture_basis="agent_settled",
        tool_execution_start_events=start_events,
        tool_execution_end_events=end_events,
        distinct_tool_call_ids=0,
        unidentified_tool_call_id_seen=False,
        aido_read_call_ids=0,
        aido_read_end_observed=0,
        aido_read_error_results=0,
        aido_edit_call_ids=0,
        aido_edit_end_observed=0,
        aido_edit_error_results=0,
        unexpected_tool_call_ids=0,
        unexpected_tool_end_observed=0,
        unexpected_tool_error_results=0,
    )
    if should_refuse:
        with pytest.raises(ActivityRecordInvariantError):
            RuntimeToolActivitySnapshot(**kwargs)
    else:
        RuntimeToolActivitySnapshot(**kwargs)  # must not raise


def test_the_full_companion_payload_gate_enforces_the_same_sum_cap(
    tmp_path: Path,
) -> None:
    """A hand-built ``proposed_facts`` mapping -- never going through
    ``RuntimeToolActivitySnapshot.__post_init__`` at all -- must be caught by
    the SAME cross-field invariant at the full-payload validation boundary
    (``_require_valid_activity_facts`` / ``_require_runtime_cross_field_invariants``),
    proving the rule lives at the shared gate, not only at construction."""
    primary = _write_primary(tmp_path)
    impossible = _facts(
        runtime_reported_tool_execution_start_events=MAX_ACTIVITY_TOOL_COUNT,
        runtime_reported_tool_execution_end_events=1,
        runtime_reported_distinct_tool_call_ids=0,
        runtime_reported_aido_read_call_ids=0,
        runtime_reported_aido_read_end_observed=0,
        runtime_reported_aido_read_error_results=0,
        runtime_reported_aido_edit_call_ids=0,
        runtime_reported_aido_edit_end_observed=0,
        runtime_reported_aido_edit_error_results=0,
        runtime_reported_unexpected_tool_call_ids=0,
        runtime_reported_unexpected_tool_end_observed=0,
        runtime_reported_unexpected_tool_error_results=0,
    )
    with pytest.raises(ActivityRecordInvariantError):
        emit_activity_companion_or_refuse(
            impossible, bound_primary_path=primary, identity=_identity(), safety=_NONE
        )
    assert not (tmp_path / "A_IQ-1.activity.json").exists()

    # And the exact boundary (sum == MAX) is accepted through the full
    # emission boundary too, not merely at direct construction.
    boundary_ok = _facts(
        runtime_reported_tool_execution_start_events=MAX_ACTIVITY_TOOL_COUNT // 2,
        runtime_reported_tool_execution_end_events=MAX_ACTIVITY_TOOL_COUNT // 2,
        runtime_reported_distinct_tool_call_ids=0,
        runtime_reported_aido_read_call_ids=0,
        runtime_reported_aido_read_end_observed=0,
        runtime_reported_aido_read_error_results=0,
        runtime_reported_aido_edit_call_ids=0,
        runtime_reported_aido_edit_end_observed=0,
        runtime_reported_aido_edit_error_results=0,
        runtime_reported_unexpected_tool_call_ids=0,
        runtime_reported_unexpected_tool_end_observed=0,
        runtime_reported_unexpected_tool_error_results=0,
    )
    emission = emit_activity_companion_or_refuse(
        boundary_ok, bound_primary_path=primary, identity=_identity(), safety=_NONE
    )
    assert emission["refused"] is False


def test_the_sum_cap_is_derived_never_a_new_invented_number() -> None:
    """No second cap was invented: the sum bound reuses the SAME
    MAX_ACTIVITY_TOOL_COUNT constant already derived from RunBounds.max_events."""
    from ar2.supervisor import RunBounds

    assert MAX_ACTIVITY_TOOL_COUNT == RunBounds().max_events
    source = (_QUALIFICATION_DIR / "runtime_activity.py").read_text(encoding="utf-8")
    # Exactly one NEW comparison site was added for the sum invariant; no
    # second constant, no clamp (`min(`), anywhere near it.
    assert "min(" not in source


# -- 4. post-fix adversarial: frozen contracts are untouched by this FU1


def test_fu1_touched_no_frozen_contract() -> None:
    """Sec. 4 of the FU1 prompt, mechanically. None of these three fixes
    added a gate, a port, a policy revision, a schema version, or a new
    disposition value."""
    from qualification import ACTIVITY_RECORD_VERSION as _ARV
    from qualification import QUALIFICATION_POLICY_REVISION as _QPR
    from qualification import RECORD_VERSION as _RV

    assert _ARV == "pi-implementer-qualification-activity.v1"
    assert _RV == "pi-implementer-qualification.v2"
    assert _QPR == "aido-implementer-role-capability-qualification-policy.r1"
    assert {d.value for d in RuntimeActivityCompanionDisposition} == {
        "EMITTED",
        "UNAVAILABLE_NO_TURN_OBSERVATION",
        "UNAVAILABLE_NO_PRIMARY",
        "UNAVAILABLE_UNBOUND_PRIMARY",
        "REFUSED_INVARIANT",
        "REFUSED_SCRUB",
        "REFUSED_PATH_COLLISION",
        "UNAVAILABLE_INTERNAL_ERROR",
    }
    names = {f.name for f in dataclasses.fields(SemanticTurnObservation)}
    assert names == {
        "runtime_session_id",
        "turn_outcome",
        "agent_end_observed",
        "tool_activity",
    }
    source = (_QUALIFICATION_DIR / "runtime_activity.py").read_text(encoding="utf-8")
    assert len(re.findall(r"^\s*except Exception:\s*$", source, re.MULTILINE)) == 1
    assert "except BaseException" not in source
    assert not re.search(r"^\s*except\s*:", source, re.MULTILINE)


# ===========================================================================
# 5F3B-HARNESS-OBS1-IMPL-FU2 -- THE PUBLIC VERIFIER PARAMETER-TYPE GATE
#
# Finding: verify_activity_companion_binding called open(companion_path, "rb")
# before mechanically establishing companion_path was an ordinary path
# string, and its read-side except clause did not catch TypeError. A
# malformed direct caller (None, object()) could therefore escape this
# purported "never raises" boolean function as an uncontrolled TypeError --
# and, more seriously, Python's open() accepts an int as an ALREADY-OPEN file
# descriptor, so a malformed caller passing an integer could cause this
# PURPORTED PATH VERIFIER to consume, read from, and CLOSE a file descriptor
# it does not own.
# ===========================================================================


#: The exact "obviously not an ordinary str path" domain the FU2 prompt
#: enumerates. A ``str`` subclass is INCLUDED here (see
#: ``_StrSubclass`` below) and is refused by the SAME exact-type discipline
#: (``type(...) is str``) this package already applies everywhere else.
class _StrSubclass(str):
    pass


def _fu2_malformed_path_values() -> tuple:
    return (
        None,
        True,
        False,
        0,
        1,
        object(),
        Path("some/relative/path.json"),
        _StrSubclass("looks/like/a/path.json"),
    )


@pytest.mark.parametrize("bad", _fu2_malformed_path_values())
def test_verifier_refuses_a_malformed_companion_path_type_before_any_io(
    tmp_path: Path, bad: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every malformed TYPE for ``companion_path`` returns ``False`` --
    never raises, never performs any filesystem operation. A genuine,
    well-formed ``primary_path`` is used as the second argument so the ONLY
    thing under test is the FIRST parameter's type gate.

    No ``open()``/``read()`` call is ever reached for a malformed type: proven
    by monkeypatching the builtin to fail the test loudly (an
    ``AssertionError``, never silently) if it is invoked at all, AFTER the
    genuine companion/primary pair has already been written to disk.
    """
    import builtins

    _companion_path, primary_path, _ = _write_genuine_companion(tmp_path)

    def _open_must_never_be_called(*args, **kwargs):  # pragma: no cover
        raise AssertionError("open() was called for a malformed companion_path type")

    monkeypatch.setattr(builtins, "open", _open_must_never_be_called)
    result = verify_activity_companion_binding(bad, primary_path)
    assert result is False
    assert type(result) is bool


@pytest.mark.parametrize("bad", _fu2_malformed_path_values())
def test_verifier_refuses_a_malformed_primary_path_type_before_any_io(
    tmp_path: Path, bad: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The identical gate, independently, for the SECOND parameter. A
    genuine, well-formed ``companion_path`` is used as the first argument."""
    import builtins

    companion_path, _primary_path, _ = _write_genuine_companion(tmp_path)

    def _open_must_never_be_called(*args, **kwargs):  # pragma: no cover
        raise AssertionError("open() was called for a malformed primary_path type")

    monkeypatch.setattr(builtins, "open", _open_must_never_be_called)
    result = verify_activity_companion_binding(companion_path, bad)
    assert result is False
    assert type(result) is bool


def test_verifier_type_gate_performs_zero_filesystem_operations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The type gate itself is LOAD-BEARING, not merely that some later
    validation happened to fail for the same reason. Proven by making the
    builtin ``open`` raise loudly (a test failure, not a caught exception) if
    it is EVER invoked, then calling the verifier with malformed types on
    BOTH parameters, independently and together."""
    import builtins

    def _open_must_never_be_called(*args, **kwargs):  # pragma: no cover
        raise AssertionError(
            f"open() was called with args={args!r} kwargs={kwargs!r} -- the "
            "type gate did not short-circuit before any filesystem operation"
        )

    monkeypatch.setattr(builtins, "open", _open_must_never_be_called)
    for bad in _fu2_malformed_path_values():
        assert verify_activity_companion_binding(bad, "genuine/looking/path.json") is False
        assert verify_activity_companion_binding("genuine/looking/path.json", bad) is False
        assert verify_activity_companion_binding(bad, bad) is False


def test_verifier_raises_nothing_and_emits_nothing_for_malformed_types(
    capsys: pytest.CaptureFixture,
) -> None:
    """No malformed-type call may raise, print, or otherwise leak anything."""
    for bad in _fu2_malformed_path_values():
        try:
            result = verify_activity_companion_binding(bad, bad)
        except Exception as exc:  # pragma: no cover - the failure path itself
            pytest.fail(f"verify_activity_companion_binding raised for {bad!r}: {exc!r}")
        assert result is False
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_verifier_never_consumes_or_closes_a_caller_owned_file_descriptor(
    tmp_path: Path,
) -> None:
    """THE load-bearing file-descriptor regression the FU2 prompt requires.

    Python's ``open()`` treats an ``int`` as an ALREADY-OPEN file descriptor
    and takes ownership of it. A genuine caller resource -- opened here via
    the real OS-level ``os.open`` -- must remain fully open, unread, and at
    its original file position after being passed as ``companion_path`` to
    this purported path verifier: the type gate must refuse it BEFORE
    ``open()`` is ever reached, not merely handle the resulting failure
    gracefully after consuming the descriptor.
    """
    victim_path = tmp_path / "caller_owned_resource.txt"
    original_content = b"caller-owned content, must survive untouched\n"
    victim_path.write_bytes(original_content)

    caller_fd = os.open(str(victim_path), os.O_RDONLY)
    try:
        # Prove the fd is genuinely open and at position 0 before the call.
        assert os.fstat(caller_fd).st_size == len(original_content)
        assert os.lseek(caller_fd, 0, os.SEEK_CUR) == 0

        result = verify_activity_companion_binding(caller_fd, "some/genuine/primary.json")
        assert result is False

        # The descriptor must remain OPEN (os.fstat does not raise) --
        # verifying the old defect (the with-block's implicit close()) is
        # closed, not merely that the return value happened to be correct.
        os.fstat(caller_fd)  # raises OSError if the fd was closed

        # Its position must be UNCHANGED -- proving no read was attempted.
        assert os.lseek(caller_fd, 0, os.SEEK_CUR) == 0

        # And its content is exactly what the caller wrote -- fully intact.
        assert os.read(caller_fd, 4096) == original_content
    finally:
        try:
            os.close(caller_fd)
        except OSError:
            pass  # already closed would itself be a test failure, caught above


def test_verifier_never_consumes_or_closes_a_caller_owned_primary_fd(
    tmp_path: Path,
) -> None:
    """The identical file-descriptor regression for ``primary_path`` -- the
    SECOND parameter, independently. A well-formed ``companion_path`` string
    is used (pointing at a file that need not even exist) so the ONLY thing
    protecting the caller's descriptor is the type gate on the second
    parameter, not any earlier short-circuit on the first.
    """
    victim_path = tmp_path / "second_caller_owned_resource.txt"
    original_content = b"a second, independent caller-owned resource\n"
    victim_path.write_bytes(original_content)

    caller_fd = os.open(str(victim_path), os.O_RDONLY)
    try:
        assert os.lseek(caller_fd, 0, os.SEEK_CUR) == 0

        result = verify_activity_companion_binding(
            str(tmp_path / "nonexistent.activity.json"), caller_fd
        )
        assert result is False

        os.fstat(caller_fd)  # raises OSError if the fd was closed
        assert os.lseek(caller_fd, 0, os.SEEK_CUR) == 0
        assert os.read(caller_fd, 4096) == original_content
    finally:
        try:
            os.close(caller_fd)
        except OSError:
            pass


def test_verifier_positive_and_ordinary_negative_controls_survive_the_gate(
    git_executable: str, tmp_path: Path
) -> None:
    """The type gate must not disturb any genuine, ordinary-``str`` behavior:
    every positive control (run/attempt/refusal companion) still verifies
    ``True``, and every ordinary negative control (a missing path, malformed
    bytes, a tampered companion) still verifies ``False`` -- all as plain
    ``str`` arguments, exactly the supported call shape.
    """
    from qualification.safety import build_refusal_record
    from qualification.semantic_session import SemanticPromptDispatchState

    # -- genuine run-record companion -> True
    run_companion, run_primary, _ = _write_genuine_companion(tmp_path, task_id="IQ-1")
    assert verify_activity_companion_binding(run_companion, run_primary) is True

    # -- genuine attempt companion -> True
    harness = Harness("A", git_executable)
    harness.dispatch_state = SemanticPromptDispatchState.SEND_STATE_INDETERMINATE
    attempt_primary = str(tmp_path / "A_IQ-2.json")
    harness.run(TASKS_BY_ID["IQ-2"], attempt_primary)
    emit_activity_companion_or_refuse(
        _facts(),
        bound_primary_path=attempt_primary,
        identity=_identity(task_id="IQ-2"),
        safety=_NONE,
    )
    attempt_companion = str(tmp_path / "A_IQ-2.activity.json")
    assert verify_activity_companion_binding(attempt_companion, attempt_primary) is True

    # -- genuine refusal companion -> True
    refusal = build_refusal_record(
        refused_record_kind="qualification run record",
        finding_count=1,
        finding_categories=["api_key_value_present"],
    )
    refusal_primary = str(tmp_path / "A_IQ-3.json")
    Path(refusal_primary).write_text(
        json.dumps(refusal, indent=2, sort_keys=True) + chr(10),
        encoding="utf-8",
        newline=chr(10),
    )
    emit_activity_companion_or_refuse(
        _facts(), bound_primary_path=refusal_primary, identity=_identity(task_id="IQ-3"), safety=_NONE
    )
    refusal_companion = str(tmp_path / "A_IQ-3.activity.json")
    assert verify_activity_companion_binding(refusal_companion, refusal_primary) is True

    # -- missing ordinary-str path -> False
    assert (
        verify_activity_companion_binding(
            str(tmp_path / "does_not_exist.activity.json"), run_primary
        )
        is False
    )

    # -- malformed companion bytes -> False
    malformed = tmp_path / "malformed.activity.json"
    malformed.write_text("not json at all", encoding="utf-8")
    assert verify_activity_companion_binding(str(malformed), run_primary) is False

    # -- tampered companion -> False
    tampered = json.loads(Path(run_companion).read_text(encoding="utf-8"))
    tampered["scoring_authority"] = True
    tampered_path = tmp_path / "tampered.activity.json"
    tampered_path.write_text(json.dumps(tampered), encoding="utf-8")
    assert verify_activity_companion_binding(str(tampered_path), run_primary) is False


def test_fu2_touched_no_frozen_contract() -> None:
    """The FU2 prompt's Sec. 'Preserve frozen OBS1 contracts', mechanically.
    This fix is a pure input-type gate on one already-existing function; it
    added no gate, no port, no disposition, no policy revision, no schema
    bump."""
    from qualification import ACTIVITY_RECORD_VERSION as _ARV
    from qualification import QUALIFICATION_POLICY_REVISION as _QPR
    from qualification import RECORD_VERSION as _RV

    assert _ARV == "pi-implementer-qualification-activity.v1"
    assert _RV == "pi-implementer-qualification.v2"
    assert _QPR == "aido-implementer-role-capability-qualification-policy.r1"
    assert {d.value for d in RuntimeActivityCompanionDisposition} == {
        "EMITTED",
        "UNAVAILABLE_NO_TURN_OBSERVATION",
        "UNAVAILABLE_NO_PRIMARY",
        "UNAVAILABLE_UNBOUND_PRIMARY",
        "REFUSED_INVARIANT",
        "REFUSED_SCRUB",
        "REFUSED_PATH_COLLISION",
        "UNAVAILABLE_INTERNAL_ERROR",
    }
    # The public signature is unchanged -- two positional-or-keyword params,
    # no new parameter, no *args/**kwargs escape hatch added.
    assert list(inspect.signature(verify_activity_companion_binding).parameters) == [
        "companion_path",
        "primary_path",
    ]


# ===========================================================================
# Sec. 17 items 55-68 -- FAILURE CONTAINMENT, BY EXCEPTION ORIGIN
# ===========================================================================


def _inject_open_failure(monkeypatch, *, target_suffix: str, error: Exception):
    """Raise ``error`` from the REAL ``open`` call for exactly one file shape.

    Sec. 17's methodological requirement: the exception is injected at the
    SPECIFIC internal operation (the primary read, vs. the companion's own
    write inside ``emit_evidence_or_refuse``), never at the containment
    boundary's own ``try`` -- so the SAME exception TYPE arising from two
    different origins is genuinely told apart.
    """
    real_open = open

    def fake_open(file, *args, **kwargs):
        if isinstance(file, (str, os.PathLike)) and str(file).endswith(target_suffix):
            raise error
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr("builtins.open", fake_open)


@pytest.mark.parametrize(
    "error",
    [
        FileNotFoundError(2, "no such file"),
        PermissionError(13, "permission denied"),
        OSError(28, "no space left on device"),
    ],
)
def test_a_primary_read_failure_is_always_unavailable_no_primary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    """Items 55-56. Every ``OSError`` at the primary-read ORIGIN -- not merely
    the ``FileNotFoundError`` special case -- becomes the one dedicated,
    single-origin exception."""
    primary = _write_primary(tmp_path)
    _inject_open_failure(monkeypatch, target_suffix="A_IQ-1.json", error=error)
    with pytest.raises(PrimaryArtifactUnavailableError) as caught:
        emit_activity_companion_or_refuse(
            _facts(), bound_primary_path=primary, identity=_identity(), safety=_NONE
        )
    assert not isinstance(caught.value, OSError)
    assert caught.value.__cause__ is None  # `from None` -- no errno, no path
    assert str(primary) not in str(caught.value)

    disposition = ra._attempt_runtime_activity_companion(
        turn_observation=SemanticTurnObservation(
            runtime_session_id="rsess-1",
            turn_outcome=SemanticTurnOutcome.SETTLED,
            tool_activity=_snapshot(),
        ),
        broker_activity=None,
        bound_primary_path=primary,
        candidate="A",
        model_id=CANDIDATE_MODEL_IDS["A"],
        task_id="IQ-1",
        task_revision=TASKS_BY_ID["IQ-1"].task_revision,
        safety=_NONE,
    )
    assert disposition is RuntimeActivityCompanionDisposition.UNAVAILABLE_NO_PRIMARY


@pytest.mark.parametrize(
    "error",
    [
        PermissionError(13, "permission denied"),
        FileNotFoundError(2, "the destination directory disappeared"),
        OSError(28, "no space left on device"),
    ],
)
def test_a_companion_write_failure_is_never_blamed_on_the_primary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    """Items 57-59, the load-bearing FU4 property. The bound primary is read
    SUCCESSFULLY, and only afterwards the COMPANION'S OWN write fails with a
    structurally identical ``OSError`` -- explicitly asserted NOT to be
    ``UNAVAILABLE_NO_PRIMARY``, even for the identical ``FileNotFoundError``
    class item 55 uses."""
    primary = _write_primary(tmp_path)
    before = Path(primary).read_bytes()
    _inject_open_failure(monkeypatch, target_suffix=".activity.json", error=error)

    disposition = ra._attempt_runtime_activity_companion(
        turn_observation=SemanticTurnObservation(
            runtime_session_id="rsess-1",
            turn_outcome=SemanticTurnOutcome.SETTLED,
            tool_activity=_snapshot(),
        ),
        broker_activity=None,
        bound_primary_path=primary,
        candidate="A",
        model_id=CANDIDATE_MODEL_IDS["A"],
        task_id="IQ-1",
        task_revision=TASKS_BY_ID["IQ-1"].task_revision,
        safety=_NONE,
    )
    assert disposition is RuntimeActivityCompanionDisposition.UNAVAILABLE_INTERNAL_ERROR
    assert disposition is not RuntimeActivityCompanionDisposition.UNAVAILABLE_NO_PRIMARY
    assert Path(primary).read_bytes() == before


def test_an_unexpected_helper_fault_is_contained_without_stringifying_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Item 64. A ``RuntimeError`` with no relationship to the primary read or
    the companion write at all, whose ``__str__``/``__repr__`` raise if ever
    invoked -- proving no exception text reaches the disposition."""

    class _Unspeakable(RuntimeError):
        def __str__(self):  # pragma: no cover - must never be called
            raise AssertionError("the contained exception was stringified")

        def __repr__(self):  # pragma: no cover - must never be called
            raise AssertionError("the contained exception was repr'd")

    primary = _write_primary(tmp_path)
    monkeypatch.setattr(
        ra,
        "_build_proposed_facts",
        lambda *a, **k: (_ for _ in ()).throw(_Unspeakable()),
    )
    disposition = ra._attempt_runtime_activity_companion(
        turn_observation=SemanticTurnObservation(
            runtime_session_id="rsess-1", turn_outcome=SemanticTurnOutcome.SETTLED
        ),
        broker_activity=None,
        bound_primary_path=primary,
        candidate="A",
        model_id=CANDIDATE_MODEL_IDS["A"],
        task_id="IQ-1",
        task_revision=TASKS_BY_ID["IQ-1"].task_revision,
        safety=_NONE,
    )
    assert disposition is RuntimeActivityCompanionDisposition.UNAVAILABLE_INTERNAL_ERROR
    assert disposition.value == "UNAVAILABLE_INTERNAL_ERROR"
    assert not (tmp_path / "A_IQ-1.activity.json").exists()


@pytest.mark.parametrize("base_exc", [KeyboardInterrupt, SystemExit, GeneratorExit])
def test_base_exceptions_propagate_through_the_containment_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, base_exc
) -> None:
    """Item 65. OBS1 must never keep a process alive through an
    operator-requested interrupt or an interpreter shutdown to finish writing
    a non-scoring companion."""
    primary = _write_primary(tmp_path)
    monkeypatch.setattr(
        ra,
        "_build_proposed_facts",
        lambda *a, **k: (_ for _ in ()).throw(base_exc()),
    )
    with pytest.raises(base_exc):
        ra._attempt_runtime_activity_companion(
            turn_observation=SemanticTurnObservation(
                runtime_session_id="rsess-1", turn_outcome=SemanticTurnOutcome.SETTLED
            ),
            broker_activity=None,
            bound_primary_path=primary,
            candidate="A",
            model_id=CANDIDATE_MODEL_IDS["A"],
            task_id="IQ-1",
            task_revision=TASKS_BY_ID["IQ-1"].task_revision,
            safety=_NONE,
        )


def test_the_except_chain_is_origin_keyed_and_never_names_a_builtin() -> None:
    """Items 66-68, source-level. This is what makes items 57-59 mechanically
    provable rather than incidentally true of the current test doubles."""
    source = (_QUALIFICATION_DIR / "runtime_activity.py").read_text(encoding="utf-8")
    assert len(re.findall(r"^\s*except Exception:\s*$", source, re.MULTILINE)) == 1
    assert "except BaseException" not in source
    assert not re.search(r"^\s*except\s*:", source, re.MULTILINE)

    boundary = inspect.getsource(ra._attempt_runtime_activity_companion)
    clauses = re.findall(r"^\s*except (\w+):\s*$", boundary, re.MULTILINE)
    assert clauses == [
        "PrimaryArtifactUnavailableError",
        "UnboundPrimaryError",
        "ActivityRecordInvariantError",
        "EvidencePathCollisionError",
        "Exception",
    ]
    for builtin in ("OSError", "FileNotFoundError", "PermissionError", "IOError", "ValueError"):
        assert builtin not in clauses

    # The controller wraps neither the companion call nor the construction.
    controller = (_QUALIFICATION_DIR / "semantic_controller.py").read_text(encoding="utf-8")
    call_index = controller.index("_attempt_runtime_activity_companion(")
    construction_index = controller.index("result = SemanticTaskAttemptResult(")
    assert call_index < construction_index
    between = controller[call_index:construction_index]
    assert "try:" not in between
    assert "except" not in between


def test_the_scrub_refusal_path_is_a_normal_return_not_an_exception(
    tmp_path: Path,
) -> None:
    """Item 63. ``REFUSED_SCRUB`` is ordinary control flow over
    ``emission['refused']``, and a durable bounded refusal record IS written."""
    primary = _write_primary(tmp_path)
    disposition = ra._attempt_runtime_activity_companion(
        turn_observation=SemanticTurnObservation(
            runtime_session_id="rsess-1",
            turn_outcome=SemanticTurnOutcome.SETTLED,
            tool_activity=_snapshot(),
        ),
        broker_activity=None,
        bound_primary_path=primary,
        candidate="A",
        model_id=CANDIDATE_MODEL_IDS["A"],
        task_id="IQ-1",
        task_revision=TASKS_BY_ID["IQ-1"].task_revision,
        safety=ArtifactSafetyContext(api_key=CANDIDATE_MODEL_IDS["A"]),
    )
    assert disposition is RuntimeActivityCompanionDisposition.REFUSED_SCRUB
    written = json.loads((tmp_path / "A_IQ-1.activity.json").read_text(encoding="utf-8"))
    assert written["outcome"] == "artifact_emission_refused"


def test_the_disposition_vocabulary_is_closed_at_exactly_eight_values() -> None:
    """Sec. 12/12.2. Nothing else may ever appear."""
    assert {d.value for d in RuntimeActivityCompanionDisposition} == {
        "EMITTED",
        "UNAVAILABLE_NO_TURN_OBSERVATION",
        "UNAVAILABLE_NO_PRIMARY",
        "UNAVAILABLE_UNBOUND_PRIMARY",
        "REFUSED_INVARIANT",
        "REFUSED_SCRUB",
        "REFUSED_PATH_COLLISION",
        "UNAVAILABLE_INTERNAL_ERROR",
    }


def test_no_turn_observation_means_unavailable_never_a_zeroed_claim(
    tmp_path: Path,
) -> None:
    """Item 11. The early return happens BEFORE the ``try`` is even entered,
    and nothing is written."""
    primary = _write_primary(tmp_path)
    assert (
        ra._attempt_runtime_activity_companion(
            turn_observation=None,
            broker_activity=None,
            bound_primary_path=primary,
            candidate="A",
            model_id=CANDIDATE_MODEL_IDS["A"],
            task_id="IQ-1",
            task_revision=TASKS_BY_ID["IQ-1"].task_revision,
            safety=_NONE,
        )
        is RuntimeActivityCompanionDisposition.UNAVAILABLE_NO_TURN_OBSERVATION
    )
    assert not (tmp_path / "A_IQ-1.activity.json").exists()


def test_an_absent_tool_activity_still_emits_a_truthful_unavailable_companion(
    tmp_path: Path,
) -> None:
    """A turn WAS observed but carried no snapshot: the companion exists and
    says so, with every count zeroed and a null capture basis. Availability
    false is never read as 'no tool call occurred'."""
    primary = _write_primary(tmp_path)
    disposition = ra._attempt_runtime_activity_companion(
        turn_observation=SemanticTurnObservation(
            runtime_session_id="rsess-1", turn_outcome=SemanticTurnOutcome.SETTLED
        ),
        broker_activity=None,
        bound_primary_path=primary,
        candidate="A",
        model_id=CANDIDATE_MODEL_IDS["A"],
        task_id="IQ-1",
        task_revision=TASKS_BY_ID["IQ-1"].task_revision,
        safety=_NONE,
    )
    assert disposition is RuntimeActivityCompanionDisposition.EMITTED
    written = json.loads((tmp_path / "A_IQ-1.activity.json").read_text(encoding="utf-8"))
    assert written["runtime_reported_tool_activity_available"] is False
    assert written["runtime_reported_tool_activity_capture_basis"] is None
    assert written["broker_recorded_activity_available"] is False
    assert written["scoring_authority"] is False
    assert "Absence of this artifact is NOT evidence" in written["claim_scope"]


def test_a_failed_broker_call_is_recorded_as_unavailable_and_zeroed(
    tmp_path: Path,
) -> None:
    """Sec. 6.1's broker half, through ``_build_proposed_facts`` itself."""
    facts = ra._build_proposed_facts(
        SemanticTurnObservation(
            runtime_session_id="rsess-1",
            turn_outcome=SemanticTurnOutcome.DEADLINE_REACHED,
            tool_activity=_snapshot(capture_basis="wait_ended_before_settled"),
        ),
        BrokerActivityObservation(runtime_session_id="rsess-1", call_succeeded=False),
    )
    assert set(facts) == ra._ALLOWED_PROPOSED_FACTS_KEYS
    assert facts["broker_recorded_activity_available"] is False
    assert facts["broker_recorded_read_operation_count"] == 0
    assert facts["runtime_reported_tool_activity_capture_basis"] == (
        "wait_ended_before_settled"
    )
    # COUNTS ONLY: no path ever leaves the broker observation.
    populated = ra._build_proposed_facts(
        SemanticTurnObservation(
            runtime_session_id="rsess-1", turn_outcome=SemanticTurnOutcome.SETTLED
        ),
        BrokerActivityObservation(
            runtime_session_id="rsess-1",
            call_succeeded=True,
            read_operation_count=2,
            edit_operation_count=2,
            edited_paths=frozenset({"money/rounding.py", "units/parse.py"}),
        ),
    )
    assert populated["broker_recorded_edited_path_count"] == 2
    assert "money/rounding.py" not in json.dumps(populated)


# ===========================================================================
# Sec. 17 items 52-54, 69 -- NON-INTERFERENCE WITH THE GENUINE RESULT
# ===========================================================================


class _ToolActivityHarness(Harness):
    """The frozen controller harness, with a populated phase-2 snapshot."""

    def observe_semantic_turn(self, request):
        observation = super().observe_semantic_turn(request)
        return SemanticTurnObservation(
            runtime_session_id=observation.runtime_session_id,
            turn_outcome=observation.turn_outcome,
            agent_end_observed=observation.agent_end_observed,
            tool_activity=_snapshot(),
        )


_QUALIFICATION_FACING_FIELDS = (
    "semantic_prompts_sent",
    "dispatch_state",
    "dispatch_evidence_code",
    "semantic_dispatch_attempted",
    "turn_outcome",
    "agent_end_observed",
    "infrastructure_refusal",
    "run_validity",
    "scoring_eligible",
    "autonomous_classification",
    "diagnostic_subclassification",
    "verification_passed",
    "expected_changed_paths_satisfied",
    "head_unchanged",
    "index_clean",
    "protected_witness_untouched",
    "no_unexpected_untracked_or_create_delete_rename",
    "broker_git_cross_check_agrees",
    "failed_gate",
    "failure_code",
)


def _qualification_facing(result) -> dict:
    facts = {name: getattr(result, name) for name in _QUALIFICATION_FACING_FIELDS}
    facts["gate_statuses"] = dict(result.gate_statuses)
    return facts


def _forced_run(git_executable, tmp_path: Path, monkeypatch, forcing) -> tuple:
    """One genuine, complete controller attempt, with the companion mechanism
    forced into exactly one outcome by a REAL injection at a real call site."""
    from qualification.hard_bar import evaluate_hard_bar

    harness = _ToolActivityHarness("A", git_executable)
    harness.repair_files = {"money/rounding.py": IQ1_CORRECT_ROUNDING}
    harness.edited_paths = frozenset({"money/rounding.py"})
    harness.claimed_changed_paths = frozenset({"money/rounding.py"})
    evidence_path = str(tmp_path / "A_IQ-1.json")
    forcing(monkeypatch, tmp_path)
    constructions: list[str] = []
    real_consume = ra  # placeholder so the name is bound before the closure
    del real_consume

    import qualification.semantic_controller as controller

    genuine_consume = controller._consume_pending_attempt_authority

    def counting_consume(token, fingerprint):
        constructions.append(token)
        return genuine_consume(token, fingerprint)

    monkeypatch.setattr(controller, "_consume_pending_attempt_authority", counting_consume)
    result = harness.run(IQ1_TASK, evidence_path)
    assert len(constructions) == 1, "exactly ONE genuine result construction"
    return result, Path(evidence_path).read_bytes(), evaluate_hard_bar


def _force_nothing(monkeypatch, tmp_path) -> None:
    return None


def _force_invariant(monkeypatch, tmp_path) -> None:
    genuine = ra._build_proposed_facts
    monkeypatch.setattr(
        ra,
        "_build_proposed_facts",
        lambda *a, **k: {**genuine(*a, **k), "bound_primary_sha256": "0" * 64},
    )


def _force_scrub(monkeypatch, tmp_path) -> None:
    # A REAL scrub finding, through the REAL shared choke point: the fixed
    # claim-scope literal is made to contain a forbidden URL scheme.
    monkeypatch.setattr(
        ra, "ACTIVITY_CLAIM_SCOPE", ra.ACTIVITY_CLAIM_SCOPE + " https://forbidden.invalid"
    )


def _force_collision(monkeypatch, tmp_path) -> None:
    (tmp_path / "A_IQ-1.activity.json").write_text("{}", encoding="utf-8")


def _force_internal_error(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        ra,
        "_build_proposed_facts",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("synthetic companion fault")),
    )


def test_five_way_non_interference_across_every_companion_outcome(
    git_executable: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Items 52-54 and 69 -- the strongest regression in the set.

    ONE identical synthetic qualification attempt is driven through the
    companion mechanism five times, forced into each of ``EMITTED``,
    ``REFUSED_INVARIANT``, ``REFUSED_SCRUB``, ``REFUSED_PATH_COLLISION`` and
    ``UNAVAILABLE_INTERNAL_ERROR``. Every qualification-facing value, the
    hard-bar result, and the primary artifact's RAW BYTES must be identical
    across all five. The ONLY permitted differences are the disposition itself
    and whether/what a companion file exists on disk.
    """
    expected = {
        _force_nothing: RuntimeActivityCompanionDisposition.EMITTED,
        _force_invariant: RuntimeActivityCompanionDisposition.REFUSED_INVARIANT,
        _force_scrub: RuntimeActivityCompanionDisposition.REFUSED_SCRUB,
        _force_collision: RuntimeActivityCompanionDisposition.REFUSED_PATH_COLLISION,
        _force_internal_error: (
            RuntimeActivityCompanionDisposition.UNAVAILABLE_INTERNAL_ERROR
        ),
    }
    observed: list[tuple] = []
    for index, (forcing, disposition) in enumerate(expected.items()):
        run_dir = tmp_path / f"run{index}"
        run_dir.mkdir()
        with monkeypatch.context() as patch:
            result, primary_bytes, evaluate_hard_bar = _forced_run(
                git_executable, run_dir, patch, forcing
            )
        assert result.runtime_activity_companion is disposition, forcing.__name__
        observed.append((_qualification_facing(result), primary_bytes))

    first_facts, first_bytes = observed[0]
    for facts, primary_bytes in observed[1:]:
        assert facts == first_facts
        assert primary_bytes == first_bytes

    # The primary's own bytes never mention the companion at all.
    assert b"runtime_activity" not in first_bytes
    assert b"activity_companion" not in first_bytes


def test_the_hard_bar_result_is_identical_whatever_the_companion_did(
    git_executable: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Item 69's hard-bar half, evaluated through the real sweep boundary."""
    from qualification.semantic_sweep import _task_hard_bar_facts

    results = []
    for index, forcing in enumerate((_force_nothing, _force_internal_error, _force_scrub)):
        run_dir = tmp_path / f"hb{index}"
        run_dir.mkdir()
        with monkeypatch.context() as patch:
            result, _, _ = _forced_run(git_executable, run_dir, patch, forcing)
        results.append(_task_hard_bar_facts(result))
    assert results[0] == results[1] == results[2]


def test_the_disposition_is_passed_into_the_one_construction_never_assigned(
    git_executable: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Items 52-53. Source-level ordering PLUS the mechanical proof that the
    one-shot issuance registry refuses a post-construction ``replace``."""
    source = (_QUALIFICATION_DIR / "semantic_controller.py").read_text(encoding="utf-8")
    assert source.count("runtime_activity_companion = ") == 2  # the two branches
    assert source.count("runtime_activity_companion=runtime_activity_companion,") == 1
    assert ".runtime_activity_companion =" not in source
    # Prose may DISCUSS `dataclasses.replace`; no STATEMENT may call it.
    assert re.search(r"^\s*(?:\w+\s*=\s*)?dataclasses\.replace\(", source, re.MULTILINE) is None
    assert re.search(r"^\s*(?:\w+\s*=\s*)?replace\(", source, re.MULTILINE) is None
    assert source.index("_attempt_runtime_activity_companion(") < source.index(
        "result = SemanticTaskAttemptResult("
    )

    run_dir = tmp_path / "one"
    run_dir.mkdir()
    with monkeypatch.context() as patch:
        result, _, _ = _forced_run(git_executable, run_dir, patch, _force_nothing)
    assert result.runtime_activity_companion is RuntimeActivityCompanionDisposition.EMITTED
    with pytest.raises(ValueError):
        dataclasses.replace(
            result,
            runtime_activity_companion=(
                RuntimeActivityCompanionDisposition.UNAVAILABLE_INTERNAL_ERROR
            ),
        )
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.runtime_activity_companion = (  # type: ignore[misc]
            RuntimeActivityCompanionDisposition.REFUSED_SCRUB
        )


def test_the_result_refuses_a_bare_string_disposition(
    git_executable: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sec. 12.1: exact enum member, never a free-form string, never a bool."""
    from qualification.semantic_controller import SemanticTaskAttemptResult

    run_dir = tmp_path / "shape"
    run_dir.mkdir()
    with monkeypatch.context() as patch:
        result, _, _ = _forced_run(git_executable, run_dir, patch, _force_nothing)
    for bad in ("EMITTED", True, 0, None):
        clone = object.__new__(SemanticTaskAttemptResult)
        for field in dataclasses.fields(SemanticTaskAttemptResult):
            object.__setattr__(clone, field.name, getattr(result, field.name))
        object.__setattr__(clone, "runtime_activity_companion", bad)
        with pytest.raises(ValueError):
            SemanticTaskAttemptResult.__post_init__(clone)


def test_the_companion_rides_a_real_sweep_alongside_each_primary(
    git_executable: str, tmp_path: Path
) -> None:
    """End-to-end through the frozen ``run_primary_sweep``: exactly ONE
    companion per invoked attempt, at the fixed sibling path, never a
    sweep-level artifact."""
    from test_semantic_sweep import _make_build_adapters
    from qualification.semantic_sweep import TaskAdapterBundle, run_primary_sweep

    fresh: list[str] = []
    inner = _make_build_adapters("A", correct=True, fresh_calls=fresh)

    def build_adapters(task):
        bundle = inner(task)
        original = bundle.observe_semantic_turn

        def observe(request):
            observation = original(request)
            return SemanticTurnObservation(
                runtime_session_id=observation.runtime_session_id,
                turn_outcome=observation.turn_outcome,
                agent_end_observed=observation.agent_end_observed,
                tool_activity=_snapshot(),
            )

        return dataclasses.replace(bundle, observe_semantic_turn=observe)

    assert TaskAdapterBundle is not None
    result = run_primary_sweep(
        candidate="A",
        ambient_environ={},
        node_executable=sys.executable,
        git_executable=git_executable,
        python_executable=sys.executable,
        build_adapters=build_adapters,
        evidence_dir=str(tmp_path),
    )
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "A_IQ-1.activity.json",
        "A_IQ-1.json",
        "A_IQ-2.activity.json",
        "A_IQ-2.json",
        "A_IQ-3.activity.json",
        "A_IQ-3.json",
    ]
    for task_id, task_result in result.task_results.items():
        assert (
            task_result.runtime_activity_companion
            is RuntimeActivityCompanionDisposition.EMITTED
        )
        assert verify_activity_companion_binding(
            str(tmp_path / f"A_{task_id}.activity.json"),
            str(tmp_path / f"A_{task_id}.json"),
        )
        companion = json.loads(
            (tmp_path / f"A_{task_id}.activity.json").read_text(encoding="utf-8")
        )
        assert companion["record_version"] == ACTIVITY_RECORD_VERSION
        assert companion["task_id"] == task_id
        assert companion["scoring_authority"] is False


# ===========================================================================
# Sec. 17 items 13.4, 74 -- HISTORICAL EVIDENCE INTEGRITY AND OFFLINE PURITY
# ===========================================================================


def test_no_historical_companion_evidence_exists_or_was_backfilled() -> None:
    """Sec. 13.4. The truthful historical state stays 'UNAVAILABLE' -- never
    manufactured, inferred, or read as 'no tool call occurred'."""
    results_dir = _QUALIFICATION_DIR.parent / "results"
    if not results_dir.is_dir():  # pragma: no cover - environment dependent
        return
    assert list(results_dir.glob("*.activity.json")) == []
    for candidate in ("A", "B", "C"):
        for index in (1, 2, 3):
            assert not (results_dir / f"{candidate}_IQ-{index}.activity.json").exists()


def test_the_whole_companion_path_is_offline_by_construction() -> None:
    """Item 74. No socket, no HTTP client, no credential read, no model call,
    and no subprocess anywhere in the companion module."""
    source = (_QUALIFICATION_DIR / "runtime_activity.py").read_text(encoding="utf-8")
    for forbidden in (
        "import socket",
        "import httpx",
        "import requests",
        "import urllib",
        "import subprocess",
        "os.environ",
        "getenv",
        "http://",
        "https://",
        "api_key",
        "Authorization",
    ):
        assert forbidden not in source, forbidden
    # The ONLY filesystem access is a read-only open of the bound primary and
    # the shared writer's own exclusive-create.
    #
    # 5F3B-HARNESS-OBS1-IMPL-FU1: `verify_activity_companion_binding` now
    # delegates its primary-side read to the SAME `_require_valid_activity_payload`
    # -> `_read_primary_bytes` call every other consumer already uses, rather
    # than opening the primary a second, independent time -- so the call-site
    # count DROPS from 3 to 2 (the one shared primary read, plus the
    # verifier's own companion-file read) as a DIRECT, intended consequence of
    # reusing the full re-derivation boundary instead of duplicating it.
    assert source.count("open(") == 2  # the shared primary read + the companion read
    assert '"rb"' in source
    for write_mode in ('"w"', '"a"', '"r+"', '"wb"', '"ab"', '"x"'):
        assert f"open({write_mode}" not in source


# ===========================================================================
# 5F3B-HARNESS-OBS1-IMPL-FU3 -- CLOSE PRIMARY-PATH VALIDATION BEFORE
# RESOURCE CONSUMPTION
#
# Finding 1: `emit_activity_companion_or_refuse` -- the documented
# consumption/trust boundary -- performed the primary READ
# (`_read_primary_bytes` -> `open(bound_primary_path, "rb")`) BEFORE calling
# `_derive_activity_path`, so a caller-owned integer file descriptor still
# reached `open()` and was consumed/closed before the later path-shape gate
# could ever refuse it. The fix reorders the boundary so
# `_derive_activity_path(bound_primary_path)` runs first, strictly before any
# primary filesystem access, and its ONE result is reused later (never
# re-derived).
#
# Finding 2: an exact ordinary `str` `bound_primary_path`/`primary_path`
# containing an embedded NUL byte was not refused by `_derive_activity_path`
# itself; it relied on Python's own later `ValueError: embedded null byte`
# from `open()`, which `_read_primary_bytes`'s `except OSError:` clause does
# not catch. `_derive_activity_path` now refuses an embedded NUL directly, as
# a bounded `ActivityRecordInvariantError`, before any filesystem operation.
# ===========================================================================


def _fu3_malformed_bound_primary_path_values() -> tuple:
    """The exact adversarial domain the FU3 prompt enumerates for
    ``bound_primary_path``: ``None``; the ``bool`` singleton that is also an
    ``int`` subclass; the two small ints that are also real, everyday fd
    numbers (``0``/``1``); a ``pathlib.Path``; a ``str`` subclass; and an
    exact ordinary ``str`` carrying an embedded NUL byte."""
    return (
        None,
        True,
        0,
        1,
        Path("A_IQ-1.json"),
        _StrSubclass("A_IQ-1.json"),
        "A_IQ-1\x00.json",
    )


@pytest.mark.parametrize("bad", _fu3_malformed_bound_primary_path_values())
def test_emitter_refuses_every_malformed_bound_primary_path_before_reading_it(
    tmp_path: Path, bad: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Finding 1 + Finding 2, closed. Every malformed ``bound_primary_path``
    shape is refused by ``_derive_activity_path`` -- now called BEFORE
    ``_read_primary_bytes`` -- so the ``open`` builtin is never reached for
    any of them and no companion file is ever created. A genuine primary is
    written to disk first so the ONLY thing under test is whether the
    malformed VALUE passed as ``bound_primary_path`` is refused before any
    I/O is attempted against it.
    """
    import builtins

    _write_primary(tmp_path)  # a genuine A_IQ-1.json exists, unrelated to `bad`

    def _open_must_never_be_called(*args, **kwargs):  # pragma: no cover
        raise AssertionError(
            f"open() was called with args={args!r} -- the path-shape gate did "
            "not run before any primary filesystem access"
        )

    monkeypatch.setattr(builtins, "open", _open_must_never_be_called)
    with pytest.raises(ActivityRecordInvariantError):
        emit_activity_companion_or_refuse(
            _facts(), bound_primary_path=bad, identity=_identity(), safety=_NONE
        )
    assert list(tmp_path.glob("*.activity.json")) == []


def test_emitter_never_consumes_or_closes_a_caller_owned_primary_fd(
    tmp_path: Path,
) -> None:
    """THE load-bearing file-descriptor regression FU3 Finding 1 requires,
    for ``emit_activity_companion_or_refuse`` itself -- the SAME class of
    defect FU2 already closed for the independent public
    ``verify_activity_companion_binding`` gate. Python's ``open`` builtin
    treats an ``int`` as an ALREADY-OPEN file descriptor and takes ownership
    of it; a genuine caller resource must remain fully open, unread, and at
    its original file position after being passed as ``bound_primary_path``
    -- proving the type gate short-circuits BEFORE ``open`` is ever reached,
    not merely that the resulting failure is handled gracefully after the
    descriptor was already consumed.
    """
    _write_primary(tmp_path)  # a genuine A_IQ-1.json exists, unrelated to the fd

    victim_path = tmp_path / "caller_owned_resource.txt"
    original_content = b"caller-owned content, must survive untouched\n"
    victim_path.write_bytes(original_content)

    caller_fd = os.open(str(victim_path), os.O_RDONLY)
    try:
        # Prove the fd is genuinely open and at position 0 before the call.
        assert os.fstat(caller_fd).st_size == len(original_content)
        assert os.lseek(caller_fd, 0, os.SEEK_CUR) == 0

        with pytest.raises(ActivityRecordInvariantError):
            emit_activity_companion_or_refuse(
                _facts(), bound_primary_path=caller_fd, identity=_identity(), safety=_NONE
            )

        # The descriptor must remain OPEN (os.fstat does not raise) --
        # verifying it was never handed to `open()` and implicitly closed.
        os.fstat(caller_fd)  # raises OSError if the fd was closed

        # Its position must be UNCHANGED -- proving no read was attempted.
        assert os.lseek(caller_fd, 0, os.SEEK_CUR) == 0

        # And its content is exactly what the caller wrote -- fully intact.
        assert os.read(caller_fd, 4096) == original_content
    finally:
        try:
            os.close(caller_fd)
        except OSError:
            pass  # already closed would itself be a test failure, caught above

    # No companion file was ever created for this refused attempt.
    assert list(tmp_path.glob("*.activity.json")) == []


def test_verifier_returns_false_for_an_exact_str_embedded_nul_primary_path(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """FU3's required exact regression: an ordinary ``str`` ``primary_path``
    (a well-typed value -- FU2's parameter-TYPE gate already covers a
    malformed non-``str`` TYPE) containing an embedded NUL byte must return
    ``False``, never raise, and never print anything. A genuine companion is
    written first so the ONLY thing distinguishing this call from a positive
    control is the embedded NUL byte in ``primary_path``.
    """
    companion_path, _genuine_primary, _ = _write_genuine_companion(tmp_path)
    primary_path = "A_IQ-1\x00.json"

    result = verify_activity_companion_binding(companion_path, primary_path)
    assert result is False
    assert type(result) is bool

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_verifier_returns_false_for_an_exact_str_embedded_nul_companion_path(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """The identical regression for ``companion_path``, independently -- it
    must remain ``False``, never raise, exactly as it already did before this
    FU (the companion-side ``open`` call was always wrapped in
    ``except (OSError, ValueError, RecursionError):``); recorded here as a
    frozen-behavior regression alongside the ``primary_path`` fix above.
    """
    _companion_path, primary_path, _ = _write_genuine_companion(tmp_path)
    companion_path = "A_IQ-1\x00.activity.json"

    result = verify_activity_companion_binding(companion_path, primary_path)
    assert result is False
    assert type(result) is bool

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_derive_activity_path_refuses_the_full_fu3_malformed_domain() -> None:
    """Extends the pre-existing path-shape coverage
    (``test_the_companion_path_is_derived_and_validated_without_python_assert``)
    with the FU3 prompt's exact adversarial list: ``True``, ``0``, ``1``, a
    ``pathlib.Path``, a ``str`` subclass, and an embedded-NUL exact ``str`` --
    every one refused as the SAME bounded ``ActivityRecordInvariantError``,
    never a raw ``TypeError``/``ValueError``, and never via ``python -O``-
    strippable ``assert``.
    """
    for bad in _fu3_malformed_bound_primary_path_values():
        with pytest.raises(ActivityRecordInvariantError):
            ra._derive_activity_path(bad)

    # A NUL byte anywhere in an otherwise well-shaped path is refused too --
    # not merely a NUL that happens to break the `.json` suffix check.
    with pytest.raises(ActivityRecordInvariantError):
        ra._derive_activity_path("/x/A\x00_IQ-1.json")


def test_emitter_ordering_matches_the_fu3_required_source_shape() -> None:
    """A source-level proof that `_derive_activity_path` is called before
    `_read_primary_bytes` inside `emit_activity_companion_or_refuse`, and
    called exactly once in that function's own body (the independent
    re-derivation inside `_require_valid_activity_payload`'s shared gate --
    used both by `build_activity_companion_record`'s tail and by step (10)'s
    own defense-in-depth re-check -- is a SEPARATE, already-accepted call
    site and is untouched by this assertion)."""
    source = (_QUALIFICATION_DIR / "runtime_activity.py").read_text(encoding="utf-8")
    start = source.index("def emit_activity_companion_or_refuse(")
    end = source.index("\ndef verify_activity_companion_binding(")
    body = source[start:end]
    assert body.count("_derive_activity_path(") == 1
    assert body.index("_derive_activity_path(") < body.index("_read_primary_bytes(")


def test_fu3_positive_controls_are_unaffected(git_executable: str, tmp_path: Path) -> None:
    """Preserve failure attribution + ordinary behavior: a genuine emission,
    and genuine run/attempt/refusal verification, are BYTE-IDENTICAL in
    outcome to the pre-FU3 behavior -- only the ORDER of internal operations
    changed, never what a well-formed call produces."""
    from qualification.safety import build_refusal_record

    primary = _write_primary(tmp_path)
    emitted = emit_activity_companion_or_refuse(
        _facts(), bound_primary_path=primary, identity=_identity(), safety=_NONE
    )
    assert emitted["refused"] is False
    companion_path = str(tmp_path / "A_IQ-1.activity.json")
    assert verify_activity_companion_binding(companion_path, primary) is True

    refusal = build_refusal_record(
        refused_record_kind="qualification run record",
        finding_count=1,
        finding_categories=["api_key_value_present"],
    )
    refusal_primary = str(tmp_path / "A_IQ-2.json")
    Path(refusal_primary).write_text(
        json.dumps(refusal, indent=2, sort_keys=True) + chr(10),
        encoding="utf-8",
        newline=chr(10),
    )
    emit_activity_companion_or_refuse(
        _facts(), bound_primary_path=refusal_primary, identity=_identity(task_id="IQ-2"), safety=_NONE
    )
    refusal_companion = str(tmp_path / "A_IQ-2.activity.json")
    assert verify_activity_companion_binding(refusal_companion, refusal_primary) is True

    # -- valid path, but the primary open/read itself fails -> still
    # PrimaryArtifactUnavailableError -> still UNAVAILABLE_NO_PRIMARY.
    missing_primary = str(tmp_path / "A_IQ-3.json")
    with pytest.raises(PrimaryArtifactUnavailableError):
        emit_activity_companion_or_refuse(
            _facts(), bound_primary_path=missing_primary, identity=_identity(task_id="IQ-3"), safety=_NONE
        )
        assert f", {write_mode})" not in source
