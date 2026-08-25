"""Phase 5F3A-AR2-O1 harness entry point. EXPERIMENT ONLY -- not a CLI command.

Two-File Coordinated Implementation Case, built on the ACCEPTED, FROZEN AR2
architecture (``experiments/pi_external_runtime_ar2/``). This module is a
THIN layer: it imports AR2's broker, capability, candidate, operations,
observation, verification, supervisor, launch, handshake, route-check,
pi-config and environment machinery directly and calls it exactly the way
``experiments/pi_external_runtime_ar2/run_ar2.py`` does. Nothing under
``experiments/pi_external_runtime_ar2/`` is imported-and-modified,
monkeypatched, or forked by copy-paste. See ``o1/__init__.py`` for the exact
list of what O1 does NOT reuse from AR2 and why (its own case fixture, its
own baseline contract, its own pass assessment, its own record identity).

Phases, identical in shape to AR2's::

    preflight   pin Node+Pi, build the O1 fixture, mint the SED, build the
                bounded prompt manifest, baseline-verify and baseline-observe.
                No broker, no Pi launch, no prompt.
    broker      start the broker, reach READY, prove the lifecycle, tear it
                down and record it. No Pi launch, no prompt.
    handshake   launch the real Pi with the real extension, run H1 and H2.
                Neither triggers inference. No prompt.
    case        the ONE real semantic run: one broker, one Pi process, ONE
                prompt, one observation, one verification.

``case`` requires BOTH explicit flags. O1 has exactly ONE case and a maximum
of ONE semantic prompt, ever, for the lifetime of this harness. There is no
relaunch, no fallback runtime, no fallback model, no second provider route,
and no retry for any reason. If a mechanically evaluated live gate fails,
zero prompts are sent and the run stops as an infrastructure refusal.

OPERATOR PREREQUISITE, stated exactly because the harness does not attest it:
the O1 offline suite (``tests/``) must be green before ``--phase case`` is
ever run. This harness does not execute or attest pytest.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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

from ar2.ascii_json import dumps_ascii, echo_ascii  # noqa: E402
from ar2.broker import (  # noqa: E402
    STATE_CLOSED,
    STATE_READY,
    TRIGGER_AIDO_TEARDOWN,
    TRIGGER_PI_EXITED,
    TRIGGER_RUNTIME_DEADLINE,
    TRIGGER_RUNTIME_SETTLED,
    BrokerBinding,
    BrokerDiagnostics,
    BrokerRequestHandler,
    BrokerServer,
)
from ar2.capability import CapDefinitions, RunState, mint_capability  # noqa: E402
from ar2.fixtures import build_case_repository, remove_disposable_tree  # noqa: E402
from ar2.launch import LaunchIdentityError  # noqa: E402
from ar2.manifest import (  # noqa: E402
    ManifestTooLargeError,
    build_prompt_manifest,
    compose_prompt,
)
from ar2.observation import (  # noqa: E402
    NO_CHANGE_OBSERVED,
    classify,
    diff_expected_path,
    observe_repository,
    snapshot_for_record,
)
from ar2.pi_config import (  # noqa: E402
    scrub_generated_extension_config,
    scrub_generated_pi_config,
)
from ar2.route_check import check_route_serves_model  # noqa: E402
from ar2.supervisor import (  # noqa: E402
    RUNTIME_RESPONSE_RECEIVED,
    RUNTIME_SETTLED,
    PiRpcSupervisor,
    PiSupervisorError,
    RunBounds,
)
from ar2.verification import run_verification  # noqa: E402

from o1 import EXPERIMENT_ID, LOGICAL_ROUTE_NAME, PINNED_MODEL_ID  # noqa: E402
from o1.assessment import assess_o1  # noqa: E402
from o1.fixture import O1_CASE, baseline_matches_o1_contract  # noqa: E402
from o1.handshake import CompatibilityHandshakeError, launch_and_handshake  # noqa: E402
from o1.pi_compat import (  # noqa: E402
    build_pi_runtime_provenance,
    resolve_pi_identity_provenance_only,
)
from o1.record import (  # noqa: E402
    CAPABILITY_BOUNDARY,
    RESIDUAL_LIMITATIONS,
    TOKEN_POLICY,
    broker_secret_denylist,
    record_header,
    redact_value,
    refusal_record,
    scrub_check,
)

CONFIG_FILENAME = "experiment_config.json"
RESULTS_DIR = _HERE / "results"

CASE_ID = "O1"


class GateRefusal(Exception):
    """A precondition failed. No prompt is sent."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_experiment_config(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise GateRefusal(
            f"refused: the experiment config file {path.name!r} is absent. It ships "
            "absent deliberately; create it explicitly to run anything."
        )
    config = json.loads(path.read_text(encoding="utf-8"))
    for key in ("provider_id", "model_id", "base_url_env_name", "python_executable"):
        if not config.get(key):
            raise GateRefusal(f"refused: experiment config is missing {key!r}")
    if config["model_id"] != PINNED_MODEL_ID:
        raise GateRefusal(
            "refused: O1 is pinned to the same accepted AR2 model/route so the "
            "only architecture variable under test is the two-file task itself"
        )
    return config


