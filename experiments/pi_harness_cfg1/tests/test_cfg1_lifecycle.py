"""T-11 and T-12: the L0-L28 state machine, and ownership by handle only.

Every failure is injected at a real step, through the port that owns it, and
the resulting refusal code, refused step, closure facts and classification are
checked against exactly what Sec. 16.2 and Sec. 18 declare.

Every workspace here is a GENUINE, freshly-minted disposable repository under
an ``ar2``-created root -- never a double, because workspace ownership is
deliberately not a port. Everything live (broker, Pi runtime, route, Node) is
a synthetic double: no process, no pipe, no socket, no model, no credential.
"""

from __future__ import annotations

from pathlib import Path

import inspect

import pytest
from cfg1_doubles import (
    SYNTHETIC_BASE_URL,
    FakeBroker,
    FakeHandshake,
    FakeSupervisor,
    FakeVerificationOutcome,
    build_doubled_ports,
    probe_facts_for_arm,
    seam_digests_all_match,
)

from pi_harness_cfg1 import run_workspace
from pi_harness_cfg1.run_contract import Cfg1RunAdmission
from pi_harness_cfg1.run_executor import execute_cfg1_run
from pi_harness_cfg1.schedule import _schedule_arm_for, _schedule_block_position


@pytest.fixture()
def admission():
    block, position = _schedule_block_position("S1", 1)
    return Cfg1RunAdmission(
        stage_id="S1",
        stage_execution_id="S1-X1",
        run_ordinal=1,
        arm_id=_schedule_arm_for("S1", 1),
        block=block,
        position=position,
        run_id="a" * 32,
    )


@pytest.fixture(autouse=True)
def _seam_digests(monkeypatch):
    seam_digests_all_match(monkeypatch)


def _run(admission, git_exe, **overrides):
    """``git_exe`` is named to avoid colliding with the ``git_executable`` PORT.

    A test that overrides the port passes ``git_executable=<raiser>`` in
    ``overrides``; the positional argument is the real resolved executable the
    other ports still need.
    """
    ports, made = build_doubled_ports(git_executable=git_exe, overrides=overrides)
    return execute_cfg1_run(admission, ports=ports), made


def _raiser(error):
    def _raise(*_args, **_kwargs):
        raise error

    return _raise


# ---------------------------------------------------------------------------
# The clean path -- the control every injected failure is measured against
# ---------------------------------------------------------------------------


def test_the_clean_path_closes_every_resource_and_classifies_inactive(
    admission, git_executable
):
    from pi_harness_cfg1.classification import classify_cfg1_run
    from pi_harness_cfg1.records import build_cfg1_run_payload

    outcome, made = _run(admission, git_executable)
    observations = outcome.observations

    assert observations["pre_dispatch_refusal_code"] is None
    assert observations["refused_at_step"] is None
    assert observations["dispatch_state"] == "CONFIRMED_SENT"
    assert observations["prompt_writes"] == 1
    assert observations["manipulation_check_agrees"] is True
    assert observations["runtime_reported_compat_shape"] == "ABSENT"  # arm Q
    assert observations["lifecycle_all_closed"] is True
    assert observations["lifecycle_failure_steps"] == []
    assert observations["verification_attempted"] is True
    assert observations["verification_skip_reason"] is None

    # Closure genuinely ran: the runtime and broker were both torn down, the
    # generated material was verified-unlinked, and the workspace is gone.
    assert made["supervisor"].shutdown_calls == 1
    assert made["broker"].shutdown_calls == 1
    assert observations["generated_config_scrub_verified"] is True
    assert observations["extension_binding_scrub_verified"] is True
    assert observations["workspace_removed_verified"] is True
    assert not Path(made["workspace"].experiment_root).exists()
    # ...and the run left no registry entry behind (Sec. 19.1 item 4).
    assert run_workspace.minted_workspace_count() == 0

    payload = build_cfg1_run_payload(
        stage_id="S1",
        stage_execution_id="S1-X1",
        run_ordinal=1,
        observations=observations,
    )
    assert classify_cfg1_run(payload) == "INACTIVE"


# ---------------------------------------------------------------------------
# T-11 -- one injected failure per step, against Sec. 16.2's own refusal codes
# ---------------------------------------------------------------------------

