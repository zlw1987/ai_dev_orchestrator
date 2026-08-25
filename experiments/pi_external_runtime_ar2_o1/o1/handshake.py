"""Exception-safe launch + zero-prompt handshake, with guaranteed teardown.

5F3A-AR2-O1-FU1. Extracted from what was previously ``run_o1.py``'s local
``_launch_and_handshake`` so this sequence is independently testable. On the
happy path this function does EXACTLY what it did before the extraction:
write the disposable Pi config and extension (AR2's own
``write_disposable_pi_config`` / ``write_disposable_extension``, unmodified),
build AR2's own unmodified ``build_pi_argv`` argv, launch a
``PiRpcSupervisor`` (AR2's own, unmodified), and run H1 (``get_commands``) /
H2 (``get_state``). Neither handshake triggers inference and no prompt is
ever sent here.

FU1 closed an EXCEPTIONAL path that existed before it. Before FU1: if
anything in this sequence raised (a Pi launch failure, a stdin/RPC failure,
or any other compatibility-seam exception), the exception escaped ALL THE
WAY to ``run_o1.py``'s ``main()`` before the broker (already started and
READY by that point in ``phase_case``) had any chance to shut down, and
before the disposable fixture could be cleaned up or explicitly preserved as
evidence.

After FU1: ANY exception raised during this sequence is caught HERE. A
best-effort BOUNDED shutdown of AIDO's own direct child is attempted, using
AR2's own unmodified ``PiRpcSupervisor.shutdown()`` -- never redesigned,
never given a thread-kill, never retried, never given a second attempt. The
original failure, plus whatever was truthfully observed about that shutdown
attempt, is packaged into :class:`CompatibilityHandshakeError` and
re-raised. The caller (``run_o1.py``'s ``phase_case``) catches that ONE
exception type and folds it into the ordinary compatibility-gate-failed
path: broker shutdown and fixture cleanup/preservation then proceed exactly
as they already do for any other compatibility failure, and zero prompts are
ever sent -- the prompt-send statement is lexically unreachable unless a
live, successfully-returned supervisor exists.

FU1A closes two residual gaps FU1 left open:

1. **Both generated resources are tracked independently.** Write order is
   Pi config first, then the extension. If the Pi config write succeeds and
   the LATER extension write then fails, the pre-FU1A exception carried only
   ``extension_dir`` (empty in that exact window), so a caller that scrubbed
   "only if ``extension_dir``" could leave an endpoint-bearing generated
   ``models.json`` unsanitized in preserved evidence. This module now tracks
   ``pi_config_dir`` and ``extension_dir`` as two SEPARATE fields -- neither
   one's presence is inferred from the other -- so a caller can scrub each
   independently, unconditionally, regardless of which one (if either)
   succeeded. Both are INTERNAL-ONLY absolute paths: they are attributes for
   the caller's own cleanup calls, and are never written into ``as_dict()``
   or any other emitted evidence (only their booleans are).
2. **A failing shutdown can no longer mask the original failure.** Before
   FU1A, ``supervisor.shutdown()`` was called unguarded inside the except
   block; had it itself raised, THAT exception -- not the original
   launch/RPC compatibility failure -- would have propagated, and the truth
   of what actually went wrong first would have been lost. The shutdown
   call is now itself wrapped: the ORIGINAL exception is always what
   :class:`CompatibilityHandshakeError` reports as the primary failure;
   whether a shutdown was attempted, and whether IT ALSO raised, are
   recorded as separate, independent facts. A failed shutdown is never
   reported as though the child stopped -- ``termination`` stays ``{}``
   in that case, the same "nothing observed" shape used when no shutdown
   was attempted at all.
"""

from __future__ import annotations

import os
import time
from typing import Any

from ar2.environment import audit_withheld_names, build_launch_environment
from ar2.handshakes import evaluate_extension_identity, evaluate_model_identity
from ar2.launch import build_pi_argv
from ar2.pi_config import (
    TOOL_ALLOWLIST,
    describe_generated_config,
    write_disposable_extension,
    write_disposable_pi_config,
)
from ar2.supervisor import PiRpcSupervisor, PiSupervisorError, RunBounds


_MAX_REASON_LENGTH = 500


