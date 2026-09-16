"""T-33 - T-37, T-50, T-62 - T-68, T-80 - T-82: post-hoc artifact binding.

These regressions construct TWO or more genuine execution directories, via real
separate ``establish_stage_output_authority`` calls, and move/copy/rename REAL
files between them with the standard library -- never a fabricated in-memory
record object simulating a moved file, which post-FU5 there is no parameter to
supply anyway.

Pure Python, ``tmp_path``-scoped, no live Pi/network/model/credential activity.
"""

from __future__ import annotations

import inspect
import json
import os
import shutil
from pathlib import Path

import pytest
from cfg1_builders import refusal_payload, run_payload, synthetic_run_executor
from conftest import make_directory_redirect, make_file_symlink
from qualification.safety import ArtifactSafetyContext

from pi_harness_cfg1 import MAX_CFG1_ARTIFACT_BYTES, records
from pi_harness_cfg1.binding import (
    verify_cfg1_run_artifact_binding,
    verify_cfg1_stage_closure_binding,
)
from pi_harness_cfg1.stage_runner import _run_cfg1_stage_with_injected_executor as run_cfg1_stage
from pi_harness_cfg1.writers import emit_cfg1_refusal_record, emit_cfg1_run_record

NO_NEEDLES = ArtifactSafetyContext.none_declared()


def _write_run_record(authority, ordinal=1):
    result = emit_cfg1_run_record(
        authority,
        run_ordinal=ordinal,
        payload=run_payload(
            stage_execution_id=authority.stage_execution_id, run_ordinal=ordinal
        ),
        lifecycle_all_closed=True,
        safety=NO_NEEDLES,
    )
    assert result.emission_status == "RECORD_EMITTED"
    from pi_harness_cfg1.schedule import _schedule_arm_for

    arm = _schedule_arm_for(authority.stage_id, ordinal)
    return Path(authority.execution_directory, f"S1_{ordinal:02d}_{arm}.json")


def _complete_stage(authority):
    result = run_cfg1_stage(authority, run_executor=synthetic_run_executor())
    assert result.disposition == "STAGE_COMPLETED"
    return Path(authority.execution_directory, "S1_stage_closure.json")


# ---------------------------------------------------------------------------
# T-37 / T-54 / T-68 / T-80 -- positive controls
# ---------------------------------------------------------------------------


def test_t37_and_t68_genuine_artifacts_in_their_genuine_directories_return_true(
    make_authority,
):
    authority = make_authority("S1-X1")
    closure_path = _complete_stage(authority)
    run_path = Path(authority.execution_directory, "S1_01_Q.json")

    assert verify_cfg1_run_artifact_binding(str(run_path)) is True
    assert verify_cfg1_stage_closure_binding(str(closure_path)) is True


def test_t80_the_run_literal_branch_is_the_dispatch_positive_control(make_authority):
    authority = make_authority("S1-X1")
    path = _write_run_record(authority)
    parsed = json.loads(path.read_text(encoding="utf-8"))
    assert (parsed["record_version"], parsed["record_kind"]) == (
        "pi-harness-cfg1-run.v1",
        "harness configuration diagnostic run",
    )
    assert verify_cfg1_run_artifact_binding(str(path)) is True


def test_t81_a_genuine_refusal_record_at_a_run_path_is_also_accepted(make_authority):
    """The OTHER legitimate occupant of a run path (FU6's Finding 2).

    An undispatched "run the payload validator" composition could never have
    accepted this -- it would have called the run-record validator against a
    refusal record and refused every genuine instance.
    """
    authority = make_authority("S1-X1")
    result = emit_cfg1_refusal_record(
        authority,
        run_ordinal=1,
        refusal_payload=refusal_payload(stage_execution_id="S1-X1"),
        safety=NO_NEEDLES,
    )
    assert result.emission_status == "EVIDENCE_REFUSED"
    path = Path(authority.execution_directory, "S1_01_Q.json")
    assert verify_cfg1_run_artifact_binding(str(path)) is True


# ---------------------------------------------------------------------------
# T-82 -- an ambiguous discriminator invokes NO validator at all
# ---------------------------------------------------------------------------


