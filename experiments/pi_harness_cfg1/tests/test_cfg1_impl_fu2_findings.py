"""CFG1-IMPL-FU2: adversarial regressions for the reviewer's four findings.

Design authority: ``5F3B-HARNESS-CFG1-DESIGN`` through FU14 (frozen), reviewed
against implementation commit ``790ea85``. This module adds ONLY the
regressions the FU2 review requires, on top of (and in one place correcting)
``test_cfg1_impl_fu1_findings.py``'s own FU1 regressions. Findings are
numbered exactly as FU2's review prompt numbers them -- these are NOT the same
four things FU1's own "Finding 1-4" named, even though several titles overlap.

Pure Python, ``tmp_path``/``cfg1_package_dir``-scoped, no live Pi/network/
model/credential activity -- the same discipline every other module in this
suite follows (see ``conftest.py``).
"""

from __future__ import annotations

import dataclasses
import inspect

import pytest
from cfg1_doubles import SYNTHETIC_BASE_URL, SYNTHETIC_CREDENTIAL, FakeBroker, build_doubled_ports

from pi_harness_cfg1 import classification, config_issuance, lifecycle, run_executor, run_workspace
from pi_harness_cfg1.environment import build_cfg1_child_environment
from pi_harness_cfg1.run_contract import Cfg1RunAdmission
from pi_harness_cfg1.schedule import _schedule_arm_for, _schedule_block_position

# ---------------------------------------------------------------------------
# Finding 1 -- the genuine executor token must be bound to its EXACT callable
# ---------------------------------------------------------------------------


def test_f1_genuine_token_with_a_substituted_callable_is_refused_at_construction():
    """``Cfg1GenuineRunExecutor(token=genuine.token, call=forged)`` must fail.

    Token MEMBERSHIP alone (FU1's shape) would have let this through --
    ``token`` was genuinely minted, so membership held, and the substituted
    ``call`` was never compared against anything. The fix binds the registry
    to the exact callable, so this must now fail at ``__post_init__``, before
    ``forged`` is ever reachable from anywhere.
    """
    genuine = run_executor.bind_genuine_cfg1_run_executor()
    calls: list[object] = []

    def forged(admission):
        calls.append(admission)
        return "NOT_A_REAL_OUTCOME"

    with pytest.raises(run_executor.Cfg1GenuineRunExecutorError) as excinfo:
        run_executor.Cfg1GenuineRunExecutor(token=genuine.token, call=forged)
    assert excinfo.value.reason_code == "EXECUTOR_BINDING_UNPROVEN"
    assert calls == []


def test_f1_unknown_token_with_a_fake_callable_is_refused():
    calls: list[object] = []
    with pytest.raises(run_executor.Cfg1GenuineRunExecutorError) as excinfo:
        run_executor.Cfg1GenuineRunExecutor(
            token="totally-unknown-token", call=lambda admission: calls.append(admission)
        )
    assert excinfo.value.reason_code == "EXECUTOR_BINDING_UNPROVEN"
    assert calls == []


def test_f1_mutating_the_callable_after_mint_is_refused_at_invoke():
    """``object.__setattr__`` bypasses ``frozen=True`` field assignment, but
    ``invoke`` re-proves the binding on EVERY call, not merely at construction.
    """
    genuine = run_executor.bind_genuine_cfg1_run_executor()
    calls: list[object] = []

    def forged(admission):
        calls.append(admission)
        return "NOT_A_REAL_OUTCOME"

    object.__setattr__(genuine, "call", forged)

    with pytest.raises(run_executor.Cfg1GenuineRunExecutorError) as excinfo:
        genuine.invoke(object())
    assert excinfo.value.reason_code == "EXECUTOR_BINDING_UNPROVEN"
    assert calls == []


def test_f1_dataclasses_replace_with_a_substituted_callable_is_refused():
    """``dataclasses.replace`` re-runs ``__init__``/``__post_init__`` fresh."""
    genuine = run_executor.bind_genuine_cfg1_run_executor()

    def forged(admission):
        return "NOT_A_REAL_OUTCOME"

    with pytest.raises(run_executor.Cfg1GenuineRunExecutorError) as excinfo:
        dataclasses.replace(genuine, call=forged)
    assert excinfo.value.reason_code == "EXECUTOR_BINDING_UNPROVEN"