# FU1 (AMEND1 AMD-1): L1 has no identity-probe port any more -- the static Pi
# identity proof is not a port, and its three anticipated refusals (and its
# unexpected-raise boundaries) are exercised by FU1 Tests A and G. L1's one
# remaining port is Git resolution.
_PRE_RESOURCE_INJECTIONS = [
    ("L1", "git_executable", "OFFLINE_PREFLIGHT_FAILED"),
    ("L2", "mint_workspace", "WORKSPACE_BASELINE_FAILED"),
    ("L4", "read_connection", "CREDENTIAL_BOUNDARY_FAILED"),
    ("L7", "observe_route", "ROUTE_UNAVAILABLE"),
    ("L8", "mint_capability", "CAPABILITY_MINT_FAILED"),
    ("L9", "write_config", "CONFIG_GENERATION_FAILED"),
    ("L10", "build_broker", "BROKER_CONSTRUCTION_FAILED"),
    ("L11", "write_extension", "EXTENSION_GENERATION_FAILED"),
    ("L12", "build_environment", "CHILD_ENVIRONMENT_FAILED"),
]


@pytest.mark.parametrize(
    "step,port_name,expected_code",
    _PRE_RESOURCE_INJECTIONS,
    ids=[f"{s}-{p}" for s, p, _c in _PRE_RESOURCE_INJECTIONS],
)
def test_t11_a_raised_port_reaches_exactly_the_declared_refusal_code(
    step, port_name, expected_code, admission, git_executable
):
    outcome, _made = _run(
        admission,
        git_executable,
        **{port_name: _raiser(RuntimeError("a distinctive injected needle 7c1f"))},
    )
    observations = outcome.observations
    assert observations["pre_dispatch_refusal_code"] == expected_code
    assert observations["refused_at_step"] == step
    assert observations["prompt_writes"] == 0
    assert observations["dispatch_state"] == "NOT_ATTEMPTED"
    # Sec. 21.1's reduction rule: the raw value is dropped where it was caught.
    import json

    assert "7c1f" not in json.dumps(observations)
    assert "RuntimeError" not in json.dumps(observations)


def test_t11_l3_a_baseline_that_does_not_show_the_seeded_failure_refuses(
    admission, git_executable
):
    """CFG1-T1 declares a seeded failure; a PASSING baseline is not this task."""
    outcome, made = _run(
        admission,
        git_executable,
        run_verification=lambda *, workspace_root, args: FakeVerificationOutcome(
            return_code=0, passed=True, counts={"passed": 1, "failed": 0, "error": 0}
        ),
    )
    observations = outcome.observations
    assert observations["pre_dispatch_refusal_code"] == "WORKSPACE_BASELINE_FAILED"
    assert observations["refused_at_step"] == "L3"
    # The workspace WAS created, so closure removed it.
    assert observations["workspace_removed_verified"] is True
    assert not Path(made["workspace"].experiment_root).exists()


def test_t11_l3_an_unreaped_baseline_child_is_a_lifecycle_failure(
    admission, git_executable
):
    outcome, _made = _run(
        admission,
        git_executable,
        run_verification=lambda *, workspace_root, args: FakeVerificationOutcome(
            return_code=None, completed=False
        ),
    )
    observations = outcome.observations
    assert observations["refused_at_step"] == "L3"
    assert observations["verification_child_reaped_or_not_started"] is False
    assert observations["lifecycle_all_closed"] is False
    assert "L26" in observations["lifecycle_failure_steps"]


def test_t11_l5_a_structurally_invalid_base_url_refuses_at_the_secret_context(
    admission, git_executable
):
    outcome, _made = _run(
        admission,
        git_executable,
        read_connection=lambda: ("not-a-url", "cfg1-synthetic-key"),
    )
    assert outcome.observations["pre_dispatch_refusal_code"] == "SECRET_CONTEXT_FAILED"
    assert outcome.observations["refused_at_step"] == "L5"


