"""Phase 5F3A-AR1 harness entry point. EXPERIMENT ONLY -- not a CLI command.

Gating without a production gate (AR0-FU1 section 10): two explicit flags plus a
required, explicitly-named experiment config file that ships ABSENT. An absent
config file is a refusal, not a default.

Phases::

    preflight   pin Node+Pi, build the fixture, baseline-verify, baseline-observe
    probe-env   launch Pi (NO prompt, NO inference) to find the minimum
                environment it starts under -- answers AR0 U-2/U-3/U-4
    live        the ONE real semantic run: one launch, one prompt, one observation

``live`` requires BOTH flags. Exactly one real semantic prompt is permitted, ever.
There is no relaunch, no fallback runtime, no fallback model, no second provider
route, and no retry for any reason -- including a disappointing result.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(_HERE))

from ai_dev_orchestrator.workspace.git_adapter import (  # noqa: E402
    GitExecutableError,
    resolve_git_executable,
)

from ar1 import EXPERIMENT_ID  # noqa: E402
from ar1.ascii_json import dumps_ascii, echo_ascii  # noqa: E402
from ar1.environment import (  # noqa: E402
    PROFILE_NAMES_UNDER_TEST,
    audit_withheld_names,
    build_launch_environment,
)
from ar1.fixture import (  # noqa: E402
    EXPECTED_BASELINE_FAILING_TEST,
    EXPECTED_CHANGED_PATH,
    create_experiment_root,
    create_synthetic_repository,
    remove_disposable_tree,
    sha256_of_file,
)
from ar1.launch import (  # noqa: E402
    LaunchIdentityError,
    build_pi_argv,
    resolve_runtime_identity,
)
from ar1.observation import (  # noqa: E402
    CLEAN_EXPECTED,
    NO_CHANGE_OBSERVED,
    classify,
    diff_expected_path,
    observe_repository,
    snapshot_for_record,
)
from ar1.pi_config import (  # noqa: E402
    EXPECTED_EXTENSION_SOURCE_KIND,
    SENTINEL_COMMAND_NAME,
    TOOL_ALLOWLIST,
    describe_generated_config,
    write_disposable_extension,
    write_disposable_pi_config,
)
from ar1.record import (  # noqa: E402
    CAPABILITY_BOUNDARY,
    RESIDUAL_LIMITATIONS,
    TOKEN_POLICY,
    record_header,
    refusal_record,
    relative_to_experiment_root,
    scrub_check,
)
from ar1.supervisor import (  # noqa: E402
    RUNTIME_SETTLED,
    PiRpcSupervisor,
    PiSupervisorError,
    RunBounds,
)
from ar1.verification import (  # noqa: E402
    baseline_matches_seeded_defect,
    run_verification,
)

CONFIG_FILENAME = "experiment_config.json"
RESULTS_DIR = _HERE / "results"

# The ONE prompt. Short and explicit enough not to require ls/find, and it does
# not name the operator, the diff, or ask for tests to be run (no bash exists).
THE_ONE_PROMPT = (
    "Inspect calc.py and test_calc.py.\n"
    "Fix the failing boundary behavior in calc.py only.\n"
    "Do not modify test_calc.py.\n"
    "Finish when the implementation is complete."
)


class GateRefusal(Exception):
    """A precondition failed. No prompt is sent."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_experiment_config(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise GateRefusal(
            f"refused: the experiment config file {path.name!r} is absent. It "
            "ships absent deliberately; create it explicitly to run anything."
        )
    config = json.loads(path.read_text(encoding="utf-8"))
    for key in ("provider_id", "model_id", "base_url_env_name", "python_executable"):
        if not config.get(key):
            raise GateRefusal(f"refused: experiment config is missing {key!r}")
    return config


def _resolve_base_url(config: dict[str, Any]) -> str:
    name = config["base_url_env_name"]
    value = os.environ.get(name, "").strip()
    if not value:
        raise GateRefusal(
            f"refused: the route endpoint variable {name!r} is unset or blank. "
            "The experiment is NOT EXECUTED. No key or endpoint is invented."
        )
    return value


