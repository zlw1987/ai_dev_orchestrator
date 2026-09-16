"""CFG1-IMPL-FU1: adversarial regressions for Findings 1-4.

Design authority: ``5F3B-HARNESS-CFG1-DESIGN`` through FU14 (frozen), reviewed
against implementation commit ``802aa0b``. This module adds ONLY the
regressions the FU1 review requires; it does not re-litigate anything already
covered by the pre-existing offline suite.

Pure Python, ``tmp_path``/``cfg1_package_dir``-scoped, no live Pi/network/
model/credential activity -- the same discipline every other module in this
suite follows (see ``conftest.py``).
"""

from __future__ import annotations

import inspect
import os
from pathlib import Path

import pytest
from cfg1_builders import happy_observations
from cfg1_doubles import SYNTHETIC_BASE_URL, SYNTHETIC_CREDENTIAL, build_doubled_ports
from conftest import make_directory_redirect, make_file_symlink

from pi_harness_cfg1 import classification, run_executor, run_workspace, stage_output, stage_runner
from pi_harness_cfg1.run_contract import Cfg1RunAdmission
from pi_harness_cfg1.schedule import _schedule_arm_for, _schedule_block_position

#: Sec. adversarial review's own list: malformed-truthy values that must never
#: be coerced into a plausible ``bool`` or ``int``.
_MALFORMED_TRUTHY_VALUES = (1, 0, "true", "false", [], object())


class _CustomTruthyInt:
    """A custom object claiming to be int-like -- ``int(x)`` would accept it."""

    def __int__(self) -> int:
        return 999

    def __index__(self) -> int:
        return 999

    def __bool__(self) -> bool:
        return True


# ---------------------------------------------------------------------------
# Finding 1 -- evidence-provenance bypass via a caller-supplied run_executor
# ---------------------------------------------------------------------------


def test_finding1_the_authoritative_entry_has_no_executor_or_ports_seam():
    """A caller cannot even ATTEMPT to name a substitute executor or ports."""
    parameters = inspect.signature(stage_runner.run_cfg1_stage).parameters
    assert list(parameters) == ["authority"]

    with pytest.raises(TypeError):
        stage_runner.run_cfg1_stage(object(), run_executor=lambda admission: None)
    with pytest.raises(TypeError):
        stage_runner.run_cfg1_stage(object(), ports=object())
    with pytest.raises(TypeError):
        stage_runner.run_cfg1_stage(object(), _internal_probe=object())


def test_finding1_the_authoritative_entry_binds_the_genuine_executor_mechanically():
    """A source-level proof, mirroring T-101's technique.

    ``run_cfg1_stage`` is proven to obtain its executor from
    :func:`run_executor.bind_genuine_cfg1_run_executor` -- the ONE mint-
    registry-backed, unforgeable binder -- and to delegate to the shared
    orchestration routine with that genuine handle, never a bare callable of
    its own construction.
    """
    source = inspect.getsource(stage_runner.run_cfg1_stage)
    assert "from .run_executor import bind_genuine_cfg1_run_executor" in source
    assert "bind_genuine_cfg1_run_executor()" in source
    assert "_run_cfg1_stage_with_injected_executor(" in source
    assert "run_executor" not in inspect.signature(stage_runner.run_cfg1_stage).parameters


def test_finding1_a_hand_built_genuine_executor_lookalike_is_refused():
    """A caller cannot construct ``Cfg1GenuineRunExecutor`` with a fake callable."""
    calls: list[object] = []

    with pytest.raises(run_executor.Cfg1GenuineRunExecutorError) as excinfo:
        run_executor.Cfg1GenuineRunExecutor(
            token="not-a-real-token", call=lambda admission: calls.append(admission)
        )
    assert excinfo.value.reason_code == "UNKNOWN_EXECUTOR_TOKEN"
    assert calls == []