def test_t82_ambiguous_discriminators_are_refused_with_zero_validator_calls(
    make_authority, monkeypatch
):
    authority = make_authority("S1-X1")
    path = Path(authority.execution_directory, "S1_01_Q.json")

    run_calls: list[object] = []
    refusal_calls: list[object] = []
    monkeypatch.setitem(
        records._RUN_PATH_DISCRIMINATORS,
        ("pi-harness-cfg1-run.v1", "harness configuration diagnostic run"),
        lambda payload: run_calls.append(payload),
    )
    monkeypatch.setitem(
        records._RUN_PATH_DISCRIMINATORS,
        ("pi-harness-cfg1-refusal.v1", "cfg1 artifact emission refusal"),
        lambda payload: refusal_calls.append(payload),
    )

    sub_cases = [
        # 1. a pair matching neither known combination
        {"record_version": "pi-harness-cfg1-run.v9", "record_kind": "something else"},
        # 2. one present, the other absent
        {"record_version": "pi-harness-cfg1-run.v1"},
        {"record_kind": "harness configuration diagnostic run"},
        # 3. both present but MISMATCHED, in both directions
        {
            "record_version": "pi-harness-cfg1-refusal.v1",
            "record_kind": "harness configuration diagnostic run",
        },
        {
            "record_version": "pi-harness-cfg1-run.v1",
            "record_kind": "cfg1 artifact emission refusal",
        },
        # 4. the stage-closure kind, at a run path
        {
            "record_version": "pi-harness-cfg1-stage-closure.v1",
            "record_kind": "cfg1 stage closure",
        },
    ]
    for payload in sub_cases:
        path.write_text(json.dumps(payload), encoding="utf-8")
        assert verify_cfg1_run_artifact_binding(str(path)) is False, payload

    assert run_calls == []
    assert refusal_calls == []


# ---------------------------------------------------------------------------
# T-33 / T-34 / T-35 / T-36 -- real relocation, rename and outside-root cases
# ---------------------------------------------------------------------------


def test_t33_a_byte_for_byte_copy_in_another_genuine_directory_returns_false(
    make_authority,
):
    first = make_authority("S1-X1")
    second = make_authority("S1-X2")
    genuine = _write_run_record(first)

    copied = Path(second.execution_directory, "S1_01_Q.json")
    shutil.copyfile(str(genuine), str(copied))

    # The copy's own PAYLOAD is still perfectly self-consistent...
    records._require_valid_cfg1_run_payload(
        json.loads(copied.read_text(encoding="utf-8"))
    )
    # ...and it is the LOCATION that disagrees.
    assert verify_cfg1_run_artifact_binding(str(genuine)) is True
    assert verify_cfg1_run_artifact_binding(str(copied)) is False


def test_t34_an_in_place_rename_returns_false(make_authority):
    authority = make_authority("S1-X1")
    genuine = _write_run_record(authority)
    renamed = Path(authority.execution_directory, "S1_02_R.json")
    os.rename(str(genuine), str(renamed))

    records._require_valid_cfg1_run_payload(
        json.loads(renamed.read_text(encoding="utf-8"))
    )
    assert verify_cfg1_run_artifact_binding(str(renamed)) is False


def test_t35_a_relocated_stage_closure_record_returns_false(make_authority):
    first = make_authority("S1-X1")
    second = make_authority("S1-X2")
    closure = _complete_stage(first)
    moved = Path(second.execution_directory, "S1_stage_closure.json")
    shutil.copyfile(str(closure), str(moved))

    assert verify_cfg1_stage_closure_binding(str(closure)) is True
    assert verify_cfg1_stage_closure_binding(str(moved)) is False


def test_t36_an_artifact_outside_the_fixed_root_returns_false(make_authority, tmp_path):
    authority = make_authority("S1-X1")
    genuine = _write_run_record(authority)

    sibling = tmp_path / "sibling_temp" / "S1-X1"
    sibling.mkdir(parents=True)
    outside = sibling / "S1_01_Q.json"
    shutil.copyfile(str(genuine), str(outside))
    assert verify_cfg1_run_artifact_binding(str(outside)) is False

    closure = _complete_stage(make_authority("S1-X2"))
    outside_closure = sibling / "S1_stage_closure.json"
    shutil.copyfile(str(closure), str(outside_closure))
    assert verify_cfg1_stage_closure_binding(str(outside_closure)) is False