def test_f1_genuine_token_plus_genuine_original_callable_positive_control(monkeypatch):
    """The positive control: the ACTUAL bound callable, unmodified, still works."""
    from cfg1_builders import happy_observations
    from pi_harness_cfg1.arms import ARM_SHAPE
    from pi_harness_cfg1.run_contract import Cfg1RunOutcome
    from qualification.safety import ArtifactSafetyContext

    def _fake_execute_cfg1_run(admission, *, ports):
        return Cfg1RunOutcome(
            observations=happy_observations(
                runtime_reported_compat_shape=ARM_SHAPE[admission.arm_id]
            ),
            safety=ArtifactSafetyContext.none_declared(),
            live_references_released=True,
        )

    monkeypatch.setattr(run_executor, "execute_cfg1_run", _fake_execute_cfg1_run)
    monkeypatch.setattr(
        run_executor, "default_cfg1_run_ports", lambda *, ambient_environ: "sentinel"
    )

    genuine = run_executor.bind_genuine_cfg1_run_executor()
    block, position = _schedule_block_position("S1", 1)
    admission = Cfg1RunAdmission(
        stage_id="S1",
        stage_execution_id="S1-X1",
        run_ordinal=1,
        arm_id=_schedule_arm_for("S1", 1),
        block=block,
        position=position,
        run_id="a" * 32,
    )
    outcome = genuine.invoke(admission)
    assert outcome.observations["lifecycle_all_closed"] is True


# --- Finding 1's test-hook boundary: a probe must never reach the genuine branch


def test_f1_a_genuine_executor_combined_with_any_probe_is_mechanically_refused():
    """The genuine branch must refuse a non-None ``_internal_probe`` outright,
    regardless of ``stage_output._CAPTURED_PACKAGE_DIR`` -- the offline-seam
    guard only ever gated the OTHER branch, never this one.
    """
    from pi_harness_cfg1 import stage_output, stage_runner

    genuine = run_executor.bind_genuine_cfg1_run_executor()

    class _FakeAuthority:
        pass

    probe_calls: list[object] = []

    def _probe(event):  # pragma: no cover - must never be reached
        probe_calls.append(event)

    with pytest.raises(stage_runner.Cfg1StageRunnerError) as excinfo:
        stage_runner._run_cfg1_stage_with_injected_executor(
            _FakeAuthority(), run_executor=genuine, _internal_probe=_probe
        )
    assert excinfo.value.reason_code == "TEST_PROBE_AGAINST_GENUINE_EXECUTOR_REFUSED"
    assert probe_calls == []


def test_f1_a_genuine_executor_with_no_probe_is_unaffected_by_the_new_gate(
    make_authority, monkeypatch
):
    """Positive control: the ordinary genuine path (no probe at all) still runs."""
    from cfg1_builders import happy_observations
    from pi_harness_cfg1.arms import ARM_SHAPE
    from pi_harness_cfg1.run_contract import Cfg1RunOutcome
    from qualification.safety import ArtifactSafetyContext

    authority = make_authority("S1-X1")

    def _fake_execute_cfg1_run(admission, *, ports):
        return Cfg1RunOutcome(
            observations=happy_observations(
                runtime_reported_compat_shape=ARM_SHAPE[admission.arm_id]
            ),
            safety=ArtifactSafetyContext.none_declared(),
            live_references_released=True,
        )

    monkeypatch.setattr(run_executor, "execute_cfg1_run", _fake_execute_cfg1_run)
    monkeypatch.setattr(
        run_executor, "default_cfg1_run_ports", lambda *, ambient_environ: "sentinel"
    )

    from pi_harness_cfg1 import stage_runner

    result = stage_runner.run_cfg1_stage(authority)
    assert result.disposition == "STAGE_COMPLETED"


# ---------------------------------------------------------------------------
# Finding 2 -- GeneratedCfg1Config fields are caller-mutable; only the
# VERIFIED issuance record may act as authority at a consumption boundary
# ---------------------------------------------------------------------------


def test_f2_environment_builder_ignores_a_mutated_config_dir_field(tmp_path, git_executable):
    """The literal attack from the review prompt: mutate ``config.config_dir``
    after issuance, then call the environment builder with the genuine token.
    ``PI_CODING_AGENT_DIR`` must be the VERIFIED directory, never the foreign one.
    """
    from pi_harness_cfg1.cfg1_pi_config import write_cfg1_pi_config

    workspace, _built = run_workspace.mint_cfg1_run_workspace(git_executable=git_executable)
    try:
        config = write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
        genuine_config_dir = config.config_dir

        foreign = tmp_path / "foreign_pi_agent_dir"
        foreign.mkdir()
        config.config_dir = str(foreign)  # caller-mutable plain attribute

        built = build_cfg1_child_environment(
            ambient_environ={"SystemRoot": r"C:\Windows"},
            node_executable=r"C:\Program Files\nodejs\node.exe",
            generated_config=config,
            workspace=workspace,
            credential_value=SYNTHETIC_CREDENTIAL,
        )
        assert built.environment["PI_CODING_AGENT_DIR"] == genuine_config_dir
        assert built.environment["PI_CODING_AGENT_DIR"] != str(foreign)
        assert built.pi_config_dir == genuine_config_dir
    finally:
        config_issuance.discard_config_issuance(config.issuance_token)
        run_workspace.remove_cfg1_run_workspace(workspace)


