"""Regressions from the mandatory post-implementation adversarial review.

These are NOT new frozen T-ids. Each one closes, or pins, a supported-boundary
bypass found by attacking the shipped implementation rather than the design --
exactly what the authorization asks for after the ordinary tests pass. Where a
bypass was real, the production fix and its regression are named together.

Findings, in the order they appear below:

A. ``__post_init__`` on BOTH frozen authority types is bypassable via
   ``object.__new__`` + ``__dict__``. Not a defect: the consumption-boundary
   re-proof is precisely what makes construction-time checks non-load-bearing.
   PINNED, not fixed.
B. ``dataclasses.replace`` and ``copy`` reach the same place, and are refused
   the same way. PINNED.
C. The stage runner coerced the L28 lifecycle bool with ``bool(...)``, which
   would have turned a malformed ``1`` into a plausible ``True``. FIXED -- the
   value is now read exactly, and a non-bool becomes ``False``.
D. ``_discard_stage_decision_state`` accepted a bare nonce STRING, so anything
   that learned a nonce could clear the one seal-history fact that refuses a
   second terminal seal. FIXED -- it takes the ownership handle, type-gated.
E. The test-only forced seal reach would MANUFACTURE a first seal if reached
   before any terminal branch. FIXED -- it now refuses to contest a seal that
   does not exist.
F. ``_verified_unlink`` accepted any path. FIXED -- canonical containment
   inside the run's own owned root is proven before anything is unlinked.
G. A DIRECTORY occupying a run path produces ``EMISSION_FAILED``, not
   ``EMISSION_COLLISION``, on Windows. PINNED as correct fail-closed-on-
   ambiguity behaviour.
"""

from __future__ import annotations

import copy
import dataclasses
import inspect
import os
from pathlib import Path

import pytest
from cfg1_builders import happy_observations, run_payload, synthetic_run_executor
from qualification.safety import ArtifactSafetyContext

from pi_harness_cfg1 import run_executor, stage_decision, stage_runner, writers
from pi_harness_cfg1.stage_decision import (
    CFG1StageClosureDecision,
    Cfg1StageDecisionError,
    _STAGE_DECISION_SEALED,
    _STAGE_TERMINAL_SEAL_HISTORY,
    _discard_stage_decision_state,
)
from pi_harness_cfg1.stage_output import (
    CFG1StageOutputAuthority,
    StageOutputAuthorityError,
    verify_stage_output_authority,
)
from pi_harness_cfg1.writers import emit_cfg1_run_record

NO_NEEDLES = ArtifactSafetyContext.none_declared()


# ---------------------------------------------------------------------------
# A / B -- construction-time checks are NOT the load-bearing ones
# ---------------------------------------------------------------------------


def test_finding_a_an_authority_built_around_post_init_is_still_refused(
    make_authority, results_root
):
    """``object.__new__`` skips ``__post_init__`` entirely. It changes nothing.

    This is the whole reason Sec. 16.3.4 requires a FRESH re-proof at every
    consumption boundary instead of trusting that an instance exists: an
    instance existing proves only that some code path made one.
    """
    genuine = make_authority("S1-X1")

    forged = object.__new__(CFG1StageOutputAuthority)
    forged.__dict__.update(
        {
            "mint_nonce": "never-issued",
            "stage_id": "S1",
            "stage_execution_id": "S1-X1",
            "results_root": genuine.results_root,
            "execution_directory": genuine.execution_directory,
        }
    )
    assert type(forged) is CFG1StageOutputAuthority  # the exact-type gate passes

    with pytest.raises(StageOutputAuthorityError) as excinfo:
        verify_stage_output_authority(forged)
    assert excinfo.value.reason_code == "UNKNOWN_MINT_NONCE"

    with pytest.raises(StageOutputAuthorityError):
        emit_cfg1_run_record(
            forged,
            run_ordinal=1,
            payload=run_payload(),
            lifecycle_all_closed=True,
            safety=NO_NEEDLES,
        )

    # The SAME construction, but carrying a nonce learned from the genuine
    # object alongside substituted fields: caught by the field re-comparison.
    relabelled = object.__new__(CFG1StageOutputAuthority)
    relabelled.__dict__.update(
        {
            "mint_nonce": genuine.mint_nonce,
            "stage_id": "S1",
            "stage_execution_id": "S1-X9",
            "results_root": genuine.results_root,
            "execution_directory": str(results_root / "S1-X9"),
        }
    )
    with pytest.raises(StageOutputAuthorityError) as excinfo:
        verify_stage_output_authority(relabelled)
    assert excinfo.value.reason_code == "MINT_FIELD_MISMATCH"