def test_t11_l6_a_detection_matching_base_url_refuses_before_any_route_check(
    admission, git_executable
):
    route_calls: list = []

    def _observe_route(*, base_url, api_key, model_id):  # pragma: no cover
        route_calls.append(base_url)
        raise AssertionError("L7 must not run after an L6 refusal")

    outcome, _made = _run(
        admission,
        git_executable,
        read_connection=lambda: ("https://api.openai.com/v1", "k"),
        observe_route=_observe_route,
    )
    observations = outcome.observations
    assert observations["pre_dispatch_refusal_code"] == "BASE_URL_COMPAT_DETECTION_TRIGGERED"
    assert observations["refused_at_step"] == "L6"
    assert observations["base_url_compat_detection_clear"] is False
    assert route_calls == []


def test_t11_l7_an_unserved_model_refuses_before_any_live_resource_exists(
    admission, git_executable
):
    from cfg1_doubles import FakeRouteObservation

    broker_builds: list = []

    outcome, _made = _run(
        admission,
        git_executable,
        observe_route=lambda *, base_url, api_key, model_id: FakeRouteObservation(
            reachable=True, configured_model_served=False
        ),
        build_broker=lambda *, capability: broker_builds.append(capability),
    )
    observations = outcome.observations
    assert observations["pre_dispatch_refusal_code"] == "ROUTE_UNAVAILABLE"
    assert observations["route_reachable"] is True
    assert observations["route_configured_model_served"] is False
    # The route check is placed BEFORE broker/runtime creation precisely so a
    # route refusal creates no live resource at all.
    assert broker_builds == []
    assert observations["broker_resource_created"] is False
    assert observations["runtime_created"] is False


def test_t11_l13_a_broker_that_never_reaches_ready_still_gets_shut_down(
    admission, git_executable
):
    broker = FakeBroker(start_error=RuntimeError("injected start failure"))
    outcome, _made = _run(
        admission, git_executable, build_broker=lambda *, capability: broker
    )
    observations = outcome.observations
    assert observations["pre_dispatch_refusal_code"] == "BROKER_NOT_READY"
    assert observations["refused_at_step"] == "L13"
    assert observations["broker_reached_ready"] is False
    # Sec. 18 row 1: the broker resource exists, so L23 still runs.
    assert observations["broker_resource_created"] is True
    assert broker.shutdown_calls == 1
    assert observations["broker_state_closed"] is True


def test_t11_l14_a_failed_launch_leaves_no_runtime_to_tear_down(
    admission, git_executable
):
    supervisor = FakeSupervisor(launch_error=RuntimeError("injected launch failure"))
    outcome, made = _run(
        admission,
        git_executable,
        build_supervisor=lambda **kwargs: supervisor,
    )
    observations = outcome.observations
    assert observations["pre_dispatch_refusal_code"] == "RUNTIME_LAUNCH_FAILED"
    assert observations["refused_at_step"] == "L14"
    assert observations["runtime_created"] is False
    assert supervisor.shutdown_calls == 0  # nothing was created to shut down
    # The broker was created, so it still closes.
    assert made["broker"].shutdown_calls == 1


def test_t11_l15_h1_mismatch_and_correlation_failure_are_distinct_codes(
    admission, git_executable
):
    outcome, _made = _run(
        admission,
        git_executable,
        evaluate_extension_identity=lambda *, supervisor, extension: FakeHandshake(
            matched=False
        ),
    )
    assert outcome.observations["pre_dispatch_refusal_code"] == "H1_MISMATCH"
    assert outcome.observations["refused_at_step"] == "L15"

    outcome, _made = _run(
        admission,
        git_executable,
        evaluate_extension_identity=_raiser(RuntimeError("injected")),
    )
    assert outcome.observations["pre_dispatch_refusal_code"] == "RUNTIME_CORRELATION_FAILED"
    assert outcome.observations["refused_at_step"] == "L15"


def test_t11_l16_h2_mismatch_and_config_shape_mismatch_are_distinct_codes(
    admission, git_executable
):
    outcome, _made = _run(
        admission,
        git_executable,
        probe_facts=(False, "TRUE", "ABSENT", "medium"),
    )
    assert outcome.observations["pre_dispatch_refusal_code"] == "H2_MISMATCH"

    # The prompt is written ONLY to a runtime proven to have loaded THIS arm's
    # declared shape. Arm Q expects ABSENT; a runtime reporting arm R's shape
    # refuses pre-dispatch and never writes.
    outcome, made = _run(
        admission,
        git_executable,
        probe_facts=probe_facts_for_arm("R"),
    )
    observations = outcome.observations
    assert observations["pre_dispatch_refusal_code"] == "CONFIG_SHAPE_MISMATCH"
    assert observations["refused_at_step"] == "L16"
    assert observations["runtime_reported_compat_shape"] == "DEVELOPER_ROLE_FALSE_ONLY"
    assert observations["manipulation_check_agrees"] is False
    assert observations["prompt_writes"] == 0
    assert made["supervisor"].commands_sent == []