def test_f2_environment_builder_refuses_a_freshly_built_config_with_substituted_fields(
    tmp_path, git_executable
):
    """A hand-built ``GeneratedCfg1Config`` carrying the genuine token but every
    OTHER field substituted must still be refused (or fully ignored for
    authority) -- the token/workspace re-derivation, not the object's own
    fields, is what ``verify_config_issuance`` checks.
    """
    from pi_harness_cfg1.cfg1_pi_config import GeneratedCfg1Config, write_cfg1_pi_config

    workspace, _built = run_workspace.mint_cfg1_run_workspace(git_executable=git_executable)
    try:
        genuine = write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
        genuine_config_dir = genuine.config_dir

        substituted = GeneratedCfg1Config(
            config_dir=str(tmp_path / "totally_foreign_dir"),
            settings_path=str(tmp_path / "totally_foreign_dir" / "settings.json"),
            models_path=str(tmp_path / "totally_foreign_dir" / "models.json"),
            arm_id="R",
            provider_id="a_different_provider",
            model_id="a-different-model",
            settings_sha256="0" * 64,
            models_redacted_sha256="0" * 64,
            issuance_token=genuine.issuance_token,  # the ONLY genuine field
        )

        built = build_cfg1_child_environment(
            ambient_environ={"SystemRoot": r"C:\Windows"},
            node_executable=r"C:\Program Files\nodejs\node.exe",
            generated_config=substituted,
            workspace=workspace,
            credential_value=SYNTHETIC_CREDENTIAL,
        )
        # Even with every other field forged, only the VERIFIED, re-derived
        # directory is ever used -- never anything from `substituted` itself.
        assert built.environment["PI_CODING_AGENT_DIR"] == genuine_config_dir
    finally:
        config_issuance.discard_config_issuance(genuine.issuance_token)
        run_workspace.remove_cfg1_run_workspace(workspace)


def test_f2_l24_scrub_ignores_a_substituted_models_path_and_never_touches_it(
    tmp_path, git_executable, monkeypatch
):
    """Adversarial double: ``write_config`` returns a genuine issuance whose
    ``models_path`` field is mutated to point at a foreign file BEFORE
    ``execute_cfg1_run`` reaches L24. L24 must never unlink the foreign file.
    """
    from pi_harness_cfg1.cfg1_pi_config import write_cfg1_pi_config
    from pi_harness_cfg1.run_executor import execute_cfg1_run

    from cfg1_doubles import seam_digests_all_match

    foreign_target = tmp_path / "innocent_bystander.json"
    foreign_target.write_text('{"do": "not delete me"}', encoding="utf-8")
    real_models_path_holder: list[str] = []

    def _write_config_then_forge(*, workspace, arm_id, base_url):
        generated = write_cfg1_pi_config(workspace, arm_id=arm_id, base_url=base_url)
        real_models_path_holder.append(generated.models_path)
        generated.models_path = str(foreign_target)  # forged AFTER genuine issuance
        return generated

    ports, _made = build_doubled_ports(
        git_executable=git_executable,
        overrides={"write_config": _write_config_then_forge},
    )

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
    outcome = execute_cfg1_run(admission, ports=ports)

    # The foreign file must survive completely untouched -- L24 never even
    # looked at the forged field, let alone unlinked what it pointed to.
    assert foreign_target.exists()
    assert foreign_target.read_text(encoding="utf-8") == '{"do": "not delete me"}'
    # The scrub still succeeds, but against the REAL, verified models.json
    # path -- re-derived from the issuance registry, never read from the
    # (forged) object field.
    assert real_models_path_holder, "the double never captured the real path"
    import os as _os

    assert not _os.path.exists(real_models_path_holder[0])
    assert outcome.observations["generated_config_scrub_verified"] is True


# ---------------------------------------------------------------------------
# Finding 3 -- malformed counts must never be laundered into a proof-bearing
# exact zero. "observed zero" and "malformed/unavailable" must stay distinct.
# ---------------------------------------------------------------------------


_MALFORMED_COUNTS = ("0", "1", True, False, None, -5, 3.5, [], {}, object())


class _CustomIntLike:
    def __int__(self) -> int:
        return 0

    def __index__(self) -> int:
        return 0