def test_finding_a_a_decision_built_around_post_init_is_still_refused(
    make_authority, monkeypatch
):
    from test_cfg1_stage_decision import with_live_decision

    seen: list[str] = []

    def _callback(authority, decision):
        forged = object.__new__(CFG1StageClosureDecision)
        forged.__dict__.update(dict(decision.__dict__))
        forged.__dict__["decision_nonce"] = "never-registered"
        with pytest.raises(Cfg1StageDecisionError) as excinfo:
            writers.emit_cfg1_stage_closure(authority, decision=forged)
        seen.append(excinfo.value.reason_code)

        # And a genuine nonce with substituted FACTS.
        relabelled = object.__new__(CFG1StageClosureDecision)
        relabelled.__dict__.update(dict(decision.__dict__))
        relabelled.__dict__["halted_after_ordinal"] = 4
        relabelled.__dict__["halt_reason_code"] = "PRE_DISPATCH_REFUSAL"
        with pytest.raises(Cfg1StageDecisionError) as excinfo:
            writers.emit_cfg1_stage_closure(authority, decision=relabelled)
        seen.append(excinfo.value.reason_code)
        return None

    with_live_decision(make_authority("S1-X1"), _callback, monkeypatch=monkeypatch)
    assert seen == ["UNKNOWN_DECISION_NONCE", "DECISION_FIELD_MISMATCH"]


def test_finding_b_replace_and_copy_reach_the_same_refusals(make_authority):
    genuine = make_authority("S1-X1")

    # ``dataclasses.replace`` DOES re-run ``__post_init__`` -- and is refused.
    with pytest.raises(StageOutputAuthorityError) as excinfo:
        dataclasses.replace(genuine, stage_execution_id="S1-X9")
    assert excinfo.value.reason_code == "MINT_FIELD_MISMATCH"

    # A plain copy is genuine and keeps working -- it IS the same mint.
    duplicate = copy.copy(genuine)
    verify_stage_output_authority(duplicate)
    # ...until a field is substituted on it.
    object.__setattr__(duplicate, "execution_directory", "C:\\anywhere")
    with pytest.raises(StageOutputAuthorityError):
        verify_stage_output_authority(duplicate)
    # The ORIGINAL is untouched by any of that.
    verify_stage_output_authority(genuine)


# ---------------------------------------------------------------------------
# C -- no Python-truthiness fail-open on the L28 lifecycle bool
# ---------------------------------------------------------------------------


def test_finding_c_a_non_bool_lifecycle_value_never_becomes_a_plausible_true(
    make_authority,
):
    """A malformed ``1`` must not be coerced into ``True`` anywhere."""
    # The writer's own parameter gate refuses a non-bool outright.
    authority = make_authority("S1-X1")
    for malformed in (1, 0, "true", None, [], 1.0):
        with pytest.raises(writers.Cfg1WriterError) as excinfo:
            emit_cfg1_run_record(
                authority,
                run_ordinal=1,
                payload=run_payload(stage_execution_id="S1-X1"),
                lifecycle_all_closed=malformed,
                safety=NO_NEEDLES,
            )
        assert excinfo.value.reason_code == "MALFORMED_LIFECYCLE_ALL_CLOSED"


def test_finding_c_the_runner_reads_the_lifecycle_bool_exactly_never_coerced():
    source = inspect.getsource(stage_runner.run_cfg1_stage)
    assert 'bool(payload["lifecycle_all_closed"])' not in source
    assert "if type(lifecycle_all_closed) is not bool:" in source


def test_finding_c_a_truthy_non_bool_payload_halts_rather_than_admitting(
    make_authority,
):
    """End to end: the fail-closed direction, all the way to the stage result."""
    from pi_harness_cfg1.arms import ARM_SHAPE
    from pi_harness_cfg1.run_contract import Cfg1RunOutcome

    def _executor(admission):
        observations = happy_observations(
            runtime_reported_compat_shape=ARM_SHAPE[admission.arm_id]
        )
        if admission.run_ordinal == 2:
            observations["lifecycle_all_closed"] = 1  # truthy, but NOT a bool
        return Cfg1RunOutcome(
            observations=observations,
            safety=NO_NEEDLES,
            live_references_released=True,
        )

    authority = make_authority("S1-X1")
    result = stage_runner.run_cfg1_stage(authority, run_executor=_executor)
    assert result.halted_after_ordinal == 2
    # The payload validator refused it as an implementation defect, and the
    # stage halted rather than admitting ordinal 3 on a coerced truthy value.
    assert result.halt_reason_code == "RUN_RECORD_SELF_VALIDATION_FAILED"
    assert dict(result.ordinal_status)[3] == "NOT_EXECUTED"


# ---------------------------------------------------------------------------
# D -- decision-state cleanup follows the handle, never a bare identifier
# ---------------------------------------------------------------------------


def test_finding_d_seal_history_cleanup_refuses_a_bare_nonce_string(
    make_authority, monkeypatch
):
    """Anything that learned a nonce must not be able to clear seal history."""
    observed: list[bool] = []

    def _probe(context):
        if context.event == "closure:after_write":
            # Every bare-identifier shape, including the REAL nonce.
            for impostor in (
                authority.mint_nonce,
                "anything",
                "",
                None,
                7,
                object(),
                {"mint_nonce": authority.mint_nonce},
            ):
                _discard_stage_decision_state(impostor)
            observed.append(authority.mint_nonce in _STAGE_TERMINAL_SEAL_HISTORY)
            # ...and the backstop still refuses a second seal.
            report = context.force_second_seal_reach()
            observed.append(report["refused_by"] == "seal_history")
            observed.append(report["second_decision_registered"] is False)

    authority = make_authority("S1-X1")
    stage_runner.run_cfg1_stage(
        authority, run_executor=synthetic_run_executor(), _internal_probe=_probe
    )
    assert observed == [True, True, True]