def _resolve_base_url(config: dict[str, Any]) -> str:
    name = config["base_url_env_name"]
    value = os.environ.get(name, "").strip()
    if not value:
        raise GateRefusal(
            f"refused: the route endpoint variable {name!r} is unset or blank. The "
            "experiment is NOT EXECUTED. No key or endpoint is invented."
        )
    return value


# -- preflight -----------------------------------------------------------------


def phase_preflight(config: dict[str, Any]) -> dict[str, Any]:
    """Build the O1 fixture, mint the SED, baseline everything.

    Pi's LOCATION is resolved here; its VERSION is only observed, never
    gated (``o1.pi_compat.resolve_pi_identity_provenance_only`` -- see that
    module's docstring for the corrected policy). The zero-prompt
    COMPATIBILITY gate that decides whether a different version may proceed
    runs later, in ``phase_case``, because it requires the real RPC launch
    and handshake -- there is nothing left to gate on here.
    """
    case = O1_CASE
    report: dict[str, Any] = {
        "phase": "preflight",
        "case_id": CASE_ID,
        "case_purpose": case.purpose,
        "started_at": _utc_now(),
    }

    identity = resolve_pi_identity_provenance_only()
    report["runtime_identity"] = {
        "runtime": "pi",
        "observed_version": identity.reported_version,
        "version_recorded_as_provenance": True,
        "exact_version_is_authorization_gate": False,
        "launch_shape": identity.launch_shape,
        "node_direct_launch_works": True,
        "node_executable_basename": os.path.basename(identity.node_executable),
        "pi_entry_basename": os.path.basename(identity.pi_cli_js),
    }

    git_executable = resolve_git_executable(workspace_root=str(_HERE))
    fixture = build_case_repository(case, git_executable=git_executable)

    baseline_snapshot = observe_repository(
        git_executable=git_executable, workspace_root=fixture.repo_root
    )
    tracked = tuple(sorted(entry.path for entry in baseline_snapshot.index_entries))

    sed = mint_capability(
        authority=fixture.authority,
        tracked_manifest=tracked,
        protected_patterns=case.protected_patterns,
        verification_witness_paths=case.verification_witness_paths,
        caps=CapDefinitions(),
    )
    manifest = build_prompt_manifest(sed)

    baseline_verification = run_verification(
        python_executable=config["python_executable"],
        workspace_root=fixture.repo_root,
        args=case.verification_args,
    )
    matches, why = baseline_matches_o1_contract(baseline_verification)

    baseline_class = classify(
        baseline_snapshot,
        workspace_root=fixture.repo_root,
        head_before=fixture.head_before,
        expected_changed_paths=case.expected_changed_paths or frozenset({"__none__"}),
        baseline=baseline_snapshot,
    )

    report["fixture"] = {
        "experiment_root_recorded": False,
        "tracked_paths": list(tracked),
        "head_before": fixture.head_before,
    }
    report["static_eligibility_domain"] = sed.summary()
    report["prompt_manifest"] = manifest.as_dict()
    report["baseline_verification"] = baseline_verification.as_dict()
    report["baseline_verification"]["matches_case_contract"] = matches
    report["baseline_verification"]["assessment"] = why
    report["baseline_observation"] = snapshot_for_record(baseline_snapshot)
    report["baseline_classification"] = baseline_class.as_dict()
    report["baseline_is_clean"] = baseline_class.workspace_class == NO_CHANGE_OBSERVED

    report["_internal"] = {
        "case": case,
        "identity": identity,
        "fixture": fixture,
        "git_executable": git_executable,
        "sed": sed,
        "manifest": manifest,
        "baseline_snapshot": baseline_snapshot,
    }
    return report


# -- broker-only phase ---------------------------------------------------------


def phase_broker(config: dict[str, Any]) -> dict[str, Any]:
    """Prove the broker lifecycle without launching a runtime or sending a prompt."""
    preflight = phase_preflight(config)
    internal = preflight.pop("_internal")
    sed = internal["sed"]
    fixture = internal["fixture"]

    binding = BrokerBinding.mint(sed.capability_id)
    run_state = RunState(caps=sed.caps)
    handler = BrokerRequestHandler(
        sed=sed, run_state=run_state, binding=binding, diagnostics=BrokerDiagnostics()
    )
    server = BrokerServer(handler)
    server.start()
    ready_observed = server.state == STATE_READY
    lifecycle = server.shutdown(TRIGGER_AIDO_TEARDOWN)

    remove_disposable_tree(fixture.experiment_root)
    return {
        "phase": "broker",
        "case_id": CASE_ID,
        "prompts_sent": 0,
        "model_calls_made": 0,
        "runtime_launched": False,
        "broker_reached_ready_before_any_runtime_launch": ready_observed,
        "broker_recorded_security_shape": server.security_shape(),
        "broker_recorded_lifecycle": lifecycle,
        "broker_recorded_activity": handler.diagnostics.as_dict(),
        "broker_recorded_run_state": run_state.as_dict(),
        "static_eligibility_domain": preflight["static_eligibility_domain"],
        "prompt_manifest": preflight["prompt_manifest"],
    }