# -- phases --------------------------------------------------------------------


def phase_preflight(config: dict[str, Any], *, with_canary: bool) -> dict[str, Any]:
    """Pin the runtime, build the fixture, baseline-verify and baseline-observe."""
    report: dict[str, Any] = {"phase": "preflight", "started_at": _utc_now()}

    identity = resolve_runtime_identity()
    report["runtime_identity"] = {
        "runtime": "pi",
        "version": identity.reported_version,
        "launch_shape": identity.launch_shape,
        "node_direct_launch_works": True,
        "node_executable_basename": os.path.basename(identity.node_executable),
        "pi_entry_basename": os.path.basename(identity.pi_cli_js),
    }

    git_executable = resolve_git_executable(workspace_root=str(_HERE))
    experiment_root = create_experiment_root()
    fixture = create_synthetic_repository(
        experiment_root, git_executable=git_executable, with_outside_canary=with_canary
    )
    report["fixture"] = {
        "experiment_root_recorded": False,
        "repo_relative_files": ["calc.py", "test_calc.py"],
        "head_before": fixture.head_before,
        "calc_sha256_before": sha256_of_file(fixture.calc_path),
        "outside_canary_present": fixture.outside_canary_path is not None,
    }

    baseline_verification = run_verification(
        python_executable=config["python_executable"], workspace_root=fixture.repo_root
    )
    ok, why = baseline_matches_seeded_defect(
        baseline_verification, expected_failing_test=EXPECTED_BASELINE_FAILING_TEST
    )
    report["baseline_verification"] = baseline_verification.as_dict()
    report["baseline_verification"]["matches_seeded_defect"] = ok
    report["baseline_verification"]["assessment"] = why

    baseline_snapshot = observe_repository(
        git_executable=git_executable, workspace_root=fixture.repo_root
    )
    baseline_class = classify(
        baseline_snapshot,
        workspace_root=fixture.repo_root,
        head_before=fixture.head_before,
        expected_changed_paths=frozenset({EXPECTED_CHANGED_PATH}),
        baseline=baseline_snapshot,
    )
    report["baseline_observation"] = snapshot_for_record(baseline_snapshot)
    report["baseline_classification"] = baseline_class.as_dict()
    # A pristine fixture has no tracked modification at all, which classify()
    # reports as NO_CHANGE_OBSERVED. That IS the clean baseline.
    report["baseline_is_clean"] = baseline_class.workspace_class == NO_CHANGE_OBSERVED

    report["_internal"] = {
        "identity": identity,
        "fixture": fixture,
        "git_executable": git_executable,
        "baseline_snapshot": baseline_snapshot,
    }
    return report


