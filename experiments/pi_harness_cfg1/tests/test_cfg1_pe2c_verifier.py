"""PE-2c: the read-only post-hoc profile binding verifier (PE-1 Sec. 21, C-11).

Every chain is a genuine PE-2b load of a SYNTHETIC committed chain; every
artifact is a synthetic v3 payload (or the genuine writer's own output over a
synthetic executor). The verifier is review tooling: nothing in the runtime
path imports it.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from cfg1_builders import (
    happy_observations_v2,
    refusal_payload,
    run_payload,
    stage_closure_payload,
    stage_closure_payload_v3,
    synthetic_run_executor,
    v2_run_payload,
)
from pe2b_support import base_payload, non_seam_payload
from pe2c_support import install_policy_load, synthetic_policy_load

from pi_harness_cfg1 import pi_profile_binding_verifier as verifier
from pi_harness_cfg1 import pi_profile_policy_loader as loader
from pi_harness_cfg1 import stage_runner
from pi_harness_cfg1.pi_profile_binding_verifier import (
    PI_PROFILE_BINDING_REFUSED_BINDING_MISMATCH,
    PI_PROFILE_BINDING_REFUSED_DECLARED_VERSION_MISMATCH,
    PI_PROFILE_BINDING_REFUSED_HEAD_NOT_IN_COMMITTED_CHAIN,
    PI_PROFILE_BINDING_REFUSED_HEAD_OR_LITERAL_MISMATCH,
    PI_PROFILE_BINDING_REFUSED_HISTORICAL_ARTIFACT,
    PI_PROFILE_BINDING_REFUSED_INVALID_ARTIFACT,
    PI_PROFILE_BINDING_REFUSED_MALFORMED_INPUT,
    PI_PROFILE_BINDING_REFUSED_MISSING_RUN_RECORD,
    PI_PROFILE_BINDING_REFUSED_POLICY_UNAVAILABLE,
    PI_PROFILE_BINDING_REFUSED_PROFILE_NOT_ELIGIBLE_AT_HEAD,
    PI_PROFILE_BINDING_REFUSED_RUN_PROFILE_MISMATCH,
    PI_PROFILE_BINDING_REFUSED_STAGE_MISMATCH,
    PI_PROFILE_BINDING_REFUSED_UNCONFIRMED_ORDINAL_ARTIFACT,
    PI_PROFILE_BINDING_RESULTS,
    PI_PROFILE_BINDING_VERIFIED,
    verify_stage_pi_profile_binding,
)

_PACKAGE_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture()
def chain(monkeypatch):
    """r1 approves A; r2 approves B (a non-manifest variant, C3 floor); r3 retires A."""
    a = base_payload()
    b = non_seam_payload()
    load = synthetic_policy_load([{"approve": [a]}, {"approve": [b]}, {"retire": [a.profile_id]}])
    install_policy_load(monkeypatch, load)
    heads = [summary[1] for summary in load.revisions]
    return {
        "a": a,
        "b": b,
        "a_version": a.facts.declared_dict()["package_version"],
        "b_version": b.facts.declared_dict()["package_version"],
        "r1": heads[0],
        "r2": heads[1],
        "r3": heads[2],
        "load": load,
    }


def _run(ordinal: int, profile_id: str, version: str, head: str, **overrides) -> dict:
    payload = run_payload(
        run_ordinal=ordinal,
        pi_profile_id=profile_id,
        pi_profile_declared_package_version=version,
        **overrides,
    )
    payload["pi_profile_set_head_sha256"] = head
    return payload


def _stage(chain, head_key="r1", profile="a", **kwargs):
    profile_id = chain[profile].profile_id
    version = chain[f"{profile}_version"]
    closure = stage_closure_payload_v3(
        stage_pi_profile_id=profile_id,
        stage_pi_profile_declared_package_version=version,
        head=chain[head_key],
        **kwargs,
    )
    runs = {}
    for ordinal in range(1, 10):
        if closure["ordinal_status"][str(ordinal)] == "RECORD_EMITTED":
            runs[ordinal] = _run(ordinal, profile_id, version, chain[head_key])
    return closure, runs


def test_c11_a_genuine_binding_at_the_bound_historical_head_verifies(chain):
    closure, runs = _stage(chain, "r1")
    assert verify_stage_pi_profile_binding(closure, runs) == PI_PROFILE_BINDING_VERIFIED


def test_c11_eligibility_is_checked_at_the_bound_head_not_the_current_one(chain):
    # A is eligible at r1 and r2, retired at r3 (the CURRENT head).
    assert loader.SEALED_POLICY_SNAPSHOT.aps_head_sha256 == chain["r3"]
    closure, runs = _stage(chain, "r2")
    assert verify_stage_pi_profile_binding(closure, runs) == PI_PROFILE_BINDING_VERIFIED
    closure, runs = _stage(chain, "r3")
    assert verify_stage_pi_profile_binding(closure, runs) == PI_PROFILE_BINDING_REFUSED_PROFILE_NOT_ELIGIBLE_AT_HEAD
    # B did not exist at r1.
    closure, runs = _stage(chain, "r1", profile="b")
    assert verify_stage_pi_profile_binding(closure, runs) == PI_PROFILE_BINDING_REFUSED_PROFILE_NOT_ELIGIBLE_AT_HEAD
    closure, runs = _stage(chain, "r3", profile="b")
    assert verify_stage_pi_profile_binding(closure, runs) == PI_PROFILE_BINDING_VERIFIED


def test_c11_a_forged_head_is_refused(chain):
    closure, runs = _stage(chain, "r1")
    forged = "7" * 64
    closure["pi_profile_set_head_sha256"] = forged
    for record in runs.values():
        record["pi_profile_set_head_sha256"] = forged
    assert verify_stage_pi_profile_binding(closure, runs) == PI_PROFILE_BINDING_REFUSED_HEAD_NOT_IN_COMMITTED_CHAIN


def test_c11_declared_versions_must_equal_the_committed_profiles(chain):
    closure, runs = _stage(chain, "r1")
    closure["stage_pi_profile_declared_package_version"] = "9.9.9"
    assert verify_stage_pi_profile_binding(closure, runs) == PI_PROFILE_BINDING_REFUSED_DECLARED_VERSION_MISMATCH
    closure, runs = _stage(chain, "r1")
    runs[4]["pi_profile_declared_package_version"] = "9.9.9"
    assert verify_stage_pi_profile_binding(closure, runs) == PI_PROFILE_BINDING_REFUSED_DECLARED_VERSION_MISMATCH


def test_c11_a_run_profile_different_from_the_stage_profile_is_refused(chain):
    closure, runs = _stage(chain, "r2")
    runs[5] = _run(5, chain["b"].profile_id, chain["b_version"], chain["r2"])
    assert verify_stage_pi_profile_binding(closure, runs) == PI_PROFILE_BINDING_REFUSED_RUN_PROFILE_MISMATCH


def test_c11_the_binding_must_agree_with_every_record_emitted_run(chain):
    status = {str(k): ("RECORD_EMITTED" if k <= 3 else "NOT_EXECUTED") for k in range(1, 10)}
    closure, runs = _stage(chain, "r1", ordinal_status=status, halted_after_ordinal=3, halt_reason_code="PRE_DISPATCH_REFUSAL")
    assert verify_stage_pi_profile_binding(closure, runs) == PI_PROFILE_BINDING_VERIFIED
    closure["ordinal_pi_profile_binding"]["3"] = "NO_PROFILE"  # coherent closure, false claim
    assert verify_stage_pi_profile_binding(closure, runs) == PI_PROFILE_BINDING_REFUSED_BINDING_MISMATCH


def test_c11_historical_v1_and_v2_artifacts_are_refused(chain):
    _closure, runs = _stage(chain, "r1")
    assert verify_stage_pi_profile_binding(stage_closure_payload(), runs) == PI_PROFILE_BINDING_REFUSED_HISTORICAL_ARTIFACT
    closure, runs = _stage(chain, "r1")
    runs[2] = v2_run_payload(run_ordinal=2, observations=happy_observations_v2(runtime_reported_compat_shape="REQUIRES_SYSTEM_ROLE"))
    assert verify_stage_pi_profile_binding(closure, runs) == PI_PROFILE_BINDING_REFUSED_HISTORICAL_ARTIFACT


def test_c11_a_refusal_record_is_never_profile_evidence(chain):
    status = {str(k): "RECORD_EMITTED" for k in range(1, 10)}
    status["6"] = "EVIDENCE_REFUSED"
    closure, runs = _stage(chain, "r1", ordinal_status=status)
    refusal = refusal_payload(run_ordinal=6)
    refusal["pi_profile_set_head_sha256"] = chain["r1"]
    runs[6] = refusal
    # A refusal at its own NO_RUN_EVIDENCE ordinal: head/literals checked, and
    # nothing at all is inferred about that ordinal's profile.
    assert verify_stage_pi_profile_binding(closure, runs) == PI_PROFILE_BINDING_VERIFIED
    # A refusal standing where a run record must be is never accepted in its place.
    closure, runs = _stage(chain, "r1")
    refusal = refusal_payload(run_ordinal=6)
    refusal["pi_profile_set_head_sha256"] = chain["r1"]
    runs[6] = refusal
    assert verify_stage_pi_profile_binding(closure, runs) == PI_PROFILE_BINDING_REFUSED_UNCONFIRMED_ORDINAL_ARTIFACT
    # A run record at an EVIDENCE_REFUSED ordinal is not a confirmed occupant.
    closure, runs = _stage(chain, "r1", ordinal_status=status)
    runs[6] = _run(6, chain["a"].profile_id, chain["a_version"], chain["r1"])
    assert verify_stage_pi_profile_binding(closure, runs) == PI_PROFILE_BINDING_REFUSED_UNCONFIRMED_ORDINAL_ARTIFACT


def test_c11_nothing_is_inferred_for_no_run_evidence_or_not_executed(chain):
    status = {str(k): ("RECORD_EMITTED" if k <= 2 else "EMISSION_FAILED" if k == 3 else "NOT_EXECUTED") for k in range(1, 10)}
    closure, runs = _stage(
        chain, "r1", ordinal_status=status, halted_after_ordinal=3, halt_reason_code="RUN_RECORD_EMISSION_FAILED"
    )
    assert set(runs) == {1, 2}
    assert verify_stage_pi_profile_binding(closure, runs) == PI_PROFILE_BINDING_VERIFIED


def test_c11_missing_mismatched_and_malformed_inputs_are_refused(chain, monkeypatch):
    closure, runs = _stage(chain, "r1")
    runs.pop(7)
    assert verify_stage_pi_profile_binding(closure, runs) == PI_PROFILE_BINDING_REFUSED_MISSING_RUN_RECORD
    closure, runs = _stage(chain, "r1")
    runs[2]["pi_profile_set_head_sha256"] = chain["r2"]
    assert verify_stage_pi_profile_binding(closure, runs) == PI_PROFILE_BINDING_REFUSED_HEAD_OR_LITERAL_MISMATCH
    closure, runs = _stage(chain, "r1")
    runs[2] = _run(2, chain["a"].profile_id, chain["a_version"], chain["r1"])
    runs[2]["stage_execution_id"] = "S1-X2"
    assert verify_stage_pi_profile_binding(closure, runs) == PI_PROFILE_BINDING_REFUSED_STAGE_MISMATCH
    closure, runs = _stage(chain, "r1")
    runs[3]["pi_profile_id"] = "Z"
    assert verify_stage_pi_profile_binding(closure, runs) == PI_PROFILE_BINDING_REFUSED_INVALID_ARTIFACT
    for bad_closure, bad_runs in ((None, runs), (closure, None), (closure, {"1": runs[1]}), (closure, {True: runs[1]})):
        assert verify_stage_pi_profile_binding(bad_closure, bad_runs) == PI_PROFILE_BINDING_REFUSED_MALFORMED_INPUT
    monkeypatch.setattr(loader, "_GENUINE_POLICY_LOAD", object())
    closure, runs = _stage(chain, "r1")
    assert verify_stage_pi_profile_binding(closure, runs) == PI_PROFILE_BINDING_REFUSED_POLICY_UNAVAILABLE


def test_c11_the_verifier_is_total_and_its_vocabulary_is_closed(chain):
    class Hostile(dict):
        def get(self, *a, **k):
            raise RuntimeError("hostile")

    result = verify_stage_pi_profile_binding(Hostile(), {})
    assert result in PI_PROFILE_BINDING_RESULTS
    assert len([code for code in PI_PROFILE_BINDING_RESULTS if not code.startswith("PI_PROFILE_BINDING_REFUSED_")]) == 1


def test_c11_end_to_end_the_genuine_writer_output_verifies(make_authority):
    authority = make_authority("S1-X1")
    result = stage_runner._run_cfg1_stage_with_injected_executor(authority, run_executor=synthetic_run_executor())
    assert result.stage_closure_confirmed is True
    directory = Path(authority.execution_directory)
    closure = json.loads((directory / "S1_stage_closure.json").read_text(encoding="utf-8"))
    runs = {}
    for path in directory.glob("S1_0*.json"):
        record = json.loads(path.read_text(encoding="utf-8"))
        runs[record["run_ordinal"]] = record
    assert verify_stage_pi_profile_binding(closure, runs) == PI_PROFILE_BINDING_VERIFIED


def test_c11_no_runtime_module_imports_the_verifier():
    for path in sorted(_PACKAGE_DIR.glob("*.py")):
        if path.name == "pi_profile_binding_verifier.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert "pi_profile_binding_verifier" not in (node.module or ""), path.name
                assert "pi_profile_binding_verifier" not in {alias.name for alias in node.names}, path.name
            if isinstance(node, ast.Import):
                assert not any("pi_profile_binding_verifier" in alias.name for alias in node.names), path.name