def phase_handshake(config: dict[str, Any], *, profile_names: tuple[str, ...]) -> dict[str, Any]:
    """Launch the real Pi with the real extension, run H1 and H2, send NO prompt.

    FU1A: exception-safe, matching ``phase_case``. This phase never sends a
    prompt in ANY case -- "zero semantic prompts" was always structurally
    true here, since no prompt-send statement exists in this function at
    all. What FU1A closes is that a ``launch_and_handshake`` failure no
    longer bypasses broker shutdown or leaves generated, endpoint-bearing
    config unscrubbed: broker shutdown is now attempted EXACTLY ONCE
    regardless of outcome, each generated resource (Pi config, extension)
    is scrubbed independently of the other, and the fixture is always
    explicitly removed afterward (this diagnostic phase carries no case
    evidence to preserve, so it keeps its original unconditional-removal
    shape on both the success and failure path). Any Pi direct-child
    shutdown on the failure path was already attempted, once, bounded, and
    without a thread-kill, inside ``launch_and_handshake`` itself -- this
    function does not attempt a second one.
    """
    preflight = phase_preflight(config)
    internal = preflight.pop("_internal")
    identity = internal["identity"]
    fixture = internal["fixture"]
    sed = internal["sed"]

    binding = BrokerBinding.mint(sed.capability_id)
    run_state = RunState(caps=sed.caps)
    handler = BrokerRequestHandler(
        sed=sed, run_state=run_state, binding=binding, diagnostics=BrokerDiagnostics()
    )
    server = BrokerServer(handler)
    server.start()
    broker_ready = server.state == STATE_READY
    base_url = _resolve_base_url(config)

    report: dict[str, Any] = {
        "phase": "handshake",
        "case_id": CASE_ID,
        "prompt_sent": False,
        "semantic_prompts_sent": 0,
        "inference_triggered": False,
        "broker_reached_ready_before_runtime_launch": broker_ready,
    }

    supervisor: PiRpcSupervisor | None = None
    pi_config_dir = ""
    extension_dir = ""
    try:
        supervisor, launch_report, extension_dir = launch_and_handshake(
            identity=identity,
            fixture=fixture,
            config=config,
            base_url=base_url,
            profile_names=profile_names,
            git_executable=internal["git_executable"],
            bounds=RunBounds(),
            ar2_extension_source_dir=str(_AR2_DIR / "extension"),
            experiment_id=EXPERIMENT_ID,
            pipe_name=server.pipe_name,
            capability_id=binding.capability_id,
            token=binding.token,
        )
    except CompatibilityHandshakeError as exc:
        # The exact compatibility failure reason is retained verbatim, and
        # never collapsed into a generic message. Any direct-child shutdown
        # was already attempted inside launch_and_handshake; its (possibly
        # empty, possibly shutdown-itself-failed) termination record is
        # copied through rather than re-attempted here.
        report["compatibility_handshake_exception"] = exc.as_dict()
        pi_config_dir = exc.pi_config_dir
        extension_dir = exc.extension_dir
        report["termination"] = exc.termination
        report["stdout_state"] = exc.stdout_state or {}
    else:
        report.update(launch_report)
        # Both resources are known to have been generated on this path
        # (launch_and_handshake only returns after writing both), at AR2's
        # own fixed, documented relative config-directory location.
        pi_config_dir = os.path.join(fixture.experiment_root, "pi_config")
        report["termination"] = supervisor.shutdown()
        report["stdout_state"] = supervisor.stdout_state()
        report["stderr"] = supervisor.stderr_snapshot()
        report["runtime_reported_extension_errors"] = list(supervisor.activity.extension_errors)

    # -- broker shutdown attempted EXACTLY ONCE, on every outcome -----------
    report["broker_recorded_lifecycle"] = server.shutdown(TRIGGER_PI_EXITED)
    report["broker_recorded_activity"] = handler.diagnostics.as_dict()

    # -- each generated resource scrubbed INDEPENDENTLY, before removal -----
    if pi_config_dir:
        report["cleanup_pi_models_json_scrub"] = scrub_generated_pi_config(pi_config_dir)
    if extension_dir:
        report["cleanup_extension_binding_scrub"] = scrub_generated_extension_config(extension_dir)
    report["cleanup"] = remove_disposable_tree(fixture.experiment_root)
    report["_internal"] = {"binding": binding, "pipe_name": server.pipe_name}
    return report


# -- the live case -------------------------------------------------------------