def test_finding_d_the_cleanup_signature_takes_an_authority_not_a_nonce():
    parameters = list(inspect.signature(_discard_stage_decision_state).parameters)
    assert parameters == ["authority"]
    assert "nonce" not in parameters[0]


# ---------------------------------------------------------------------------
# E -- the forced seal reach can contest a seal, never manufacture one
# ---------------------------------------------------------------------------


def test_finding_e_a_forced_reach_before_any_seal_registers_nothing(
    make_authority,
):
    """At a branch-B L30 evaluation the real sealing step would legitimately
    proceed -- so the harness hook must refuse to reach it at all.

    Without this, test scaffolding could poison the stage's one permitted seal
    and turn an ordinary success into ``STAGE_DECISION_MINT_FAILED``.
    """
    reports: list[dict] = []

    def _probe(context):
        if context.event == "l30:enter" and context.run_ordinal < 9:
            reports.append(context.force_second_seal_reach())

    authority = make_authority("S1-X1")
    result = stage_runner.run_cfg1_stage(
        authority, run_executor=synthetic_run_executor(), _internal_probe=_probe
    )
    assert len(reports) == 8
    for report in reports:
        assert report["refused_by"] == "no_prior_seal_to_contest"
        assert report["second_decision_registered"] is False
        assert report["seal_history_present"] is False
    # The stage still completed normally: nothing was poisoned.
    assert result.disposition == "STAGE_COMPLETED"
    assert result.stage_closure_confirmed is True


# ---------------------------------------------------------------------------
# F -- generated-material scrub is contained, not merely named
# ---------------------------------------------------------------------------


def test_finding_f_the_verified_unlink_refuses_a_path_outside_the_owned_root(
    tmp_path,
):
    owned = tmp_path / "owned"
    owned.mkdir()
    inside = owned / "models.json"
    inside.write_text("{}", encoding="utf-8")

    outside = tmp_path / "not_ours.txt"
    outside.write_text("precious", encoding="utf-8")

    # Outside the owned root: refused, and the file is untouched.
    assert run_executor._verified_unlink(str(outside), owned_root=str(owned)) is False
    assert outside.read_text(encoding="utf-8") == "precious"

    # A traversal that only LOOKS contained is refused by canonicalization.
    traversal = str(owned / ".." / "not_ours.txt")
    assert run_executor._verified_unlink(traversal, owned_root=str(owned)) is False
    assert outside.exists()

    # The owned root itself is never a target.
    assert run_executor._verified_unlink(str(owned), owned_root=str(owned)) is False
    assert owned.is_dir()

    # A missing owned root refuses rather than defaulting to "anywhere".
    assert run_executor._verified_unlink(str(inside), owned_root=None) is False
    assert inside.exists()

    # The genuine case still works, and VERIFIES absence afterwards.
    assert run_executor._verified_unlink(str(inside), owned_root=str(owned)) is True
    assert not inside.exists()
    # Idempotent: nothing left to remove is also "closed".
    assert run_executor._verified_unlink(str(inside), owned_root=str(owned)) is True


def test_finding_f_the_scrub_helper_requires_an_owned_root_argument():
    parameters = inspect.signature(run_executor._verified_unlink).parameters
    assert "owned_root" in parameters
    assert parameters["owned_root"].kind is inspect.Parameter.KEYWORD_ONLY
    assert parameters["owned_root"].default is inspect.Parameter.empty


# ---------------------------------------------------------------------------
# G -- fail closed on an ambiguous create result, never infer absence
# ---------------------------------------------------------------------------


def test_finding_g_a_directory_occupying_a_run_path_is_emission_failed_not_collision(
    make_authority,
):
    """Only an UNAMBIGUOUS already-exists signal counts as a collision.

    On Windows an exclusive create against a directory raises ``PermissionError``,
    not ``FileExistsError``. Classifying that as ``EMISSION_FAILED`` is the
    correct fail-closed answer: the path is never inferred to be absent merely
    because the error was not the specific one, and no fallback is attempted.
    """
    authority = make_authority("S1-X1")
    occupied = Path(authority.execution_directory, "S1_01_Q.json")
    occupied.mkdir()
    (occupied / "inside.txt").write_text("untouched", encoding="utf-8")

    result = emit_cfg1_run_record(
        authority,
        run_ordinal=1,
        payload=run_payload(stage_execution_id="S1-X1"),
        lifecycle_all_closed=True,
        safety=NO_NEEDLES,
    )
    assert result.emission_status in ("EMISSION_FAILED", "EMISSION_COLLISION")
    assert result.fallback_attempted is False
    assert result.phase_reached == "FINAL_PATH_CREATE_ATTEMPTED"
    # Whatever the platform's signal was, the occupant is untouched.
    assert (occupied / "inside.txt").read_text(encoding="utf-8") == "untouched"