@pytest.mark.parametrize("malformed", list(_MALFORMED_COUNTS) + [_CustomIntLike()])
def test_f3_malformed_pending_unreaped_never_reads_as_proven_zero_end_to_end(
    malformed, git_executable, monkeypatch
):
    """L23, end to end: a broker double whose ``shutdown_for_cfg1`` returns a
    malformed (never a real ``0``) ``pending_operations_unreaped`` must never
    let ``broker_pending_unreaped_zero`` read True -- exactly mirroring the
    RAW value the fixed adapter now passes through unlaundered.
    """
    from cfg1_doubles import seam_digests_all_match
    from pi_harness_cfg1.run_executor import execute_cfg1_run

    seam_digests_all_match(monkeypatch)

    class _MalformedPendingBroker(FakeBroker):
        def __init__(self):
            super().__init__()
            self.lifecycle["pending_operations_unreaped"] = malformed

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
    ports, _made = build_doubled_ports(
        git_executable=git_executable,
        overrides={"build_broker": lambda **_kwargs: _MalformedPendingBroker()},
    )
    outcome = execute_cfg1_run(admission, ports=ports)
    assert outcome.observations["broker_pending_unreaped_zero"] is False
    assert outcome.observations["lifecycle_all_closed"] is False
    assert "L23" in outcome.observations["lifecycle_failure_steps"]


@pytest.mark.parametrize("malformed", list(_MALFORMED_COUNTS) + [_CustomIntLike()])
def test_f3_malformed_broker_activity_count_forces_activity_unavailable(
    malformed, git_executable, monkeypatch
):
    """A broker double whose ``diagnostics_counts`` returns ONE malformed
    field (never an exception) must still force
    ``broker_recorded_activity_available`` False -- the manufactured-zero
    laundering this finding targets would otherwise leave it True.
    """
    from cfg1_doubles import seam_digests_all_match
    from pi_harness_cfg1.run_executor import execute_cfg1_run

    seam_digests_all_match(monkeypatch)

    class _MalformedActivityBroker(FakeBroker):
        def diagnostics_counts(self) -> dict:
            counts = dict(self.counts)
            counts["read_operations"] = malformed
            return counts

    block, position = _schedule_block_position("S1", 1)
    admission = Cfg1RunAdmission(
        stage_id="S1",
        stage_execution_id="S1-X1",
        run_ordinal=1,
        arm_id=_schedule_arm_for("S1", 1),
        block=block,
        position=position,
        run_id="e" * 32,
    )
    ports, _made = build_doubled_ports(
        git_executable=git_executable,
        overrides={"build_broker": lambda **_kwargs: _MalformedActivityBroker()},
    )
    outcome = execute_cfg1_run(admission, ports=ports)
    assert outcome.observations["broker_recorded_activity_available"] is False
    # And the classifier must route this to indeterminate, never ACTIVE/INACTIVE.
    assert (
        classification.classify_cfg1_run(outcome.observations)
        == classification.CLASSIFICATION_INDETERMINATE_NO_ACTIVITY_EVIDENCE
    )


def test_f3_adapter_source_no_longer_pre_launders_pending_unreaped_or_activity_counts():
    """Source audit (mirrors FU1's own style): the live adapter inside
    ``default_cfg1_run_ports`` must not wrap ``pending_operations_unreaped``,
    ``read_operations`` or ``edit_operations`` in ``_exact_count`` -- doing so
    there manufactures a plausible zero BEFORE the real consumption-boundary
    check ever sees the raw value, which is the exact defect this finding
    reports.
    """
    source = inspect.getsource(run_executor.default_cfg1_run_ports)
    collapsed = " ".join(source.split())
    assert '"pending_operations_unreaped": lifecycle.get( "pending_operations_unreaped" ),' in collapsed
    assert '"read_operations": consumed.read_operations,' in collapsed
    assert '"edit_operations": consumed.edit_operations,' in collapsed
    assert "_exact_count(consumed.read_operations)" not in collapsed
    assert "_exact_count(consumed.edit_operations)" not in collapsed
    assert '_exact_count( lifecycle.get("pending_operations_unreaped"' not in collapsed


