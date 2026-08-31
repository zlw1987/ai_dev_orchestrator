"""Phase 5F3B-I2B-L1 harness entry point. **LIVE.** Not a CLI command.

**THIS SCRIPT PERFORMS REAL ACTIVITY**: it reads a real B300 credential (via
the frozen ``AIDO_LITELLM_BASE_URL``/``AIDO_LITELLM_API_KEY`` environment
variables), creates a real broker (a real Windows named pipe and a real
daemon thread), launches a real Node/Pi process, and performs a real,
non-inference ``GET /models`` HTTP request. It sends **zero semantic
prompts** -- there is no code path here, in
``qualification.i2b_live_adapters``, or in the frozen
``qualification.i2b_controller``/``qualification.i2b_session`` it drives,
that can send one.

This is **not** Q1/Q2. It authorizes exactly ONE thing: running the frozen,
already-accepted ``run_category_b_controller`` state machine to completion
against real infrastructure, using the live adapters in
``qualification.i2b_live_adapters``. The frozen controller remains the only
authority over gate ordering, first failure, compatibility facts, resource/
session correlation, creator partial-failure accounting, teardown/shutdown
status, cleanup status, evidence safety, and the terminal PASS/REFUSAL
decision -- this script sequences nothing itself beyond assembling the
adapters and calling that one function once.

**One command, one candidate, ONE Category-B attempt.** There is no
relaunch, no retry, no fallback candidate, no fallback model, and no
automatic continuation to a second candidate on either outcome -- see
``main()``'s own explicit gate flag and its docstring.

Operator prerequisite, stated exactly because this script does not attest
it: the qualification offline suite (``tests/``, including
``tests/test_i2b_live_adapters.py``) must be green before this script is
ever run with ``--run-category-b-live-gate``. This script does not execute
or attest pytest.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
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
from ar2.launch import LaunchIdentityError  # noqa: E402
from ar2.pi_config import scrub_generated_extension_config  # noqa: E402

from qualification.i2_credentials import InfrastructureRefusal  # noqa: E402
from qualification.i2b_controller import (  # noqa: E402
    CategoryBOutcome,
    run_category_b_controller,
)
from qualification.i2b_live_adapters import (  # noqa: E402
    LiveCategoryBAdapters,
    preflight_artifact_safety_scrub_self_check,
    preflight_candidate_route_generator_symmetry,
    preflight_child_environment_builder_self_check,
    preflight_config_generator_no_credential_literal_path,
    preflight_config_generator_self_check,
    preflight_environment_forbidden_fragment_audit,
    preflight_pi_installed_offline,
    preflight_planned_cli_argv_shape,
    resolve_pi_identity,
    route_checker,
)
from qualification.i2b_workspace import (  # noqa: E402
    mint_qualification_run_workspace,
    remove_run_workspace,
)
from qualification.records import CANDIDATE_MODEL_IDS  # noqa: E402

RESULTS_DIR = _HERE / "results"


class GateRefusal(Exception):
    """A precondition failed before any live activity was attempted."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _independent_pre_live_safety_check(*, candidate: str) -> None:
    """FIRST-LIVE SAFETY (L1 brief): confirmed BEFORE any credential read.

    - the candidate/model route is exact (refuses an unknown candidate here,
      before the frozen ``ROUTE_DESCRIPTOR`` gate would);
    - no real workspace is nameable (structurally true: there is no
      parameter anywhere in this script, in
      ``qualification.i2b_live_adapters``, or in the frozen
      ``run_category_b_controller``/``mint_qualification_run_workspace``
      through which an existing path could be named -- confirmed by
      inspection, not merely asserted, at review time);
    - no semantic-prompt code is reachable (confirmed by
      ``tests/test_i2b_live_adapters.py``'s own source-level proofs, which
      this script does not re-run -- see the module docstring's operator
      prerequisite).
    """
    if candidate not in CANDIDATE_MODEL_IDS:
        raise GateRefusal(
            f"refused: unknown candidate {candidate!r}; declared: "
            f"{sorted(CANDIDATE_MODEL_IDS)}"
        )