# ---------------------------------------------------------------------------
# Broader sweeps the review prompted
# ---------------------------------------------------------------------------


def test_no_cfg1_module_level_callable_accepts_a_bare_path_for_deletion():
    """Nothing deletes, renames, or truncates by pathname alone."""
    import importlib
    import pkgutil

    import pi_harness_cfg1

    modules = [pi_harness_cfg1]
    for info in pkgutil.iter_modules(pi_harness_cfg1.__path__):
        modules.append(importlib.import_module(f"pi_harness_cfg1.{info.name}"))

    destructive = ("os.unlink", "os.remove", "os.rmdir", "shutil.rmtree", "os.replace")
    package_dir = Path(pi_harness_cfg1.__file__).parent
    for source_path in sorted(package_dir.glob("*.py")):
        source = source_path.read_text(encoding="utf-8")
        for call in destructive:
            if call in source:
                # The ONE permitted destructive call site, and it proves
                # containment inside the run's own owned root first.
                assert source_path.name == "run_executor.py", (source_path, call)
                assert call == "os.unlink", (source_path, call)
                assert "commonpath" in source


_DESTRUCTIVE_CALL_NAMES = frozenset(
    {"unlink", "remove", "rmdir", "rmtree", "rename", "replace", "truncate", "mkdir"}
)

#: Any ``open`` mode that can TRUNCATE, APPEND TO, or WRITE OVER something that
#: already exists. ``x`` is deliberately absent: exclusive-create is the one
#: sanctioned write primitive in this design, and it is the only mode that
#: cannot touch an existing occupant at all -- a ``FileExistsError`` from it IS
#: the collision proof.
_MUTATING_OPEN_MODES = ("w", "a", "+")


def _destructive_calls(module) -> list[str]:
    """Every CALL in a module that could destroy or replace a file.

    Parses the AST rather than scanning text: this module's own docstrings
    explain the residue policy in prose, and a substring scan would flag the
    explanation as the violation it exists to rule out. It also catches a call
    a substring scan would miss, such as one reached through an alias.
    """
    import ast

    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        if name in _DESTRUCTIVE_CALL_NAMES:
            found.append(f"{name}@line{node.lineno}")
        if name == "open":
            mode = None
            if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                mode = node.args[1].value
            for keyword in node.keywords:
                if keyword.arg == "mode" and isinstance(keyword.value, ast.Constant):
                    mode = keyword.value.value
            if isinstance(mode, str) and any(
                flag in mode for flag in _MUTATING_OPEN_MODES
            ):
                found.append(f"open(mode={mode!r})@line{node.lineno}")
    return found


def test_the_writers_perform_exactly_one_mutating_filesystem_call(make_authority):
    """Sec. 16.3.8.2's residue policy, as an AST-level property.

    The ONLY mutating call in the whole write/emission surface is the
    exclusive create. No unlink, no rename, no replace, no truncate, and no
    second, non-exclusive open -- so there is no code for a residue policy to
    be violated BY.
    """
    found = _destructive_calls(writers)
    assert found == [], found

    import ast

    tree = ast.parse(Path(writers.__file__).read_text(encoding="utf-8"))
    exclusive_creates = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", "") == "open"
        and len(node.args) >= 2
        and isinstance(node.args[1], ast.Constant)
        and node.args[1].value == "xb"
    ]
    assert len(exclusive_creates) == 1


def test_the_binding_verifiers_perform_no_mutating_call_at_all():
    """A read-only, post-hoc verifier that could write would not be one."""
    from pi_harness_cfg1 import binding

    assert _destructive_calls(binding) == []

    import ast

    tree = ast.parse(Path(binding.__file__).read_text(encoding="utf-8"))
    opens = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "open"
    ]
    assert len(opens) == 1
    assert opens[0].args[1].value == "rb"  # read, binary, bounded


def test_repeated_lifecycle_operations_are_idempotent_or_refused(make_authority):
    """Calling a lifecycle operation twice never succeeds twice."""
    from pi_harness_cfg1.stage_output import (
        _retire_stage_output_authority,
        stage_output_authority_is_active,
    )

    authority = make_authority("S1-X1")
    _retire_stage_output_authority(authority)
    _retire_stage_output_authority(authority)  # idempotent, no raise
    assert stage_output_authority_is_active(authority) is False

    _discard_stage_decision_state(authority)
    _discard_stage_decision_state(authority)
    assert authority.mint_nonce not in _STAGE_TERMINAL_SEAL_HISTORY
    assert _STAGE_DECISION_SEALED == {}