@pytest.mark.parametrize("malformed", list(_MALFORMED_COUNTS) + [_CustomIntLike()])
def test_f3_malformed_workspace_residual_count_never_allows_lifecycle_closure(
    malformed, git_executable, monkeypatch
):
    """A workspace-removal double returning a malformed ``residual_file_count``
    (with ``removed=True``, the otherwise-fully-closing case) must never let
    L27 -- and therefore ``lifecycle_all_closed`` -- read as proven closed.
    """
    from cfg1_doubles import seam_digests_all_match
    from pi_harness_cfg1.run_executor import execute_cfg1_run

    seam_digests_all_match(monkeypatch)

    real_remove = run_workspace.remove_cfg1_run_workspace

    def _fake_remove(workspace):
        real_remove(workspace)
        return {"removed": True, "residual_file_count": malformed}

    monkeypatch.setattr(run_workspace, "remove_cfg1_run_workspace", _fake_remove)

    block, position = _schedule_block_position("S1", 1)
    admission = Cfg1RunAdmission(
        stage_id="S1",
        stage_execution_id="S1-X1",
        run_ordinal=1,
        arm_id=_schedule_arm_for("S1", 1),
        block=block,
        position=position,
        run_id="f" * 32,
    )
    ports, _made = build_doubled_ports(git_executable=git_executable)
    outcome = execute_cfg1_run(admission, ports=ports)
    assert outcome.observations["workspace_removed_verified"] is False
    assert outcome.observations["lifecycle_all_closed"] is False
    assert "L27" in outcome.observations["lifecycle_failure_steps"]


def test_f3_genuine_zero_residual_and_removed_true_still_closes_l27(git_executable, monkeypatch):
    """Positive control: an ACTUAL exact ``0`` with ``removed=True`` still closes."""
    from cfg1_doubles import seam_digests_all_match
    from pi_harness_cfg1.run_executor import execute_cfg1_run

    seam_digests_all_match(monkeypatch)

    block, position = _schedule_block_position("S1", 1)
    admission = Cfg1RunAdmission(
        stage_id="S1",
        stage_execution_id="S1-X1",
        run_ordinal=1,
        arm_id=_schedule_arm_for("S1", 1),
        block=block,
        position=position,
        run_id="1" * 32,
    )
    ports, _made = build_doubled_ports(git_executable=git_executable)
    outcome = execute_cfg1_run(admission, ports=ports)
    assert outcome.observations["workspace_removed_verified"] is True
    assert outcome.observations["workspace_residual_file_count"] == 0


@pytest.mark.parametrize("malformed", list(_MALFORMED_COUNTS) + [_CustomIntLike()])
def test_f3_malformed_auto_retry_count_cannot_be_laundered_to_zero(
    malformed, git_executable, monkeypatch
):
    """A malformed ``activity.auto_retry_events`` must route classification to
    ``INDETERMINATE_PROVIDER`` -- never let it silently read as "0 retries"
    and fall through to a determinate classification.
    """
    from cfg1_doubles import FakeSupervisor, seam_digests_all_match
    from pi_harness_cfg1.run_executor import execute_cfg1_run

    seam_digests_all_match(monkeypatch)

    def _build_supervisor(**_kwargs):
        supervisor = FakeSupervisor()
        supervisor.activity.auto_retry_events = malformed
        return supervisor

    block, position = _schedule_block_position("S1", 1)
    admission = Cfg1RunAdmission(
        stage_id="S1",
        stage_execution_id="S1-X1",
        run_ordinal=1,
        arm_id=_schedule_arm_for("S1", 1),
        block=block,
        position=position,
        run_id="2" * 32,
    )
    ports, _made = build_doubled_ports(
        git_executable=git_executable,
        overrides={"build_supervisor": _build_supervisor},
    )
    outcome = execute_cfg1_run(admission, ports=ports)
    assert outcome.observations["auto_retry_events"] == 0  # display field: bounded minimum
    assert outcome.observations["stop_reasons_available"] is False
    assert (
        classification.classify_cfg1_run(outcome.observations)
        == classification.CLASSIFICATION_INDETERMINATE_PROVIDER
    )


@pytest.mark.parametrize("malformed", list(_MALFORMED_COUNTS) + [_CustomIntLike()])
def test_f3_malformed_verification_counts_never_strengthen_a_passing_claim(
    malformed, git_executable, monkeypatch
):
    """A verification outcome reporting ``passed=True`` alongside ONE malformed
    count must never let ``verification_passed`` read True.
    """
    from dataclasses import dataclass, field as _field

    from cfg1_doubles import seam_digests_all_match
    from pi_harness_cfg1.run_executor import execute_cfg1_run

    seam_digests_all_match(monkeypatch)

    @dataclass
    class _SeededFailureBaseline:
        # L3's own gate: CFG1_T1 is a declared SEEDED FAILURE, so the baseline
        # call must report `passed=False` or the run refuses pre-dispatch
        # before L26 -- the call this test actually targets -- is ever
        # reached.
        started: bool = True
        completed: bool = True
        timed_out: bool = False
        output_limit_exceeded: bool = False
        return_code: int = 1
        passed: bool = False
        counts: dict = _field(default_factory=lambda: {"passed": 0, "failed": 1, "error": 0})

    @dataclass
    class _MalformedVerification:
        started: bool = True
        completed: bool = True
        timed_out: bool = False
        output_limit_exceeded: bool = False
        return_code: int = 0
        passed: bool = True
        counts: dict = _field(
            default_factory=lambda: {"passed": malformed, "failed": 0, "error": 0}
        )

    # `run_verification` is called twice: once for L3's baseline (which must
    # see the seeded-failure shape) and once for L26 (the call this finding
    # targets). A call counter distinguishes them.
    calls: list[int] = []

    def _run_verification(**_kwargs):
        calls.append(1)
        return _SeededFailureBaseline() if len(calls) == 1 else _MalformedVerification()

    block, position = _schedule_block_position("S1", 1)
    admission = Cfg1RunAdmission(
        stage_id="S1",
        stage_execution_id="S1-X1",
        run_ordinal=1,
        arm_id=_schedule_arm_for("S1", 1),
        block=block,
        position=position,
        run_id="3" * 32,
    )
    ports, _made = build_doubled_ports(
        git_executable=git_executable,
        overrides={"run_verification": _run_verification},
    )
    outcome = execute_cfg1_run(admission, ports=ports)
    assert len(calls) == 2, "the test never reached L26's own verification call"
    assert outcome.observations["verification_passed"] is False