def test_t11_l16_a_wrong_thinking_level_also_refuses_before_the_prompt(
    admission, git_executable
):
    outcome, made = _run(
        admission,
        git_executable,
        probe_facts=(True, "TRUE", "ABSENT", "high"),
    )
    assert outcome.observations["pre_dispatch_refusal_code"] == "CONFIG_SHAPE_MISMATCH"
    assert outcome.observations["runtime_reported_thinking_level"] == "high"
    assert made["supervisor"].commands_sent == []


def test_t11_l18_a_failed_write_is_indeterminate_and_never_retried(
    admission, git_executable
):
    supervisor = FakeSupervisor(send_error=OSError("injected stdin failure"))
    outcome, _made = _run(
        admission, git_executable, build_supervisor=lambda **kwargs: supervisor
    )
    observations = outcome.observations
    assert observations["dispatch_state"] == "SEND_STATE_INDETERMINATE"
    assert observations["prompt_writes"] == 1
    assert observations["pre_dispatch_refusal_code"] is None
    # NEVER a second write.
    assert supervisor.commands_sent == []


def test_t11_l18_a_runtime_refusal_is_confirmed_not_sent(admission, git_executable):
    supervisor = FakeSupervisor(
        prompt_response={"type": "response", "command": "prompt", "success": False}
    )
    outcome, _made = _run(
        admission, git_executable, build_supervisor=lambda **kwargs: supervisor
    )
    observations = outcome.observations
    assert observations["dispatch_state"] == "CONFIRMED_NOT_SENT"
    assert observations["pre_dispatch_refusal_code"] == "PROMPT_REFUSED_BY_RUNTIME"
    assert observations["refused_at_step"] == "L18"


def test_t11_l19_a_stream_terminal_outcome_is_recorded_and_classified(
    admission, git_executable
):
    from pi_harness_cfg1.classification import classify_cfg1_run
    from pi_harness_cfg1.records import build_cfg1_run_payload

    outcome, _made = _run(
        admission,
        git_executable,
        build_supervisor=lambda **kwargs: FakeSupervisor(
            wait_outcome="runtime_protocol_violation"
        ),
    )
    observations = outcome.observations
    assert observations["runtime_wait_outcome"] == "PROTOCOL_VIOLATION"
    payload = build_cfg1_run_payload(
        stage_id="S1",
        stage_execution_id="S1-X1",
        run_ordinal=1,
        observations=observations,
    )
    assert classify_cfg1_run(payload) == "INDETERMINATE_RUNTIME_STREAM"


def test_t11_l24_precedes_l26_so_verification_never_sees_the_endpoint_on_disk(
    admission, git_executable
):
    """Model-influenced code runs only after the endpoint and token are scrubbed.

    AMEND2 (Y6): L24 empties the exact issued object (``EndOfFile == 0``) rather
    than deleting a name, so what verification must not see is any endpoint
    BYTES -- the zero-length object may still be named until L27.
    """
    seen_during_verification: list[bool] = []
    state: dict = {}

    def _write_config(*, workspace, arm_id, base_url):
        from pi_harness_cfg1.cfg1_pi_config import write_cfg1_pi_config

        config = write_cfg1_pi_config(workspace, arm_id=arm_id, base_url=base_url)
        state["models_path"] = config.models_path
        state["arm_id"] = arm_id
        return config

    calls = {"n": 0}

    def _run_verification(*, workspace_root, args):
        calls["n"] += 1
        if calls["n"] > 1:  # the L26 call, not the L3 baseline
            models = Path(state["models_path"])
            seen_during_verification.append(
                models.exists() and models.stat().st_size > 0
            )
        return FakeVerificationOutcome()

    ports, _made = build_doubled_ports(
        git_executable=git_executable,
        overrides={
            "write_config": _write_config,
            "run_verification": _run_verification,
            "probe_facts": probe_facts_for_arm("Q"),
        },
    )
    outcome = execute_cfg1_run(admission, ports=ports)
    assert outcome.observations["verification_attempted"] is True
    assert seen_during_verification == [False]