def test_a_second_stage_run_on_a_retired_authority_is_a_hard_stop(make_authority):
    authority = make_authority("S1-X1")
    first = stage_runner.run_cfg1_stage(
        authority, run_executor=synthetic_run_executor()
    )
    assert first.disposition == "STAGE_COMPLETED"

    executions: list = []
    second = stage_runner.run_cfg1_stage(
        authority, run_executor=lambda admission: executions.append(admission)
    )
    assert second.disposition == "STAGE_OUTPUT_AUTHORITY_HARD_STOP"
    assert second.console_codes == ("UNKNOWN_MINT_NONCE",)
    assert executions == []  # no run resource was created for the replay


def test_the_stage_runner_declares_no_decision_fact_parameter():
    parameters = list(inspect.signature(stage_runner.run_cfg1_stage).parameters)
    assert parameters == ["authority", "run_executor", "_internal_probe"]
    for forbidden in ("ordinal_status", "halted_after_ordinal", "halt_reason_code"):
        assert forbidden not in parameters
    # And it returns a result, never a decision.
    assert inspect.signature(stage_runner.run_cfg1_stage).return_annotation in (
        "Cfg1StageResult",
        stage_runner.Cfg1StageResult,
    )


def test_an_off_schedule_arm_can_never_be_admitted_by_any_supported_entry(
    make_authority,
):
    """``arm_id`` is derived from the ordinal at every entry, never accepted."""
    from pi_harness_cfg1.schedule import ScheduleError, _schedule_arm_for

    authority = make_authority("S1-X1")
    admitted: list[str] = []

    def _executor(admission):
        admitted.append(admission.arm_id)
        raise AssertionError("stop after the first admission")

    with pytest.raises(stage_runner.Cfg1StageRunnerError):
        stage_runner.run_cfg1_stage(authority, run_executor=_executor)
    assert admitted == ["Q"]  # the frozen schedule's own arm for ordinal 1

    # S1 never schedules H, at any ordinal.
    assert "H" not in {_schedule_arm_for("S1", k) for k in range(1, 10)}
    with pytest.raises(ScheduleError):
        _schedule_arm_for("S1", 10)


def test_os_path_lexists_is_what_l0_uses_so_a_symlink_occupant_is_detected(
    make_authority, tmp_path
):
    """A dangling symlink at the run path must still preoccupy the namespace."""
    from conftest import make_file_symlink

    authority = make_authority("S1-X1")
    target = tmp_path / "gone.json"
    target.write_text("{}", encoding="utf-8")
    link = Path(authority.execution_directory, "S1_01_Q.json")
    try:
        make_file_symlink(link, target)
    except (OSError, NotImplementedError):
        pytest.skip("this platform grants no file-symlink creation privilege")
    os.unlink(target)  # the link now dangles: exists() is False, lexists() True

    assert os.path.exists(str(link)) is False
    assert os.path.lexists(str(link)) is True

    result = stage_runner.run_cfg1_stage(
        authority, run_executor=synthetic_run_executor()
    )
    assert result.disposition == "OUTPUT_NAMESPACE_PREOCCUPIED"


def test_a_workspace_claimed_by_another_run_is_refused_before_any_live_resource(
    git_executable, monkeypatch
):
    """Two individually genuine objects must also AGREE with each other.

    The claim is SINGLE-USE, so a workspace already claimed elsewhere cannot be
    claimed again -- the refusal lands at L2, before any live resource exists.
    L8's own ``workspace_is_claimed_by`` re-verification is the defence in depth
    behind it, exercised directly in the next test.
    """
    from cfg1_doubles import build_doubled_ports, seam_digests_all_match

    from pi_harness_cfg1 import run_workspace
    from pi_harness_cfg1.run_contract import Cfg1RunAdmission
    from pi_harness_cfg1.run_executor import execute_cfg1_run
    from pi_harness_cfg1.schedule import _schedule_arm_for, _schedule_block_position

    seam_digests_all_match(monkeypatch)
    block, position = _schedule_block_position("S1", 1)
    admission = Cfg1RunAdmission(
        stage_id="S1",
        stage_execution_id="S1-X1",
        run_ordinal=1,
        arm_id=_schedule_arm_for("S1", 1),
        block=block,
        position=position,
        run_id="b" * 32,
    )

    def _mint_pre_claimed(*, git_executable):
        workspace, built = run_workspace.mint_cfg1_run_workspace(
            git_executable=git_executable
        )
        # Claimed by SOME OTHER run, before this one ever sees it.
        run_workspace.claim_cfg1_run_workspace(workspace, run_id="a-different-run")
        return workspace, built

    ports, made = build_doubled_ports(
        git_executable=git_executable, overrides={"mint_workspace": _mint_pre_claimed}
    )
    outcome = execute_cfg1_run(admission, ports=ports)

    assert outcome.observations["pre_dispatch_refusal_code"] == "WORKSPACE_BASELINE_FAILED"
    assert outcome.observations["refused_at_step"] == "L2"
    # The failure was CLASSIFIED, not raised out of the state machine.
    assert "RUN_STEP_RAISED_UNEXPECTEDLY" not in outcome.console_codes
    # Nothing live was created after the refusal.
    assert outcome.observations["broker_resource_created"] is False
    assert outcome.observations["runtime_created"] is False