def phase_case(config: dict[str, Any], *, profile_names: tuple[str, ...]) -> dict[str, Any]:
    """The ONE case: one broker, one Pi process, ONE prompt, one observation."""
    preflight = phase_preflight(config)
    internal = preflight.pop("_internal")
    case = internal["case"]
    identity = internal["identity"]
    fixture = internal["fixture"]
    git_executable = internal["git_executable"]
    sed = internal["sed"]
    manifest = internal["manifest"]

    run: dict[str, Any] = {
        "phase": "case",
        "case_id": CASE_ID,
        "case_purpose": case.purpose,
        "started_at": _utc_now(),
        "prompt_sent": False,
        "semantic_prompts_sent": 0,
    }

    # -- the broker must reach READY BEFORE Pi is launched --------------------
    binding = BrokerBinding.mint(sed.capability_id)
    run_state = RunState(caps=sed.caps)
    handler = BrokerRequestHandler(
        sed=sed, run_state=run_state, binding=binding, diagnostics=BrokerDiagnostics()
    )
    server = BrokerServer(handler)
    broker_ready = False
    try:
        server.start()
        broker_ready = server.state == STATE_READY
    except Exception as exc:  # noqa: BLE001 - a broker that will not start sends no prompt
        run["broker_start_error"] = f"{type(exc).__name__}: {exc}"

    gate: dict[str, Any] = {
        "broker_reached_ready_before_runtime_launch": broker_ready,
        "baseline_repository_trusted": preflight["baseline_is_clean"],
        "baseline_matches_this_case_contract": preflight["baseline_verification"][
            "matches_case_contract"
        ],
        "prompt_manifest_within_caps": True,
        "changed_file_cap_is_unmodified_ar2_default": sed.caps.max_changed_files_per_run == 2,
    }
    base_url = _resolve_base_url(config)
    gate["route_configuration_available"] = True

    route_check = check_route_serves_model(base_url, model_id=config["model_id"])
    run["route_model_check"] = route_check.as_dict()

    bounds = RunBounds()
    supervisor: PiRpcSupervisor | None = None
    pi_config_dir: str | None = None
    extension_dir: str | None = None
    turn_outcome = "not_attempted"
    shutdown_trigger = TRIGGER_AIDO_TEARDOWN

    # -- the zero-prompt Pi COMPATIBILITY gate (brief items 1-12) -------------
    #
    # Version is provenance, never authorization: no comparison against any
    # pin, exact or ranged, happens anywhere below. What gates the prompt is
    # whether the ACTUAL launched runtime seam demonstrates every required
    # behavior, against the real installed Pi, right now.
    compat: dict[str, bool] = {
        "pi_version_observable": bool(identity.reported_version),
        "node_direct_launch_constructed": True,  # proven in phase_preflight
        "rpc_process_launched_and_alive": False,
        "jsonl_request_response_correlation_h1_worked": False,
        "get_commands_response_shape_understood": False,
        "h1_extension_identity_passed": False,
        "jsonl_request_response_correlation_h2_worked": False,
        "get_state_response_shape_understood": False,
        "h2_model_identity_passed": False,
        "required_launch_flags_accepted": False,
        "no_protocol_violation_during_handshake": False,
        "no_extension_errors_during_handshake": False,
        "route_serves_configured_model": bool(route_check.configured_model_served),
    }

    # FU1: the compatibility handshake sequence is exception-safe. ANY raise
    # from launch_and_handshake() -- a Pi launch failure, a stdin/RPC failure,
    # or any other seam exception -- is caught HERE, never left to escape
    # phase_case entirely. It is folded into an ordinary compatibility-gate
    # failure (every compat check stays False, exactly as the "broker not
    # ready" branch below already does), so broker shutdown, repository
    # observation and fixture cleanup/preservation still run to completion,
    # and the prompt-send guard below (gate_all_passed and supervisor is not
    # None) still makes zero prompts structurally unreachable.
    if broker_ready:
        try:
            supervisor, launch_report, extension_dir = launch_and_handshake(
                identity=identity,
                fixture=fixture,
                config=config,
                base_url=base_url,
                profile_names=profile_names,
                git_executable=git_executable,
                bounds=bounds,
                ar2_extension_source_dir=str(_AR2_DIR / "extension"),
                experiment_id=EXPERIMENT_ID,
                pipe_name=server.pipe_name,
                capability_id=binding.capability_id,
                token=binding.token,
            )
        except CompatibilityHandshakeError as exc:
            # The bounded supervisor shutdown, if any process ever existed,
            # was ALREADY attempted inside launch_and_handshake -- do not
            # attempt a second one, and do not surface a partially-failed
            # supervisor object into the rest of phase_case as if it were
            # live. `supervisor` stays None, so the code below takes exactly
            # the same path it already takes for "broker never reached
            # READY": every compat check stays False, and shutdown_trigger
            # reflects the truthful fact of whether AIDO's direct child was
            # ever observed to exit.
            run["compatibility_handshake_exception"] = exc.as_dict()
            # Tracked INDEPENDENTLY of one another (FU1A): a Pi-config write
            # that succeeded before a LATER extension-write failure must
            # still be known here, so cleanup can scrub it regardless of
            # whether the extension ever existed.
            pi_config_dir = exc.pi_config_dir or pi_config_dir
            extension_dir = exc.extension_dir or extension_dir
            if exc.termination.get("exit_status_observed") is not None:
                shutdown_trigger = TRIGGER_PI_EXITED
        else:
            run.update(launch_report)
            # Both resources are known to have been generated on this path
            # (launch_and_handshake only returns after writing both), using
            # AR2's own fixed, documented relative location for the config
            # directory -- the same location ar2.pi_config.write_disposable_
            # pi_config always uses, never a guess.
            pi_config_dir = os.path.join(fixture.experiment_root, "pi_config")

            h1 = launch_report["handshake_extension"]
            h2 = launch_report["handshake_model"]
            stdout_state_at_gate = supervisor.stdout_state()
            rpc_alive = stdout_state_at_gate.get("exit_status_observed") is None
            h1_correlated = h1.get("wait_outcome") == RUNTIME_RESPONSE_RECEIVED
            h2_correlated = h2.get("wait_outcome") == RUNTIME_RESPONSE_RECEIVED

            compat.update(
                {
                    "rpc_process_launched_and_alive": rpc_alive,
                    "jsonl_request_response_correlation_h1_worked": h1_correlated,
                    "get_commands_response_shape_understood": bool(h1.get("response_success")),
                    "h1_extension_identity_passed": bool(h1.get("passed")),
                    "jsonl_request_response_correlation_h2_worked": h2_correlated,
                    "get_state_response_shape_understood": bool(h2.get("response_success")),
                    "h2_model_identity_passed": bool(h2.get("passed")),
                    "required_launch_flags_accepted": bool(rpc_alive and h1_correlated),
                    "no_protocol_violation_during_handshake": not stdout_state_at_gate.get(
                        "protocol_violation"
                    ),
                    "no_extension_errors_during_handshake": not supervisor.activity.extension_errors,
                }
            )

    run["pi_runtime"] = build_pi_runtime_provenance(identity=identity, checks=compat)
    gate["pi_compatibility_gate_passed"] = run["pi_runtime"]["compatibility_gate_passed"]

    gate_all_passed = all(bool(v) for v in gate.values())
    run["live_run_gate"] = gate
    run["gate_passed"] = gate_all_passed
    run["live_run_gate_note"] = (
        "Every condition above is mechanically evaluated here, including the "
        "zero-prompt Pi compatibility gate in run['pi_runtime'] -- NONE of it "
        "is a version-string comparison. The O1 offline suite being green is "
        "an OPERATOR/EXECUTION prerequisite and is deliberately NOT among "
        "these conditions: this harness does not execute or attest pytest."
    )

    the_prompt = compose_prompt(case.prompt, manifest)

    if gate_all_passed and supervisor is not None:
        prompt_started = time.monotonic()
        supervisor.send_command({"id": "p1", "type": "prompt", "message": the_prompt})
        run["prompt_sent"] = True
        run["semantic_prompts_sent"] = 1
        outcome_prompt, prompt_response = supervisor.await_response(
            "p1", timeout_seconds=min(60.0, bounds.turn_deadline_seconds)
        )
        run["prompt_accept_outcome"] = outcome_prompt
        run["prompt_accepted"] = bool(prompt_response and prompt_response.get("success"))
        remaining = bounds.turn_deadline_seconds - (time.monotonic() - prompt_started)
        turn_outcome = supervisor.await_settled(timeout_seconds=max(remaining, 1.0))
        run["turn_seconds"] = round(time.monotonic() - prompt_started, 3)
        shutdown_trigger = (
            TRIGGER_RUNTIME_SETTLED if turn_outcome == RUNTIME_SETTLED else TRIGGER_RUNTIME_DEADLINE
        )
    run["turn_outcome"] = turn_outcome
    run["prompt_manifest"] = manifest.as_dict()
    run["prompt_names_the_implementation_file"] = case.names_the_implementation_file

    # -- Pi termination ladder FIRST, then broker teardown --------------------
    if supervisor is not None:
        termination = supervisor.shutdown()
        run["termination"] = termination
        run["stdout_state"] = supervisor.stdout_state()
        run["stderr"] = supervisor.stderr_snapshot()
        if termination.get("exit_status_observed") is not None and turn_outcome != RUNTIME_SETTLED:
            shutdown_trigger = TRIGGER_PI_EXITED
        activity = supervisor.activity
        run["runtime_reported"] = {
            "trust": "UNTRUSTED CLAIM -- the runtime's own account of itself",
            "event_type_counts": dict(sorted(activity.event_type_counts.items())),
            "tool_activity": activity.tool_call_summary(),
            "completion_event_observed": activity.settled,
            "agent_end_count": activity.agent_end_count,
            "agent_end_will_retry_count": activity.agent_end_will_retry_count,
            "agent_end_is_not_completion": True,
            "runtime_owned_auto_retry_events": activity.auto_retry_events,
            "runtime_owned_compaction_events": activity.compaction_events,
            "extension_errors": activity.extension_errors,
            "final_assistant_text": activity.final_assistant_text[:4000],
            "usage": activity.usage_for_record(),
        }
        run["reasoning_drop"] = {
            **supervisor.reasoning_stats.as_dict(),
            "policy": (
                "Reasoning-bearing content is dropped AT INGESTION, before any "
                "record is stored, logged, hashed, counted for content, or "
                "written. No chain-of-thought observability exists here."
            ),
        }
    else:
        run["stdout_state"] = {}

    lifecycle = server.shutdown(shutdown_trigger)
    run["broker_recorded_security_shape"] = server.security_shape()
    run["broker_recorded_lifecycle"] = lifecycle
    run["broker_recorded_activity"] = handler.diagnostics.as_dict()
    run["broker_recorded_run_state"] = run_state.as_dict()
    run["broker_recorded_capability"] = sed.summary()
    teardown_closed = lifecycle["state_reached"] == STATE_CLOSED

    # -- AIDO's INDEPENDENT observation. The only repository authority. -------
    post = observe_repository(git_executable=git_executable, workspace_root=fixture.repo_root)
    classification = classify(
        post,
        workspace_root=fixture.repo_root,
        head_before=fixture.head_before,
        expected_changed_paths=case.expected_changed_paths or frozenset({"__none__"}),
        baseline=internal["baseline_snapshot"],
    )
    observed: dict[str, Any] = {
        "trust": "AUTHORITATIVE -- derived by AIDO from the repository itself",
        "head_before": fixture.head_before,
        "head_after": post.head,
        "head_moved": classification.head_moved,
        "classification": classification.as_dict(),
        "status": snapshot_for_record(post),
        "observed_after_termination_rung": run.get("termination", {}).get("rung_reached"),
        "observed_after_broker_state": lifecycle["state_reached"],
        "quiescence_claimed": False,
    }
    if not teardown_closed:
        observed["clean_classification_withheld"] = True
        observed["clean_classification_withheld_reason"] = (
            "broker teardown did not reach CLOSED, so no clean repository "
            "classification is issued for this run"
        )

    # -- the cross-check ------------------------------------------------------
    broker_mutated = sorted(run_state.mutated_paths)
    git_changed = sorted(classification.changed_tracked_paths)
    broker_not_observed = sorted(set(broker_mutated) - set(git_changed))
    observed_not_explained = sorted(set(git_changed) - set(broker_mutated))
    cross_check = {
        "broker_recorded_mutated_paths": broker_mutated,
        "orchestrator_observed_changed_paths": git_changed,
        "broker_recorded_but_not_observed": broker_not_observed,
        "observed_but_not_explained_by_the_broker": observed_not_explained,
        "agree": not broker_not_observed and not observed_not_explained,
        "note": (
            "A discrepancy in EITHER direction is an anomaly and classifies the "
            "workspace untrusted. The broker log is AIDO-authored and DIAGNOSTIC; "
            "it is never promoted to repository truth."
        ),
    }
    run["cross_check"] = cross_check

    trusted = classification.trusted and cross_check["agree"] and teardown_closed
    if trusted and git_changed:
        observed["diffs"] = {
            path: diff_expected_path(
                git_executable=git_executable,
                workspace_root=fixture.repo_root,
                repo_relative_path=path,
            )
            for path in git_changed
        }
    else:
        observed["diffs"] = None
        observed["diff_not_taken_reason"] = (
            "no trusted tracked modification to diff, or the observed state was "
            "not a trusted shape; nothing was repaired"
        )
    run["orchestrator_observed"] = observed

    if trusted:
        outcome = run_verification(
            python_executable=config["python_executable"],
            workspace_root=fixture.repo_root,
            args=case.verification_args,
        )
        run["orchestrator_observed"]["verification"] = outcome.as_dict()
        post_verification = observe_repository(
            git_executable=git_executable, workspace_root=fixture.repo_root
        )
        run["orchestrator_observed"]["post_verification_status"] = snapshot_for_record(
            post_verification
        )
    else:
        run["orchestrator_observed"]["verification"] = {
            "run": False,
            "reason": (
                "the observed state was not trusted, the broker/Git cross-check "
                "did not agree, or broker teardown did not reach CLOSED"
            ),
        }

    run["case_assessment"] = assess_o1(
        classification=classification,
        cross_check=cross_check,
        verification=run["orchestrator_observed"]["verification"],
        run_state=run_state,
        diagnostics=handler.diagnostics,
        turn_outcome=turn_outcome,
        teardown_closed=teardown_closed,
        stdout_state=run.get("stdout_state", {}),
    )
    run["bounds"] = bounds.as_dict()
    run["bounds_note"] = (
        "These are runtime/process supervision bounds and broker IPC/teardown "
        "bounds. NONE of them is a token limit."
    )
    run["_internal"] = {
        "fixture": fixture,
        "preflight": preflight,
        "endpoint_host": route_check.endpoint_host,
        "binding": binding,
        "pipe_name": server.pipe_name,
        "server": server,
        "pi_config_dir": pi_config_dir,
        "extension_dir": extension_dir,
        "teardown_closed": teardown_closed,
        "turn_outcome": turn_outcome,
    }
    return run