def evaluate_extension_identity(
    commands: list[Any],
    *,
    extension_entry: str,
    sentinel_command_name: str = SENTINEL_COMMAND_NAME,
    expected_source_kind: str = EXPECTED_EXTENSION_SOURCE_KIND,
) -> dict[str, Any]:
    """H1 -- prove the extension identity (AR1-FU1). Fails closed on ambiguity.

    A sentinel command merely existing is NOT sufficient (that was the pre-FU1
    gate, and the historical AR1 live run used exactly that weaker gate -- see
    FINDINGS.md). This proves, in order:

    1. a command named ``sentinel_command_name`` was reported at all;
    2. its reported ``source`` is exactly ``"extension"``;
    3. its reported path -- read from ``sourceInfo.path`` (Pi 0.84.2's actual
       shape) or, if that is absent, the flat ``path`` field some documentation
       shows -- resolves to exactly the expected extension entry point AIDO
       itself passed via ``--extension``;
    4. when Pi also reports a source-origin field (``sourceInfo.source``), it
       does not contradict the one known-expected value for a CLI-loaded
       extension. The field is optional; a *wrong* value is never ignored.

    Any missing, wrong, or malformed piece fails the whole gate. There is no
    partial credit and no path repair: an expected path is never guessed at from
    a mismatched one.
    """
    same_name = [
        c for c in commands if isinstance(c, dict) and c.get("name") == sentinel_command_name
    ]
    sentinel_name_matched = bool(same_name)
    sentinel = next((c for c in same_name if c.get("source") == "extension"), None)
    extension_source_matched = sentinel is not None

    extension_path_matched = False
    noncontradictory_source_origin = True
    malformed_source_metadata = False
    reported_source_kind: Any = None
    failure_reasons: list[str] = []

    if not sentinel_name_matched:
        failure_reasons.append(f"no command named {sentinel_command_name!r} was reported")
    elif not extension_source_matched:
        failure_reasons.append(
            f"a command named {sentinel_command_name!r} exists but its reported "
            "source is not 'extension'"
        )
    else:
        source_info = sentinel.get("sourceInfo")
        if source_info is not None and not isinstance(source_info, dict):
            malformed_source_metadata = True
            failure_reasons.append("sourceInfo is present but not an object")
            source_info = None

        reported_path: Any = None
        if isinstance(source_info, dict):
            reported_source_kind = source_info.get("source")
            candidate = source_info.get("path")
            if candidate is not None and not isinstance(candidate, str):
                malformed_source_metadata = True
                failure_reasons.append("sourceInfo.path is present but not a string")
            elif isinstance(candidate, str):
                reported_path = candidate

        flat_path = sentinel.get("path")
        if flat_path is not None and not isinstance(flat_path, str):
            malformed_source_metadata = True
            failure_reasons.append("the flat 'path' field is present but not a string")
        elif reported_path is None and isinstance(flat_path, str):
            reported_path = flat_path

        if reported_path is None:
            failure_reasons.append(
                "neither sourceInfo.path nor the flat 'path' field is a usable "
                "string; extension identity cannot be proven"
            )
        else:
            try:
                extension_path_matched = os.path.normcase(
                    os.path.realpath(reported_path)
                ) == os.path.normcase(os.path.realpath(extension_entry))
            except OSError:  # pragma: no cover - defensive
                extension_path_matched = False
            if not extension_path_matched:
                failure_reasons.append(
                    "the reported extension path does not resolve to the "
                    "expected extension entry point"
                )

        if reported_source_kind is not None and reported_source_kind != expected_source_kind:
            noncontradictory_source_origin = False
            failure_reasons.append(
                "sourceInfo.source reported "
                f"{reported_source_kind!r}, contradicting the expected "
                f"{expected_source_kind!r} for a CLI-loaded extension"
            )

    passed = (
        sentinel_name_matched
        and extension_source_matched
        and extension_path_matched
        and noncontradictory_source_origin
        and not malformed_source_metadata
    )

    return {
        "sentinel_command_name": sentinel_command_name,
        "sentinel_name_matched": sentinel_name_matched,
        "extension_source_matched": extension_source_matched,
        "extension_path_matched": extension_path_matched,
        "noncontradictory_source_origin": noncontradictory_source_origin,
        "malformed_source_metadata": malformed_source_metadata,
        "expected_source_kind": expected_source_kind,
        "failure_reasons": failure_reasons,
        # Field names preserved from the pre-FU1 report shape. Their MEANING is
        # now stricter: "present" now means "present, extension-sourced, at the
        # expected path, with no contradictory reported origin" -- never
        # "a same-named command existed".
        "sentinel_present_from_extension_source": extension_source_matched,
        "sentinel_extension_path_matched_expected": extension_path_matched,
        "sentinel_source_kind": reported_source_kind,
        "proves": (
            "the intended extension loaded, at the expected path, with a "
            "noncontradictory reported source origin"
        ),
        "does_not_prove": (
            "the exact contents of the active tool registry; Pi 0.84.2 has no "
            "RPC command that enumerates tools"
        ),
        "passed": passed,
    }