def test_t11_l26_is_skipped_when_closure_is_unproven(admission, git_executable):
    broker = FakeBroker()
    broker.lifecycle["state_reached"] = "TEARDOWN_INCOMPLETE"
    verification_calls = {"n": 0}

    def _run_verification(*, workspace_root, args):
        verification_calls["n"] += 1
        return FakeVerificationOutcome()

    outcome, _made = _run(
        admission,
        git_executable,
        build_broker=lambda *, capability: broker,
        run_verification=_run_verification,
    )
    observations = outcome.observations
    assert observations["broker_state_closed"] is False
    assert observations["lifecycle_all_closed"] is False
    assert "L23" in observations["lifecycle_failure_steps"]
    assert observations["verification_attempted"] is False
    assert observations["verification_skip_reason"] == "LIFECYCLE_UNPROVEN"
    # Only the L3 baseline ran; L26 never did.
    assert verification_calls["n"] == 1


def test_t11_a_partial_workspace_mint_is_never_deleted(admission, git_executable):
    """Sec. 18 row 13: ownership unprovable means the tree is NEVER removed."""
    outcome, _made = _run(
        admission,
        git_executable,
        mint_workspace=_raiser(RuntimeError("injected mint failure")),
    )
    observations = outcome.observations
    assert observations["pre_dispatch_refusal_code"] == "WORKSPACE_BASELINE_FAILED"
    assert observations["refused_at_step"] == "L2"
    assert "WORKSPACE_MINT_PARTIAL" in outcome.console_codes
    assert observations["workspace_authority_reproved"] is False
    assert observations["workspace_removed_verified"] is False
    assert observations["lifecycle_all_closed"] is False


# ---------------------------------------------------------------------------
# T-12 -- ownership refusals, before any side effect
# ---------------------------------------------------------------------------


def test_t12_a_foreign_workspace_object_is_refused_before_any_removal(tmp_path):
    from pi_harness_cfg1.run_workspace import (
        Cfg1RunWorkspace,
        Cfg1WorkspaceAuthorityError,
        remove_cfg1_run_workspace,
        verify_cfg1_run_workspace,
    )

    victim = tmp_path / "not_ours"
    victim.mkdir()
    (victim / "precious.txt").write_text("untouched", encoding="utf-8")

    class _LooksLikeAWorkspace:
        run_workspace_nonce = "anything"
        experiment_root = str(victim)
        workspace_root = str(victim)

    for impostor in (_LooksLikeAWorkspace(), None, str(victim), object()):
        with pytest.raises(Cfg1WorkspaceAuthorityError) as excinfo:
            remove_cfg1_run_workspace(impostor)
        assert excinfo.value.reason_code == "NOT_A_CFG1_RUN_WORKSPACE"
        with pytest.raises(Cfg1WorkspaceAuthorityError):
            verify_cfg1_run_workspace(impostor)

    assert (victim / "precious.txt").read_text(encoding="utf-8") == "untouched"

    # And direct construction with an unregistered nonce is refused too.
    with pytest.raises(Cfg1WorkspaceAuthorityError) as excinfo:
        Cfg1RunWorkspace(
            run_workspace_nonce="forged",
            experiment_root=str(victim),
            workspace_root=str(victim),
        )
    assert excinfo.value.reason_code == "NOT_MINTED_BY_CFG1"


def test_t12_a_workspace_claim_is_single_use_even_for_the_run_that_claimed_it(
    git_executable,
):
    from pi_harness_cfg1.run_workspace import (
        Cfg1WorkspaceAuthorityError,
        claim_cfg1_run_workspace,
        remove_cfg1_run_workspace,
        workspace_is_claimed_by,
    )

    workspace, _built = run_workspace.mint_cfg1_run_workspace(
        git_executable=git_executable
    )
    try:
        claim_cfg1_run_workspace(workspace, run_id="run-a")
        assert workspace_is_claimed_by(workspace, run_id="run-a") is True
        assert workspace_is_claimed_by(workspace, run_id="run-b") is False
        for run_id in ("run-a", "run-b"):
            with pytest.raises(Cfg1WorkspaceAuthorityError) as excinfo:
                claim_cfg1_run_workspace(workspace, run_id=run_id)
            assert excinfo.value.reason_code == "RUN_WORKSPACE_ALREADY_CLAIMED"
    finally:
        remove_cfg1_run_workspace(workspace)