class CompatibilityHandshakeError(PiSupervisorError):
    """The zero-prompt Pi launch/handshake sequence failed before any prompt.

    A subclass of AR2's own ``PiSupervisorError`` -- deliberately, so any
    caller that already catches ``PiSupervisorError`` (``run_o1.py``'s
    ``main()`` does, unchanged) keeps catching this too, with no change to
    that except tuple. Carries whatever partial state was gathered so the
    caller can close the lifecycle truthfully instead of guessing:

    - ``original_exception_class`` / ``original_exception_reason`` -- the
      EXACT, ORIGINAL failure that triggered this handler, never collapsed
      into a generic "compatibility failed", and NEVER replaced by a later
      failure encountered while trying to clean up (see ``shutdown_*``
      below);
    - ``shutdown_attempted`` -- whether ``PiRpcSupervisor.shutdown()`` was
      even called (only true when a supervisor had been constructed);
    - ``shutdown_exception_class`` / ``shutdown_exception_reason`` -- set
      ONLY if the shutdown attempt ITSELF raised. When this is set,
      ``termination`` is deliberately ``{}`` -- a failed shutdown is never
      reported as though the child stopped;
    - ``termination`` -- AR2's own ``PiRpcSupervisor.shutdown()`` record,
      obtained ONLY to the extent it was actually and successfully returned
      (``{}`` when no shutdown was attempted, or when the attempt itself
      raised);
    - ``stdout_state`` -- AR2's own ``stdout_state()`` snapshot, IF a real
      process had actually been launched (``None`` otherwise -- calling it
      before a successful launch would itself raise an ``AssertionError``,
      per AR2's own contract, so this is never attempted in that case);
    - ``pi_config_dir`` / ``extension_dir`` -- the generated Pi config and
      extension directories, tracked INDEPENDENTLY of one another (neither
      one's presence is inferred from the other), so a caller can scrub
      each unconditionally. Both are INTERNAL-ONLY absolute paths: they
      exist for the caller's own cleanup calls and are NEVER included in
      ``as_dict()`` or any other emitted evidence -- only their booleans
      are;
    - ``partial_report`` -- whatever keys of the normal success report were
      already populated before the failure.

    Never claims Pi/provider inference stopped, never kills a thread, never
    retries, and never falls back to a different launch or a different
    runtime. ``as_dict()`` exposes only bounded, non-secret fields: exception
    class names and length-capped reason strings, never a raw traceback and
    never a credential.
    """

    def __init__(
        self,
        *,
        original_exception: BaseException,
        termination: dict[str, Any],
        stdout_state: dict[str, Any] | None,
        pi_config_dir: str,
        extension_dir: str,
        partial_report: dict[str, Any],
        shutdown_attempted: bool = False,
        shutdown_exception_class: str | None = None,
        shutdown_exception_reason: str | None = None,
    ) -> None:
        self.original_exception_class = type(original_exception).__name__
        self.original_exception_reason = str(original_exception)[:_MAX_REASON_LENGTH]
        self.termination = termination
        self.stdout_state = stdout_state
        self.pi_config_dir = pi_config_dir
        self.extension_dir = extension_dir
        self.partial_report = partial_report
        self.shutdown_attempted = shutdown_attempted
        self.shutdown_exception_class = shutdown_exception_class
        self.shutdown_exception_reason = (
            shutdown_exception_reason[:_MAX_REASON_LENGTH]
            if shutdown_exception_reason is not None
            else None
        )
        super().__init__(
            "compatibility handshake failed: "
            f"{self.original_exception_class}: {self.original_exception_reason}"
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "original_exception_class": self.original_exception_class,
            "original_exception_reason": self.original_exception_reason,
            "supervisor_shutdown_attempted": self.shutdown_attempted,
            "supervisor_shutdown_itself_raised": self.shutdown_exception_class is not None,
            "supervisor_shutdown_exception_class": self.shutdown_exception_class,
            "supervisor_shutdown_exception_reason": self.shutdown_exception_reason,
            "termination": self.termination,
            "stdout_state_at_failure": self.stdout_state,
            "pi_config_dir_generated": bool(self.pi_config_dir),
            "extension_dir_generated": bool(self.extension_dir),
            "partial_report_keys_populated_before_failure": sorted(self.partial_report),
            "claim_scope": (
                "AIDO attempted a bounded shutdown of its OWN direct child, if "
                "one existed. This is not a claim that Pi/provider inference "
                "stopped, that GPU work stopped, or that any descendant "
                "process was terminated. If the shutdown attempt itself "
                "raised, that is recorded separately and NEVER read as proof "
                "the child stopped. No thread was killed, no retry was "
                "attempted, and no fallback launch or runtime was tried."
            ),
        }