def test_finding1_the_authoritative_entry_completes_via_the_genuine_binder(
    make_authority, monkeypatch
):
    """Positive control: ``run_cfg1_stage`` really does drive the mint/dispatch
    wiring end to end, with the genuine binder's OWN live-composition points
    (``execute_cfg1_run``/``default_cfg1_run_ports``) swapped for synthetic
    stand-ins -- never with a caller-supplied executor of any kind.
    """
    from cfg1_builders import happy_observations
    from pi_harness_cfg1.arms import ARM_SHAPE
    from pi_harness_cfg1.run_contract import Cfg1RunOutcome
    from qualification.safety import ArtifactSafetyContext

    authority = make_authority("S1-X1")

    def _fake_execute_cfg1_run(admission, *, ports):
        assert ports == "genuine-ports-sentinel"
        return Cfg1RunOutcome(
            observations=happy_observations(
                runtime_reported_compat_shape=ARM_SHAPE[admission.arm_id]
            ),
            safety=ArtifactSafetyContext.none_declared(),
            live_references_released=True,
        )

    monkeypatch.setattr(run_executor, "execute_cfg1_run", _fake_execute_cfg1_run)
    monkeypatch.setattr(
        run_executor,
        "default_cfg1_run_ports",
        lambda *, ambient_environ: "genuine-ports-sentinel",
    )

    result = stage_runner.run_cfg1_stage(authority)
    assert result.disposition == "STAGE_COMPLETED"


def test_finding1_genuine_authority_plus_fake_executor_cannot_reach_the_genuine_root(
    make_authority, monkeypatch
):
    """T-25-style adversarial construction #1: genuine authority + fake executor.

    Even holding a genuine, ACTIVE ``CFG1StageOutputAuthority`` and an
    "all green" synthetic executor, the offline dependency-injection seam
    refuses outright the moment ``stage_output``'s results-root capture looks
    like an un-retargeted (production-like) installation -- BEFORE the fake
    executor is ever invoked, before the authority is even type-checked, and
    before any filesystem operation of any kind.
    """
    authority = make_authority("S1-X1")  # genuine, minted under the synthetic root

    # Simulate a production-like (never retargeted) capture.
    monkeypatch.setattr(
        stage_output,
        "_CAPTURED_PACKAGE_DIR",
        stage_runner._GENUINE_PACKAGE_DIRECTORY,
        raising=True,
    )

    invoked: list[object] = []

    with pytest.raises(stage_runner.Cfg1StageRunnerError) as excinfo:
        stage_runner._run_cfg1_stage_with_injected_executor(
            authority, run_executor=lambda admission: invoked.append(admission)
        )
    assert (
        excinfo.value.reason_code
        == "OFFLINE_EXECUTOR_INJECTION_REFUSED_IN_GENUINE_PACKAGE_ROOT"
    )
    assert invoked == []  # the fake executor was never reached, let alone run


def test_finding1_genuine_authority_plus_fake_live_ports_cannot_author_evidence(
    make_authority, monkeypatch
):
    """Adversarial construction #2: genuine authority + substitute live ports.

    A caller cannot reach the genuine L1-L28 executor's OWN live-port
    injection point from the stage runner at all: ``run_cfg1_stage`` has no
    ``ports`` parameter, and the offline seam's ``run_executor`` parameter
    takes a bound callable, never a ``Cfg1RunPorts`` instance -- so there is
    no supported path from "holds an authority" to "supplies live ports" that
    produces authoritative evidence.
    """
    authority = make_authority("S1-X1")
    monkeypatch.setattr(
        stage_output,
        "_CAPTURED_PACKAGE_DIR",
        stage_runner._GENUINE_PACKAGE_DIRECTORY,
        raising=True,
    )

    fake_ports = object()  # stands in for a caller-selected Cfg1RunPorts
    with pytest.raises(stage_runner.Cfg1StageRunnerError) as excinfo:
        stage_runner._run_cfg1_stage_with_injected_executor(
            authority, run_executor=fake_ports
        )
    assert (
        excinfo.value.reason_code
        == "OFFLINE_EXECUTOR_INJECTION_REFUSED_IN_GENUINE_PACKAGE_ROOT"
    )


def test_finding1_the_offline_seam_still_works_once_genuinely_retargeted(make_authority):
    """Positive control: the fixture-retargeted (test) path is unaffected."""
    from cfg1_builders import synthetic_run_executor

    authority = make_authority("S1-X1")
    result = stage_runner._run_cfg1_stage_with_injected_executor(
        authority, run_executor=synthetic_run_executor()
    )
    assert result.disposition == "STAGE_COMPLETED"


# ---------------------------------------------------------------------------
# Finding 2 -- generated-config issuance bound to a genuine ownership handle
# ---------------------------------------------------------------------------


def test_finding2_register_and_verify_take_no_path_parameter_at_all():
    from pi_harness_cfg1.config_issuance import register_config_issuance, verify_config_issuance

    register_params = inspect.signature(register_config_issuance).parameters
    for forbidden in ("config_dir", "settings_path", "models_path"):
        assert forbidden not in register_params
    verify_params = inspect.signature(verify_config_issuance).parameters
    for forbidden in ("config_dir", "settings_path", "models_path"):
        assert forbidden not in verify_params


