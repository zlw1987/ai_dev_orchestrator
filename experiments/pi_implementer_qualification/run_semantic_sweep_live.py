"""Phase 5F3B-LIVE1-I1 harness entry point. **LIVE.** Not a CLI command.

**THIS SCRIPT PERFORMS REAL ACTIVITY**, including the first thing this
repository has ever authorized: it sends up to three real semantic prompts
(one per frozen IQ task) to a real, live Pi runtime, over the accepted
:mod:`qualification.semantic_live_adapters`. It reads a real B300
credential, creates real brokers, launches real Node/Pi processes, performs
real non-inference route observations, and -- unlike
:mod:`run_i2b_live` -- reaches a real model through Pi's own agent loop.

This is **not** Q1 or Q2. Running this script authorizes exactly ONE thing:
driving the frozen, already-accepted
:func:`qualification.semantic_sweep.run_primary_sweep` to completion for ONE
candidate, using the live adapters in
:mod:`qualification.semantic_live_adapters`. The frozen sweep and its
underlying frozen controller remain the only authority over task order,
gate ordering, first failure, the one-shot dispatch budget, stop-after-
indeterminate behaviour, evidence emission, and the hard-bar verdict -- this
script sequences nothing itself beyond resolving two trusted executables,
assembling a fresh adapter bundle per task, and calling
``run_primary_sweep`` exactly once.

**One command, one candidate, ONE primary sweep.** There is no relaunch, no
retry, no fallback candidate, no fallback model, and no path -- anywhere in
this file -- that runs both candidates or calls ``run_primary_sweep`` more
than once. There is no ``--workspace``, no real-workspace parameter of any
kind, and no sweep-level artifact is ever written: this script's only
output is the existing per-task evidence files the frozen controller itself
emits, plus ONE bounded console summary printed to stdout (design Sec.
12.7). Nothing here is retained, and nothing here is read back by anything.

Operator prerequisite, stated exactly because this script does not attest
it: the qualification offline suite (``tests/``, including every LIVE1-I1
test) must be green, and 5F3B-LIVE1-C1/-C2/-C4/-C3 must be accepted, before
this script is ever run with ``--run-primary-sweep-live``. This script does
not execute or attest pytest, and it is not itself Q1/Q2 authorization.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parents[1]
_AR2_DIR = _HERE.parent / "pi_external_runtime_ar2"
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(_AR2_DIR))
sys.path.insert(0, str(_HERE))

from ai_dev_orchestrator.workspace.git_adapter import (  # noqa: E402
    GitExecutableError,
    resolve_git_executable,
)
from ar2.launch import LaunchIdentityError  # noqa: E402

from qualification.corpus import QualificationTask  # noqa: E402
from qualification.i2b_live_adapters import (  # noqa: E402
    AuthenticatedB300RouteObserver,
    LiveCategoryBAdapters,
    build_authenticated_route_checker,
    preflight_artifact_safety_scrub_self_check,
    preflight_candidate_route_generator_symmetry,
    preflight_child_environment_builder_self_check,
    preflight_config_generator_no_credential_literal_path,
    preflight_config_generator_self_check,
    preflight_environment_forbidden_fragment_audit,
    preflight_pi_installed_offline,
    preflight_planned_cli_argv_shape,
)
from qualification.i2b_live_adapters import (  # noqa: E402
    _ar2_resolve_node_executable,  # noqa: F401 -- deliberate reuse, already re-exported there
)
from qualification.records import CANDIDATE_MODEL_IDS  # noqa: E402
from qualification.semantic_live_adapters import LiveSemanticAdapters  # noqa: E402
from qualification.semantic_sweep import PrimarySweepResult, TaskAdapterBundle, run_primary_sweep  # noqa: E402

RESULTS_DIR = _HERE / "results"

#: The eight real, offline, credential-free Category-A non-secret gates
#: (I2A Sec. 14), identical to the accepted Category-B live entry point's
#: own gate tuple (``run_i2b_live.py``). Every one is actually checked,
#: before the credential boundary, for every task attempt -- never a
#: vacuous ``()`` and never a hardcoded ``passed=True``.
_NON_SECRET_GATES: tuple[Callable[[], Any], ...] = (
    preflight_pi_installed_offline,
    preflight_config_generator_self_check,
    preflight_child_environment_builder_self_check,
    preflight_candidate_route_generator_symmetry,
    preflight_planned_cli_argv_shape,
    preflight_artifact_safety_scrub_self_check,
    preflight_config_generator_no_credential_literal_path,
    lambda: preflight_environment_forbidden_fragment_audit(ambient_environ=os.environ),
)


class PreSweepRefusal(Exception):
    """The attempt refused BEFORE ``run_primary_sweep`` was ever called.

    Zero tasks were invoked, zero prompts were dispatched, and no per-task
    evidence exists. Carries only a fixed bounded reason or an exception
    class name -- never a path, endpoint, token, credential, candidate
    value, or other caller-controlled runtime text.
    """

    def __init__(self, *, reason: str) -> None:
        super().__init__(f"refused before the primary sweep began: {reason}")
        self.reason = reason


#: The ONE fixed, bounded literal for an unknown/undeclared candidate.
#: **5F3B-LIVE1-I1-FU2.** Never an f-string embedding the caller-supplied
#: ``candidate`` value -- see :func:`_independent_pre_live_safety_check`.
_UNKNOWN_CANDIDATE_REASON = "unknown_candidate"


def _independent_pre_live_safety_check(*, candidate: str) -> None:
    """FIRST-LIVE SAFETY, mirroring ``run_i2b_live.py``'s own check: refuse
    an unknown candidate before any trusted-executable resolution or any
    live activity.

    **There is no real-workspace parameter anywhere.** Confirmed by
    inspection (design Sec. 12.2 step 2), not merely asserted here: this
    script, :class:`~qualification.semantic_live_adapters.LiveSemanticAdapters`,
    :func:`~qualification.semantic_sweep.run_primary_sweep`, and
    :func:`~qualification.i2b_workspace.mint_qualification_run_workspace`
    accept no existing-path argument through which a real repository could
    be named.

    **5F3B-LIVE1-I1-FU2.** ``candidate`` is caller-supplied and, unlike the
    CLI's own ``choices=``-restricted ``--candidate``, this function is a
    supported Python entry point a caller can invoke directly with an
    ARBITRARY string. The refusal reason is therefore the fixed literal
    :data:`_UNKNOWN_CANDIDATE_REASON` -- never an f-string or any other
    interpolation of ``candidate`` -- so a path-, token-, endpoint-, or
    secret-like value passed as ``candidate`` can never reach
    ``PreSweepRefusal.reason``, ``str(exception)``, or any repr-visible
    exception argument.
    """
    if candidate not in CANDIDATE_MODEL_IDS:
        raise PreSweepRefusal(reason=_UNKNOWN_CANDIDATE_REASON)


class _SemanticRouteCheckerBinder:
    """The ONE runner-owned binder satisfying design Sec. 12.2A.4.

    Exactly two constructor parameters -- ``candidate`` and this task's own
    :class:`~qualification.semantic_live_adapters.LiveSemanticAdapters`
    instance. No transport, client, requester, sender, session, http_client,
    request_callback, base_url, api_key, endpoint, provider, or model_id
    parameter exists anywhere on it.

    Never activates the adapter itself (R3): it only asks the adapter for
    its ALREADY-activated exact-type base
    (:meth:`~qualification.semantic_live_adapters.LiveSemanticAdapters.base_for_route_authority`),
    which raises rather than activating when the adapter is not yet
    activated. Constructs the frozen
    :class:`~qualification.i2b_live_adapters.AuthenticatedB300RouteObserver`
    exactly once and caches it, so every later call -- including the
    observer's own frozen "one observation per run" refusal -- is the SAME
    observer's, never duplicated here.
    """

    def __init__(self, *, candidate: str, adapters: LiveSemanticAdapters) -> None:
        self._candidate = candidate
        self._adapters = adapters
        self._observer: AuthenticatedB300RouteObserver | None = None

    def __call__(self, base_url: str, *, model_id: str) -> Any:
        if self._observer is None:
            base: LiveCategoryBAdapters = self._adapters.base_for_route_authority()
            self._observer = build_authenticated_route_checker(
                candidate=self._candidate, adapters=base
            )
        return self._observer(base_url, model_id=model_id)


def build_adapters(candidate: str, task: QualificationTask) -> TaskAdapterBundle:
    """The per-task factory ``run_primary_sweep`` calls once per IQ task.

    Design Sec. 12.3: **inert by construction.** Constructing
    :class:`~qualification.semantic_live_adapters.LiveSemanticAdapters` here
    performs zero subprocess, zero credential read, zero broker/runtime
    resource, and zero network activity -- it only binds the frozen task
    object and an ``environ_reader`` callable. ``candidate`` reaches ONLY
    the runner-owned route-checker binder above; it is never passed to, or
    readable from, ``LiveSemanticAdapters`` itself.
    """
    adapters = LiveSemanticAdapters(task=task, environ_reader=os.environ.get)
    route_checker = _SemanticRouteCheckerBinder(candidate=candidate, adapters=adapters)
    return TaskAdapterBundle(
        non_secret_gates=_NON_SECRET_GATES,
        read_connection=adapters.read_connection,
        create_broker=adapters.create_broker,
        launch_runtime=adapters.launch_runtime,
        get_commands=adapters.get_commands,
        get_state=adapters.get_state,
        observe_protocol=adapters.observe_protocol,
        route_checker=route_checker,
        dispatch_semantic_prompt=adapters.dispatch_semantic_prompt,
        observe_semantic_turn=adapters.observe_semantic_turn,
        collect_broker_activity=adapters.collect_broker_activity,
        collect_final_report_claims=adapters.collect_final_report_claims,
        shutdown_runtime=adapters.shutdown_runtime,
        shutdown_broker=adapters.shutdown_broker,
    )


def run_one_primary_sweep_live(*, candidate: str) -> PrimarySweepResult:
    """Exactly ONE ``run_primary_sweep`` call, against real infrastructure.

    Steps 1-4 (flag check by the caller, this safety check, trusted
    executable resolution, and creating the results directory) launch NO
    process. Calling :func:`~qualification.semantic_sweep.run_primary_sweep`
    below IS the live sweep itself -- within it, per task, a task's own
    ``node cli.js --version`` identity probe begins only after THAT task's
    eight Category-A non-secret gates have already passed (design Sec.
    12.2A), inside
    :meth:`~qualification.semantic_live_adapters.LiveSemanticAdapters.read_connection`.
    """
    _independent_pre_live_safety_check(candidate=candidate)

    try:
        # No subprocess: shutil.which + realpath + isfile only. There is no
        # real target workspace yet, so this is resolved against this
        # script's own directory -- exactly `run_i2b_live.py`'s precedent --
        # and re-proved by exact string equality at the frozen C1-P12a
        # fixture-population checkpoint before any Git subprocess runs.
        git_executable = resolve_git_executable(workspace_root=str(_HERE))
    except GitExecutableError as exc:
        raise PreSweepRefusal(reason=type(exc).__name__) from None

    try:
        # The SAME trusted resolver the Category-A gate
        # `preflight_pi_installed_offline` and every per-task identity
        # issuance already use. No subprocess: shutil.which + realpath +
        # isfile only.
        node_executable = _ar2_resolve_node_executable()
    except LaunchIdentityError as exc:
        raise PreSweepRefusal(reason=type(exc).__name__) from None

    try:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise PreSweepRefusal(reason=type(exc).__name__) from None

    return run_primary_sweep(
        candidate=candidate,
        ambient_environ=os.environ,
        node_executable=node_executable,
        git_executable=git_executable,
        python_executable=sys.executable,
        build_adapters=lambda task: build_adapters(candidate, task),
        evidence_dir=str(RESULTS_DIR),
    )


def _artifact_file_name(evidence_emission: Any) -> str | None:
    if evidence_emission is None:
        return None
    return os.path.basename(evidence_emission.path)


def _scrub_outcome(evidence_emission: Any) -> str | None:
    if evidence_emission is None:
        return None
    return "refused" if evidence_emission.refused else "clean"


def _task_summary(result: Any) -> dict[str, Any]:
    """ONE task's bounded summary. Every field is already a declared,
    bounded, non-secret typed field the frozen controller/sweep produced.
    Never prompt text, assistant text, reasoning, an absolute path, a base
    URL, an endpoint host, an API key, a credential, a broker token, a pipe
    name, a capability id, an argv token, a raw Pi record, or exception
    text.
    """
    return {
        "gate_statuses": dict(result.gate_statuses),
        "dispatch_state": result.dispatch_state.value,
        "run_validity": result.run_validity.value if result.run_validity is not None else None,
        "scoring_eligible": result.scoring_eligible,
        "failed_gate": result.failed_gate.value if result.failed_gate is not None else None,
        "artifact_file_name": _artifact_file_name(result.evidence_emission),
        "scrub_outcome": _scrub_outcome(result.evidence_emission),
        # 5F3B-HARNESS-OBS1. The bounded, closed-vocabulary companion
        # disposition ONLY -- never a count, never a tool name, never a path,
        # and never exception text. An `UNAVAILABLE_*`/`REFUSED_*` value means
        # exactly "runtime activity evidence unavailable"; it is NEVER to be
        # read or reported as "no tool activity occurred".
        "runtime_activity_companion": result.runtime_activity_companion.value,
    }


def print_bounded_summary(result: PrimarySweepResult) -> None:
    """The ONE bounded operator summary this script ever prints. Design
    Sec. 12.7: stdout only, not a file, not retained, not an evidence
    record, and never read back by anything.
    """
    summary = {
        "phase": "5F3B-LIVE1-I1",
        "candidate": result.candidate,
        "model_id": result.model_id,
        "confirmed_semantic_prompts_sent": result.confirmed_semantic_prompts_sent,
        "semantic_dispatch_attempts": result.semantic_dispatch_attempts,
        "indeterminate_dispatch_task_ids": list(result.indeterminate_dispatch_task_ids),
        "not_attempted_task_ids": list(result.not_attempted_task_ids),
        "hard_bar_result": result.hard_bar_result.qualification_state.value,
        "aido_requested_max_output_tokens": None,
        "tasks": {
            task_id: _task_summary(task_result)
            for task_id, task_result in result.task_results.items()
        },
    }
    json.dump(summary, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


def _exit_code(result: PrimarySweepResult) -> int:
    """Design Sec. 12.5. About the harness, never a qualification verdict."""
    if result.not_attempted_task_ids or result.indeterminate_dispatch_task_ids:
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run_semantic_sweep_live.py",
        description=(
            "Phase 5F3B-LIVE1-I1: run the frozen primary IQ-1/IQ-2/IQ-3 "
            "semantic sweep for ONE candidate against REAL infrastructure. "
            "NOT Q1/Q2. Sends up to three real semantic prompts."
        ),
    )
    parser.add_argument(
        "--candidate",
        choices=tuple(sorted(CANDIDATE_MODEL_IDS)),
        required=True,
        help="Required. No default -- there is no convenience candidate.",
    )
    parser.add_argument(
        "--run-primary-sweep-live",
        action="store_true",
        help=(
            "Required explicit flag. Authorizes exactly ONE live primary "
            "sweep for --candidate. Does NOT itself authorize Q1/Q2, a "
            "second candidate, or a retry -- it is operator friction, not "
            "authorization."
        ),
    )
    args = parser.parse_args(argv)

    if not args.run_primary_sweep_live:
        json.dump(
            {
                "refused": True,
                "reason": "refused: --run-primary-sweep-live was not passed",
                "semantic_dispatch_attempts": 0,
            },
            sys.stdout,
            indent=2,
        )
        sys.stdout.write("\n")
        return 1

    try:
        result = run_one_primary_sweep_live(candidate=args.candidate)
    except PreSweepRefusal as refusal:
        json.dump(
            {
                "refused": True,
                "reason": refusal.reason,
                "semantic_dispatch_attempts": 0,
                "note": (
                    "Refused before the frozen primary sweep began. Zero "
                    "tasks were invoked and zero semantic prompts were "
                    "dispatched."
                ),
            },
            sys.stdout,
            indent=2,
        )
        sys.stdout.write("\n")
        return 1

    print_bounded_summary(result)
    return _exit_code(result)


if __name__ == "__main__":
    raise SystemExit(main())
