"""Phase 5F3B-I2B-L1 harness entry point. **LIVE.** Not a CLI command.

**THIS SCRIPT PERFORMS REAL ACTIVITY**: it reads a real B300 credential (via
the frozen ``AIDO_LITELLM_BASE_URL``/``AIDO_LITELLM_API_KEY`` environment
variables), creates a real broker (a real Windows named pipe and a real
daemon thread), launches a real Node/Pi process, and performs a real,
**credential-bearing**, non-inference ``GET /models`` HTTP request
(5F3B-I2B-L1-LF2: that request now carries this run's own
``Authorization: Bearer`` header, so a 401/403 is attributable as an auth
fact instead of collapsing into "the model is absent"). It sends **zero semantic
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
    build_authenticated_route_checker,
    preflight_artifact_safety_scrub_self_check,
    preflight_candidate_route_generator_symmetry,
    preflight_child_environment_builder_self_check,
    preflight_config_generator_no_credential_literal_path,
    preflight_config_generator_self_check,
    preflight_environment_forbidden_fragment_audit,
    preflight_pi_installed_offline,
    preflight_planned_cli_argv_shape,
    resolve_pi_identity,
)
from qualification.i2b_workspace import (  # noqa: E402
    mint_qualification_run_workspace,
    remove_run_workspace,
)
from qualification.records import CANDIDATE_MODEL_IDS  # noqa: E402

RESULTS_DIR = _HERE / "results"


class GateRefusal(Exception):
    """A precondition failed before any live activity was attempted."""


#: The one pre-controller stage this harness can fail in AFTER a
#: qualification run workspace has been minted (L1-FU4 BLOCKER 2). Kept as a
#: named constant rather than an inline string so the refusal record and its
#: test both name the same fact.
STAGE_ADAPTER_CONSTRUCTION = "adapter_construction"

#: The two post-controller-entry stages this harness can unexpectedly fail
#: in (L1-FU5 nearby gap): inside the frozen ``run_category_b_controller``
#: call itself, or while reducing its result to the bounded summary. Kept as
#: named constants for the same reason as ``STAGE_ADAPTER_CONSTRUCTION``.
STAGE_CONTROLLER_EXECUTION = "controller_execution"
STAGE_RESULT_PROCESSING = "result_processing"


class PreControllerRefusal(Exception):
    """The attempt failed BEFORE ``run_category_b_controller`` was entered,
    but AFTER a qualification run workspace existed (L1-FU4 BLOCKER 2).

    This is the smallest bounded harness-level representation of that state.
    It deliberately does **not** fabricate a
    :class:`~qualification.i2b_controller.CategoryBControllerResult`: the
    frozen controller never ran, so no gate status, compatibility fact,
    teardown status or terminal verdict of its own exists to report, and
    inventing one would be a lie about which authority produced it. Nothing
    frozen is reopened to carry this.

    It records exactly four things, all bounded and secret-free: the stage
    that failed, the failing exception's CLASS NAME (never its message, and
    never a path, endpoint, token or credential), what this harness's own
    outer cleanup attempted, and that zero semantic prompts were sent.

    ``outer_cleanup`` is populated by the workspace ownership scope's
    ``finally`` before this propagates, so a caller always sees the cleanup
    truth alongside the primary failure -- and the cleanup outcome never
    replaces or erases that primary failure.
    """

    def __init__(self, *, stage: str, failure_type: str) -> None:
        super().__init__(
            "refused before the Category-B controller was entered: " + stage
        )
        self.stage = stage
        self.failure_type = failure_type
        self.outer_cleanup: dict[str, Any] | None = None

    def as_refusal_record(self) -> dict[str, Any]:
        """The bounded, no-secret record ``main()`` prints."""
        return {
            "refused": True,
            "reason": self.failure_type,
            "stage": self.stage,
            "semantic_prompts_sent": 0,
            "controller_entered": False,
            "outer_cleanup": self.outer_cleanup,
            "note": (
                "A bounded pre-controller failure occurred after the "
                "qualification run workspace was minted. The frozen "
                "Category-B controller was never entered, so no controller "
                "result exists and none is fabricated. The workspace's own "
                "outer cleanup ran regardless; its truthful outcome is "
                "reported above and does not erase the primary failure."
            ),
        }


class PostControllerExceptionalFailure(Exception):
    """An unexpected exception raised AFTER the frozen Category-B
    controller was ENTERED (L1-FU5 nearby gap) -- either from
    ``run_category_b_controller`` itself (``STAGE_CONTROLLER_EXECUTION``)
    or while reducing its result to the bounded summary
    (``STAGE_RESULT_PROCESSING``).

    This is deliberately the smallest bounded harness-level representation
    of that state, sibling to :class:`PreControllerRefusal` rather than a
    replacement for it. It does **not** fabricate a
    :class:`~qualification.i2b_controller.CategoryBControllerResult`: either
    the controller never finished producing one, or this harness does not
    trust the summarizer's own partial output enough to report any of it.
    Nothing frozen is reopened to carry this.

    It records exactly four things, all bounded and secret-free: the stage
    that failed, the failing exception's CLASS NAME (never its message, and
    never a path, endpoint, token or credential), that the controller WAS
    entered, and that zero semantic prompts were sent -- a fixed mechanical
    invariant of this zero-prompt Category-B harness (see the module
    docstring), not an observation of the controller's own internal
    counter, which this harness does not trust after an unexpected
    exception.

    ``outer_cleanup`` is populated by the workspace ownership scope's
    ``finally`` before this propagates -- exactly like
    ``PreControllerRefusal`` -- so cleanup truth is never silently lost
    behind this exception either.
    """

    def __init__(self, *, stage: str, failure_type: str) -> None:
        super().__init__(
            "unexpected failure after the Category-B controller was entered: " + stage
        )
        self.stage = stage
        self.failure_type = failure_type
        self.outer_cleanup: dict[str, Any] | None = None

    def as_refusal_record(self) -> dict[str, Any]:
        """The bounded, no-secret record ``main()`` prints."""
        return {
            "refused": True,
            "reason": self.failure_type,
            "stage": self.stage,
            "semantic_prompts_sent": 0,
            "controller_entered": True,
            "outer_cleanup": self.outer_cleanup,
            "note": (
                "An unexpected exception occurred after the frozen "
                "Category-B controller was entered -- either during the "
                "controller call itself or while reducing its result to "
                "this harness's bounded summary. No "
                "CategoryBControllerResult is fabricated. Zero semantic "
                "prompts is reported as a fixed mechanical invariant of "
                "this zero-prompt harness, not as an observation of the "
                "controller's own internal state after this exception. "
                "The workspace's own outer cleanup ran regardless; its "
                "truthful outcome is reported above and does not erase "
                "the primary failure."
            ),
        }


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


def _workspace_removal_succeeded(result: Any) -> bool:
    """Strict, fail-CLOSED validation of the frozen
    ``ar2.fixtures.remove_disposable_tree`` return shape (L1-FU5 PRIMARY
    BLOCKER), as returned unmodified by ``remove_run_workspace``.

    A normal return from ``remove_run_workspace`` does NOT mean removal
    succeeded: the frozen contract can return, without raising,
    ``{"removed": False, "residual_file_count": N, "verified": True}`` --
    ``verified=True`` there means only that the postcondition was inspected
    truthfully, never that removal happened. Consuming that dict's
    truthiness, or treating "no exception" as success, would let a
    disposable workspace survive on disk while this harness reports
    ``workspace_removal_verified=True``.

    The ONLY shape accepted as success is the frozen success shape exactly:

        {"removed": True, "residual_file_count": 0, "verified": True}

    Every other shape fails CLOSED to ``False``: a non-dict result, a
    missing key, ``removed`` or ``verified`` not exactly the ``True``
    singleton (a truthy non-bool like the string ``"true"`` is rejected),
    or ``residual_file_count`` not exactly the ``int`` ``0`` (``bool`` is
    deliberately excluded even though it is an ``int`` subclass, since
    ``type(x) is int`` is ``False`` for a ``bool``). No ``bool(result)``,
    no ``.get(...)`` default substitution, and no reliance on absence of a
    field to mean success.
    """
    if type(result) is not dict:
        return False
    if not {"removed", "residual_file_count", "verified"} <= result.keys():
        return False
    if result["removed"] is not True:
        return False
    if result["verified"] is not True:
        return False
    residual = result["residual_file_count"]
    if type(residual) is not int or residual != 0:
        return False
    return True


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
        removal_result = remove_run_workspace(run_workspace)
    except Exception:  # noqa: BLE001 - reported truthfully, never silently swallowed
        workspace_removal_verified = False
    else:
        # L1-FU5 PRIMARY BLOCKER: a normal return does NOT mean removal
        # succeeded -- only the frozen success shape does. See
        # ``_workspace_removal_succeeded``'s own docstring for why.
        workspace_removal_verified = _workspace_removal_succeeded(removal_result)

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
    and only after every Category-A gate has passed.

    **It is ISSUED, not constructed (L1-FU3 BLOCKER 2).**
    ``resolve_pi_identity()`` -- the trusted operation that runs the one
    provenance-only ``node cli.js --version`` probe -- is also the only
    thing that mints the
    :class:`~qualification.i2b_live_adapters.IssuedRuntimeIdentity` this
    function then uses. That opaque object carries no identity data of its
    own, so nothing here (and no caller of this module) can author the
    ``reported_version`` that later appears as evidence; the version stays
    provenance only and is never compared to anything. The SAME issued
    object supplies ``node_executable`` (the frozen controller's own
    child-environment PATH narrowing, read back from the issuance registry)
    and is handed to :class:`LiveCategoryBAdapters` at construction, which
    claims it ONE-SHOT and whose own ``launch_runtime`` consumes the
    claimed identity directly rather than re-resolving a second,
    independent probe at the actual launch moment. One Category-B attempt
    therefore performs exactly one ``pi --version`` probe, never two, and
    that one probe authorizes exactly one adapter instance.

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

    # -- L1-FU4 BLOCKER 2: the WORKSPACE OWNERSHIP SCOPE -------------------
    #
    # Outer cleanup ownership becomes active the instant a workspace is
    # minted. It used to start one statement too late: the
    # ``LiveCategoryBAdapters`` construction sat OUTSIDE the ``try``, so any
    # of its supported fail-closed refusals -- trusted runtime-identity
    # validation, the frozen extension source/digest check, an unclaimable
    # or already-claimed issuance, or any other bounded LiveAdapterError --
    # stranded the minted qualification workspace on disk with no cleanup
    # attempted at all.
    #
    # Everything that can fail after the mint now lives inside this scope:
    # adapter construction, the controller invocation, and the result
    # processing. ``_run_outer_cleanup`` runs exactly once on every path.
    refusal: PreControllerRefusal | None = None
    post_controller_failure: PostControllerExceptionalFailure | None = None
    run_workspace = mint_qualification_run_workspace()
    try:
        try:
            adapters = LiveCategoryBAdapters(
                environ_reader=os.environ.get,
                runtime_identity=identity,
            )
        except Exception as exc:  # noqa: BLE001 - reduced to a bounded, no-secret record
            # Only the exception CLASS NAME is retained. ``from None``
            # deliberately drops the original traceback chain so no
            # exception message, path, endpoint or token can reach stderr
            # through an unhandled propagation.
            refusal = PreControllerRefusal(
                stage=STAGE_ADAPTER_CONSTRUCTION, failure_type=type(exc).__name__
            )
            raise refusal from None

        # 5F3B-I2B-L1-LF2. The live route checker is no longer the
        # unauthenticated, frozen ``ar2.route_check.check_route_serves_model``
        # -- it is an observer bound to THIS attempt's candidate and to the
        # very ``ConnectionValues`` the frozen controller is about to consume
        # through ``adapters.read_connection``. There is no base URL, API key,
        # provider id or model id expressible here, and the same ``candidate``
        # local drives both this binding and the controller call below.
        route_observer = build_authenticated_route_checker(
            candidate=candidate, adapters=adapters
        )

        # L1-FU5 nearby gap: the controller call and the result-summary
        # reduction are each individually guarded now. Before this fix, an
        # exception from either one propagated bare through the ``finally``
        # below -- the cleanup truth was still computed there, but it was
        # then discarded as an unused local while the raw exception (and
        # its message/traceback) propagated, silently losing the cleanup
        # fact. Each guard here reduces its exception to a bounded,
        # no-secret ``PostControllerExceptionalFailure`` the same way the
        # adapter-construction guard above already does for
        # ``PreControllerRefusal``.
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
                route_checker=route_observer,
                shutdown_runtime=adapters.shutdown_runtime,
                shutdown_broker=adapters.shutdown_broker,
                git_executable=git_executable,
            )
        except Exception as exc:  # noqa: BLE001 - reduced to a bounded, no-secret record
            post_controller_failure = PostControllerExceptionalFailure(
                stage=STAGE_CONTROLLER_EXECUTION, failure_type=type(exc).__name__
            )
            raise post_controller_failure from None

        try:
            summary = _safe_result_summary(result)
            # 5F3B-I2B-L1-LF1 OBJECTIVE 6. The bounded live launch
            # diagnostic, recorded ALONGSIDE the frozen controller's result
            # and never inside it: the frozen ``CategoryBEvidence`` schema is
            # not touched and frozen I2B is not reopened. Every value is one
            # of ``i2b_live_adapters.LAUNCH_DIAGNOSTIC_CODES`` -- a declared
            # literal that raw runtime content was reduced to at the moment
            # of observation. It exists so a FUTURE zero-prompt refusal can
            # be attributed without reading raw logs after the fact.
            #
            # 5F3B-I2B-L1-LF1-FU1 corrected this note, which previously said
            # an unknown-flag rejection "reads ``launch_correlation:
            # no_response_runtime_exited_early``". It does not: that
            # correlation code says only that the direct child exited before
            # the awaited response arrived, and an unknown-option startup
            # rejection is ONE source-supported cause of that, never a proof
            # of it. The field that answers the flag question is
            # ``required_launch_flags``, which carries the three declared
            # states -- ``required_flags_accepted``,
            # ``required_flags_rejected_unknown_option`` (mechanically
            # established from a bounded startup diagnostic, and the only
            # thing that can produce REQUIRED_LAUNCH_FLAGS_REJECTED) and
            # ``required_flags_indeterminate``. A launch-window protocol
            # violation is a separate field again
            # (``launch_window_protocol``), and it never alters the flag
            # state.
            summary["launch_diagnostics"] = adapters.launch_diagnostics()
            # 5F3B-I2B-L1-LF2 OBJECTIVE 5. The bounded route diagnostic,
            # recorded ALONGSIDE the frozen controller's result exactly as
            # LF1's launch diagnostic already is, and for the same reason:
            # the frozen ``CategoryBEvidence`` schema is not touched and
            # frozen I2B is not reopened. Every value is one of
            # ``i2_b300_route_observation.ROUTE_DIAGNOSTIC_CODES``.
            #
            # It exists because Candidate-A's second live attempt produced
            # ``route_check: FAILED:ROUTE_CHECK_FAILED`` with
            # ``exact_candidate_model_served: false`` and NOTHING that could
            # separate an auth rejection, a transport failure, a malformed
            # listing and a genuinely absent model. The controller's verdict
            # is unchanged and remains authoritative; this record only says
            # which of those the observation actually was.
            summary["route_diagnostics"] = route_observer.route_diagnostics()
        except Exception as exc:  # noqa: BLE001 - reduced to a bounded, no-secret record
            post_controller_failure = PostControllerExceptionalFailure(
                stage=STAGE_RESULT_PROCESSING, failure_type=type(exc).__name__
            )
            raise post_controller_failure from None
    finally:
        # L1 BLOCKER 7: independent, fail-closed, never-erasing outer
        # cleanup -- owned by THIS script, not by the frozen
        # CategoryBControllerResult, which never sees this disposable
        # extension resource. Reported ALONGSIDE the controller's own
        # result below, never silently swallowed and never allowed to
        # erase it. Exactly ONE call, on every path through this scope.
        outer_cleanup = _run_outer_cleanup(run_workspace)
        if refusal is not None:
            # Attach the cleanup truth to the primary failure before it
            # propagates. The cleanup outcome never becomes the failure and
            # never masks it.
            refusal.outer_cleanup = outer_cleanup
        if post_controller_failure is not None:
            post_controller_failure.outer_cleanup = outer_cleanup

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
    except PreControllerRefusal as refusal:
        # L1-FU4 BLOCKER 2: a bounded pre-controller failure that happened
        # AFTER a workspace was minted. Its own record carries the outer
        # cleanup truth; no controller result is fabricated.
        json.dump(refusal.as_refusal_record(), sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 1
    except PostControllerExceptionalFailure as failure:
        # L1-FU5 nearby gap: a bounded, unexpected failure that happened
        # AFTER the frozen Category-B controller was entered. Its own
        # record carries the outer cleanup truth; no controller result is
        # fabricated, and this can never be an accepted live PASS.
        json.dump(failure.as_refusal_record(), sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 1
    except (GateRefusal, LaunchIdentityError, InfrastructureRefusal) as exc:
        json.dump(
            {
                "refused": True,
                "reason": f"{type(exc).__name__}",
                "semantic_prompts_sent": 0,
                "controller_entered": False,
                # L1-FU4 nearby fix. The previous wording claimed "nothing
                # was launched (or the failure happened before any process
                # existed)". That is FALSE for a LaunchIdentityError raised
                # by the provenance-only ``--version`` probe, which can be
                # raised precisely BECAUSE a real Node/Pi process launched,
                # ran to completion and exited non-zero (or reported an
                # empty version). This harness never observed that no
                # process existed, so it no longer claims it.
                "note": (
                    "An infrastructure gate or identity resolution failed "
                    "before the frozen Category-B controller was entered. "
                    "Zero semantic prompts were sent and the Category-B "
                    "broker/runtime/model compatibility run was not "
                    "entered. This refusal makes NO claim about whether the "
                    "provenance-only Pi --version subprocess was attempted: "
                    "it MAY have been attempted, and if it was it may have "
                    "run to completion and exited non-zero."
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