def test_t12_a_vanished_workspace_fails_its_re_proof_with_its_mint_intact(
    git_executable,
):
    """The registry entry alone is never enough -- the marker must re-read too.

    Removal goes through the FROZEN ``remove_disposable_tree`` rather than a
    bare ``shutil.rmtree``: a Git repository's object files are read-only on
    Windows, and AIDO's own remover is the one that already handles that. The
    registry entry is deliberately left in place, so the refusal can only come
    from the filesystem re-proof.
    """
    from ar2.fixtures import remove_disposable_tree

    from pi_harness_cfg1.run_workspace import (
        Cfg1WorkspaceAuthorityError,
        discard_cfg1_run_workspace,
        verify_cfg1_run_workspace,
    )

    workspace, _built = run_workspace.mint_cfg1_run_workspace(
        git_executable=git_executable
    )
    try:
        verify_cfg1_run_workspace(workspace)  # genuine
        remove_disposable_tree(workspace.experiment_root)
        with pytest.raises(Cfg1WorkspaceAuthorityError) as excinfo:
            verify_cfg1_run_workspace(workspace)
        assert excinfo.value.reason_code == "ROOT_AUTHORITY_UNVERIFIED"
    finally:
        discard_cfg1_run_workspace(workspace)


def test_t12_a_config_issuance_claim_is_refused_for_a_foreign_directory(
    tmp_path, git_executable
):
    """CFG1-IMPL-FU1 Finding 2: no bare path can stand in for a workspace at all."""
    from pi_harness_cfg1.cfg1_pi_config import Cfg1PiConfigError, write_cfg1_pi_config
    from pi_harness_cfg1.config_issuance import ConfigIssuanceError, derive_cfg1_config_paths

    # The writer itself refuses a bare path outright.
    with pytest.raises(Cfg1PiConfigError) as excinfo:
        write_cfg1_pi_config(str(tmp_path), arm_id="Q", base_url=SYNTHETIC_BASE_URL)
    assert excinfo.value.reason_code == "NOT_A_CFG1_RUN_WORKSPACE"

    # And so does config_issuance's own derivation, independently.
    with pytest.raises(ConfigIssuanceError) as excinfo:
        derive_cfg1_config_paths(str(tmp_path))
    assert excinfo.value.reason_code == "NOT_A_CFG1_RUN_WORKSPACE"

    workspace, _built = run_workspace.mint_cfg1_run_workspace(
        git_executable=git_executable
    )
    try:
        config = write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
        from pi_harness_cfg1.config_issuance import verify_config_issuance

        # Genuine positive control.
        verify_config_issuance(token=config.issuance_token, workspace=workspace)

        # A forged token, for the genuine workspace.
        for forged in ("forged", "", None, 7):
            with pytest.raises(ConfigIssuanceError):
                verify_config_issuance(token=forged, workspace=workspace)

        # A genuine token, presented under a DIFFERENT genuine workspace.
        other_workspace, _other_built = run_workspace.mint_cfg1_run_workspace(
            git_executable=git_executable
        )
        try:
            with pytest.raises(ConfigIssuanceError) as excinfo:
                verify_config_issuance(
                    token=config.issuance_token, workspace=other_workspace
                )
            assert excinfo.value.reason_code == "ISSUANCE_WORKSPACE_MISMATCH"
        finally:
            run_workspace.remove_cfg1_run_workspace(other_workspace)

        # Tampered on-disk content is caught by the finalized digest.
        Path(config.settings_path).write_text("{}", encoding="utf-8")
        with pytest.raises(ConfigIssuanceError) as excinfo:
            verify_config_issuance(token=config.issuance_token, workspace=workspace)
        assert excinfo.value.reason_code == "SETTINGS_CONTENT_MISMATCH"
    finally:
        run_workspace.remove_cfg1_run_workspace(workspace)