def test_finding2_an_arbitrary_external_directory_cannot_be_named(tmp_path):
    """There is no supported call shape through which a bare path authorizes."""
    from pi_harness_cfg1.cfg1_pi_config import Cfg1PiConfigError, write_cfg1_pi_config
    from pi_harness_cfg1.config_issuance import ConfigIssuanceError, derive_cfg1_config_paths

    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "settings.json").write_text("{}", encoding="utf-8")
    (foreign / "models.json").write_text("{}", encoding="utf-8")

    with pytest.raises(Cfg1PiConfigError) as excinfo:
        write_cfg1_pi_config(str(foreign), arm_id="Q", base_url=SYNTHETIC_BASE_URL)
    assert excinfo.value.reason_code == "NOT_A_CFG1_RUN_WORKSPACE"

    with pytest.raises(ConfigIssuanceError) as excinfo:
        derive_cfg1_config_paths(str(foreign))
    assert excinfo.value.reason_code == "NOT_A_CFG1_RUN_WORKSPACE"


def test_finding2_a_pre_existing_config_directory_is_refused_not_adopted(
    git_executable,
):
    """Arbitrary pre-existing settings.json/models.json can never be adopted.

    The mkdir that establishes the config directory is ``exist_ok=False``: an
    attacker (or stale leftover) that pre-seeds the derived path with foreign
    content is refused at creation, never silently treated as this run's own.
    """
    from pi_harness_cfg1.cfg1_pi_config import CFG1_CONFIG_DIR_NAME, Cfg1PiConfigError, write_cfg1_pi_config

    workspace, _built = run_workspace.mint_cfg1_run_workspace(git_executable=git_executable)
    try:
        preexisting = Path(workspace.experiment_root) / CFG1_CONFIG_DIR_NAME
        preexisting.mkdir()
        (preexisting / "settings.json").write_text('{"malicious": true}', encoding="utf-8")
        (preexisting / "models.json").write_text('{"malicious": true}', encoding="utf-8")

        with pytest.raises(Cfg1PiConfigError) as excinfo:
            write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
        assert excinfo.value.reason_code == "CONFIG_DIR_NOT_CREATED"
    finally:
        run_workspace.remove_cfg1_run_workspace(workspace)


def test_finding2_a_genuine_token_is_refused_under_a_substituted_directory(
    tmp_path, git_executable
):
    """Genuine token + substituted directory: rebind the RECORD, not the call.

    Even directly manipulating the module's own registry to point a genuine
    token's record at a foreign directory is caught: the consumption boundary
    re-derives the expected paths from the workspace itself and refuses when
    the registry's own recorded paths no longer agree with that derivation.
    """
    from pi_harness_cfg1 import config_issuance
    from pi_harness_cfg1.cfg1_pi_config import write_cfg1_pi_config

    workspace, _built = run_workspace.mint_cfg1_run_workspace(git_executable=git_executable)
    try:
        config = write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
        record = config_issuance._ISSUED[config.issuance_token]

        foreign = tmp_path / "foreign_substitute"
        foreign.mkdir()
        (foreign / "settings.json").write_text(
            Path(config.settings_path).read_text(encoding="utf-8"), encoding="utf-8"
        )
        substituted = config_issuance._IssuanceRecord(
            run_workspace_nonce=record.run_workspace_nonce,
            config_dir=str(foreign),
            settings_path=str(foreign / "settings.json"),
            models_path=str(foreign / "models.json"),
            arm_id=record.arm_id,
            provider_id=record.provider_id,
            model_id=record.model_id,
            settings_sha256=record.settings_sha256,
            models_sha256=record.models_sha256,
        )
        config_issuance._ISSUED[config.issuance_token] = substituted
        try:
            with pytest.raises(config_issuance.ConfigIssuanceError) as excinfo:
                config_issuance.verify_config_issuance(
                    token=config.issuance_token, workspace=workspace
                )
            assert excinfo.value.reason_code == "ISSUANCE_PATH_MISMATCH"
        finally:
            config_issuance._ISSUED[config.issuance_token] = record
    finally:
        run_workspace.remove_cfg1_run_workspace(workspace)