def _launch_and_handshake(
    *,
    identity,
    fixture,
    config: dict[str, Any],
    base_url: str,
    profile_names: tuple[str, ...],
    git_executable: str,
    bounds: RunBounds,
) -> tuple[PiRpcSupervisor, dict[str, Any]]:
    """Generate the disposable config, launch Pi, and run BOTH handshakes.

    No prompt is sent here, and neither handshake triggers inference.
    """
    config_dir, settings_path, models_path = write_disposable_pi_config(
        fixture.experiment_root,
        provider_id=config["provider_id"],
        model_id=config["model_id"],
        base_url=base_url,
    )
    extension_dir, extension_entry = write_disposable_extension(
        fixture.experiment_root,
        source_dir=str(_HERE / "extension"),
        repo_root=fixture.repo_root,
        read_allowlist=(fixture.calc_path, fixture.test_path),
        edit_allowlist=(fixture.calc_path,),
        experiment_id=EXPERIMENT_ID,
    )

    launch_env = build_launch_environment(
        node_executable=identity.node_executable,
        pi_config_dir=config_dir,
        git_executable=git_executable,
        include_profile_names=profile_names,
    )
    argv = build_pi_argv(
        identity,
        extension_entry=extension_entry,
        tool_allowlist=TOOL_ALLOWLIST,
        provider=config["provider_id"],
        model=config["model_id"],
    )

    supervisor = PiRpcSupervisor(
        argv=argv,
        cwd=fixture.repo_root,
        environment=launch_env.environment,
        bounds=bounds,
    )
    report: dict[str, Any] = {
        "generated_pi_config": describe_generated_config(
            settings_path=settings_path, models_path=models_path
        ),
        "extension_files_present": sorted(
            p.name for p in Path(extension_dir).iterdir()
        ),
        "tool_registry_allowlist": list(TOOL_ALLOWLIST),
        "launch_flags": [a for a in argv[2:] if not os.path.isabs(a)],
        "environment": {
            "explicit_dict": True,
            "os_environ_copied": False,
            "variable_names": list(launch_env.included_names),
            "profile_names_included": list(launch_env.profile_names_included),
            "profile_names_withheld": list(launch_env.profile_names_withheld),
            "path_narrowed": launch_env.path_narrowed,
            "path_entry_count": launch_env.path_entry_count,
            "withheld_audit": audit_withheld_names(launch_env.environment),
        },
    }

    supervisor.launch()
    startup_started = time.monotonic()

    # H1 -- extension identity (AR1-FU1: exact identity, not mere presence).
    supervisor.send_command({"id": "h1", "type": "get_commands"})
    outcome_h1, response_h1 = supervisor.await_response(
        "h1", timeout_seconds=bounds.startup_deadline_seconds
    )
    commands = []
    if response_h1 and isinstance(response_h1.get("data"), dict):
        commands = response_h1["data"].get("commands") or []

    identity_result = evaluate_extension_identity(commands, extension_entry=extension_entry)

    report["handshake_extension"] = {
        "command": "get_commands",
        "wait_outcome": outcome_h1,
        "response_success": bool(response_h1 and response_h1.get("success")),
        **identity_result,
        "extension_command_count": sum(
            1 for c in commands if isinstance(c, dict) and c.get("source") == "extension"
        ),
        "other_extension_command_names": sorted(
            str(c.get("name"))
            for c in commands
            if isinstance(c, dict)
            and c.get("source") == "extension"
            and c.get("name") != SENTINEL_COMMAND_NAME
        ),
        "non_extension_command_count": sum(
            1 for c in commands if isinstance(c, dict) and c.get("source") != "extension"
        ),
    }

    # H2 -- provider/model identity. Does not trigger inference.
    supervisor.send_command({"id": "h2", "type": "get_state"})
    remaining = bounds.startup_deadline_seconds - (time.monotonic() - startup_started)
    outcome_h2, response_h2 = supervisor.await_response(
        "h2", timeout_seconds=max(remaining, 1.0)
    )
    model_obj: dict[str, Any] = {}
    if response_h2 and isinstance(response_h2.get("data"), dict):
        candidate = response_h2["data"].get("model")
        if isinstance(candidate, dict):
            model_obj = candidate
    provider_matches = model_obj.get("provider") == config["provider_id"]
    model_matches = model_obj.get("id") == config["model_id"]

    report["handshake_model"] = {
        "command": "get_state",
        "wait_outcome": outcome_h2,
        "response_success": bool(response_h2 and response_h2.get("success")),
        "expected_provider": config["provider_id"],
        "expected_model": config["model_id"],
        "reported_provider": model_obj.get("provider"),
        "reported_model": model_obj.get("id"),
        "reported_api": model_obj.get("api"),
        "reported_base_url_recorded": False,
        "runtime_native_max_tokens_reported": model_obj.get("maxTokens"),
        "provider_matches": provider_matches,
        "model_matches": model_matches,
        "triggered_inference": False,
        "passed": bool(provider_matches and model_matches),
    }
    report["startup_seconds"] = round(time.monotonic() - startup_started, 3)
    return supervisor, report