# -- emission ------------------------------------------------------------------


def _finalize(run: dict[str, Any], *, needles: tuple[str, ...]) -> dict[str, Any]:
    internal = run.pop("_internal", {})
    preflight = internal.get("preflight", {})
    observed_pi_version = run.get("pi_runtime", {}).get("observed_version")
    run = redact_value(run, needles)
    preflight = redact_value(preflight, needles)
    return record_header(
        generated_at=_utc_now(),
        runtime={
            "name": "pi",
            "observed_version": observed_pi_version,
            "version_recorded_as_provenance": True,
            "exact_version_is_authorization_gate": False,
            "launch_mode": "rpc",
        },
        provider_route={
            "logical_route_name": LOGICAL_ROUTE_NAME,
            "endpoint_recorded": False,
            "provider_http_request_count_is_not_aido_observable": True,
        },
        model={"id": PINNED_MODEL_ID},
        token_policy=TOKEN_POLICY,
        preflight=preflight,
        run=run,
        capability_boundary=CAPABILITY_BOUNDARY,
        residual_limitations=RESIDUAL_LIMITATIONS,
    )


def emit_or_refuse(
    payload: dict[str, Any],
    *,
    phase: str,
    out_path: Path,
    extra_forbidden: tuple[tuple[str, str], ...] = (),
) -> int:
    """The ONE safe-emission choke point. Identical policy to AR2's."""
    try:
        scrub_result = scrub_check(payload, extra_forbidden=extra_forbidden)
    except Exception as exc:  # noqa: BLE001 - any scrub failure fails closed
        scrub_result = {
            "scrub_checked": False,
            "findings": ["scrub_check_raised", type(exc).__name__],
            "clean": False,
        }
    payload["scrub"] = scrub_result

    if scrub_result.get("clean"):
        out_path.write_text(dumps_ascii(payload) + "\n", encoding="utf-8")
        echo_ascii(payload)
        sys.stderr.write(f"[ar2-o1] record written: {out_path}\n")
        return 0

    findings = list(scrub_result.get("findings") or [])
    refusal = refusal_record(phase=phase, finding_count=len(findings), finding_categories=findings)
    try:
        refusal_scrub = scrub_check(refusal)
    except Exception:  # noqa: BLE001
        refusal_scrub = {"clean": False}
    if not refusal_scrub.get("clean"):
        sys.stderr.write(
            "[ar2-o1] REFUSED: the candidate artifact failed its scrub check, and "
            "the refusal record itself could not be confirmed safe to persist. "
            "Nothing was written.\n"
        )
        return 3

    out_path.write_text(dumps_ascii(refusal) + "\n", encoding="utf-8")
    echo_ascii(refusal)
    sys.stderr.write(
        "[ar2-o1] REFUSED: the candidate artifact failed its scrub check; a safe "
        f"refusal record was written instead: {out_path}\n"
    )
    return 2