def test_t36_an_artifact_reached_through_a_real_redirect_returns_false(
    make_authority, tmp_path
):
    """The redirect form, not merely a differently-rooted path."""
    authority = make_authority("S1-X1")
    genuine = _write_run_record(authority)

    alias = tmp_path / "execution_dir_alias"
    try:
        make_directory_redirect(alias, Path(authority.execution_directory))
    except OSError:
        pytest.skip("this platform grants neither symlink nor junction creation")

    through_alias = alias / "S1_01_Q.json"
    assert through_alias.exists()
    assert verify_cfg1_run_artifact_binding(str(through_alias)) is False
    # The genuine path is unaffected.
    assert verify_cfg1_run_artifact_binding(str(genuine)) is True


# ---------------------------------------------------------------------------
# T-50 / T-62 -- the input boundary, and the parameter that does not exist
# ---------------------------------------------------------------------------


class _HasFspath:
    def __fspath__(self) -> str:  # pragma: no cover - never reached
        return "anything"


class _StrSubclass(str):
    pass


@pytest.mark.parametrize(
    "value",
    [None, 1, True, False, Path("x"), _HasFspath(), _StrSubclass("x"), b"x", 1.0],
    ids=lambda v: type(v).__name__,
)
def test_t50_non_exact_str_inputs_return_false_with_zero_filesystem_calls(
    value, filesystem_spy
):
    assert verify_cfg1_run_artifact_binding(value) is False
    assert verify_cfg1_stage_closure_binding(value) is False
    assert filesystem_spy.total_mutations == 0
    assert filesystem_spy.lstat_calls == []


def test_t62_neither_verifier_has_a_second_parameter():
    """Proven by the API surface itself, never merely documented.

    There is no parameter through which a stale, previously-parsed, or
    hand-built record object could be supplied -- which is a stronger guarantee
    than any runtime check could be.
    """
    for verifier in (verify_cfg1_run_artifact_binding, verify_cfg1_stage_closure_binding):
        parameters = inspect.signature(verifier).parameters
        assert list(parameters) == ["actual_path"]
        assert "parsed_record" not in parameters


# ---------------------------------------------------------------------------
# T-63 / T-64 -- lexical checks run BEFORE resolve()
# ---------------------------------------------------------------------------


def test_t63_a_symlink_alias_and_a_redirected_parent_both_return_false(
    make_authority, tmp_path
):
    """A test that resolved first could not distinguish these from genuine ones."""
    authority = make_authority("S1-X1")
    genuine = _write_run_record(authority)

    alias = Path(authority.execution_directory, "S1_02_R.json")
    try:
        make_file_symlink(alias, genuine)
    except (OSError, NotImplementedError):
        pytest.skip("this platform grants no file-symlink creation privilege")
    assert alias.exists()  # it resolves to a genuine, valid record...
    assert verify_cfg1_run_artifact_binding(str(alias)) is False  # ...and is not one

    parent_alias = tmp_path / "parent_alias"
    try:
        make_directory_redirect(parent_alias, Path(authority.execution_directory))
    except OSError:
        pytest.skip("this platform grants neither symlink nor junction creation")
    assert verify_cfg1_run_artifact_binding(str(parent_alias / "S1_01_Q.json")) is False


def test_t64_a_directory_shaped_like_a_record_filename_returns_false(make_authority):
    authority = make_authority("S1-X1")
    directory = Path(authority.execution_directory, "S1_01_Q.json")
    directory.mkdir()
    assert verify_cfg1_run_artifact_binding(str(directory)) is False


# ---------------------------------------------------------------------------
# T-65 / T-66 / T-67 -- byte authority, and the fresh-read discipline
# ---------------------------------------------------------------------------


def test_t65_an_on_disk_field_edit_must_return_false_on_a_fresh_call(make_authority):
    """One exact mutation, one MANDATORY outcome. No cached result exists."""
    tampered_authority = make_authority("S1-X1")
    untouched_authority = make_authority("S1-X2")
    tampered = _write_run_record(tampered_authority)
    untouched = _write_run_record(untouched_authority)

    assert verify_cfg1_run_artifact_binding(str(tampered)) is True

    payload = json.loads(tampered.read_text(encoding="utf-8"))
    assert payload["stage_execution_id"] == "S1-X1"
    payload["stage_execution_id"] = "S1-X2"  # still grammar-valid, file unmoved
    tampered.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # MUST be False: the payload's own id now disagrees with its actual parent.
    assert verify_cfg1_run_artifact_binding(str(tampered)) is False

    # The positive control, run AFTER the tampered case, against a DIFFERENT
    # path -- proving the fresh-read discipline itself, not only detection.
    assert verify_cfg1_run_artifact_binding(str(untouched)) is True