def test_finding2_post_issuance_directory_redirect_is_refused(tmp_path, git_executable):
    """Post-issuance symlink/junction replacement of the config directory."""
    import shutil

    from pi_harness_cfg1 import config_issuance
    from pi_harness_cfg1.cfg1_pi_config import write_cfg1_pi_config

    workspace, _built = run_workspace.mint_cfg1_run_workspace(git_executable=git_executable)
    try:
        config = write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
        config_issuance.verify_config_issuance(
            token=config.issuance_token, workspace=workspace
        )  # genuine, passes first

        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        config_dir = Path(config.config_dir)
        shutil.rmtree(config_dir)
        try:
            make_directory_redirect(config_dir, elsewhere)
        except OSError:
            pytest.skip(
                "this platform grants neither symlink nor junction creation"
            )

        with pytest.raises(config_issuance.ConfigIssuanceError) as excinfo:
            config_issuance.verify_config_issuance(
                token=config.issuance_token, workspace=workspace
            )
        assert excinfo.value.reason_code == "GENERATED_PATH_REDIRECTED"
    finally:
        # The redirected path is no longer a genuine, removable CFG1 tree
        # member; only discard the in-memory records so the run-workspace
        # itself can still be torn down cleanly.
        config_issuance.discard_config_issuance(config.issuance_token)
        run_workspace.discard_cfg1_run_workspace(workspace)
        try:
            os.unlink(config.config_dir)
        except OSError:
            pass
        shutil.rmtree(Path(workspace.experiment_root), ignore_errors=True)


def test_finding2_post_issuance_settings_file_symlink_is_refused(tmp_path, git_executable):
    """Post-issuance symlink replacement of ``settings.json`` itself."""
    from pi_harness_cfg1 import config_issuance
    from pi_harness_cfg1.cfg1_pi_config import write_cfg1_pi_config

    workspace, _built = run_workspace.mint_cfg1_run_workspace(git_executable=git_executable)
    try:
        config = write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
        config_issuance.verify_config_issuance(
            token=config.issuance_token, workspace=workspace
        )

        decoy = tmp_path / "decoy_settings.json"
        decoy.write_text(Path(config.settings_path).read_text(encoding="utf-8"), encoding="utf-8")

        settings_path = Path(config.settings_path)
        settings_path.unlink()
        try:
            make_file_symlink(settings_path, decoy)
        except OSError:
            pytest.skip("this platform grants no unprivileged file-symlink creation")

        with pytest.raises(config_issuance.ConfigIssuanceError) as excinfo:
            config_issuance.verify_config_issuance(
                token=config.issuance_token, workspace=workspace
            )
        assert excinfo.value.reason_code == "GENERATED_PATH_REDIRECTED"
    finally:
        run_workspace.remove_cfg1_run_workspace(workspace)


def test_finding2_genuine_positive_control_end_to_end(git_executable):
    """A wholly genuine issuance passes every re-proof, repeatedly."""
    from pi_harness_cfg1 import config_issuance
    from pi_harness_cfg1.cfg1_pi_config import write_cfg1_pi_config

    workspace, _built = run_workspace.mint_cfg1_run_workspace(git_executable=git_executable)
    try:
        config = write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
        for _ in range(3):
            record = config_issuance.verify_config_issuance(
                token=config.issuance_token, workspace=workspace
            )
            assert record.arm_id == "Q"
    finally:
        run_workspace.remove_cfg1_run_workspace(workspace)


# ---------------------------------------------------------------------------
# Finding 3 -- a short write can never reach EMISSION_CONFIRMED
# ---------------------------------------------------------------------------