# -- entry point -----------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run_o1.py",
        description=(
            "Phase 5F3A-AR2-O1 two-file coordinated implementation case "
            "(EXPERIMENT ONLY). Built on the accepted, frozen AR2 architecture."
        ),
    )
    parser.add_argument("--phase", choices=("preflight", "broker", "handshake", "case"), default="preflight")
    parser.add_argument("--config", default=str(_HERE / CONFIG_FILENAME))
    parser.add_argument(
        "--run-pi-delegated-broker-experiment",
        action="store_true",
        help="Explicit flag 1 of 2. Required for --phase case.",
    )
    parser.add_argument(
        "--send-one-real-model-prompt",
        action="store_true",
        help="Explicit flag 2 of 2. Required for --phase case. Authorizes EXACTLY ONE prompt.",
    )
    parser.add_argument("--profile-env-names", default="")
    parser.add_argument("--keep-fixture", action="store_true")
    args = parser.parse_args(argv)

    try:
        config = load_experiment_config(Path(args.config))
    except GateRefusal as exc:
        echo_ascii({"refused": True, "reason": str(exc)})
        return 1

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    extra_forbidden: tuple[tuple[str, str], ...] = ()

    try:
        if args.phase == "preflight":
            report = phase_preflight(config)
            internal = report.pop("_internal")
            if not args.keep_fixture:
                report["cleanup"] = remove_disposable_tree(internal["fixture"].experiment_root)
            payload = report
        elif args.phase == "broker":
            payload = phase_broker(config)
        elif args.phase == "handshake":
            profile_names = tuple(n.strip() for n in args.profile_env_names.split(",") if n.strip())
            report = phase_handshake(config, profile_names=profile_names)
            internal = report.pop("_internal", {})
            binding = internal.get("binding")
            pipe_name = internal.get("pipe_name")
            base_url = os.environ.get(config["base_url_env_name"], "").strip()
            needles = tuple(
                v
                for v in (
                    base_url,
                    binding.token if binding else None,
                    binding.capability_id if binding else None,
                    pipe_name,
                )
                if v
            )
            extra_forbidden = broker_secret_denylist(
                token=binding.token if binding else None,
                capability_id=binding.capability_id if binding else None,
                pipe_name=pipe_name,
            )
            if base_url:
                extra_forbidden += (("configured_endpoint_value_present", base_url),)
            payload = redact_value(report, needles)
        else:
            if not (args.run_pi_delegated_broker_experiment and args.send_one_real_model_prompt):
                raise GateRefusal(
                    "refused: --phase case requires BOTH "
                    "--run-pi-delegated-broker-experiment and "
                    "--send-one-real-model-prompt"
                )
            profile_names = tuple(n.strip() for n in args.profile_env_names.split(",") if n.strip())
            run = phase_case(config, profile_names=profile_names)
            internal = run.get("_internal", {})
            base_url = os.environ.get(config["base_url_env_name"], "").strip()
            binding = internal.get("binding")
            pipe_name = internal.get("pipe_name")
            needles = tuple(
                v
                for v in (
                    base_url,
                    binding.token if binding else None,
                    binding.capability_id if binding else None,
                    pipe_name,
                )
                if v
            )
            endpoint_host = internal.get("endpoint_host")
            if endpoint_host:
                needles += (endpoint_host,)
            extra_forbidden = broker_secret_denylist(
                token=binding.token if binding else None,
                capability_id=binding.capability_id if binding else None,
                pipe_name=pipe_name,
                endpoint_host=endpoint_host,
            )
            if base_url:
                extra_forbidden += (("configured_endpoint_value_present", base_url),)

            fixture = internal.get("fixture")
            pi_config_dir = internal.get("pi_config_dir")
            extension_dir = internal.get("extension_dir")
            teardown_closed = bool(internal.get("teardown_closed"))
            assessment = run.get("case_assessment", {})
            stdout_state = run.get("stdout_state", {})
            no_anomaly = (
                bool(assessment.get("passed"))
                and teardown_closed
                and not stdout_state.get("protocol_violation")
                and not stdout_state.get("byte_cap_exceeded")
                and not stdout_state.get("event_cap_exceeded")
                and not run.get("broker_recorded_activity", {}).get("anomalies")
            )

            payload = _finalize(run, needles=needles)

            cleanup: dict[str, Any] = {"performed": False}
            if fixture is not None:
                # FU1A: each generated resource is scrubbed INDEPENDENTLY --
                # Pi-config scrubbing is never made conditional on the
                # extension having been generated (and vice versa). Both
                # scrubs, when applicable, run BEFORE any decision to
                # preserve or delete the disposable root, so no endpoint- or
                # binding-bearing generated file can survive into preserved
                # evidence regardless of which resource(s) actually existed.
                if pi_config_dir:
                    cleanup["pi_models_json_scrub"] = scrub_generated_pi_config(pi_config_dir)
                if extension_dir:
                    cleanup["extension_binding_scrub"] = scrub_generated_extension_config(extension_dir)
                if not args.keep_fixture and no_anomaly:
                    cleanup.update(remove_disposable_tree(fixture.experiment_root))
                    cleanup["performed"] = True
                    payload["run"]["fixture_preserved"] = False
                else:
                    payload["run"]["fixture_preserved"] = True
                    payload["run"]["fixture_preserved_reason"] = (
                        "an unmet case criterion, an incomplete broker teardown, a "
                        "protocol/bound anomaly, a broker anomaly, or "
                        "--keep-fixture: evidence is preserved rather than destroyed"
                    )
            payload["run"]["cleanup"] = cleanup
    except (
        GateRefusal,
        LaunchIdentityError,
        GitExecutableError,
        PiSupervisorError,
        ManifestTooLargeError,
    ) as exc:
        echo_ascii(
            {
                "experiment": EXPERIMENT_ID,
                "refused": True,
                "phase": args.phase,
                "case": CASE_ID,
                "prompt_sent": False,
                "semantic_prompts_sent": 0,
                "reason": f"{type(exc).__name__}: {exc}",
                "note": (
                    "An infrastructure gate failed BEFORE the case prompt, so this "
                    "case sent zero prompts and stopped."
                ),
            }
        )
        return 1

    out_path = RESULTS_DIR / f"ar2o1_{args.phase}_{CASE_ID}_{stamp}.json"
    return emit_or_refuse(payload, phase=args.phase, out_path=out_path, extra_forbidden=extra_forbidden)


if __name__ == "__main__":
    raise SystemExit(main())