def phase_probe_env(config: dict[str, Any]) -> dict[str, Any]:
    """Find the minimum environment Pi starts under. NO prompt, NO inference."""
    preflight = phase_preflight(config, with_canary=False)
    internal = preflight.pop("_internal")
    base_url = _resolve_base_url(config)
    bounds = RunBounds()

    attempts: list[dict[str, Any]] = []
    ladder: list[tuple[str, ...]] = [(), ("USERPROFILE",), ("USERPROFILE", "APPDATA"), PROFILE_NAMES_UNDER_TEST]
    minimum: tuple[str, ...] | None = None

    for profile_names in ladder:
        # Each attempt needs its own disposable root so nothing is reused.
        fixture = create_synthetic_repository(
            create_experiment_root(),
            git_executable=internal["git_executable"],
            with_outside_canary=False,
        )
        supervisor = None
        try:
            supervisor, report = _launch_and_handshake(
                identity=internal["identity"],
                fixture=fixture,
                config=config,
                base_url=base_url,
                profile_names=profile_names,
                git_executable=internal["git_executable"],
                bounds=bounds,
            )
            passed = (
                report["handshake_extension"]["passed"]
                and report["handshake_model"]["passed"]
            )
            attempts.append(
                {
                    "profile_names_included": list(profile_names),
                    "extension_handshake_passed": report["handshake_extension"]["passed"],
                    "model_handshake_passed": report["handshake_model"]["passed"],
                    "handshake_extension": report["handshake_extension"],
                    "handshake_model": report["handshake_model"],
                    "environment_variable_names": report["environment"]["variable_names"],
                    "withheld_audit": report["environment"]["withheld_audit"],
                    "stdout_state": supervisor.stdout_state(),
                    "stderr": supervisor.stderr_snapshot(),
                    "startup_seconds": report["startup_seconds"],
                    "started_successfully": passed,
                }
            )
            if passed and minimum is None:
                minimum = profile_names
        except (PiSupervisorError, LaunchIdentityError) as exc:
            attempts.append(
                {
                    "profile_names_included": list(profile_names),
                    "started_successfully": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
        finally:
            if supervisor is not None:
                supervisor.shutdown()
            remove_disposable_tree(fixture.experiment_root)
        if minimum is not None:
            break

    remove_disposable_tree(internal["fixture"].experiment_root)
    return {
        "phase": "probe-env",
        "question": "AR0 U-2/U-3/U-4: can HOME/USERPROFILE/APPDATA be withheld, and does a narrowed PATH work?",
        "attempts": attempts,
        "minimum_profile_names_required": list(minimum) if minimum is not None else None,
        "home_userprofile_appdata_withheld": minimum == (),
        "path_narrowed": True,
        "model_calls_made": 0,
        "prompts_sent": 0,
    }


def phase_live(config: dict[str, Any], *, profile_names: tuple[str, ...]) -> dict[str, Any]:
    """The ONE real semantic run. One launch, one prompt, one observation."""
    preflight = phase_preflight(config, with_canary=False)
    internal = preflight.pop("_internal")
    identity = internal["identity"]
    fixture = internal["fixture"]
    git_executable = internal["git_executable"]

    # -- the live-run gate. Any failure means the prompt is NOT sent. ---------
    gate: dict[str, Any] = {
        "pi_version_is_pinned_0_84_2": identity.reported_version == "0.84.2",
        "node_direct_launch_works": True,
        "baseline_repository_trusted": preflight["baseline_is_clean"],
        "baseline_shows_exactly_seeded_failure": preflight["baseline_verification"][
            "matches_seeded_defect"
        ],
    }
    base_url = _resolve_base_url(config)
    gate["route_configuration_available"] = True

    bounds = RunBounds()
    supervisor, launch_report = _launch_and_handshake(
        identity=identity,
        fixture=fixture,
        config=config,
        base_url=base_url,
        profile_names=profile_names,
        git_executable=git_executable,
        bounds=bounds,
    )
    gate["extension_sentinel_handshake_passed"] = launch_report["handshake_extension"][
        "passed"
    ]
    gate["model_identity_handshake_passed"] = launch_report["handshake_model"]["passed"]
    gate_all_passed = all(bool(v) for v in gate.values())

    run: dict[str, Any] = {
        "phase": "live",
        "started_at": _utc_now(),
        "live_run_gate": gate,
        "gate_passed": gate_all_passed,
        "prompt_sent": False,
        "semantic_prompts_sent": 0,
    }
    run.update(launch_report)

    turn_outcome = "not_attempted"
    if gate_all_passed:
        prompt_started = time.monotonic()
        supervisor.send_command({"id": "p1", "type": "prompt", "message": THE_ONE_PROMPT})
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
    run["turn_outcome"] = turn_outcome

    termination = supervisor.shutdown()
    run["termination"] = termination
    run["stdout_state"] = supervisor.stdout_state()
    run["stderr"] = supervisor.stderr_snapshot()
    run["bounds"] = bounds.as_dict()
    run["bounds_note"] = (
        "These are runtime/process supervision bounds. They are NOT token limits."
    )

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
            "Reasoning-bearing content is dropped AT INGESTION, before any record "
            "is stored, logged, hashed, counted for content, or written. No "
            "chain-of-thought observability exists here."
        ),
    }

    # -- AIDO's INDEPENDENT observation. The only repository authority. -------
    post = observe_repository(git_executable=git_executable, workspace_root=fixture.repo_root)
    classification = classify(
        post,
        workspace_root=fixture.repo_root,
        head_before=fixture.head_before,
        expected_changed_paths=frozenset({EXPECTED_CHANGED_PATH}),
        baseline=internal["baseline_snapshot"],
    )
    observed: dict[str, Any] = {
        "trust": "AUTHORITATIVE -- derived by AIDO from the repository itself",
        "head_before": fixture.head_before,
        "head_after": post.head,
        "head_moved": classification.head_moved,
        "classification": classification.as_dict(),
        "status": snapshot_for_record(post),
        "observed_after_termination_rung": termination.get("rung_reached"),
        "quiescence_claimed": False,
    }
    if classification.trusted and classification.changed_tracked_paths == [
        EXPECTED_CHANGED_PATH
    ]:
        observed["diff"] = diff_expected_path(
            git_executable=git_executable,
            workspace_root=fixture.repo_root,
            repo_relative_path=EXPECTED_CHANGED_PATH,
        )
        observed["calc_sha256_after"] = sha256_of_file(fixture.calc_path)
    else:
        observed["diff"] = None
        observed["diff_not_taken_reason"] = (
            "the observed state was not the one expected tracked-modification "
            "shape, so no diff was requested and nothing was repaired"
        )
    run["orchestrator_observed"] = observed

    # -- verification, only for a trusted observed state. ---------------------
    if classification.trusted:
        outcome = run_verification(
            python_executable=config["python_executable"],
            workspace_root=fixture.repo_root,
        )
        run["orchestrator_observed"]["verification"] = outcome.as_dict()
        run["orchestrator_observed"]["seeded_bug_fixed"] = bool(
            outcome.passed and outcome.counts.get("passed") == 3
        )
        post_verification = observe_repository(
            git_executable=git_executable, workspace_root=fixture.repo_root
        )
        run["orchestrator_observed"]["post_verification_status"] = snapshot_for_record(
            post_verification
        )
        run["orchestrator_observed"]["post_verification_note"] = (
            "State AFTER AIDO's own verification ran, kept separate from the "
            "pre-verification observation above."
        )
    else:
        run["orchestrator_observed"]["verification"] = {
            "run": False,
            "reason": "workspace untrusted; stopped before verification",
        }
        run["orchestrator_observed"]["seeded_bug_fixed"] = False

    run["_internal"] = {"fixture": fixture, "preflight": preflight}
    return run