class _FakeHandle:
    """A ``write``-only fake; each test supplies the sequence of return values."""

    def __init__(self, returns):
        self._returns = list(returns)
        self.calls: list[bytes] = []
        self.closed = False

    def write(self, data: bytes):
        self.calls.append(bytes(data))
        value = self._returns.pop(0)
        if isinstance(value, Exception):
            raise value
        return value

    def flush(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True


@pytest.mark.parametrize(
    "returns,expected_reason",
    [
        ([3, 0], "SHORT_WRITE_NO_PROGRESS"),  # short positive count, then stalls
        ([0], "SHORT_WRITE_NO_PROGRESS"),  # zero progress
        ([None], "SHORT_WRITE_MALFORMED_PROGRESS"),  # None
        ([-1], "SHORT_WRITE_NO_PROGRESS"),  # negative count
        ([True], "SHORT_WRITE_MALFORMED_PROGRESS"),  # bool
        (["5"], "SHORT_WRITE_MALFORMED_PROGRESS"),  # non-int
        ([999], "SHORT_WRITE_PROGRESS_EXCEEDS_REMAINING"),  # larger than remaining
        ([4, 0], "SHORT_WRITE_NO_PROGRESS"),  # partial, then zero progress
    ],
)
def test_finding3_write_all_never_confirms_a_short_or_malformed_write(
    returns, expected_reason
):
    from pi_harness_cfg1.writers import Cfg1WriterError, _write_all

    data = b"0123456789"  # 10 bytes; the first short return is always < 10
    handle = _FakeHandle(returns)
    with pytest.raises(Cfg1WriterError) as excinfo:
        _write_all(handle, data)
    assert excinfo.value.reason_code == expected_reason


def test_finding3_partial_progress_followed_by_an_exception_never_confirms():
    from pi_harness_cfg1.writers import _write_all

    handle = _FakeHandle([4, OSError("disk full")])
    with pytest.raises(OSError):
        _write_all(handle, b"0123456789")
    # The first call saw all 10 bytes and made partial progress (4); the
    # second call, for the remaining 6, is what raised.
    assert handle.calls == [b"0123456789", b"456789"]


def test_finding3_a_genuine_multi_chunk_short_write_still_completes():
    """A short write is not itself forbidden -- only a NON-progressing one is."""
    from pi_harness_cfg1.writers import _write_all

    handle = _FakeHandle([4, 3, 3])  # 4 + 3 + 3 == 10, drained across 3 calls
    _write_all(handle, b"0123456789")
    assert b"".join(handle.calls[:1]) == b"0123456789"  # first call sees ALL data
    assert len(handle.calls) == 3


def test_finding3_end_to_end_short_write_never_reaches_emission_confirmed(
    make_authority, monkeypatch
):
    """The full ten-step writer, with a genuinely short ``handle.write``."""
    from pi_harness_cfg1 import writers
    from pi_harness_cfg1.halt import PHASE_FINAL_PATH_CREATED
    from cfg1_builders import run_payload
    from qualification.safety import ArtifactSafetyContext

    authority = make_authority("S1-X1")

    class _ShortWriteHandle:
        def __init__(self, real_handle):
            self._real = real_handle
            self.first = True

        def write(self, data: bytes):
            if self.first:
                self.first = False
                return max(1, len(data) - 1)  # one byte short, first call
            raise AssertionError("a second write call means the short write leaked")

        def flush(self):
            pass

        def close(self):
            self._real.close()

    real_open = writers._open_exclusive

    def _open_exclusive(path):
        handle = real_open(path)
        return _ShortWriteHandle(handle)

    monkeypatch.setattr(writers, "_open_exclusive", _open_exclusive)

    result = writers.emit_cfg1_run_record(
        authority,
        run_ordinal=1,
        payload=run_payload(stage_execution_id=authority.stage_execution_id, run_ordinal=1),
        lifecycle_all_closed=True,
        safety=ArtifactSafetyContext.none_declared(),
    )
    assert result.emission_status != "RECORD_EMITTED"
    assert result.phase_reached != "EMISSION_CONFIRMED"
    assert result.phase_reached == PHASE_FINAL_PATH_CREATED


# ---------------------------------------------------------------------------
# Finding 4 -- malformed truthy live facts are never coerced
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", list(_MALFORMED_TRUTHY_VALUES) + [_CustomTruthyInt()])
def test_finding4_exact_bool_never_truthiness_coerces(value):
    assert run_executor._exact_bool(value) is False
    assert run_executor._exact_bool(True) is True
    assert run_executor._exact_bool(False) is False


@pytest.mark.parametrize("value", list(_MALFORMED_TRUTHY_VALUES) + [_CustomTruthyInt(), -5, 3.5])
def test_finding4_exact_count_never_duck_type_coerces(value):
    if type(value) is int and value >= 0:
        pytest.skip("not an adversarial case for this helper")
    assert run_executor._exact_count(value) == 0
    assert run_executor._exact_count(5) == 5


@pytest.mark.parametrize("value", list(_MALFORMED_TRUTHY_VALUES) + [_CustomTruthyInt(), -5, 3.5])
def test_finding4_classification_exact_count_never_duck_type_coerces(value):
    if type(value) is int and value >= 0:
        pytest.skip("not an adversarial case for this helper")
    assert classification._exact_count(value) == 0
    assert classification._exact_count(5) == 5


def test_finding4_a_malformed_route_reachable_fact_refuses_pre_dispatch(
    git_executable, monkeypatch
):
    """A truthy-but-non-bool ``route.reachable`` must never admit the run."""
    from dataclasses import dataclass

    from cfg1_doubles import seam_digests_all_match

    from pi_harness_cfg1.run_executor import execute_cfg1_run

    seam_digests_all_match(monkeypatch)

    @dataclass
    class _MalformedRoute:
        reachable: object = "false"  # truthy in Python, but NOT a bool
        configured_model_served: bool = True

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
    ports, _made = build_doubled_ports(
        git_executable=git_executable,
        overrides={"observe_route": lambda **_kwargs: _MalformedRoute()},
    )
    outcome = execute_cfg1_run(admission, ports=ports)
    assert outcome.observations["pre_dispatch_refusal_code"] == "ROUTE_UNAVAILABLE"
    assert outcome.observations["route_reachable"] is False


def test_finding4_a_malformed_h1_matched_fact_refuses_pre_dispatch(
    git_executable, monkeypatch
):
    from dataclasses import dataclass

    from cfg1_doubles import seam_digests_all_match

    from pi_harness_cfg1.run_executor import execute_cfg1_run

    seam_digests_all_match(monkeypatch)

    @dataclass
    class _MalformedHandshake:
        matched: object = 1  # truthy, but NOT a bool

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
        overrides={
            "evaluate_extension_identity": lambda **_kwargs: _MalformedHandshake()
        },
    )
    outcome = execute_cfg1_run(admission, ports=ports)
    assert outcome.observations["pre_dispatch_refusal_code"] == "H1_MISMATCH"
    assert outcome.observations["h1_extension_identity_matched"] is False