def test_f3_genuine_passing_verification_with_exact_counts_still_passes(
    git_executable, monkeypatch
):
    """Positive control: an actual passing verification with exact-int counts
    still reads as passed.
    """
    from dataclasses import dataclass, field as _field

    from cfg1_doubles import seam_digests_all_match
    from pi_harness_cfg1.run_executor import execute_cfg1_run

    seam_digests_all_match(monkeypatch)

    @dataclass
    class _SeededFailureBaseline:
        started: bool = True
        completed: bool = True
        timed_out: bool = False
        output_limit_exceeded: bool = False
        return_code: int = 1
        passed: bool = False
        counts: dict = _field(default_factory=lambda: {"passed": 0, "failed": 1, "error": 0})

    @dataclass
    class _GenuineVerification:
        started: bool = True
        completed: bool = True
        timed_out: bool = False
        output_limit_exceeded: bool = False
        return_code: int = 0
        passed: bool = True
        counts: dict = _field(
            default_factory=lambda: {"passed": 1, "failed": 0, "error": 0}
        )

    calls: list[int] = []

    def _run_verification(**_kwargs):
        calls.append(1)
        return _SeededFailureBaseline() if len(calls) == 1 else _GenuineVerification()

    block, position = _schedule_block_position("S1", 1)
    admission = Cfg1RunAdmission(
        stage_id="S1",
        stage_execution_id="S1-X1",
        run_ordinal=1,
        arm_id=_schedule_arm_for("S1", 1),
        block=block,
        position=position,
        run_id="4" * 32,
    )
    ports, _made = build_doubled_ports(
        git_executable=git_executable,
        overrides={"run_verification": _run_verification},
    )
    outcome = execute_cfg1_run(admission, ports=ports)
    assert len(calls) == 2
    assert outcome.observations["verification_passed"] is True


def test_f3_untracked_and_staged_counts_deliberately_unchanged_no_authority_riding_on_zero():
    """Documents the audit's own conclusion for the two repository counts the
    finding also names: neither feeds a closure, cleanliness, authority or
    verification predicate anywhere in this package, so ``malformed -> 0``
    (the field's own documented minimum) remains the correct, ALREADY
    fail-closed reduction for them -- changing it would be scope creep with no
    security benefit. Proven by absence: no lifecycle/classification predicate
    reads either key.
    """
    lifecycle_source = inspect.getsource(lifecycle.compute_lifecycle_closure)
    classification_source = inspect.getsource(classification)
    assert "untracked_path_count" not in lifecycle_source
    assert "staged_path_count" not in lifecycle_source
    assert "untracked_path_count" not in classification_source
    assert "staged_path_count" not in classification_source


# ---------------------------------------------------------------------------
# Finding 4 -- config-generation filesystem TOCTOU (file-level half closed;
# directory-level half is a reported, not silently claimed, residual)
# ---------------------------------------------------------------------------


