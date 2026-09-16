"""T-75 - T-79, T-83 - T-87, T-95 - T-100, T-116 - T-122: phases and residue.

The one boundary this file exists to prove: **the refusal-fallback window
closes at the exclusive-create CALL, not at a collision.** Step 10 is four
distinct sub-actions, and the create can succeed and only afterwards have the
write, flush or close fail -- leaving zero bytes, partial JSON, or complete
bytes whose durability was never established. A fallback at that same path
could then overwrite, collide, or leave two artifacts of undefined relative
trustworthiness.

Pure Python, ``tmp_path``-scoped, no live Pi/network/model/credential activity.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from cfg1_builders import happy_observations, refusal_payload, run_payload, synthetic_run_executor
from qualification.safety import ArtifactSafetyContext

from pi_harness_cfg1 import binding, records, writers
from pi_harness_cfg1.records import Cfg1RecordValidationError
from pi_harness_cfg1.stage_runner import _run_cfg1_stage_with_injected_executor as run_cfg1_stage
from pi_harness_cfg1.writers import emit_cfg1_refusal_record, emit_cfg1_run_record

NO_NEEDLES = ArtifactSafetyContext.none_declared()

#: A needle that genuinely appears in a run payload (``pi_observed_version``)
#: and genuinely does NOT appear in a refusal record. That asymmetry is what
#: makes an ordinary Sec. 18 row-11 scrub refusal constructible at all.
SCRUB_TRIPPING_SAFETY = ArtifactSafetyContext(api_key="0.85.1")


def _emit_run(authority, *, ordinal=1, payload=None, safety=NO_NEEDLES, lifecycle=True):
    """Emit one run record, with a payload bound to THIS authority by default.

    The default payload takes its ``stage_execution_id`` from the authority, so
    a test that means to exercise some other boundary does not accidentally
    exercise step 7 instead.
    """
    if payload is None:
        payload = run_payload(
            stage_execution_id=authority.stage_execution_id, run_ordinal=ordinal
        )
    return emit_cfg1_run_record(
        authority,
        run_ordinal=ordinal,
        payload=payload,
        lifecycle_all_closed=lifecycle,
        safety=safety,
    )


@pytest.fixture()
def residue_spy(monkeypatch):
    """Proves the post-create residue policy MECHANICALLY.

    Any unlink, rename, truncate, or truncating re-open of a final path would
    be recorded here. The policy is: leave it exactly as the failed write left
    it, whatever it contains.
    """
    import os

    calls: list[str] = []
    real_unlink = os.unlink
    real_remove = os.remove
    real_rename = os.rename
    real_replace = os.replace
    real_truncate = os.truncate
    real_open = writers._open_exclusive

    monkeypatch.setattr(os, "unlink", lambda p, *a, **k: calls.append(f"unlink:{p}"))
    monkeypatch.setattr(os, "remove", lambda p, *a, **k: calls.append(f"remove:{p}"))
    monkeypatch.setattr(os, "rename", lambda s, d, *a, **k: calls.append(f"rename:{s}"))
    monkeypatch.setattr(os, "replace", lambda s, d, *a, **k: calls.append(f"replace:{s}"))
    monkeypatch.setattr(os, "truncate", lambda p, n, *a, **k: calls.append(f"truncate:{p}"))

    def _spy_open(path):
        calls.append(f"exclusive_create:{path}")
        return real_open(path)

    monkeypatch.setattr(writers, "_open_exclusive", _spy_open)
    yield calls
    monkeypatch.setattr(os, "unlink", real_unlink)
    monkeypatch.setattr(os, "remove", real_remove)
    monkeypatch.setattr(os, "rename", real_rename)
    monkeypatch.setattr(os, "replace", real_replace)
    monkeypatch.setattr(os, "truncate", real_truncate)


@pytest.fixture()
def refusal_entry_spy(monkeypatch):
    calls: list[tuple] = []
    real = writers.emit_cfg1_refusal_record

    def _spy(authority, /, **kwargs):
        calls.append(kwargs)
        return real(authority, **kwargs)

    monkeypatch.setattr(writers, "emit_cfg1_refusal_record", _spy)
    return calls


def _raiser(error):
    def _raise(*_args, **_kwargs):
        raise error

    return _raise


def _fail_after_create(monkeypatch, sub_action: str, *, only_suffix: str = ".json"):
    """Inject a failure strictly AFTER a successful exclusive-create."""
    real = {
        "write": writers._write_all,
        "flush": writers._flush_handle,
        "close": writers._close_handle,
    }[sub_action]
    name = {"write": "_write_all", "flush": "_flush_handle", "close": "_close_handle"}[
        sub_action
    ]
    tracked: dict[str, object] = {"handle": None}
    real_open = writers._open_exclusive

    def _open(path):
        handle = real_open(path)
        if path.endswith(only_suffix):
            tracked["handle"] = handle
        return handle

    def _fail(handle, *args, **kwargs):
        if handle is tracked["handle"]:
            if sub_action != "write":
                # Everything up to this sub-action genuinely succeeded, so the
                # residue is exactly what a real partial failure would leave.
                real(handle, *args, **kwargs)
            raise OSError(f"injected {sub_action} failure")
        return real(handle, *args, **kwargs)

    monkeypatch.setattr(writers, "_open_exclusive", _open)
    monkeypatch.setattr(writers, name, _fail)


# ---------------------------------------------------------------------------
# T-83 -- a PRE_CREATE failure gets exactly one fallback, after zero creates
# ---------------------------------------------------------------------------


def test_t83_pre_create_failure_gets_one_fallback_after_zero_final_path_writes(
    make_authority, monkeypatch, residue_spy, refusal_entry_spy
):
    authority = make_authority("S1-X1")
    monkeypatch.setattr(
        writers,
        "_require_valid_cfg1_run_payload",
        _raiser(Cfg1RecordValidationError("SCHEMA_VIOLATION", "INJECTED")),
    )
    result = _emit_run(authority)

    assert len(refusal_entry_spy) == 1
    creates = [c for c in residue_spy if c.startswith("exclusive_create:")]
    assert len(creates) == 1  # the refusal artifact's own, and nothing before it
    assert result.emission_status == "EVIDENCE_REFUSED"
    assert result.fallback_attempted is True


# ---------------------------------------------------------------------------
# T-84 / T-85 / T-95 -- a POST-create failure gets ZERO fallbacks, ever
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("sub_action", ["write", "flush", "close"])
def test_t84_post_create_primary_failure_attempts_zero_fallbacks(
    sub_action, make_authority, monkeypatch, refusal_entry_spy
):
    authority = make_authority("S1-X1")
    _fail_after_create(monkeypatch, sub_action)
    result = _emit_run(authority)

    assert result.emission_status == "EMISSION_FAILED"
    assert result.fallback_attempted is False
    assert refusal_entry_spy == []


@pytest.mark.parametrize("sub_action", ["write", "flush", "close"])
def test_t85_post_create_residue_is_never_touched(
    sub_action, make_authority, monkeypatch, residue_spy
):
    authority = make_authority("S1-X1")
    _fail_after_create(monkeypatch, sub_action)
    _emit_run(authority)

    destructive = [
        call
        for call in residue_spy
        if call.split(":", 1)[0] in ("unlink", "remove", "rename", "replace", "truncate")
    ]
    assert destructive == []
    # And exactly one create ever happened -- no second attempt at the path.
    assert len([c for c in residue_spy if c.startswith("exclusive_create:")]) == 1


def test_t95_a_direct_post_create_failure_maps_to_the_truthful_neutral_code(
    make_authority, monkeypatch, refusal_entry_spy
):
    """Never the retired ``RUN_RECORD_REFUSAL_FALLBACK_FAILED`` literal."""
    authority = make_authority("S1-X1")
    _fail_after_create(monkeypatch, "write", only_suffix="S1_01_Q.json")
    result = run_cfg1_stage(authority, run_executor=synthetic_run_executor())

    assert result.halt_reason_code == "RUN_RECORD_EMISSION_FAILED"
    assert result.halted_after_ordinal == 1
    assert dict(result.ordinal_status)[1] == "EMISSION_FAILED"
    assert refusal_entry_spy == []

    closure = json.loads(
        Path(authority.execution_directory, "S1_stage_closure.json").read_text(
            encoding="utf-8"
        )
    )
    assert closure["halt_reason_code"] == "RUN_RECORD_EMISSION_FAILED"
    assert "REFUSAL_FALLBACK" not in json.dumps(closure)


# ---------------------------------------------------------------------------
# T-75 / T-86 / T-96 -- the fallback's OWN failure, and its truthful code
# ---------------------------------------------------------------------------


def test_t75_a_pre_create_fallback_that_also_fails_pre_create_writes_nothing(
    make_authority, monkeypatch, residue_spy
):
    authority = make_authority("S1-X1")
    monkeypatch.setattr(
        writers,
        "_require_valid_cfg1_run_payload",
        _raiser(Cfg1RecordValidationError("SCHEMA_VIOLATION", "INJECTED")),
    )
    monkeypatch.setattr(
        writers,
        "_require_valid_cfg1_refusal_payload",
        _raiser(Cfg1RecordValidationError("SCHEMA_VIOLATION", "INJECTED")),
    )
    result = run_cfg1_stage(authority, run_executor=synthetic_run_executor())

    # Every injected failure is PRE_CREATE, so "zero writes" is mechanically
    # true here specifically -- see T-98 for the post-create case where it
    # would be false.
    run_creates = [c for c in residue_spy if c.endswith("S1_01_Q.json")]
    assert run_creates == []
    assert not Path(authority.execution_directory, "S1_01_Q.json").exists()

    assert dict(result.ordinal_status)[1] == "EMISSION_FAILED"
    assert result.halt_reason_code == "RUN_RECORD_EMISSION_FAILED"
    assert result.halt_reason_code != "EVIDENCE_REFUSED"


@pytest.mark.parametrize("sub_action", ["write", "flush", "close"])
def test_t86_a_refusal_writer_post_create_failure_is_non_recursive(
    sub_action, make_authority, monkeypatch, refusal_entry_spy
):
    authority = make_authority("S1-X1")
    _fail_after_create(monkeypatch, sub_action)
    result = emit_cfg1_refusal_record(
        authority,
        run_ordinal=1,
        refusal_payload=refusal_payload(),
        safety=NO_NEEDLES,
    )
    assert result.emission_status == "EMISSION_FAILED"
    assert refusal_entry_spy == []  # zero RE-entries


def test_t96_a_fallback_then_failure_is_indistinguishable_from_a_direct_failure(
    make_authority, monkeypatch
):
    """Both structurally different causes resolve to the IDENTICAL closed code."""
    # Scoped contexts, never ``monkeypatch.undo()``: a blanket undo would also
    # revert the harness's own ``_CAPTURED_PACKAGE_DIR`` retarget and send the
    # rest of the test writing into the real package results root.
    direct = make_authority("S1-direct")
    with monkeypatch.context() as scoped:
        _fail_after_create(scoped, "write", only_suffix="S1_01_Q.json")
        direct_result = run_cfg1_stage(direct, run_executor=synthetic_run_executor())

    fallback = make_authority("S1-fallback")
    with monkeypatch.context() as scoped:
        scoped.setattr(
            writers,
            "_require_valid_cfg1_run_payload",
            _raiser(Cfg1RecordValidationError("SCHEMA_VIOLATION", "INJECTED")),
        )
        scoped.setattr(writers, "_write_all", _raiser(OSError("injected")))
        fallback_result = run_cfg1_stage(fallback, run_executor=synthetic_run_executor())

    assert direct_result.halt_reason_code == fallback_result.halt_reason_code
    assert direct_result.halt_reason_code == "RUN_RECORD_EMISSION_FAILED"


# ---------------------------------------------------------------------------
# T-77 -- a refusal record's identity is FRESHLY built, never copied
# ---------------------------------------------------------------------------


def test_t77_refusal_identity_is_never_traceable_to_the_rejected_payload(make_authority):
    authority = make_authority("S1-X1")
    hostile = run_payload()
    hostile["stage_execution_id"] = "S1-FORGED"
    hostile["arm_id"] = "H"
    hostile["record_filename"] = "S1_99_H.json"
    hostile["claim_scope"] = "x" * 4096

    result = _emit_run(authority, payload=hostile)
    assert result.emission_status == "EVIDENCE_REFUSED"

    written = json.loads(
        Path(authority.execution_directory, "S1_01_Q.json").read_text(encoding="utf-8")
    )
    assert written["stage_id"] == authority.stage_id
    assert written["stage_execution_id"] == authority.stage_execution_id
    assert written["run_ordinal"] == 1
    assert written["arm_id"] == "Q"
    assert written["record_filename"] == "S1_01_Q.json"
    serialized = json.dumps(written)
    assert "S1-FORGED" not in serialized
    assert "S1_99_H.json" not in serialized
    assert "x" * 100 not in serialized


# ---------------------------------------------------------------------------
# T-78 / T-79 -- row 11 and row 15 share a status but not the admission bool
# ---------------------------------------------------------------------------


def test_t78_a_row_15_defect_halts_even_when_its_refusal_artifact_succeeds(
    make_authority, monkeypatch
):
    authority = make_authority("S1-X1")
    monkeypatch.setattr(
        writers,
        "_require_valid_cfg1_run_payload",
        _raiser(Cfg1RecordValidationError("SCHEMA_VIOLATION", "INJECTED")),
    )
    result = run_cfg1_stage(authority, run_executor=synthetic_run_executor())

    assert dict(result.ordinal_status)[1] == "EVIDENCE_REFUSED"
    assert result.halted_after_ordinal == 1  # no token for ordinal 2
    assert result.halt_reason_code == "RUN_RECORD_SELF_VALIDATION_FAILED"
    assert dict(result.ordinal_status)[2] == "NOT_EXECUTED"

    # The bool itself never appears in any durable payload (T-94's scope).
    written = json.loads(
        Path(authority.execution_directory, "S1_01_Q.json").read_text(encoding="utf-8")
    )
    assert "halt_triggered_by_this_run" not in written
    assert "halt_reason_code" not in written


def test_t79_row_11_and_row_15_are_durably_distinguishable_only_at_the_closure(
    make_authority, monkeypatch
):
    # Row 11: an ordinary scrub-needle hit. Non-halting.
    row11 = make_authority("S1-row11")
    row11_result = run_cfg1_stage(
        row11,
        run_executor=_scrub_tripping_executor(),
    )
    assert dict(row11_result.ordinal_status)[1] == "EVIDENCE_REFUSED"
    assert row11_result.disposition == "STAGE_COMPLETED"
    assert row11_result.halted_after_ordinal is None
    assert row11_result.halt_reason_code is None

    # Row 15: an implementation defect. Halting, same emission status.
    row15 = make_authority("S1-row15")
    monkeypatch.setattr(
        writers,
        "_require_valid_cfg1_run_payload",
        _raiser(Cfg1RecordValidationError("SCHEMA_VIOLATION", "INJECTED")),
    )
    row15_result = run_cfg1_stage(row15, run_executor=synthetic_run_executor())
    assert dict(row15_result.ordinal_status)[1] == "EVIDENCE_REFUSED"
    assert row15_result.halt_reason_code == "RUN_RECORD_SELF_VALIDATION_FAILED"

    # The two runs' own DURABLE run-path artifacts are indistinguishable on
    # this point -- neither carries the bool at all.
    row11_artifact = json.loads(
        Path(row11.execution_directory, "S1_01_Q.json").read_text(encoding="utf-8")
    )
    row15_artifact = json.loads(
        Path(row15.execution_directory, "S1_01_Q.json").read_text(encoding="utf-8")
    )
    assert row11_artifact["record_version"] == row15_artifact["record_version"]
    for artifact in (row11_artifact, row15_artifact):
        assert "halt_triggered_by_this_run" not in artifact
        assert "halt_reason_code" not in artifact


def _scrub_tripping_executor():
    """An executor whose run payload trips the scrub for ordinal 1 only."""
    from pi_harness_cfg1.arms import ARM_SHAPE
    from pi_harness_cfg1.run_contract import Cfg1RunOutcome

    def _executor(admission):
        observations = happy_observations(
            runtime_reported_compat_shape=ARM_SHAPE[admission.arm_id]
        )
        safety = (
            SCRUB_TRIPPING_SAFETY if admission.run_ordinal == 1 else NO_NEEDLES
        )
        return Cfg1RunOutcome(
            observations=observations, safety=safety, live_references_released=True
        )

    return _executor


# ---------------------------------------------------------------------------
# T-87 / T-98 / T-99 -- close-after-full-write, and post-hoc reads
# ---------------------------------------------------------------------------


def test_t87_and_t98_stage_closure_close_failure_is_live_failed_despite_valid_residue(
    make_authority, monkeypatch, refusal_entry_spy, residue_spy
):
    authority = make_authority("S1-X1")
    _fail_after_create(monkeypatch, "close", only_suffix="S1_stage_closure.json")
    result = run_cfg1_stage(authority, run_executor=synthetic_run_executor())

    closure_path = Path(authority.execution_directory, "S1_stage_closure.json")

    # (1) the LIVE result the runner acted on is FAILED.
    assert result.stage_closure_confirmed is False
    assert result.disposition == "STAGE_CLOSURE_EMISSION_FAILED"
    # (2) zero refusal-writer calls.
    assert refusal_entry_spy == []
    # (3) no replacement path, no second attempt.
    closure_creates = [c for c in residue_spy if c.endswith("S1_stage_closure.json")]
    assert len(closure_creates) == 1
    assert sorted(p.name for p in Path(authority.execution_directory).glob("*stage_closure*")) == [
        "S1_stage_closure.json"
    ]
    # (4) the stage-output authority is retired.
    from pi_harness_cfg1.stage_output import stage_output_authority_is_active

    assert stage_output_authority_is_active(authority) is False
    # (5) the residue -- here a complete, byte-for-byte valid artifact -- is
    # left untouched.
    destructive = [
        call
        for call in residue_spy
        if call.split(":", 1)[0] in ("unlink", "remove", "rename", "replace", "truncate")
    ]
    assert destructive == []
    records._require_valid_cfg1_stage_closure_payload(
        json.loads(closure_path.read_text(encoding="utf-8"))
    )


def test_t99_a_post_hoc_true_on_valid_residue_never_reclassifies_the_live_outcome(
    make_authority, monkeypatch
):
    authority = make_authority("S1-X1")
    with monkeypatch.context() as scoped:
        _fail_after_create(scoped, "close", only_suffix="S1_stage_closure.json")
        result = run_cfg1_stage(authority, run_executor=synthetic_run_executor())
    closure_path = Path(authority.execution_directory, "S1_stage_closure.json")

    # (a) The residue IS a genuine, correctly-bound artifact by the verifier's
    # own byte-authoritative rules...
    assert binding.verify_cfg1_stage_closure_binding(str(closure_path)) is True
    # (b) ...and the already-recorded live outcome is unchanged by that fact.
    assert result.stage_closure_confirmed is False
    assert result.disposition == "STAGE_CLOSURE_EMISSION_FAILED"
    # ...and re-reading it a second time changes nothing either.
    assert binding.verify_cfg1_stage_closure_binding(str(closure_path)) is True
    assert result.stage_closure_confirmed is False

    # (c) The identical property for the RUN-record case.
    run_authority = make_authority("S1-X2")
    with monkeypatch.context() as scoped:
        _fail_after_create(scoped, "close", only_suffix="S1_01_Q.json")
        run_result = run_cfg1_stage(run_authority, run_executor=synthetic_run_executor())
    run_path = Path(run_authority.execution_directory, "S1_01_Q.json")
    assert binding.verify_cfg1_run_artifact_binding(str(run_path)) is True
    assert dict(run_result.ordinal_status)[1] == "EMISSION_FAILED"
    assert run_result.halt_reason_code == "RUN_RECORD_EMISSION_FAILED"


def test_t97_a_pre_create_stage_closure_failure_leaves_no_file_at_all(
    make_authority, monkeypatch, residue_spy
):
    authority = make_authority("S1-X1")
    monkeypatch.setattr(
        writers,
        "_require_valid_cfg1_stage_closure_payload",
        _raiser(Cfg1RecordValidationError("SCHEMA_VIOLATION", "INJECTED")),
    )
    result = run_cfg1_stage(authority, run_executor=synthetic_run_executor())

    assert result.disposition == "STAGE_CLOSURE_EMISSION_FAILED"
    closure_calls = [c for c in residue_spy if c.endswith("S1_stage_closure.json")]
    assert closure_calls == []
    assert not Path(authority.execution_directory, "S1_stage_closure.json").exists()
    # Every run record genuinely written before the failure is untouched and
    # individually still True under the read-only verifier.
    for ordinal, arm in enumerate(["Q", "R", "E", "R", "E", "Q", "E", "Q", "R"], start=1):
        path = Path(authority.execution_directory, f"S1_{ordinal:02d}_{arm}.json")
        assert binding.verify_cfg1_run_artifact_binding(str(path)) is True


# ---------------------------------------------------------------------------
# T-116 - T-122 -- the create-attempt outcome matrix
# ---------------------------------------------------------------------------


def test_t116_primary_writer_create_collision_is_emission_collision(
    make_authority, refusal_entry_spy, residue_spy
):
    authority = make_authority("S1-X1")
    occupied = Path(authority.execution_directory, "S1_01_Q.json")
    occupied.write_text("pre-existing occupant", encoding="utf-8")

    result = run_cfg1_stage(authority, run_executor=synthetic_run_executor())
    # L0's own absence check fires FIRST here -- before any run is admitted --
    # which is Sec. 16.3.10's distinct hard stop, not a writer collision.
    assert result.disposition == "OUTPUT_NAMESPACE_PREOCCUPIED"
    assert occupied.read_text(encoding="utf-8") == "pre-existing occupant"

    # The writer-level collision is reached by calling the writer directly,
    # which is the boundary T-116 is actually about.
    other = make_authority("S1-X2")
    Path(other.execution_directory, "S1_01_Q.json").write_text("occupant", encoding="utf-8")
    emission = _emit_run(other)
    assert emission.emission_status == "EMISSION_COLLISION"
    assert emission.fallback_attempted is False
    assert refusal_entry_spy == []
    destructive = [
        call
        for call in residue_spy
        if call.split(":", 1)[0] in ("unlink", "remove", "rename", "replace", "truncate")
    ]
    assert destructive == []
    assert (
        Path(other.execution_directory, "S1_01_Q.json").read_text(encoding="utf-8")
        == "occupant"
    )


def test_t117_primary_writer_non_collision_create_error_is_emission_failed(
    make_authority, monkeypatch, refusal_entry_spy
):
    authority = make_authority("S1-X1")
    monkeypatch.setattr(
        writers, "_open_exclusive", _raiser(OSError("injected permission error"))
    )
    result = _emit_run(authority)
    assert result.emission_status == "EMISSION_FAILED"
    assert result.fallback_attempted is False
    assert refusal_entry_spy == []

    # And a platform-ambiguous create result is treated identically -- the path
    # is NEVER inferred absent merely because the error was not FileExistsError.
    monkeypatch.setattr(writers, "_open_exclusive", _raiser(OSError(13, "ambiguous")))
    assert _emit_run(authority, ordinal=2).emission_status == "EMISSION_FAILED"


def test_t118_refusal_writer_create_collision_is_emission_collision(
    make_authority, refusal_entry_spy
):
    """Collision is never a primary-writer-only concept."""
    authority = make_authority("S1-X1")
    Path(authority.execution_directory, "S1_01_Q.json").write_text(
        "occupant", encoding="utf-8"
    )
    result = emit_cfg1_refusal_record(
        authority, run_ordinal=1, refusal_payload=refusal_payload(), safety=NO_NEEDLES
    )
    assert result.emission_status == "EMISSION_COLLISION"
    assert refusal_entry_spy == []
    assert (
        Path(authority.execution_directory, "S1_01_Q.json").read_text(encoding="utf-8")
        == "occupant"
    )


def test_t119_refusal_writer_non_collision_create_error_is_emission_failed(
    make_authority, monkeypatch, refusal_entry_spy
):
    authority = make_authority("S1-X1")
    monkeypatch.setattr(writers, "_open_exclusive", _raiser(OSError("injected")))
    result = emit_cfg1_refusal_record(
        authority, run_ordinal=1, refusal_payload=refusal_payload(), safety=NO_NEEDLES
    )
    assert result.emission_status == "EMISSION_FAILED"
    assert refusal_entry_spy == []
    assert not Path(authority.execution_directory, "S1_01_Q.json").exists()


def test_t120_no_create_attempt_failure_ever_triggers_another_fallback(
    make_authority, monkeypatch, refusal_entry_spy
):
    """One spy, all four T-116 - T-119 sub-cases."""
    collision_primary = make_authority("S1-a")
    Path(collision_primary.execution_directory, "S1_01_Q.json").write_text("x", encoding="utf-8")
    assert _emit_run(collision_primary).emission_status == "EMISSION_COLLISION"

    collision_refusal = make_authority("S1-b")
    Path(collision_refusal.execution_directory, "S1_01_Q.json").write_text("x", encoding="utf-8")
    assert (
        emit_cfg1_refusal_record(
            collision_refusal,
            run_ordinal=1,
            refusal_payload=refusal_payload(stage_execution_id="S1-b"),
            safety=NO_NEEDLES,
        ).emission_status
        == "EMISSION_COLLISION"
    )

    monkeypatch.setattr(writers, "_open_exclusive", _raiser(OSError("injected")))
    error_primary = make_authority("S1-c")
    assert _emit_run(error_primary).emission_status == "EMISSION_FAILED"
    error_refusal = make_authority("S1-d")
    assert (
        emit_cfg1_refusal_record(
            error_refusal,
            run_ordinal=1,
            refusal_payload=refusal_payload(stage_execution_id="S1-d"),
            safety=NO_NEEDLES,
        ).emission_status
        == "EMISSION_FAILED"
    )

    assert refusal_entry_spy == []


def test_t121_stage_closure_create_collision_fails_live_and_retires(make_authority):
    from pi_harness_cfg1.stage_output import stage_output_authority_is_active

    authority = make_authority("S1-X1")
    occupant = Path(authority.execution_directory, "S1_stage_closure.json")
    occupant.write_text("occupant", encoding="utf-8")

    result = run_cfg1_stage(authority, run_executor=synthetic_run_executor())
    assert result.stage_closure_confirmed is False
    assert result.disposition == "STAGE_CLOSURE_EMISSION_FAILED"
    assert "STAGE_CLOSURE_CREATE_COLLISION" in result.console_codes
    assert occupant.read_text(encoding="utf-8") == "occupant"
    assert stage_output_authority_is_active(authority) is False


def test_t122_stage_closure_non_collision_create_error_has_the_identical_shape(
    make_authority, monkeypatch
):
    from pi_harness_cfg1.stage_output import stage_output_authority_is_active

    authority = make_authority("S1-X1")
    real_open = writers._open_exclusive

    def _open(path):
        if path.endswith("S1_stage_closure.json"):
            raise OSError("injected non-collision create failure")
        return real_open(path)

    monkeypatch.setattr(writers, "_open_exclusive", _open)
    result = run_cfg1_stage(authority, run_executor=synthetic_run_executor())

    assert result.stage_closure_confirmed is False
    assert result.disposition == "STAGE_CLOSURE_EMISSION_FAILED"
    assert "STAGE_CLOSURE_CREATE_FAILED" in result.console_codes
    assert stage_output_authority_is_active(authority) is False
    assert not Path(authority.execution_directory, "S1_stage_closure.json").exists()


# ---------------------------------------------------------------------------
# T-100 -- L0 output-namespace preoccupation, a THIRD hard-stop class
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("occupant_kind", ["file", "directory"])
def test_t100_l0_output_namespace_preoccupation_creates_nothing_and_writes_nothing(
    occupant_kind, make_authority, residue_spy
):
    from pi_harness_cfg1.stage_output import stage_output_authority_is_active

    authority = make_authority("S1-X1")
    occupied = Path(authority.execution_directory, "S1_01_Q.json")
    if occupant_kind == "file":
        occupied.write_text("pre-existing", encoding="utf-8")
    else:
        occupied.mkdir()
        (occupied / "inside.txt").write_text("pre-existing", encoding="utf-8")

    admissions: list[object] = []

    def _executor(admission):  # pragma: no cover - must never be reached
        admissions.append(admission)
        raise AssertionError("no run resource may be created for a preoccupied path")

    result = run_cfg1_stage(authority, run_executor=_executor)

    # (1) zero run-scoped resources.
    assert admissions == []
    # (2) the authority is retired immediately.
    assert stage_output_authority_is_active(authority) is False
    # (3) exactly one closed console code, and nothing else.
    assert result.disposition == "OUTPUT_NAMESPACE_PREOCCUPIED"
    assert result.console_codes == ("OUTPUT_NAMESPACE_PREOCCUPIED",)
    # (4) zero artifacts of any kind.
    assert [c for c in residue_spy if c.startswith("exclusive_create:")] == []
    assert sorted(p.name for p in Path(authority.execution_directory).iterdir()) == [
        "S1_01_Q.json"
    ]
    # (5) the occupant itself is completely untouched.
    if occupant_kind == "file":
        assert occupied.read_text(encoding="utf-8") == "pre-existing"
    else:
        assert (occupied / "inside.txt").read_text(encoding="utf-8") == "pre-existing"


def test_t76_a_pre_create_stage_closure_failure_reports_console_only_and_retires(
    make_authority, monkeypatch, residue_spy
):
    """Sec. 18 row 17, narrowed to the PRE_CREATE sub-case (FU8 Finding 3).

    The "no artifact exists" claim here is scoped strictly to ``PRE_CREATE``.
    The post-create sub-case, where residue may exist and this claim would be
    false, is T-87/T-98 -- not this test.
    """
    from pi_harness_cfg1.stage_output import stage_output_authority_is_active

    authority = make_authority("S1-X1")
    monkeypatch.setattr(
        writers, "_scrub", _raiser(writers.Cfg1WriterError("SCRUB_NEEDLE_MATCH"))
    )
    result = run_cfg1_stage(authority, run_executor=synthetic_run_executor())

    # Zero final-path create calls for the closure: no artifact of ANY kind --
    # valid, malformed, or partial -- exists on disk for that path.
    assert [c for c in residue_spy if c.endswith("S1_stage_closure.json")] == []
    assert not Path(authority.execution_directory, "S1_stage_closure.json").exists()
    # Reporting is console-only...
    assert result.disposition == "STAGE_CLOSURE_EMISSION_FAILED"
    assert "STAGE_CLOSURE_PRE_CREATE_FAILED" in result.console_codes
    # ...the authority is retired immediately...
    assert stage_output_authority_is_active(authority) is False
    # ...and this writer NEVER has a refusal fallback of any kind.
    assert result.stage_closure_confirmed is False