def _run_outer_cleanup(run_workspace: Any) -> dict[str, Any]:
    """L1 BLOCKER 7: the outer, live-harness-owned extension/workspace
    cleanup -- NOT owned by the frozen ``CategoryBControllerResult``, which
    never sees this disposable extension resource at all.

    Both actions are attempted INDEPENDENTLY: an extension-scrub failure
    can never skip workspace removal, and a workspace-removal failure is
    never silently swallowed. Neither failure erases a result already
    obtained from the frozen controller -- this function only reports what
    ITS OWN two cleanup actions did. No raw absolute path, token, pipe
    name, or exception text is ever retained in the returned dict.
    """
    extension_dir = str(Path(run_workspace.experiment_root) / "pi_extension")

    extension_scrub_attempted = os.path.isdir(extension_dir)
    extension_scrub_verified: bool | None = True
    if extension_scrub_attempted:
        try:
            scrub_generated_extension_config(extension_dir)
            extension_scrub_verified = True
        except Exception:  # noqa: BLE001 - never let this skip workspace removal below
            extension_scrub_verified = False

    workspace_removal_attempted = True
    try:
        remove_run_workspace(run_workspace)
        workspace_removal_verified = True
    except Exception:  # noqa: BLE001 - reported truthfully, never silently swallowed
        workspace_removal_verified = False

    return {
        "extension_scrub_attempted": extension_scrub_attempted,
        "extension_scrub_verified": extension_scrub_verified,
        "workspace_removal_attempted": workspace_removal_attempted,
        "workspace_removal_verified": workspace_removal_verified,
        "outer_cleanup_verified": bool(extension_scrub_verified)
        and bool(workspace_removal_verified),
    }


def _safe_result_summary(result: Any) -> dict[str, Any]:
    """Every field here is already a bounded, non-secret typed field on the
    frozen ``CategoryBControllerResult`` -- there is no second scrub layer
    here because there is nothing here that could carry a raw secret; the
    ONE place a secret-shaped payload could ever appear
    (``result.evidence``) is already the frozen, scrub-checked evidence
    object, printed through its own ``as_dict()``/``retention_ready``.
    """
    return {
        "candidate": result.candidate,
        "outcome": result.outcome.value,
        "semantic_prompts_sent": result.semantic_prompts_sent,
        "failed_gate": result.failed_gate.value if result.failed_gate else None,
        "failure_code": result.failure_code.value if result.failure_code else None,
        "gate_statuses": dict(result.gate_statuses),
        "compatibility_facts": result.facts.as_dict(),
        "observed_pi_version": result.observed_pi_version,
        "pi_config_created": result.pi_config_created,
        "broker_created": result.broker_created,
        "runtime_session_established": result.runtime_session_established,
        "runtime_teardown_status": result.runtime_teardown.status_text,
        "broker_shutdown_status": result.broker_shutdown.status_text,
        "cleanup_status": result.cleanup.status_text,
        "evidence_retention_ready": result.evidence.retention_ready,
        "evidence": result.evidence.as_dict() if result.evidence.retention_ready else None,
        "evidence_scrub_findings": list(result.evidence.scrub_findings),
    }


def _require_all_category_a_gates_pass(non_secret_gates: tuple) -> None:
    """L1-FU2: establish every Category-A (I2A §14) fact BEFORE the one
    real Node/Pi subprocess this attempt ever launches
    (:func:`~qualification.i2b_live_adapters.resolve_pi_identity`'s
    ``--version`` probe).

    Mirrors ``i2_credentials.resolve_connection_after_preflight``'s own
    gate-loop semantics exactly (order-preserving, first failure raises)
    but never touches a credential -- credential reading stays exclusively
    the frozen controller's own, unchanged ``read_connection`` step, which
    still runs its OWN pass over these same gates before it reads
    ``AIDO_LITELLM_*`` (the frozen controller remains the sole authority
    over that internal ordering; this is a redundant, harmless,
    side-effect-light pre-check that exists only to gate the version probe
    below it).
    """
    for gate in non_secret_gates:
        result = gate()
        if not result.passed:
            raise InfrastructureRefusal(result.name, result.failure_code)