def test_f4_end_to_end_race_window_symlink_plant_between_mkdir_and_write_is_refused(
    tmp_path, git_executable, monkeypatch
):
    """The file-level TOCTOU, reproduced through the PUBLIC entry point.

    ``Path.mkdir`` is patched to plant a real file symlink at the EXACT
    ``settings.json`` path immediately after ``config_dir``'s own
    ``mkdir(exist_ok=False)`` returns -- i.e. exactly the race window between
    directory creation and the first write -- and then delegates to the real
    ``mkdir``. This proves the exclusive-create fix, not merely the directory
    ``exist_ok=False`` guard (which a directory-already-existing test alone
    would exercise instead).
    """
    from pathlib import Path

    from conftest import make_file_symlink
    from pi_harness_cfg1.cfg1_pi_config import (
        CFG1_CONFIG_DIR_NAME,
        Cfg1PiConfigError,
        write_cfg1_pi_config,
    )

    decoy_target = tmp_path / "decoy_settings_target.json"
    decoy_target.write_text('{"attacker": "controlled"}', encoding="utf-8")
    planted: list[bool] = []
    real_mkdir = Path.mkdir

    def _mkdir_then_plant(self, *args, **kwargs):
        result = real_mkdir(self, *args, **kwargs)
        if not planted and self.name == CFG1_CONFIG_DIR_NAME:
            try:
                make_file_symlink(self / "settings.json", decoy_target)
                planted.append(True)
            except OSError:
                planted.append(False)
        return result

    monkeypatch.setattr(Path, "mkdir", _mkdir_then_plant)

    workspace, _built = run_workspace.mint_cfg1_run_workspace(git_executable=git_executable)
    try:
        with pytest.raises(Cfg1PiConfigError) as excinfo:
            write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
        if not planted or not planted[0]:
            pytest.skip("this platform grants no unprivileged file-symlink creation")
        assert excinfo.value.reason_code == "CONFIG_FILE_ALREADY_EXISTS"
        # The decoy is never followed or overwritten.
        assert decoy_target.read_text(encoding="utf-8") == '{"attacker": "controlled"}'
    finally:
        # A planted symlink now sits inside the owned tree; tear down without
        # depending on the frozen remover's own removal-verification handling
        # a member it never wrote, mirroring the FU1 redirect-test pattern.
        import shutil

        run_workspace.discard_cfg1_run_workspace(workspace)
        shutil.rmtree(Path(workspace.experiment_root), ignore_errors=True)


def test_f4_a_preexisting_symlink_at_settings_json_path_inside_a_fresh_directory_is_refused(
    tmp_path, monkeypatch, git_executable
):
    """A tighter reproduction: hold ``config_dir.mkdir`` back to keep the race
    window open, plant the symlink, THEN attempt the create -- proving the
    exclusive create (not merely the directory's own ``exist_ok=False``)
    is what refuses it.

    **Both symlink shapes, and the second one is why this test changed
    (CFG1-IMPL-FU3).** FU2 closed this with ``open(path, "x")`` and proved it
    against a symlink whose TARGET ALREADY EXISTED -- where ``CREATE_NEW``
    refuses for a reason that has nothing to do with the link. Against a
    symlink whose target does NOT exist, ``open(path, "x")`` on win32
    **followed the link and created the target**, because it is
    ``CreateFileW(CREATE_NEW)`` underneath and name resolution walks the
    reparse point. FU15's step-6 create adds
    ``FILE_FLAG_OPEN_REPARSE_POINT``, which stops resolution at the link, so
    both shapes now refuse and neither target receives anything.
    """
    from pathlib import Path

    from conftest import make_file_symlink
    from pi_harness_cfg1 import win_config_authority as win

    if not win.PLATFORM_SUPPORTED:
        pytest.skip("the FU15 exclusive-create authority is win32-only")

    existing_target = tmp_path / "decoy_settings_target_2.json"
    existing_target.write_text('{"attacker": "controlled"}', encoding="utf-8")
    dangling_target = tmp_path / "decoy_settings_target_3.json"
    assert not dangling_target.exists()

    workspace, _built = run_workspace.mint_cfg1_run_workspace(git_executable=git_executable)
    try:
        config_dir_str, settings_path_str, models_path_str = (
            config_issuance.derive_cfg1_config_paths(workspace)
        )
        Path(config_dir_str).mkdir(parents=False, exist_ok=False)
        try:
            make_file_symlink(Path(settings_path_str), existing_target)
            make_file_symlink(Path(models_path_str), dangling_target)
        except OSError:
            pytest.skip("this platform grants no unprivileged file-symlink creation")

        for name in ("settings.json", "models.json"):
            with pytest.raises(win.Cfg1DirectoryAuthorityError) as excinfo:
                win.create_exclusive_child(config_dir=config_dir_str, name=name)
            assert excinfo.value.reason_code == "CONFIG_FILE_ALREADY_EXISTS"

        # Neither target is followed: the existing one is untouched, and the
        # dangling one is never brought into existence.
        assert existing_target.read_text(encoding="utf-8") == '{"attacker": "controlled"}'
        assert not dangling_target.exists(), (
            "the exclusive create followed a dangling symlink and created a "
            "file outside the owned root"
        )
        assert win.held_child_count() == 0
    finally:
        run_workspace.discard_cfg1_run_workspace(workspace)
        import shutil

        shutil.rmtree(Path(workspace.experiment_root), ignore_errors=True)