def test_t12_a_genuine_config_cannot_be_registered_for_a_foreign_root(git_executable):
    """A caller cannot bless an existing directory by naming it explicitly.

    Two mechanical facts, neither of which is caller convention:

    1. ``register_config_issuance`` has NO path parameter of any kind -- not
       ``config_dir``, not ``settings_path``, not ``models_path``, not a
       prefix or a parent. The location is derived from ``workspace`` alone.
    2. Since FU15 it also requires the three UNFORGEABLE proofs L9's own gate
       mints (``proven``, ``settings_child``, ``models_child``), so a caller
       cannot register an issuance for files that never passed the parentage
       gate -- even files it planted at exactly the right derived path.
    """
    import os

    from pi_harness_cfg1.cfg1_pi_config import write_cfg1_pi_config
    from pi_harness_cfg1.config_issuance import (
        ConfigIssuanceError,
        derive_cfg1_config_paths,
        register_config_issuance,
        verify_config_issuance,
    )

    signature = inspect.signature(register_config_issuance)
    assert set(signature.parameters) == {
        "workspace",
        "arm_id",
        "provider_id",
        "model_id",
        "proven",
        "settings_child",
        "models_child",
        # FU1 (R6 Sec. 9.2b item 6): the raw digests of the bytes L9's step 9a
        # checked -- DIGESTS, never a path.
        "expected_settings_sha256",
        "expected_models_sha256",
        # AMEND2 (Y6): the retained exact-object AUTHORITY -- a mint-backed
        # value carrying a nonce, never a path and never a raw handle.
        "retained",
    }
    for name in ("config_dir", "settings_path", "models_path", "path", "root", "parent"):
        assert name not in signature.parameters

    workspace, _built = run_workspace.mint_cfg1_run_workspace(
        git_executable=git_executable
    )
    try:
        # Files planted at the exact derived location, by a caller that holds a
        # genuine workspace, cannot be registered: there is no supported way to
        # produce the proofs without going through L9 itself.
        config_dir, settings_path, models_path = derive_cfg1_config_paths(workspace)
        Path(config_dir).mkdir(parents=False, exist_ok=False)
        Path(settings_path).write_text("{}", encoding="utf-8")
        Path(models_path).write_text("{}", encoding="utf-8")
        with pytest.raises(ConfigIssuanceError) as excinfo:
            register_config_issuance(
                workspace=workspace,
                arm_id="Q",
                provider_id="p",
                model_id="m",
                proven=object(),
                settings_child=object(),
                models_child=object(),
            )
        assert excinfo.value.reason_code == "PARENTAGE_NOT_PROVEN"

        # Positive control: the genuine path through L9 registers and verifies.
        os.unlink(settings_path)
        os.unlink(models_path)
        os.rmdir(config_dir)
        config = write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
        record = verify_config_issuance(
            token=config.issuance_token, workspace=workspace
        )
        assert record.arm_id == "Q"
    finally:
        run_workspace.remove_cfg1_run_workspace(workspace)


def test_t12_the_child_environment_refuses_a_config_it_cannot_re_prove(
    git_executable,
):
    from pi_harness_cfg1.cfg1_pi_config import write_cfg1_pi_config
    from cfg1_issuance_cleanup import discard_config_for_test as discard_config_issuance
    from pi_harness_cfg1.config_issuance import ConfigIssuanceError
    from pi_harness_cfg1.environment import build_cfg1_child_environment

    workspace, _built = run_workspace.mint_cfg1_run_workspace(
        git_executable=git_executable
    )
    try:
        config = write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
        discard_config_issuance(config.issuance_token)  # the run already ended

        with pytest.raises(ConfigIssuanceError) as excinfo:
            build_cfg1_child_environment(
                ambient_environ={"SystemRoot": r"C:\Windows"},
                node_executable=r"C:\Program Files\nodejs\node.exe",
                generated_config=config,
                workspace=workspace,
                credential_value="cfg1-synthetic-key",
            )
        assert excinfo.value.reason_code == "UNKNOWN_ISSUANCE_TOKEN"
    finally:
        run_workspace.remove_cfg1_run_workspace(workspace)