def _redact_endpoint(value: Any, base_url: str) -> Any:
    """A redaction BACKSTOP, never a guarantee.

    If runtime- or child-produced text happened to echo the endpoint, replace it
    before the record is written. This does not make the record provably
    secret-free and must never be described as if it did.
    """
    if isinstance(value, str):
        return value.replace(base_url, "<endpoint redacted>")
    if isinstance(value, dict):
        return {k: _redact_endpoint(v, base_url) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_endpoint(v, base_url) for v in value]
    return value


def _finalize(run: dict[str, Any], *, base_url: str | None) -> dict[str, Any]:
    """Build the candidate record. Does NOT scrub-gate emission -- that is the
    single choke point in ``emit_or_refuse``, which runs after this and needs
    the endpoint value (if any) to build its ``extra_forbidden`` codes."""
    internal = run.pop("_internal", {})
    preflight = internal.get("preflight", {})
    if base_url:
        run = _redact_endpoint(run, base_url)
        preflight = _redact_endpoint(preflight, base_url)
    return record_header(
        generated_at=_utc_now(),
        runtime={"name": "pi", "version": "0.84.2", "launch_mode": "rpc"},
        provider_route={"logical_route_name": "qwen36-direct-vllm", "endpoint_recorded": False},
        model={"id": "Qwen3.6-27B-131K"},
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
    """The one safe-emission choke point (AR1-FU1).

    ``scrub_check`` can DETECT an unsafe candidate artifact; this function is
    what makes that detection fail-closed rather than advisory. A clean result
    writes and echoes the full candidate. Anything else -- an actual finding, OR
    the scrub check itself raising on a malformed candidate -- refuses the
    candidate outright and emits a small, fixed, independently scrub-checked
    refusal record in its place. The candidate is never written, echoed, or
    otherwise persisted once it is refused; only bounded metadata (finding
    counts and codes) survives into the refusal record.

    Returns 0 (candidate written), 2 (candidate refused, safe refusal written),
    or 3 (candidate refused, AND the refusal record itself could not be
    confirmed safe -- nothing at all is written).
    """
    try:
        scrub_result = scrub_check(payload, extra_forbidden=extra_forbidden)
    except Exception as exc:  # noqa: BLE001 - any scrub-check failure fails closed
        scrub_result = {
            "scrub_checked": False,
            "findings": ["scrub_check_raised", type(exc).__name__],
            "clean": False,
        }
    payload["scrub"] = scrub_result

    if scrub_result.get("clean"):
        out_path.write_text(dumps_ascii(payload) + "\n", encoding="utf-8")
        echo_ascii(payload)
        sys.stderr.write(f"[ar1] record written: {out_path}\n")
        return 0

    findings = list(scrub_result.get("findings") or [])
    refusal = refusal_record(
        phase=phase, finding_count=len(findings), finding_categories=findings
    )
    try:
        refusal_scrub = scrub_check(refusal)
    except Exception:  # noqa: BLE001 - doubt about the refusal record fails closed too
        refusal_scrub = {"clean": False}

    if not refusal_scrub.get("clean"):
        sys.stderr.write(
            "[ar1] REFUSED: the candidate artifact failed its scrub check, and "
            "the refusal record itself could not be confirmed safe to persist. "
            "Nothing was written.\n"
        )
        return 3

    out_path.write_text(dumps_ascii(refusal) + "\n", encoding="utf-8")
    echo_ascii(refusal)
    sys.stderr.write(
        "[ar1] REFUSED: the candidate artifact failed its scrub check; a safe "
        f"refusal record was written instead: {out_path}\n"
    )
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run_ar1.py",
        description="Phase 5F3A-AR1 Pi external runtime synthetic PoC (EXPERIMENT ONLY).",
    )
    parser.add_argument(
        "--phase", choices=("preflight", "probe-env", "live"), default="preflight"
    )
    parser.add_argument("--config", default=str(_HERE / CONFIG_FILENAME))
    parser.add_argument(
        "--run-pi-external-runtime-experiment",
        action="store_true",
        help="Explicit flag 1 of 2. Required for --phase live.",
    )
    parser.add_argument(
        "--send-one-real-model-prompt",
        action="store_true",
        help="Explicit flag 2 of 2. Required for --phase live. Authorizes EXACTLY ONE prompt.",
    )
    parser.add_argument(
        "--profile-env-names",
        default="",
        help="Comma-separated subset of USERPROFILE,HOME,APPDATA to include (default: none).",
    )
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
            report = phase_preflight(config, with_canary=False)
            fixture = report.pop("_internal")["fixture"]
            if not args.keep_fixture:
                remove_disposable_tree(fixture.experiment_root)
            payload = report
        elif args.phase == "probe-env":
            payload = phase_probe_env(config)
        else:
            if not (
                args.run_pi_external_runtime_experiment
                and args.send_one_real_model_prompt
            ):
                raise GateRefusal(
                    "refused: --phase live requires BOTH "
                    "--run-pi-external-runtime-experiment and "
                    "--send-one-real-model-prompt"
                )
            profile_names = tuple(
                n.strip() for n in args.profile_env_names.split(",") if n.strip()
            )
            run = phase_live(config, profile_names=profile_names)
            base_url = os.environ.get(config["base_url_env_name"], "").strip()
            fixture = run.get("_internal", {}).get("fixture")
            payload = _finalize(run, base_url=base_url or None)
            if base_url:
                extra_forbidden = (("configured_endpoint_value_present", base_url),)
            observed = payload["run"].get("orchestrator_observed", {})
            classification = observed.get("classification", {})
            stdout_state = payload["run"].get("stdout_state", {})
            no_anomaly = (
                bool(classification.get("trusted"))
                and payload["run"].get("turn_outcome") == RUNTIME_SETTLED
                and not stdout_state.get("protocol_violation")
                and not stdout_state.get("byte_cap_exceeded")
                and not stdout_state.get("event_cap_exceeded")
                and payload["run"].get("termination", {}).get("rung_reached")
                == "exited_after_stdin_close"
            )
            if fixture is not None and not args.keep_fixture and no_anomaly:
                remove_disposable_tree(fixture.experiment_root)
                payload["run"]["fixture_preserved"] = False
            elif fixture is not None:
                payload["run"]["fixture_preserved"] = True
                payload["run"]["fixture_preserved_reason"] = (
                    "an untrusted classification, a protocol/bound/termination "
                    "anomaly, or --keep-fixture: evidence is preserved rather "
                    "than destroyed"
                )
    except (GateRefusal, LaunchIdentityError, GitExecutableError, PiSupervisorError) as exc:
        echo_ascii(
            {
                "experiment": EXPERIMENT_ID,
                "refused": True,
                "phase": args.phase,
                "prompt_sent": False,
                "reason": f"{type(exc).__name__}: {exc}",
            }
        )
        return 1

    out_path = RESULTS_DIR / f"ar1_{args.phase}_{stamp}.json"
    return emit_or_refuse(
        payload, phase=args.phase, out_path=out_path, extra_forbidden=extra_forbidden
    )


if __name__ == "__main__":
    raise SystemExit(main())