def test_f4_pythons_own_exclusive_create_is_not_symlink_safe_on_win32(tmp_path):
    """The evidence that made CFG1-IMPL-FU3 replace FU2's mechanism.

    FU2's source claimed ``O_CREAT | O_EXCL`` "never follows an existing
    symlink to write through it", and Sec. 37.2's W10 repeats that claim. This
    test establishes, on the real platform, that the claim is FALSE for a
    dangling symlink -- so the invariant FU2 and Sec. 37.3.4 row 3 state can
    only be satisfied by the ``FILE_FLAG_OPEN_REPARSE_POINT`` create FU15's
    step 6 now uses. If a future Windows makes ``open(path, "x")`` refuse
    here, this test fails loudly and the residual can be re-reviewed rather
    than silently carried.
    """
    import os

    if os.name != "nt":
        pytest.skip("this is a win32 name-resolution fact")

    target = tmp_path / "outside_the_root.json"
    link = tmp_path / "planted.json"
    try:
        os.symlink(str(target), str(link))
    except (OSError, NotImplementedError):
        pytest.skip("this platform grants no unprivileged file-symlink creation")

    wrote_through = False
    try:
        with open(link, "x", encoding="utf-8") as handle:
            handle.write("ENDPOINT")
        wrote_through = True
    except FileExistsError:
        pass

    assert wrote_through is True and target.exists(), (
        "open(path, 'x') refused a dangling symlink on this platform; W10's "
        "symlink clause may now hold and FU3's correction can be re-reviewed"
    )
    assert target.read_text(encoding="utf-8") == "ENDPOINT"


def test_f4_genuine_write_is_still_byte_identical_after_the_exclusive_create_change(
    git_executable,
):
    """Positive control: the exclusive-create switch changes nothing about the
    genuine, untampered write path's own bytes (T-1 must keep holding).
    """
    from pathlib import Path

    from qualification.i2_pi_config import write_qualification_pi_config
    from pi_harness_cfg1.cfg1_pi_config import write_cfg1_pi_config
    from pi_harness_cfg1.identity import CFG1_MODEL_ID

    import tempfile

    workspace, _built = run_workspace.mint_cfg1_run_workspace(git_executable=git_executable)
    try:
        generated = write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
        with tempfile.TemporaryDirectory() as frozen_root:
            frozen = write_qualification_pi_config(
                frozen_root, model_id=CFG1_MODEL_ID, base_url=SYNTHETIC_BASE_URL
            )
            assert (
                Path(generated.settings_path).read_bytes()
                == Path(frozen.settings_path).read_bytes()
            )
            assert (
                Path(generated.models_path).read_bytes() == Path(frozen.models_path).read_bytes()
            )
    finally:
        run_workspace.remove_cfg1_run_workspace(workspace)


def test_f4_directory_level_replacement_remains_a_documented_residual_not_a_false_claim():
    """This is NOT a security proof -- it is the honest, mechanical record of
    what CFG1 does NOT claim to close, updated for FU15/FU15-D1.

    FU2's own source comment described the directory-level half of the
    config-generation TOCTOU as an open design question needing a
    Windows-specific directory-handle authority "this design has never
    frozen". FU15 froze that authority and FU15-D1 accepted ``R-WINDOW`` as a
    documented, bounded residual (``D-A`` = A1), so the source must now cite
    that resolution rather than continue to read as an unstated gap -- and it
    must still never claim the residual was eliminated. This test fails loudly
    in EITHER direction.
    """
    from pi_harness_cfg1 import cfg1_pi_config, win_config_authority

    source = inspect.getsource(cfg1_pi_config.write_cfg1_pi_config)
    # The resolution is cited, by name, where the gap used to be described.
    assert "R-WINDOW" in source
    assert "FU15-D1" in source
    assert "ACCEPTED as a" in source and "residual" in source
    # And the claim it must never make, stated as a prohibition in the source
    # itself rather than merely absent from it.
    assert "never" in source and "be described as proving the pinned object" in source
    assert "must never be called secure, isolated" in source

    module_source = inspect.getsource(win_config_authority)
    assert "R-WINDOW" in module_source
    assert "not closed and is not claimed closed" in module_source
    # NtCreateFile stays unauthorized (Sec. 37.3.7's A2 was NOT taken), and
    # nothing in this module loads or calls the native ntdll surface.
    assert 'WinDLL("ntdll' not in module_source
    assert "NtCreateFile" not in module_source.replace(
        "``NtCreateFile`` is the only mechanism that would close ``R-WINDOW`` and is", ""
    ).replace("NtCreateFile", "", 1)