def test_finding4_a_malformed_broker_worker_termination_fact_fails_closed():
    """L23's own adapter: a truthy-but-non-bool lifecycle fact never proves closure."""
    assert run_executor._exact_bool("false") is False
    # And the exact reduction used at L23 for the "absent" default is preserved.
    assert run_executor._exact_bool(True) is True


def test_finding4_a_malformed_broker_lifecycle_dict_fails_closed_end_to_end(
    git_executable, monkeypatch
):
    """L23, end to end: a broker whose OWN teardown adapter returns malformed
    truthy lifecycle facts must never let ``broker_worker_terminated_or_absent``
    or ``broker_pending_unreaped_zero`` read as proven-closed.
    """
    from cfg1_doubles import FakeBroker, seam_digests_all_match

    from pi_harness_cfg1.run_executor import execute_cfg1_run

    seam_digests_all_match(monkeypatch)

    class _MalformedBroker(FakeBroker):
        def __init__(self):
            super().__init__()
            self.lifecycle = {
                "state_reached": "CLOSED",
                "pending_operations_unreaped": "0",  # truthy string, NOT an int
                "worker_termination_observed": "false",  # truthy string, NOT a bool
            }

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
    ports, _made = build_doubled_ports(
        git_executable=git_executable,
        overrides={"build_broker": lambda **_kwargs: _MalformedBroker()},
    )
    outcome = execute_cfg1_run(admission, ports=ports)
    assert outcome.observations["broker_worker_terminated_or_absent"] is False
    assert outcome.observations["broker_pending_unreaped_zero"] is False


def test_finding4_a_malformed_verification_passed_fact_never_reads_as_passed():
    """Directly exercises the reduction L26 now applies to every outcome field."""
    for malformed in _MALFORMED_TRUTHY_VALUES:
        assert run_executor._exact_bool(malformed) is False


def test_finding4_source_audit_no_bare_bool_or_int_coercion_remains():
    """Re-run the post-fix source audit: every remaining ``bool(``/``int(`` is
    either this module's own helper definition, a container-truthiness check
    on a dict/response (never a scalar fact), or a false positive substring
    match (e.g. ``point(`` inside ``reparse_point(``)."""
    run_executor_source = inspect.getsource(run_executor)
    classification_source = inspect.getsource(classification)
    # The only remaining literal `bool(` call is the intentional container
    # existence check `bool(response)` inside the H1 handshake adapter.
    bool_calls = [
        line
        for line in run_executor_source.splitlines()
        if "bool(" in line and "_exact_bool(" not in line and "def _exact_bool" not in line
        and "``bool(" not in line
    ]
    assert bool_calls == ["            matched=bool(response)"], bool_calls
    int_calls = [
        line
        for line in classification_source.splitlines()
        if "int(" in line
        and "_exact_count(" not in line
        and "def _exact_count" not in line
        and "``int(" not in line
    ]
    assert int_calls == [], int_calls
