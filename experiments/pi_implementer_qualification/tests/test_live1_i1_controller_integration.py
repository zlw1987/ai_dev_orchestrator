"""5F3B-LIVE1-I1-FU1 -- controller-level integration proofs for LIVE1-I1.

**OFFLINE ONLY.** No real Node/Pi process is launched, no real broker pipe
is opened, no socket is opened, B300 is never contacted, and no real
credential is read.

This module drives the REAL, frozen
:func:`qualification.semantic_controller.run_semantic_task_attempt` and
:func:`qualification.semantic_sweep.run_primary_sweep` end-to-end, using
THIS phase's OWN production :class:`~qualification.semantic_live_adapters.LiveSemanticAdapters`
and :func:`run_semantic_sweep_live.build_adapters` wiring, with exactly two
seams patched:

* ``qualification.semantic_live_adapters.resolve_pi_identity`` -- the one
  real ``node cli.js --version`` subprocess probe;
* ``qualification.semantic_live_adapters.build_semantic_task_live_adapters``
  -- which would otherwise construct a real, unmodified
  ``LiveCategoryBAdapters`` requiring a genuinely-issued identity.

Every attempt driven here is deliberately made to fail closed at
``BROKER_SESSION`` (the synthetic base's ``create_broker`` always reports
``session=None``), so no broker or runtime resource is ever created. This
proves GATE ORDERING and DURABLE ARTIFACT PRODUCTION -- it is not a claim
that a full qualification run was exercised.

Git (fixture population, via :mod:`qualification.semantic_workspace`) and
``python -m pytest`` (the fixture's own fixed verification command, run
against itself) are the ONE established, already-permitted local subprocess
surface this package's whole offline suite relies on -- see
``tests/test_semantic_controller.py``'s own module docstring for the
identical precedent. Neither is Pi, and neither is Node.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

from ai_dev_orchestrator.workspace.git_adapter import resolve_git_executable

import qualification.semantic_live_adapters as sla
from qualification.corpus import IQ1_TASK, IQ2_TASK, IQ3_TASK, REQUIRED_TASKS
from qualification.i2_credentials import ConnectionValues, PreflightGateResult
from qualification.i2b_live_adapters import (
    preflight_artifact_safety_scrub_self_check,
    preflight_candidate_route_generator_symmetry,
    preflight_child_environment_builder_self_check,
    preflight_config_generator_no_credential_literal_path,
    preflight_config_generator_self_check,
    preflight_environment_forbidden_fragment_audit,
    preflight_pi_installed_offline,
    preflight_planned_cli_argv_shape,
)
from qualification.i2b_session import BrokerCreationObservation
from qualification.records import CANDIDATE_MODEL_IDS
from qualification.semantic_controller import SemanticGateName, run_semantic_task_attempt
from qualification.semantic_sweep import run_primary_sweep

import run_semantic_sweep_live as runner


@pytest.fixture(scope="module")
def git_executable() -> str:
    """AIDO's OWN accepted Git resolution (5F3B-LIVE1-C1-P12a) -- the
    IDENTICAL fixture shape ``tests/test_semantic_controller.py`` already
    establishes as the safe, offline, permitted pattern."""
    exe = shutil.which("git")
    assert exe, "git must be on PATH to build synthetic fixtures"
    return resolve_git_executable(workspace_root=str(Path(__file__).resolve().parents[1]))


#: The eight real, offline, credential-free Category-A non-secret gates,
#: IDENTICAL to the runner's own tuple (`run_semantic_sweep_live._NON_SECRET_GATES`).
_REAL_GATE_FUNCS = (
    preflight_pi_installed_offline,
    preflight_config_generator_self_check,
    preflight_child_environment_builder_self_check,
    preflight_candidate_route_generator_symmetry,
    preflight_planned_cli_argv_shape,
    preflight_artifact_safety_scrub_self_check,
    preflight_config_generator_no_credential_literal_path,
    lambda: preflight_environment_forbidden_fragment_audit(ambient_environ=os.environ),
)

_SYNTHETIC_BASE_URL = "https://b300-proxy.example.invalid:8443/v1"
_SYNTHETIC_API_KEY = "sk-synthetic-live1-i1-fu1-0001"


def _logged_non_secret_gates(event_log: list[str], *, fail_at: int | None = None) -> tuple:
    """The REAL eight gates, each wrapped to append an ordered event marker
    ``non_secret_gate_<n>`` AFTER it actually executes. When ``fail_at`` is
    set, that ONE gate's real return value is discarded and a synthetic
    failure is substituted -- the gate still genuinely executes (and is
    logged), it is only the OUTCOME that is forced, so the frozen preflight
    ordering rule (stop at first failure) can be exercised deterministically
    for every one of the eight positions.
    """
    gates = []
    for index, real_gate in enumerate(_REAL_GATE_FUNCS, start=1):
        def _wrapped(real_gate=real_gate, index=index):
            result = real_gate()
            event_log.append(f"non_secret_gate_{index}")
            if fail_at == index:
                return PreflightGateResult(
                    name=result.name, passed=False, failure_code="CHECK_FAILED"
                )
            return result

        gates.append(_wrapped)
    return tuple(gates)


def _make_activation_fakes(event_log: list[str]):
    """Patches for the two seams this phase owns: the identity probe and
    the C1 base-adapter composition. Everything AFTER activation returns a
    clean, deterministic BROKER_SESSION failure, so the attempt closes
    without ever creating a broker or runtime resource.
    """
    fake_identity = object()

    def fake_resolve_pi_identity():
        event_log.append("activation_resolve_pi_identity")
        return fake_identity

    class _FakeBase:
        def read_connection(self):
            event_log.append("credential_read")
            return ConnectionValues(base_url=_SYNTHETIC_BASE_URL, api_key=_SYNTHETIC_API_KEY)

        def create_broker(self, request):
            event_log.append("create_broker_called")
            return BrokerCreationObservation(
                session=None, start_attempted=False, resource_created=False
            )

    def fake_build_semantic_task_live_adapters(*, environ_reader, runtime_identity, capability_grant):
        assert runtime_identity is fake_identity
        return _FakeBase()

    return fake_resolve_pi_identity, fake_build_semantic_task_live_adapters


def _drive_one_attempt(
    *,
    candidate: str,
    task,
    tmp_path: Path,
    git_executable: str,
    monkeypatch: pytest.MonkeyPatch,
    fail_at: int | None = None,
):
    """Drive the REAL frozen ``run_semantic_task_attempt`` for one task,
    returning ``(result, event_log)``. Fails closed at BROKER_SESSION on the
    happy activation path; fails closed at NON_SECRET_PREFLIGHT when
    ``fail_at`` names a gate position.
    """
    event_log: list[str] = []
    fake_resolve, fake_build = _make_activation_fakes(event_log)
    monkeypatch.setattr(sla, "resolve_pi_identity", fake_resolve)
    monkeypatch.setattr(sla, "build_semantic_task_live_adapters", fake_build)

    adapters = sla.LiveSemanticAdapters(task=task, environ_reader=os.environ.get)
    non_secret_gates = _logged_non_secret_gates(event_log, fail_at=fail_at)

    def _unreached_route_checker(*a, **kw):
        raise AssertionError("route_checker must never be reached -- BROKER_SESSION fails first")

    result = run_semantic_task_attempt(
        candidate=candidate,
        task=task,
        ambient_environ=os.environ,
        node_executable="node",  # never launched: string-only PATH narrowing
        git_executable=git_executable,
        python_executable=sys.executable,
        non_secret_gates=non_secret_gates,
        read_connection=adapters.read_connection,
        create_broker=adapters.create_broker,
        launch_runtime=adapters.launch_runtime,
        get_commands=adapters.get_commands,
        get_state=adapters.get_state,
        observe_protocol=adapters.observe_protocol,
        route_checker=_unreached_route_checker,
        dispatch_semantic_prompt=adapters.dispatch_semantic_prompt,
        observe_semantic_turn=adapters.observe_semantic_turn,
        collect_broker_activity=adapters.collect_broker_activity,
        collect_final_report_claims=adapters.collect_final_report_claims,
        shutdown_runtime=adapters.shutdown_runtime,
        shutdown_broker=adapters.shutdown_broker,
        evidence_path=str(tmp_path / f"{candidate}_{task.task_id}.json"),
    )
    return result, event_log


# ===========================================================================
# Case 47 -- real frozen-controller ordering test
# ===========================================================================


def test_case47_real_controller_orders_gates_then_activation_then_credential_read(
    tmp_path, git_executable, monkeypatch
):
    """Drives the REAL frozen ``run_semantic_task_attempt``. All eight
    non-secret gates execute, in order; activation (the identity probe)
    happens strictly after all eight; the credential read happens strictly
    after activation. No sequencing logic is duplicated here -- the frozen
    controller's own ``resolve_connection_after_preflight`` and gate loop
    produce this order; this test only observes it.
    """
    result, event_log = _drive_one_attempt(
        candidate="A", task=IQ1_TASK, tmp_path=tmp_path, git_executable=git_executable,
        monkeypatch=monkeypatch,
    )

    assert event_log == [
        "non_secret_gate_1",
        "non_secret_gate_2",
        "non_secret_gate_3",
        "non_secret_gate_4",
        "non_secret_gate_5",
        "non_secret_gate_6",
        "non_secret_gate_7",
        "non_secret_gate_8",
        "activation_resolve_pi_identity",
        "credential_read",
        "create_broker_called",
    ]
    # BROKER_SESSION fails closed, deliberately (session=None) -- a clean,
    # bounded pre-prompt infrastructure refusal, never a crash.
    assert result.failed_gate is SemanticGateName.BROKER_SESSION
    assert result.dispatch_state.value == "CONFIRMED_NOT_SENT"
    assert result.evidence_emission is not None


# ===========================================================================
# Case 48 -- every non-secret gate failure
# ===========================================================================


@pytest.mark.parametrize("gate_index", list(range(1, 9)))
def test_case48_each_non_secret_gate_failure_stops_the_chain(
    tmp_path, git_executable, monkeypatch, gate_index
):
    """For a failure forced at gate ``gate_index``: every gate through
    ``gate_index`` executed (and no further gate did); zero activation;
    zero credential read; zero broker/runtime/route activity; the attempt
    is attributed to NON_SECRET_PREFLIGHT.
    """
    result, event_log = _drive_one_attempt(
        candidate="A", task=IQ1_TASK, tmp_path=tmp_path, git_executable=git_executable,
        monkeypatch=monkeypatch, fail_at=gate_index,
    )

    expected_gate_events = [f"non_secret_gate_{n}" for n in range(1, gate_index + 1)]
    assert event_log == expected_gate_events  # nothing beyond the failing gate, ever

    assert "activation_resolve_pi_identity" not in event_log
    assert "credential_read" not in event_log
    assert "create_broker_called" not in event_log

    assert result.failed_gate is SemanticGateName.NON_SECRET_PREFLIGHT
    assert result.dispatch_state.value == "CONFIRMED_NOT_SENT"


# ===========================================================================
# Case 49 -- full A/B ordering fairness
# ===========================================================================


def test_case49_full_controller_order_trace_identical_for_a_and_b(
    tmp_path, git_executable, monkeypatch
):
    """Runs case 47's REAL controller-order trace for both candidates.
    Neither the gate order, the activation point, nor the credential-read
    point differs -- the traces are byte-identical, because this adapter
    carries no candidate identity at all to differ by.
    """
    traces = {}
    for candidate in ("A", "B"):
        candidate_dir = tmp_path / candidate
        candidate_dir.mkdir(exist_ok=True)
        result, event_log = _drive_one_attempt(
            candidate=candidate, task=IQ1_TASK, tmp_path=candidate_dir,
            git_executable=git_executable, monkeypatch=monkeypatch,
        )
        traces[candidate] = event_log
        assert result.failed_gate is SemanticGateName.BROKER_SESSION

    assert traces["A"] == traces["B"]


# ===========================================================================
# Case 56 -- whole fake sweep produces only per-task artifacts
# ===========================================================================


def test_case56_whole_sweep_through_runner_wiring_produces_only_per_task_artifacts(
    tmp_path, git_executable, monkeypatch
):
    """Drives the WHOLE frozen ``run_primary_sweep`` through the actual
    ``run_semantic_sweep_live.build_adapters`` wiring. Every one of the
    three tasks fails closed at BROKER_SESSION (a pre-prompt infrastructure
    refusal, never an indeterminate dispatch), so the sweep does NOT stop
    early and all three tasks are attempted. After the sweep, the results
    directory contains EXACTLY the three frozen per-task artifacts the
    controller itself names -- no sweep-summary file, no runner artifact, no
    fourth file of any kind.
    """
    event_log: list[str] = []
    fake_resolve, fake_build = _make_activation_fakes(event_log)
    monkeypatch.setattr(sla, "resolve_pi_identity", fake_resolve)
    monkeypatch.setattr(sla, "build_semantic_task_live_adapters", fake_build)

    def _build_adapters(task):
        # The REAL runner factory -- proves the I1 RUNNER wiring itself,
        # not a bespoke test-only adapter set.
        return runner.build_adapters("A", task)

    result = run_primary_sweep(
        candidate="A",
        ambient_environ=os.environ,
        node_executable="node",
        git_executable=git_executable,
        python_executable=sys.executable,
        build_adapters=_build_adapters,
        evidence_dir=str(tmp_path),
    )

    assert result.not_attempted_task_ids == ()
    assert result.indeterminate_dispatch_task_ids == ()
    assert set(result.task_results) == {task.task_id for task in REQUIRED_TASKS}

    on_disk = sorted(p.name for p in tmp_path.iterdir())
    expected = sorted(f"A_{task.task_id}.json" for task in REQUIRED_TASKS)
    assert on_disk == expected, (
        "the results directory must contain EXACTLY the frozen per-task "
        "artifacts -- no sweep-summary file, no runner artifact, no fourth "
        f"file. Found: {on_disk}"
    )