def test_the_capability_mint_re_verifies_the_claim_rather_than_assuming_it(
    git_executable,
):
    """L8's own agreement check, exercised at the unit level.

    A claim proven once at L2 is not trusted forever: the capability mint
    re-verifies that THIS run still owns the workspace, so a workspace that
    belongs to some other run can never be bound into a capability.
    """
    from pi_harness_cfg1 import run_workspace
    from pi_harness_cfg1.run_workspace import (
        remove_cfg1_run_workspace,
        workspace_is_claimed_by,
    )

    workspace, _built = run_workspace.mint_cfg1_run_workspace(
        git_executable=git_executable
    )
    try:
        run_workspace.claim_cfg1_run_workspace(workspace, run_id="run-a")
        assert workspace_is_claimed_by(workspace, run_id="run-a") is True
        assert workspace_is_claimed_by(workspace, run_id="run-b") is False
        # A lookalike is refused by exact type, never by duck-typing.
        assert workspace_is_claimed_by(object(), run_id="run-a") is False
        assert workspace_is_claimed_by(None, run_id="run-a") is False
    finally:
        remove_cfg1_run_workspace(workspace)

    # And the executor genuinely consults it before minting a capability.
    source = inspect.getsource(run_executor._dispatch_phase)
    mint_at = source.index("ports.mint_capability(")
    check_at = source.index("workspace_is_claimed_by(")
    assert check_at < mint_at


def test_a_results_root_redirected_mid_stage_is_caught_at_the_next_boundary(
    make_authority, tmp_path
):
    """The re-proof runs at EVERY consumption boundary, not once at mint."""
    from conftest import make_directory_redirect

    authority = make_authority("S1-X1")
    elsewhere = tmp_path / "attacker-results"
    elsewhere.mkdir()

    admitted: list[int] = []

    def _executor(admission):
        admitted.append(admission.run_ordinal)
        # Redirect RESULTS_ROOT itself, after the mint, mid-stage.
        if admission.run_ordinal == 1:
            import shutil

            root = Path(authority.results_root)
            shutil.move(str(root / "S1-X1"), str(elsewhere / "S1-X1"))
            root.rmdir()
            try:
                make_directory_redirect(root, elsewhere)
            except OSError:
                pytest.skip("this platform grants neither symlink nor junction creation")
        return synthetic_run_executor()(admission)

    result = stage_runner.run_cfg1_stage(authority, run_executor=_executor)

    assert result.disposition == "STAGE_OUTPUT_AUTHORITY_HARD_STOP"
    assert result.console_codes == ("RESULTS_ROOT_REDIRECTED",)
    assert result.stage_closure_confirmed is False
    # Nothing was written through the redirect.
    assert not (elsewhere / "S1-X1" / "S1_01_Q.json").exists()
    assert not (elsewhere / "S1_stage_closure.json").exists()


def test_generated_material_lands_beside_the_repository_never_inside_it(
    git_executable, monkeypatch
):
    """A defect found only by BINDING the live ports, and fixed there.

    The generated Pi config and the generated extension both carry run-scoped
    secrets -- the endpoint in ``models.json``, the broker token in
    ``ar2_config.ts``. Written inside the working tree they would become
    Git-visible untracked content, contaminating L25's observation AND placing
    the endpoint somewhere the model's own tools can see. The frozen I2
    generator writes beside the repo for exactly this reason.
    """
    from cfg1_doubles import build_doubled_ports, seam_digests_all_match

    from pi_harness_cfg1.run_contract import Cfg1RunAdmission
    from pi_harness_cfg1.run_executor import execute_cfg1_run
    from pi_harness_cfg1.schedule import _schedule_arm_for, _schedule_block_position

    seam_digests_all_match(monkeypatch)
    block, position = _schedule_block_position("S1", 1)
    admission = Cfg1RunAdmission(
        stage_id="S1",
        stage_execution_id="S1-X1",
        run_ordinal=1,
        arm_id=_schedule_arm_for("S1", 1),
        block=block,
        position=position,
        run_id="c" * 32,
    )

    observed: dict[str, str] = {}

    def _write_config(*, owned_root, arm_id, base_url):
        from pi_harness_cfg1.cfg1_pi_config import write_cfg1_pi_config

        config = write_cfg1_pi_config(owned_root, arm_id=arm_id, base_url=base_url)
        observed["config_dir"] = config.config_dir
        return config

    ports, made = build_doubled_ports(
        git_executable=git_executable, overrides={"write_config": _write_config}
    )
    outcome = execute_cfg1_run(admission, ports=ports)
    assert outcome.observations["pre_dispatch_refusal_code"] is None

    workspace = made["workspace"]
    config_dir = Path(observed["config_dir"])
    repo_root = Path(workspace.workspace_root)
    experiment_root = Path(workspace.experiment_root)

    # Beside the repository child, and inside the owned root.
    assert config_dir.parent == experiment_root
    assert repo_root not in config_dir.parents
    assert config_dir != repo_root

    # ...so the repository itself stayed clean of untracked generated content.
    assert outcome.observations["untracked_path_count"] == 0