def test_t66_malformed_json_returns_false(make_authority):
    authority = make_authority("S1-X1")
    path = _write_run_record(authority)
    path.write_text("{ this is not json", encoding="utf-8")
    assert verify_cfg1_run_artifact_binding(str(path)) is False


def test_t67_an_empty_json_object_returns_false(make_authority):
    authority = make_authority("S1-X1")
    path = _write_run_record(authority)
    path.write_text("{}", encoding="utf-8")
    # It parses as a dict (passing the bare type check) and then fails the
    # discriminator lookup, which carries neither literal. Either reason
    # independently returns False; the test asserts False, not a reason.
    assert verify_cfg1_run_artifact_binding(str(path)) is False
    assert verify_cfg1_stage_closure_binding(str(path)) is False


def test_non_utf8_bytes_and_a_non_object_top_level_return_false(make_authority):
    authority = make_authority("S1-X1")
    path = _write_run_record(authority)

    path.write_bytes(b"\xff\xfe\x00not utf-8")
    assert verify_cfg1_run_artifact_binding(str(path)) is False

    path.write_text("[1, 2, 3]", encoding="utf-8")
    assert verify_cfg1_run_artifact_binding(str(path)) is False

    path.write_text('"a bare string"', encoding="utf-8")
    assert verify_cfg1_run_artifact_binding(str(path)) is False


def test_an_oversized_artifact_is_refused_before_any_parse(make_authority):
    authority = make_authority("S1-X1")
    path = _write_run_record(authority)
    path.write_bytes(b"{}" + b" " * MAX_CFG1_ARTIFACT_BYTES)
    assert path.stat().st_size > MAX_CFG1_ARTIFACT_BYTES
    assert verify_cfg1_run_artifact_binding(str(path)) is False


def test_a_missing_file_returns_false_and_never_raises(make_authority):
    authority = make_authority("S1-X1")
    assert (
        verify_cfg1_run_artifact_binding(
            str(Path(authority.execution_directory, "S1_01_Q.json"))
        )
        is False
    )


def test_a_run_record_at_a_stage_closure_path_returns_false(make_authority):
    """No dispatch exists there: it is simply malformed for that validator."""
    authority = make_authority("S1-X1")
    genuine = _write_run_record(authority)
    closure_path = Path(authority.execution_directory, "S1_stage_closure.json")
    shutil.copyfile(str(genuine), str(closure_path))
    assert verify_cfg1_stage_closure_binding(str(closure_path)) is False


def test_the_verifiers_never_rewrite_repair_or_move_anything(make_authority, monkeypatch):
    authority = make_authority("S1-X1")
    path = _write_run_record(authority)
    original = path.read_bytes()

    touched: list[str] = []
    monkeypatch.setattr(os, "unlink", lambda p, *a, **k: touched.append(str(p)))
    monkeypatch.setattr(os, "rename", lambda s, d, *a, **k: touched.append(str(s)))
    monkeypatch.setattr(os, "replace", lambda s, d, *a, **k: touched.append(str(s)))
    monkeypatch.setattr(os, "truncate", lambda p, n, *a, **k: touched.append(str(p)))

    path.write_text("{}", encoding="utf-8")
    assert verify_cfg1_run_artifact_binding(str(path)) is False
    assert touched == []

    path.write_bytes(original)
    assert verify_cfg1_run_artifact_binding(str(path)) is True
    assert touched == []


def test_t54_a_genuine_str_path_to_a_valid_on_disk_record_returns_true(make_authority):
    """The single-argument API's own positive control, stated explicitly.

    There is no second argument through which a snapshot could be supplied, so
    the verifier read and parsed these bytes itself. Restates T-37 at the API
    level rather than at the tamper level.
    """
    authority = make_authority("S1-X1")
    path = _write_run_record(authority)
    records._require_valid_cfg1_run_payload(
        json.loads(path.read_text(encoding="utf-8"))
    )
    assert type(str(path)) is str
    assert verify_cfg1_run_artifact_binding(str(path)) is True