def test_t12_a_blank_credential_carrier_is_refused_rather_than_silently_launched(
    git_executable,
):
    from pi_harness_cfg1.cfg1_pi_config import write_cfg1_pi_config
    from cfg1_issuance_cleanup import discard_config_for_test as discard_config_issuance
    from pi_harness_cfg1.environment import (
        Cfg1EnvironmentPolicyError,
        build_cfg1_child_environment,
    )

    workspace, _built = run_workspace.mint_cfg1_run_workspace(
        git_executable=git_executable
    )
    try:
        config = write_cfg1_pi_config(workspace, arm_id="Q", base_url=SYNTHETIC_BASE_URL)
        try:
            for blank in ("", "   ", None, 7):
                with pytest.raises(Cfg1EnvironmentPolicyError) as excinfo:
                    build_cfg1_child_environment(
                        ambient_environ={"SystemRoot": r"C:\Windows"},
                        node_executable=r"C:\Program Files\nodejs\node.exe",
                        generated_config=config,
                        workspace=workspace,
                        credential_value=blank,
                    )
                assert excinfo.value.reason_code == "BLANK_CREDENTIAL_CARRIER"
        finally:
            discard_config_issuance(config.issuance_token)
    finally:
        run_workspace.remove_cfg1_run_workspace(workspace)


# ---------------------------------------------------------------------------
# The whole stage, through the REAL executor -- nine runs, nine workspaces
# ---------------------------------------------------------------------------


def test_a_full_nine_ordinal_stage_leaks_no_resource_and_no_registry_entry(
    make_authority, git_executable
):
    """End to end: L0-L30 nine times, with the real executor and real workspaces.

    Every other lifecycle test drives ONE run. This one proves the properties
    that only a full stage can show: nine distinct fresh workspaces are minted
    and all nine are removed; the run-scoped registries are empty at the end;
    each ordinal's record is written under its own schedule-derived name with
    its own arm; and the stage closes successfully exactly once.
    """
    import json

    from pi_harness_cfg1 import config_issuance, run_workspace
    from pi_harness_cfg1.binding import (
        verify_cfg1_run_artifact_binding,
        verify_cfg1_stage_closure_binding,
    )
    from pi_harness_cfg1.run_contract import Cfg1RunOutcome
    from pi_harness_cfg1.stage_runner import _run_cfg1_stage_with_injected_executor as run_cfg1_stage

    minted_roots: list[str] = []

    def _executor(admission):
        ports, made = build_doubled_ports(
            git_executable=git_executable, arm_id=admission.arm_id
        )
        outcome = execute_cfg1_run(admission, ports=ports)
        minted_roots.append(made["workspace"].experiment_root)
        assert type(outcome) is Cfg1RunOutcome
        return outcome

    authority = make_authority("S1-X1")
    result = run_cfg1_stage(authority, run_executor=_executor)

    assert result.disposition == "STAGE_COMPLETED"
    assert result.stage_closure_confirmed is True
    assert result.ordinals_attempted == tuple(range(1, 10))
    assert all(status == "RECORD_EMITTED" for _o, status in result.ordinal_status)

    # Nine DISTINCT workspaces, every one of them removed.
    assert len(set(minted_roots)) == 9
    for root in minted_roots:
        assert not Path(root).exists(), root
    # ...and nothing left in either run-scoped registry (Sec. 19.1 item 4).
    assert run_workspace.minted_workspace_count() == 0
    assert config_issuance.issued_token_count() == 0

    # Each ordinal's own artifact, under its own schedule-derived name.
    expected = ["Q", "R", "E", "R", "E", "Q", "E", "Q", "R"]
    for ordinal, arm in enumerate(expected, start=1):
        path = Path(authority.execution_directory, f"S1_{ordinal:02d}_{arm}.json")
        assert verify_cfg1_run_artifact_binding(str(path)) is True, path
        record = json.loads(path.read_text(encoding="utf-8"))
        assert record["arm_id"] == arm
        assert record["run_ordinal"] == ordinal
        assert record["run_classification"] == "INACTIVE"
    closure = Path(authority.execution_directory, "S1_stage_closure.json")
    assert verify_cfg1_stage_closure_binding(str(closure)) is True

    # Exactly ten artifacts: nine run records and one stage closure.
    assert len(list(Path(authority.execution_directory).iterdir())) == 10