def launch_and_handshake(
    *,
    identity,
    fixture,
    config: dict[str, Any],
    base_url: str,
    profile_names: tuple[str, ...],
    git_executable: str,
    bounds: RunBounds,
    ar2_extension_source_dir: str,
    experiment_id: str,
    pipe_name: str,
    capability_id: str,
    token: str,
) -> tuple[PiRpcSupervisor, dict[str, Any], str]:
    """Generate the disposable config, launch Pi, and run BOTH handshakes.

    No prompt is sent here, and neither handshake triggers inference. On the
    happy path this is exactly AR2's own launch-plus-handshake sequence,
    unmodified. On ANY exception, see :class:`CompatibilityHandshakeError`.
    """
    supervisor: PiRpcSupervisor | None = None
    pi_config_dir: str = ""
    extension_dir: str = ""
    report: dict[str, Any] = {}
    try:
        config_dir, settings_path, models_path = write_disposable_pi_config(
            fixture.experiment_root,
            provider_id=config["provider_id"],
            model_id=config["model_id"],
            base_url=base_url,
        )
        # Tracked the instant it exists, independently of whether the LATER
        # extension write succeeds -- a failure between here and a
        # successful extension write must still leave this path known to
        # the exception handler below, so the endpoint-bearing generated
        # models.json can be scrubbed regardless of what happens next.
        pi_config_dir = config_dir
        extension = write_disposable_extension(
            fixture.experiment_root,
            source_dir=ar2_extension_source_dir,
            experiment_id=experiment_id,
            pipe_name=pipe_name,
            capability_id=capability_id,
            token=token,
        )
        extension_dir = extension.extension_dir
        launch_env = build_launch_environment(
            node_executable=identity.node_executable,
            pi_config_dir=config_dir,
            git_executable=git_executable,
            include_profile_names=profile_names,
        )
        argv = build_pi_argv(
            identity,
            extension_entry=extension.extension_entry,
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
        report = {
            "generated_pi_config": describe_generated_config(
                settings_path=settings_path, models_path=models_path
            ),
            "extension_files_present": list(extension.source_file_names),
            "configured_tool_registry_allowlist": list(TOOL_ALLOWLIST),
            "launch_flags": [a for a in argv[2:] if not os.path.isabs(a)],
            "environment": {
                "explicit_dict": True,
                "os_environ_copied": False,
                "variable_names": list(launch_env.included_names),
                "profile_names_included": list(launch_env.profile_names_included),
                "profile_names_withheld": list(launch_env.profile_names_withheld),
                "path_narrowed": launch_env.path_narrowed,
                "path_entry_count": launch_env.path_entry_count,
                "broker_binding_travelled_in_environment": False,
                "withheld_audit": audit_withheld_names(launch_env.environment),
            },
        }

        supervisor.launch()
        startup_started = time.monotonic()

        supervisor.send_command({"id": "h1", "type": "get_commands"})
        outcome_h1, response_h1 = supervisor.await_response(
            "h1", timeout_seconds=bounds.startup_deadline_seconds
        )
        commands = []
        if response_h1 and isinstance(response_h1.get("data"), dict):
            commands = response_h1["data"].get("commands") or []
        report["handshake_extension"] = {
            "command": "get_commands",
            "wait_outcome": outcome_h1,
            "response_success": bool(response_h1 and response_h1.get("success")),
            **evaluate_extension_identity(
                commands, extension_entry=extension.extension_entry
            ),
            "extension_command_count": sum(
                1 for c in commands if isinstance(c, dict) and c.get("source") == "extension"
            ),
            "non_extension_command_count": sum(
                1 for c in commands if isinstance(c, dict) and c.get("source") != "extension"
            ),
        }

        supervisor.send_command({"id": "h2", "type": "get_state"})
        remaining = bounds.startup_deadline_seconds - (time.monotonic() - startup_started)
        outcome_h2, response_h2 = supervisor.await_response(
            "h2", timeout_seconds=max(remaining, 1.0)
        )
        report["handshake_model"] = {
            "wait_outcome": outcome_h2,
            **evaluate_model_identity(
                response_h2,
                expected_provider=config["provider_id"],
                expected_model=config["model_id"],
            ),
        }
        report["startup_seconds"] = round(time.monotonic() - startup_started, 3)
        return supervisor, report, extension_dir
    except Exception as exc:  # noqa: BLE001 - deliberately broad: ANY seam failure closes the lifecycle
        # The ORIGINAL exception (`exc`) is captured above and is what this
        # handler ultimately reports. Everything below is a best-effort
        # cleanup attempt around it; NOTHING here may replace `exc` as the
        # reported failure, including a shutdown attempt that itself raises.
        termination: dict[str, Any] = {}
        stdout_state: dict[str, Any] | None = None
        shutdown_attempted = False
        shutdown_exception_class: str | None = None
        shutdown_exception_reason: str | None = None
        if supervisor is not None:
            shutdown_attempted = True
            try:
                termination = supervisor.shutdown()
            except Exception as shutdown_exc:  # noqa: BLE001 - never let cleanup mask the original failure
                shutdown_exception_class = type(shutdown_exc).__name__
                shutdown_exception_reason = str(shutdown_exc)
                termination = {}  # a failed shutdown is never reported as "the child stopped"
            if supervisor.process is not None:
                try:
                    stdout_state = supervisor.stdout_state()
                except Exception:  # noqa: BLE001 - a diagnostic fetch must never mask the original failure
                    stdout_state = None
        raise CompatibilityHandshakeError(
            original_exception=exc,
            termination=termination,
            stdout_state=stdout_state,
            pi_config_dir=pi_config_dir,
            extension_dir=extension_dir,
            partial_report=report,
            shutdown_attempted=shutdown_attempted,
            shutdown_exception_class=shutdown_exception_class,
            shutdown_exception_reason=shutdown_exception_reason,
        ) from exc