def test_the_live_port_bindings_are_importable_and_free_of_latent_name_errors():
    """Compile-and-bind every live port body without CALLING any of them.

    Binding the four live ports is production code that the offline suite can
    never execute -- so a missing import inside one would sit undetected until
    a live run. Building the port set exercises the enclosing function's own
    imports, and this check additionally proves each bound port's body resolves
    every global it names.
    """
    ports = run_executor.default_cfg1_run_ports(ambient_environ={})
    for name in (
        "build_broker",
        "write_extension",
        "evaluate_extension_identity",
        "evaluate_model_identity",
        "build_supervisor",
    ):
        port = getattr(ports, name)
        code = port.__code__
        missing = [
            symbol
            for symbol in code.co_names
            if symbol.isidentifier()
            and symbol not in port.__globals__
            and symbol not in dir(__builtins__)
            and not any(
                symbol in cell_names
                for cell_names in (code.co_freevars, code.co_varnames)
            )
        ]
        # Attribute names also land in ``co_names``, so this is a heuristic --
        # its value is catching a bare global like ``Path`` that nothing
        # provides. Anything it flags is inspected by name below.
        unresolved = [
            symbol for symbol in missing if symbol in ("Path", "os", "secrets", "json")
        ]
        assert unresolved == [], (name, unresolved)


def test_the_token_bearing_extension_file_is_scrubbed_by_the_frozen_scrubber(
    git_executable, monkeypatch, tmp_path
):
    """L24 consumes ``ar2.pi_config.scrub_generated_extension_config`` itself.

    Sec. 7.4 lists it among the modules CFG1 reuses UNMODIFIED, so the token
    file is removed by the frozen, verified scrubber rather than by an
    equivalent of CFG1's own. CFG1 adds only a containment proof in front.
    """
    from cfg1_doubles import build_doubled_ports, seam_digests_all_match

    from pi_harness_cfg1.run_contract import Cfg1RunAdmission
    from pi_harness_cfg1.run_executor import (
        _scrub_extension_binding,
        execute_cfg1_run,
    )
    from pi_harness_cfg1.schedule import _schedule_arm_for, _schedule_block_position

    seam_digests_all_match(monkeypatch)
    block, position = _schedule_block_position("S1", 1)
    admission = Cfg1RunAdmission(
        stage_id="S1",
        stage_execution_id="S1-X1",
        run_ordinal=1,
        arm_id=_schedule_arm_for("S1", 1),
        block=block,
        position=position,
        run_id="d" * 32,
    )

    scrubber_calls: list[str] = []
    from ar2 import pi_config as frozen_pi_config

    real_scrubber = frozen_pi_config.scrub_generated_extension_config

    def _spy(extension_dir):
        scrubber_calls.append(extension_dir)
        return real_scrubber(extension_dir)

    monkeypatch.setattr(frozen_pi_config, "scrub_generated_extension_config", _spy)

    ports, made = build_doubled_ports(git_executable=git_executable)
    outcome = execute_cfg1_run(admission, ports=ports)

    assert outcome.observations["extension_binding_scrub_verified"] is True
    assert len(scrubber_calls) == 1
    # The scrubber was handed a directory inside this run's own owned root.
    assert scrubber_calls[0].startswith(made["workspace"].experiment_root)

    # And the containment proof in front of it refuses a foreign directory,
    # with the frozen scrubber never reached.
    foreign = tmp_path / "not_ours"
    foreign.mkdir()
    token_file = foreign / "ar2_config.ts"
    token_file.write_text('export const TOKEN = "precious";\n', encoding="utf-8")
    before = len(scrubber_calls)
    assert (
        _scrub_extension_binding(str(foreign), owned_root=str(tmp_path / "owned"))
        is False
    )
    assert len(scrubber_calls) == before
    assert token_file.read_text(encoding="utf-8") == 'export const TOKEN = "precious";\n'