def run_one_category_b_live_attempt(*, candidate: str) -> dict[str, Any]:
    """Exactly ONE ``run_category_b_controller`` call, against real
    infrastructure, using :mod:`qualification.i2b_live_adapters`.

    **Category-A before Category-B (L1-FU2).** Every one of the frozen I2A
    §14 offline, file/string-level, no-process, no-credential gates is
    established FIRST -- before ``resolve_pi_identity()``, the one real
    Node/Pi ``--version`` subprocess this attempt ever launches.

    **Node/Pi identity is resolved EXACTLY ONCE for this whole attempt**
    (L1 BLOCKER, "SINGLE RUNTIME IDENTITY BINDING"), HERE, pre-credential,
    and only after every Category-A gate has passed. The SAME
    :class:`~ar2.launch.RuntimeIdentity` object is used both for
    ``node_executable`` (the frozen controller's own child-environment PATH
    narrowing) and is handed to :class:`LiveCategoryBAdapters` at
    construction, which its own ``launch_runtime`` consumes directly rather
    than re-resolving a second, independent probe at the actual launch
    moment. One Category-B attempt therefore performs exactly one ``pi
    --version`` probe, never two.

    **The non-secret preflight gates are REAL and there are SEVEN of them**
    (L1-FU2 BLOCKER 3, I2A §14) plus one additional, non-frozen policy-
    coherence gate this package already carried -- every one a genuine,
    deterministic, credential-free fact, each actually checked before the
    credential boundary -- never a vacuous ``()`` and never a hardcoded
    ``passed=True``.
    """
    _independent_pre_live_safety_check(candidate=candidate)

    non_secret_gates = (
        preflight_pi_installed_offline,
        preflight_config_generator_self_check,
        preflight_child_environment_builder_self_check,
        preflight_candidate_route_generator_symmetry,
        preflight_planned_cli_argv_shape,
        preflight_artifact_safety_scrub_self_check,
        preflight_config_generator_no_credential_literal_path,
        lambda: preflight_environment_forbidden_fragment_audit(ambient_environ=os.environ),
    )
    _require_all_category_a_gates_pass(non_secret_gates)

    identity = resolve_pi_identity()  # THE ONE version probe, AFTER every Category-A gate
    git_executable: str | None
    try:
        git_executable = resolve_git_executable(workspace_root=str(_HERE))
    except GitExecutableError:
        git_executable = None

    run_workspace = mint_qualification_run_workspace()
    adapters = LiveCategoryBAdapters(
        environ_reader=os.environ.get,
        runtime_identity=identity,
    )

    try:
        result = run_category_b_controller(
            candidate=candidate,
            run_workspace=run_workspace,
            ambient_environ=os.environ,
            node_executable=identity.node_executable,
            non_secret_gates=non_secret_gates,
            read_connection=adapters.read_connection,
            create_broker=adapters.create_broker,
            launch_runtime=adapters.launch_runtime,
            get_commands=adapters.get_commands,
            get_state=adapters.get_state,
            observe_protocol=adapters.observe_protocol,
            route_checker=route_checker,
            shutdown_runtime=adapters.shutdown_runtime,
            shutdown_broker=adapters.shutdown_broker,
            git_executable=git_executable,
        )
    finally:
        # L1 BLOCKER 7: independent, fail-closed, never-erasing outer
        # cleanup -- owned by THIS script, not by the frozen
        # CategoryBControllerResult, which never sees this disposable
        # extension resource. Reported ALONGSIDE the controller's own
        # result below, never silently swallowed and never allowed to
        # erase it.
        outer_cleanup = _run_outer_cleanup(run_workspace)

    summary = _safe_result_summary(result)
    summary["outer_cleanup"] = outer_cleanup
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run_i2b_live.py",
        description=(
            "Phase 5F3B-I2B-L1: run the frozen Category-B zero-prompt "
            "compatibility gate against REAL infrastructure. NOT Q1/Q2. "
            "Sends ZERO semantic prompts."
        ),
    )
    parser.add_argument("--candidate", choices=tuple(sorted(CANDIDATE_MODEL_IDS)), default="A")
    parser.add_argument(
        "--run-category-b-live-gate",
        action="store_true",
        help=(
            "Required explicit flag. Authorizes exactly ONE live "
            "Category-B compatibility-gate attempt for --candidate. Does "
            "NOT authorize a prompt, a second candidate, or a retry."
        ),
    )
    args = parser.parse_args(argv)

    if not args.run_category_b_live_gate:
        json.dump(
            {
                "refused": True,
                "reason": "refused: --run-category-b-live-gate was not passed",
                "semantic_prompts_sent": 0,
            },
            sys.stdout,
            indent=2,
        )
        sys.stdout.write("\n")
        return 1

    try:
        summary = run_one_category_b_live_attempt(candidate=args.candidate)
    except (GateRefusal, LaunchIdentityError, InfrastructureRefusal) as exc:
        json.dump(
            {
                "refused": True,
                "reason": f"{type(exc).__name__}",
                "semantic_prompts_sent": 0,
                "note": (
                    "An infrastructure gate failed before or outside the "
                    "frozen controller's own gate sequence, so zero prompts "
                    "were sent and nothing was launched (or the failure "
                    "happened before any process existed)."
                ),
            },
            sys.stdout,
            indent=2,
        )
        sys.stdout.write("\n")
        return 1

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = RESULTS_DIR / f"i2b_live_{args.candidate}_{stamp}.json"
    payload = {"generated_at": _utc_now(), "phase": "5F3B-I2B-L1", "run": summary}
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    sys.stderr.write(f"[i2b-l1] record written: {out_path}\n")

    # L1 BLOCKER 7: a controller CATEGORY_B_GATE_PASSED result is NOT an
    # accepted live PASS if this script's OWN outer extension/workspace
    # cleanup did not verify -- the frozen CategoryBControllerResult never
    # saw that resource, so it cannot vouch for it either way.
    if (
        summary["outcome"] == CategoryBOutcome.CATEGORY_B_GATE_PASSED.value
        and summary["outer_cleanup"]["outer_cleanup_verified"] is True
    ):
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
