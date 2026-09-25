"""FU1 (R6 §11 + AMEND1 §16): Tests B, C, G (non-P steps) and executor-level T.

These were the four minimum requirements the first-pass FU1 report listed as not
yet implemented. Everything here runs the GENUINE executor over the doubled
ports (no Node, no Pi, no socket, no credential); the workspace is a real
synthetic ``CFG1-T1`` repository under a fresh disposable root.

* **B** -- the workspace-mint write-ahead: a mint that creates a tree and then
  raises, a malformed return (including one wrapping a GENUINE workspace) and a
  foreign type all leave W at ``ATTEMPTED_NO_AUTHORITY``: nothing is ever
  deleted, the lifecycle is indeterminate, the halt is
  ``LIFECYCLE_CLOSURE_UNPROVEN``.
* **C** -- a genuine workspace followed by a later refusal is closed by L27;
  an injected re-proof failure or residual is not, and the tree is untouched.
* **G** -- an unexpected raise at every non-P step.
* **T** -- the ``refused_at_step`` / ``pre_dispatch_refusal_code`` /
  ``unexpected_failure_step`` triple falls into exactly one of three modes for
  every scenario the executor can produce, including the clean pass.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from cfg1_doubles import (
    FakeSupervisor,
    FakeVerificationOutcome,
    FakeRouteObservation,
    build_doubled_ports,
    seam_digests_all_match,
)
from cfg1_fu1_support import make_admission

from pi_harness_cfg1 import obs1, run_executor, run_workspace
from pi_harness_cfg1 import win_config_authority as win
from pi_harness_cfg1.halt import _resolve_halt_reason_code
from pi_harness_cfg1.records import _require_valid_cfg1_run_payload_v2, build_cfg1_run_payload
from pi_harness_cfg1.run_executor import execute_cfg1_run

NEEDLE = "9d3e-unexpected-needle"


def _run(monkeypatch, git_executable, overrides=None):
    seam_digests_all_match(monkeypatch)
    ports, made = build_doubled_ports(git_executable=git_executable, overrides=overrides or {})
    return execute_cfg1_run(make_admission(), ports=ports), made


def _payload(outcome) -> dict:
    payload = build_cfg1_run_payload(
        stage_id="S1", stage_execution_id="S1-X1", run_ordinal=1,
        observations=outcome.observations,
    )
    _require_valid_cfg1_run_payload_v2(payload)  # on the serialized record ALONE
    assert NEEDLE not in json.dumps(payload)
    assert NEEDLE not in json.dumps(list(outcome.console_codes))
    return payload


def _halt(payload, outcome) -> str | None:
    return _resolve_halt_reason_code(
        emission_status="RECORD_EMITTED",
        halt_triggered_by_this_run=False,
        lifecycle_all_closed=outcome.observations["lifecycle_all_closed"],
        run_classification=payload["run_classification"],
        registries_empty=True,
    )


def _mode(observations) -> str:
    refusal = (
        observations.get("refused_at_step") is not None,
        observations.get("pre_dispatch_refusal_code") is not None,
    )
    post = observations.get("unexpected_failure_step") is not None
    if all(refusal) and not post:
        return "REFUSAL"
    if post and not any(refusal):
        return "POST_DISPATCH_UNEXPECTED"
    if not post and not any(refusal):
        return "NO_DISPATCH_FAILURE"
    return "MIXED"


# ---------------------------------------------------------------------------
# B -- the workspace-mint write-ahead
# ---------------------------------------------------------------------------


def _mint_then(kind, git_executable, roots: list):
    def _mint(*, git_executable):
        workspace, built = run_workspace.mint_cfg1_run_workspace(git_executable=git_executable)
        roots.append(workspace.experiment_root)
        if kind == "raises_after_tree":
            raise RuntimeError(NEEDLE)
        if kind == "malformed_three_tuple":
            return workspace, built, "extra"
        if kind == "malformed_list":
            return [workspace, built]
        return workspace  # a bare genuine workspace, not the required 2-tuple

    return _mint


@pytest.mark.parametrize(
    "kind",
    ["raises_after_tree", "malformed_three_tuple", "malformed_list", "bare_workspace", "foreign_type"],
)
def test_b_a_mint_that_did_not_return_authority_deletes_nothing(kind, monkeypatch, git_executable):
    roots: list[str] = []
    removals: list[object] = []
    real_remove = run_workspace.remove_cfg1_run_workspace
    monkeypatch.setattr(
        run_workspace, "remove_cfg1_run_workspace",
        lambda handle: (removals.append(handle), real_remove(handle))[1],
    )
    mint = (
        (lambda *, git_executable: object())
        if kind == "foreign_type"
        else _mint_then(kind, git_executable, roots)
    )
    try:
        outcome, _made = _run(monkeypatch, git_executable, {"mint_workspace": mint})
        observations = outcome.observations
        payload = _payload(outcome)
        assert observations["workspace_mint_state"] == "ATTEMPTED_NO_AUTHORITY"
        assert observations["refused_at_step"] == "L2"
        assert "L27" in observations["lifecycle_failure_steps"]
        assert observations["lifecycle_all_closed"] is False
        assert payload["run_classification"] == "INDETERMINATE_LIFECYCLE"
        assert _halt(payload, outcome) == "LIFECYCLE_CLOSURE_UNPROVEN"
        assert removals == []  # no remover call
        for root in roots:
            assert Path(root).exists()  # the tree still exists afterwards
    finally:
        for root in roots:
            shutil.rmtree(root, ignore_errors=True)


# ---------------------------------------------------------------------------
# C -- a genuine workspace, then a later refusal
# ---------------------------------------------------------------------------


def _later_refusal(step, monkeypatch, flags):
    if step == "L3":
        return {"run_verification": lambda *, workspace_root, args: FakeVerificationOutcome(passed=True)}
    if step == "L4":
        return {"read_connection": lambda: (_ for _ in ()).throw(RuntimeError(NEEDLE))}
    if step == "L7":
        return {
            "observe_route": lambda *, base_url, api_key, model_id: FakeRouteObservation(
                reachable=False
            )
        }

    def _environment(**_k):
        flags["l12"] = True
        raise RuntimeError(NEEDLE)

    return {"build_environment": _environment}


@pytest.mark.parametrize("step", ["L3", "L4", "L7", "L12"])
@pytest.mark.parametrize("teardown", ["success", "reproof_fails", "residual"])
def test_c_a_genuine_workspace_is_closed_only_by_a_proven_teardown(
    step, teardown, monkeypatch, git_executable
):
    flags: dict = {}
    overrides = _later_refusal(step, monkeypatch, flags)
    real_verify = run_workspace.verify_cfg1_run_workspace

    if teardown == "reproof_fails":
        # Only the L27 re-proof fails: every earlier verify passes. The git
        # observation port runs immediately before L27, so it arms the fault.
        def _observe(*, workspace_root):
            flags["l27"] = True
            from cfg1_doubles import FakeRepositorySnapshot

            return FakeRepositorySnapshot()

        overrides["observe_repository"] = _observe
        monkeypatch.setattr(
            run_workspace, "verify_cfg1_run_workspace",
            lambda handle: (_ for _ in ()).throw(run_workspace.Cfg1WorkspaceAuthorityError("X"))
            if flags.get("l27") else real_verify(handle),
        )
    elif teardown == "residual":
        monkeypatch.setattr(
            run_workspace, "remove_cfg1_run_workspace",
            lambda handle: {"removed": True, "residual_file_count": 3},
        )

    outcome, made = _run(monkeypatch, git_executable, overrides)
    root = made["workspace"].experiment_root
    try:
        observations = outcome.observations
        _payload(outcome)
        assert observations["workspace_mint_state"] == "AUTHORITY_RETURNED"
        assert observations["refused_at_step"] == step
        if teardown == "success":
            assert observations["workspace_removed_verified"] is True
            assert "L27" not in observations["lifecycle_failure_steps"]
            assert not Path(root).exists()
        elif teardown == "reproof_fails":
            assert observations["workspace_authority_reproved"] is False
            assert "L27" in observations["lifecycle_failure_steps"]
            assert Path(root).exists()  # untouched
        else:
            assert "L27" in observations["lifecycle_failure_steps"]
            assert observations["workspace_residual_file_count"] == 3
    finally:
        shutil.rmtree(root, ignore_errors=True)
        run_workspace.discard_cfg1_run_workspace(made["workspace"])


# ---------------------------------------------------------------------------
# G (non-P steps) and executor-level T
# ---------------------------------------------------------------------------


def _safety_raiser(monkeypatch, nth: int):
    """Make the ``nth`` construction of the safety context raise (2 = L5, 3 = L10)."""
    from qualification import safety

    real = safety.ArtifactSafetyContext
    calls: list[int] = []

    class _Raising(real):
        def __init__(self, *args, **kwargs):
            calls.append(1)
            if len(calls) == nth:
                raise RuntimeError(NEEDLE)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(safety, "ArtifactSafetyContext", _Raising)


def _scenario(name, monkeypatch, git_executable):
    """Install one non-P scenario; return (ports overrides, expected)."""
    overrides: dict = {}
    if name == "L2":
        _safety_raiser(monkeypatch, 1)
        return overrides, ("REFUSAL", "L2", "UNEXPECTED_STEP_FAILURE")
    if name == "L5":
        _safety_raiser(monkeypatch, 2)
        return overrides, ("REFUSAL", "L5", "UNEXPECTED_STEP_FAILURE")
    if name == "L9":
        overrides["write_config"] = lambda **_k: (_ for _ in ()).throw(RuntimeError(NEEDLE))
        return overrides, ("REFUSAL", "L9", "CONFIG_GENERATION_FAILED")
    if name == "L10":
        _safety_raiser(monkeypatch, 3)
        return overrides, ("REFUSAL", "L10", "UNEXPECTED_STEP_FAILURE")
    if name == "L11":
        overrides["write_extension"] = lambda **_k: (_ for _ in ()).throw(RuntimeError(NEEDLE))
        return overrides, ("REFUSAL", "L11", "EXTENSION_GENERATION_FAILED")
    if name == "L14":
        overrides["build_supervisor"] = lambda **_k: (_ for _ in ()).throw(RuntimeError(NEEDLE))
        return overrides, ("REFUSAL", "L14", "RUNTIME_LAUNCH_FAILED")
    if name == "L18":
        def _write(supervisor, *, observations, state):
            observations["dispatch_state"] = "SEND_STATE_INDETERMINATE"
            observations["prompt_writes"] = 1
            state.dispatch_attempted = True
            raise RuntimeError(NEEDLE)

        monkeypatch.setattr(run_executor, "_write_one_prompt", _write)
        return overrides, ("POST_DISPATCH_UNEXPECTED", "L18", None)
    if name == "L20":
        monkeypatch.setattr(
            obs1, "project_cfg1_runtime_activity",
            lambda **_k: (_ for _ in ()).throw(RuntimeError(NEEDLE)),
        )
        return overrides, ("POST_DISPATCH_UNEXPECTED", "L20", None)
    if name == "anticipated_L7":
        overrides["observe_route"] = lambda *, base_url, api_key, model_id: FakeRouteObservation(
            reachable=False
        )
        return overrides, ("REFUSAL", "L7", "ROUTE_UNAVAILABLE")
    assert name == "clean"
    return overrides, ("NO_DISPATCH_FAILURE", None, None)


_STEPS = ["L2", "L5", "L9", "L10", "L11", "L14", "L18", "L20"]


@pytest.mark.parametrize("name", _STEPS)
def test_g_an_unexpected_raise_at_every_non_p_step(name, monkeypatch, git_executable):
    overrides, (mode, step, code) = _scenario(name, monkeypatch, git_executable)
    outcome, made = _run(monkeypatch, git_executable, overrides)
    observations = outcome.observations
    payload = _payload(outcome)
    assert _mode(observations) == mode
    # Never L1 with a P-stage code; the step equals the cursor.
    assert observations["refused_at_step"] != "L1"
    assert observations["pi_identity_failure_code"] is None
    assert observations["pre_dispatch_refusal_code"] != "OFFLINE_PREFLIGHT_FAILED"
    if mode == "REFUSAL":
        assert observations["refused_at_step"] == step
        assert observations["pre_dispatch_refusal_code"] == code
        assert observations["unexpected_failure_step"] is None
    else:
        # POST_DISPATCH_UNEXPECTED: no refusal fields; the step is the cursor.
        assert observations["unexpected_failure_step"] == step
        assert observations["refused_at_step"] is None
        assert observations["pre_dispatch_refusal_code"] is None
        assert payload["run_classification"].startswith("INDETERMINATE_")
    # Lifecycle obligations match what was created.
    assert observations["workspace_mint_state"] == "AUTHORITY_RETURNED"
    assert observations["runtime_created"] is (name in ("L18", "L20"))
    if name in ("L9", "L11"):
        # An untyped raise is never credited (G6): the scrub fact stays False.
        key = "generated_config_scrub_verified" if name == "L9" else "extension_binding_scrub_verified"
        assert observations[key] is False
        assert "L24" in observations["lifecycle_failure_steps"]
    if name in ("L10", "L11", "L14", "L18", "L20", "L5", "L2"):
        assert win.held_retained_count() == 0  # L24 retired every issuance


@pytest.mark.parametrize("name", _STEPS + ["anticipated_L7", "clean"])
def test_t_every_executor_outcome_falls_into_exactly_one_mode(name, monkeypatch, git_executable):
    overrides, (mode, _step, _code) = _scenario(name, monkeypatch, git_executable)
    outcome, _made = _run(monkeypatch, git_executable, overrides)
    observations = outcome.observations
    assert _mode(observations) == mode
    payload = _payload(outcome)
    if mode == "NO_DISPATCH_FAILURE":
        # A clean pass validates with ALL THREE fields absent (B6's case).
        for key in ("refused_at_step", "pre_dispatch_refusal_code", "unexpected_failure_step"):
            assert observations[key] is None

    # No mixture validates: add a second family to the serialized record, and
    # break the refusal iff, and each must be refused.
    def _refuses(mutated):
        with pytest.raises(Exception):
            _require_valid_cfg1_run_payload_v2(mutated)

    if mode == "REFUSAL":
        mixed = dict(payload)
        mixed["unexpected_failure_step"] = "L19"
        _refuses(mixed)
        half = dict(payload)
        half.pop("pre_dispatch_refusal_code", None)
        _refuses(half)
        half = dict(payload)
        half.pop("refused_at_step", None)
        _refuses(half)
    elif mode == "POST_DISPATCH_UNEXPECTED":
        mixed = dict(payload)
        mixed["refused_at_step"] = "L9"
        mixed["pre_dispatch_refusal_code"] = "CONFIG_GENERATION_FAILED"
        _refuses(mixed)
    else:
        mixed = dict(payload)
        mixed["unexpected_failure_step"] = "L19"
        mixed["refused_at_step"] = "L9"
        _refuses(mixed)