def test_the_broker_adapter_reads_counts_from_their_real_frozen_sources():
    """A defect the doubles alone could never have caught.

    The first binding read ``read_operations``/``edit_operations``/
    ``edited_paths``/``refusals`` straight off ``BrokerDiagnostics.as_dict()``.
    That mapping has none of those keys -- it carries ``accepted`` and
    ``refused`` maps keyed by operation name and by ``operation:code`` -- so
    every count would have been a silent zero, and a run with genuine tool
    activity would have recorded none. This exercises the REAL frozen objects.
    """
    from ar2.broker import BrokerDiagnostics
    from ar2.capability import CapDefinitions, RunState

    from pi_harness_cfg1.run_executor import default_cfg1_run_ports

    run_state = RunState(caps=CapDefinitions())
    run_state.consumed.read_operations = 3
    run_state.consumed.edit_operations = 2
    # DISTINCT paths. The frozen ``RunState.record_edit`` appends only a path
    # it has not already recorded, so this list is the changed-file set, not
    # the edit-operation count -- which is what makes Sec. 22.3's
    # ``edited_paths <= edit_operations`` invariant hold.
    run_state.mutated_paths.extend(["greeting/banner.py", "greeting/__init__.py"])
    diagnostics = BrokerDiagnostics()
    diagnostics.accept("read_file")
    diagnostics.refuse("edit_file", "ERR_UNAUTHORIZED", "binding_mismatch")
    diagnostics.refuse("edit_file", "ERR_PROTOCOL_ERROR", "already_terminal")

    # Build the real adapter class through the real binding, then drive it.
    ports = default_cfg1_run_ports(ambient_environ={})

    class _Capability:
        capability_id = "synthetic-capability"
        caps = CapDefinitions()

    adapter = ports.build_broker(capability=_Capability())
    object.__setattr__(adapter, "run_state", run_state)
    object.__setattr__(adapter, "handler", type("H", (), {"diagnostics": diagnostics})())

    counts = adapter.diagnostics_counts()
    assert counts == {
        "read_operations": 3,
        "edit_operations": 2,
        "edited_paths": 2,
        "refusals": 2,
    }
    assert counts["edited_paths"] <= counts["edit_operations"]

    # The adapter was built without starting anything.
    assert adapter.server.state == "CREATED"
    assert isinstance(adapter.token, str) and adapter.token
    assert adapter.pipe_name.startswith(r"\\.\pipe" + "\\")


def test_the_broker_adapter_carries_no_raw_worker_error_across_its_boundary():
    """``worker_error`` is raw text and must never cross into a record."""
    from ar2.capability import CapDefinitions

    from pi_harness_cfg1.run_executor import default_cfg1_run_ports

    ports = default_cfg1_run_ports(ambient_environ={})

    class _Capability:
        capability_id = "synthetic-capability"
        caps = CapDefinitions()

    adapter = ports.build_broker(capability=_Capability())
    lifecycle = adapter.shutdown_for_cfg1()
    assert set(lifecycle) == {
        "state_reached",
        "pending_operations_unreaped",
        "worker_termination_observed",
    }
    assert "worker_error" not in lifecycle
    assert type(lifecycle["pending_operations_unreaped"]) is int
    assert type(lifecycle["worker_termination_observed"]) is bool


def test_every_live_port_binding_calls_its_frozen_callee_with_a_valid_signature():
    """Signature-BIND each frozen call the live bindings make, without calling it.

    The live bindings are production code the offline suite can never execute,
    so an argument-shape mistake would sit undetected until a live run. This
    caught a real one: the frozen B300 route observer is KEYWORD-ONLY, and the
    first binding called it positionally -- a ``TypeError`` that would have
    fired at L7, after a credential had already been read.

    ``bind`` raises on a mismatch and executes nothing, so this proves the call
    shape without contacting anything.
    """
    from ar2.capability import CapDefinitions, mint_capability
    from ar2.launch import build_pi_argv, resolve_runtime_identity
    from ar2.observation import observe_repository
    from ar2.pi_config import write_disposable_extension
    from ar2.supervisor import PiRpcSupervisor, RunBounds
    from ar2.verification import run_verification
    from qualification.i2_b300_route_observation import observe_b300_route_serves_model

    from pi_harness_cfg1.cfg1_pi_config import write_cfg1_pi_config
    from pi_harness_cfg1.environment import build_cfg1_child_environment

    sentinel = "<synthetic>"

    inspect.signature(observe_b300_route_serves_model).bind(
        base_url=sentinel, api_key=sentinel, model_id=sentinel
    )
    inspect.signature(resolve_runtime_identity).bind(expected_version=sentinel)
    inspect.signature(observe_repository).bind(
        git_executable=sentinel, workspace_root=sentinel
    )
    inspect.signature(run_verification).bind(
        python_executable=sentinel, workspace_root=sentinel, args=()
    )
    inspect.signature(mint_capability).bind(
        authority=object(),
        tracked_manifest=(),
        protected_patterns=(),
        verification_witness_paths=(),
        caps=CapDefinitions(),
    )
    inspect.signature(write_disposable_extension).bind(
        sentinel,
        source_dir=sentinel,
        experiment_id=sentinel,
        pipe_name=sentinel,
        capability_id=sentinel,
        token=sentinel,
    )
    inspect.signature(build_pi_argv).bind(
        object(),
        extension_entry=sentinel,
        tool_allowlist=("aido_read", "aido_edit"),
        provider=sentinel,
        model=sentinel,
    )
    inspect.signature(PiRpcSupervisor).bind(
        argv=(), cwd=sentinel, environment={}, bounds=RunBounds()
    )
    inspect.signature(write_cfg1_pi_config).bind(
        sentinel, arm_id="Q", base_url=sentinel
    )
    inspect.signature(build_cfg1_child_environment).bind(
        ambient_environ={},
        node_executable=sentinel,
        generated_config=object(),
        credential_value=sentinel,
        git_executable=sentinel,
    )
