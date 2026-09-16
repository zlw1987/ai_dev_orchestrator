"""T-16 - T-32 and T-43 - T-49: stage-output authority, provenance, lifetime.

Pure Python, ``tmp_path``-scoped, no subprocess, no live Pi/network/model/
credential activity. Where the platform allows it, the redirect regressions use
REAL filesystem tampering -- an actual symlink, or an actual junction on
Windows -- never a mocked ``resolve()`` or ``lstat()`` return value, because the
defect these close is specifically about what real ``resolve()`` does through a
real redirect.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from conftest import make_directory_redirect

from pi_harness_cfg1.stage_output import (
    CFG1StageOutputAuthority,
    StageOutputAuthorityError,
    _establish_results_root,
    _prove_results_root,
    _retire_stage_output_authority,
    _STAGE_OUTPUT_MINTED,
    establish_stage_output_authority,
    verify_stage_output_authority,
)

# ---------------------------------------------------------------------------
# T-16 -- a valid identifier yields exactly one child of the fixed root
# ---------------------------------------------------------------------------


def test_t16_valid_identifier_yields_one_child_of_the_fixed_results_root(
    make_authority, results_root
):
    authority = make_authority("S1-X1")
    execution_directory = Path(authority.execution_directory)
    assert execution_directory.is_dir()
    assert execution_directory.parent == results_root.resolve()
    assert execution_directory.name == "S1-X1"
    assert authority.results_root == str(results_root.resolve())
    # Exactly ONE child, not a tree.
    assert [p.name for p in results_root.iterdir()] == ["S1-X1"]


# ---------------------------------------------------------------------------
# T-17 / T-18 / T-19 / T-22 -- the identifier grammar, spy-proven
# ---------------------------------------------------------------------------

_DOT_FORMS = (".", "..")

_PATHY_FORMS = (
    "a/b",
    "a\\b",
    "/etc/passwd",
    "C:\\Windows",
    "C:/Windows",
    "\\\\?\\C:\\x",
    "\\\\.\\pipe\\x",
    "\\\\host\\share",
    "a\x00b",
    "a\tb",
    "a\nb",
    "a\rb",
    "a\x1bb",
    " S1-X1",
    "S1-X1 ",
    "\tS1-X1",
    "",
    "x" * 65,
    "S1.X1",
    "S1:X1",
    "S1*X1",
)


class _HasFspath:
    def __fspath__(self) -> str:  # pragma: no cover - never reached
        return "S1-X1"


class _StrSubclass(str):
    pass


_NON_STR_FORMS = (
    Path("S1-X1"),
    _HasFspath(),
    _StrSubclass("S1-X1"),
    1,
    True,
    False,
    None,
    {"stage_execution_id": "S1-X1"},
    ["S1-X1"],
)


@pytest.mark.parametrize("value", _DOT_FORMS)
def test_t17_dot_forms_are_refused_before_any_mkdir(value, cfg1_package_dir, filesystem_spy):
    with pytest.raises(StageOutputAuthorityError) as excinfo:
        establish_stage_output_authority(stage_id="S1", stage_execution_id=value)
    assert excinfo.value.reason_code == "MALFORMED_STAGE_EXECUTION_ID"
    assert filesystem_spy.mkdir_calls == []
    assert filesystem_spy.open_calls == []


@pytest.mark.parametrize("value", _PATHY_FORMS)
def test_t18_path_like_and_control_forms_are_refused_before_any_mkdir(
    value, cfg1_package_dir, filesystem_spy
):
    with pytest.raises(StageOutputAuthorityError) as excinfo:
        establish_stage_output_authority(stage_id="S1", stage_execution_id=value)
    assert excinfo.value.reason_code == "MALFORMED_STAGE_EXECUTION_ID"
    assert filesystem_spy.mkdir_calls == []
    assert filesystem_spy.open_calls == []


@pytest.mark.parametrize("value", _NON_STR_FORMS, ids=lambda v: type(v).__name__)
def test_t19_non_exact_str_types_are_refused_before_any_filesystem_operation(
    value, cfg1_package_dir, filesystem_spy
):
    with pytest.raises(StageOutputAuthorityError) as excinfo:
        establish_stage_output_authority(stage_id="S1", stage_execution_id=value)
    assert excinfo.value.reason_code == "MALFORMED_STAGE_EXECUTION_ID"
    assert filesystem_spy.total_mutations == 0
    assert filesystem_spy.lstat_calls == []


def test_t22_zero_filesystem_calls_is_mechanical_not_message_inspection(
    cfg1_package_dir, filesystem_spy
):
    """One consolidated sweep: every malformed form reaches ZERO fs calls."""
    for value in (*_DOT_FORMS, *_PATHY_FORMS, *_NON_STR_FORMS):
        with pytest.raises(StageOutputAuthorityError):
            establish_stage_output_authority(stage_id="S1", stage_execution_id=value)
    assert filesystem_spy.total_mutations == 0
    assert filesystem_spy.lstat_calls == []


def test_unknown_stage_id_is_refused_before_any_filesystem_operation(
    cfg1_package_dir, filesystem_spy
):
    for stage_id in ("S3", "s1", "", None, 1, True):
        with pytest.raises(StageOutputAuthorityError) as excinfo:
            establish_stage_output_authority(
                stage_id=stage_id, stage_execution_id="S1-X1"
            )
        assert excinfo.value.reason_code == "UNKNOWN_STAGE_ID"
    assert filesystem_spy.total_mutations == 0


# ---------------------------------------------------------------------------
# T-20 -- an existing execution directory refuses the ENTIRE stage
# ---------------------------------------------------------------------------


def test_t20_existing_execution_directory_refuses_the_stage_and_leaves_it_alone(
    cfg1_package_dir, results_root
):
    results_root.mkdir()
    occupied = results_root / "S1-X1"
    occupied.mkdir()
    (occupied / "pre-existing.txt").write_text("untouched", encoding="utf-8")

    with pytest.raises(StageOutputAuthorityError) as excinfo:
        establish_stage_output_authority(stage_id="S1", stage_execution_id="S1-X1")
    assert excinfo.value.reason_code == "EXECUTION_DIRECTORY_EXISTS"

    assert (occupied / "pre-existing.txt").read_text(encoding="utf-8") == "untouched"
    assert sorted(p.name for p in occupied.iterdir()) == ["pre-existing.txt"]


# ---------------------------------------------------------------------------
# T-23 / T-24 -- both root-presence paths, through the identical sequence
# ---------------------------------------------------------------------------


def test_t23_results_root_absent_is_created_then_proven(cfg1_package_dir, results_root):
    assert not results_root.exists()
    authority = establish_stage_output_authority(
        stage_id="S1", stage_execution_id="S1-X1"
    )
    try:
        assert results_root.is_dir()
        assert authority.results_root == str(results_root.resolve())
    finally:
        _retire_stage_output_authority(authority)


def test_t24_results_root_already_present_is_a_noop_then_proven(
    cfg1_package_dir, results_root
):
    results_root.mkdir()
    sentinel = results_root / "already-here"
    sentinel.mkdir()
    authority = establish_stage_output_authority(
        stage_id="S1", stage_execution_id="S1-X1"
    )
    try:
        assert authority.results_root == str(results_root.resolve())
        assert sentinel.is_dir()  # the ordinary case created nothing new here
    finally:
        _retire_stage_output_authority(authority)


# ---------------------------------------------------------------------------
# T-25 / T-26 / T-27 / T-28 -- the mint registry is what makes it unforgeable
# ---------------------------------------------------------------------------


def test_t25_direct_construction_with_an_unregistered_nonce_is_refused(
    cfg1_package_dir, results_root, filesystem_spy
):
    with pytest.raises(StageOutputAuthorityError) as excinfo:
        CFG1StageOutputAuthority(
            mint_nonce="not-a-registered-nonce",
            stage_id="S1",
            stage_execution_id="S1-X1",
            results_root=str(results_root),
            execution_directory=str(results_root / "S1-X1"),
        )
    assert excinfo.value.reason_code == "UNKNOWN_MINT_NONCE"
    assert filesystem_spy.total_mutations == 0


@pytest.mark.parametrize(
    "forged", ["", "0" * 32, "deadbeef" * 4, "S1-X1", "a", "\x00"]
)
def test_t26_a_forged_or_guessed_nonce_fails_identically(
    forged, cfg1_package_dir, results_root
):
    with pytest.raises(StageOutputAuthorityError) as excinfo:
        CFG1StageOutputAuthority(
            mint_nonce=forged,
            stage_id="S1",
            stage_execution_id="S1-X1",
            results_root=str(results_root),
            execution_directory=str(results_root / "S1-X1"),
        )
    assert excinfo.value.reason_code == "UNKNOWN_MINT_NONCE"


@pytest.mark.parametrize(
    "field_name",
    ["stage_id", "stage_execution_id", "results_root", "execution_directory"],
)
def test_t27_a_mutated_genuine_authority_fails_the_registry_field_recheck(
    field_name, make_authority
):
    """A nonce learned from a genuine object gains no authority with new fields."""
    authority = make_authority("S1-X1")
    verify_stage_output_authority(authority)  # genuine, before mutation

    object.__setattr__(authority, field_name, "S2" if field_name == "stage_id" else "tampered")
    with pytest.raises(StageOutputAuthorityError) as excinfo:
        verify_stage_output_authority(authority)
    assert excinfo.value.reason_code == "MINT_FIELD_MISMATCH"


def test_t28_a_genuine_unmutated_authority_passes_and_derives_a_path(make_authority):
    from pi_harness_cfg1.writers import _run_output_path

    authority = make_authority("S1-X1")
    verify_stage_output_authority(authority)
    derived = _run_output_path(authority, 1)
    assert derived == os.path.join(authority.execution_directory, "S1_01_Q.json")


def test_a_lookalike_class_is_refused_by_exact_type(make_authority):
    authority = make_authority("S1-X1")

    class CFG1StageOutputAuthority:  # noqa: N801 - a deliberate name collision
        mint_nonce = authority.mint_nonce
        stage_id = authority.stage_id
        stage_execution_id = authority.stage_execution_id
        results_root = authority.results_root
        execution_directory = authority.execution_directory

    with pytest.raises(StageOutputAuthorityError) as excinfo:
        verify_stage_output_authority(CFG1StageOutputAuthority())
    assert excinfo.value.reason_code == "NOT_A_STAGE_OUTPUT_AUTHORITY"


# ---------------------------------------------------------------------------
# T-29 / T-30 / T-31 / T-43 -- REAL filesystem tampering
# ---------------------------------------------------------------------------


def test_t29_a_redirected_results_root_is_refused_before_any_execution_directory(
    cfg1_package_dir, results_root, tmp_path
):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    try:
        mechanism = make_directory_redirect(results_root, elsewhere)
    except OSError:
        pytest.skip(
            "this platform grants neither symlink nor junction creation; the "
            "RESULTS_ROOT_REDIRECTED invariant is exercised by the POSIX "
            "symlink form where available"
        )

    with pytest.raises(StageOutputAuthorityError) as excinfo:
        establish_stage_output_authority(stage_id="S1", stage_execution_id="S1-X1")
    assert excinfo.value.reason_code == "RESULTS_ROOT_REDIRECTED"
    # No execution directory was derived or created ANYWHERE.
    assert list(elsewhere.iterdir()) == [], f"redirect target was written through ({mechanism})"


def test_t30_a_file_occupying_the_results_root_is_refused_two_independent_ways(
    cfg1_package_dir, results_root
):
    results_root.write_text("not a directory", encoding="utf-8")

    # Defense 1: mkdir's own FileExistsError (exist_ok=True does not suppress
    # it for a non-directory).
    with pytest.raises(StageOutputAuthorityError) as excinfo:
        establish_stage_output_authority(stage_id="S1", stage_execution_id="S1-X1")
    assert excinfo.value.reason_code == "RESULTS_ROOT_NOT_A_DIRECTORY"

    # Defense 2: step 2(c) refuses independently, with no mkdir involved at all.
    with pytest.raises(StageOutputAuthorityError) as excinfo:
        _prove_results_root(results_root)
    assert excinfo.value.reason_code == "RESULTS_ROOT_NOT_A_DIRECTORY"


def test_t31_a_post_mint_execution_directory_redirect_is_caught_at_the_next_boundary(
    make_authority, tmp_path
):
    """The re-proof is a CONSUMPTION-boundary check, not a mint-time one."""
    from pi_harness_cfg1.writers import Cfg1WriterError, emit_cfg1_run_record
    from qualification.safety import ArtifactSafetyContext

    authority = make_authority("S1-X1")
    verify_stage_output_authority(authority)

    elsewhere = tmp_path / "attacker-controlled"
    elsewhere.mkdir()
    os.rmdir(authority.execution_directory)
    try:
        make_directory_redirect(Path(authority.execution_directory), elsewhere)
    except OSError:
        pytest.skip("this platform grants neither symlink nor junction creation")

    with pytest.raises(StageOutputAuthorityError) as excinfo:
        emit_cfg1_run_record(
            authority,
            run_ordinal=1,
            payload={},
            lifecycle_all_closed=True,
            safety=ArtifactSafetyContext.none_declared(),
        )
    assert excinfo.value.reason_code == "EXECUTION_DIRECTORY_REDIRECTED"
    assert list(elsewhere.iterdir()) == []
    assert Cfg1WriterError  # the writer never got far enough to raise its own


@pytest.mark.skipif(os.name != "nt", reason="8.3 short-name aliases are Windows-only")
def test_t32_a_windows_short_name_alias_of_the_package_directory_is_refused(
    tmp_path, monkeypatch
):
    """T-32's reserved Windows-only ancestor-canonicalization case.

    An 8.3 alias is a perfectly ordinary, non-reparse directory entry, so steps
    (a)-(c) pass and only the canonical comparison catches it -- which is
    exactly the point of having that comparison.
    """
    import ctypes
    import ctypes.wintypes

    from pi_harness_cfg1 import stage_output

    long_name = tmp_path / "a_deliberately_long_package_directory_name"
    long_name.mkdir()

    buffer = ctypes.create_unicode_buffer(1024)
    length = ctypes.windll.kernel32.GetShortPathNameW(
        str(long_name), buffer, ctypes.wintypes.DWORD(1024)
    )
    if length == 0:
        pytest.skip("GetShortPathNameW failed on this volume")
    short = buffer.value
    if short == str(long_name):
        pytest.skip("8.3 short-name generation is disabled on this volume")

    monkeypatch.setattr(stage_output, "_CAPTURED_PACKAGE_DIR", short, raising=True)
    with pytest.raises(StageOutputAuthorityError) as excinfo:
        establish_stage_output_authority(stage_id="S1", stage_execution_id="S1-X1")
    assert excinfo.value.reason_code in (
        "PACKAGE_DIR_NOT_CANONICAL",
        "RESULTS_ROOT_NOT_CANONICAL",
    )
    assert not (long_name / "results").exists()


def test_t43_a_redirected_package_directory_refuses_before_results_root_mkdir(
    tmp_path, monkeypatch
):
    """Level A runs strictly before Level B -- creation never precedes proof."""
    from pi_harness_cfg1 import stage_output

    genuine = tmp_path / "genuine_package"
    genuine.mkdir()
    foreign = tmp_path / "foreign_target"
    foreign.mkdir()

    alias = tmp_path / "package_alias"
    try:
        make_directory_redirect(alias, foreign)
    except OSError:
        pytest.skip("this platform grants neither symlink nor junction creation")

    monkeypatch.setattr(stage_output, "_CAPTURED_PACKAGE_DIR", str(alias), raising=True)
    with pytest.raises(StageOutputAuthorityError) as excinfo:
        establish_stage_output_authority(stage_id="S1", stage_execution_id="S1-X1")
    assert excinfo.value.reason_code in (
        "PACKAGE_DIR_REDIRECTED",
        "PACKAGE_DIR_NOT_CANONICAL",
    )
    # No FOREIGN results/ was created anywhere, which is the whole point of
    # ordering Level A first.
    assert not (foreign / "results").exists()
    assert not (alias / "results").exists() or not (foreign / "results").exists()
    assert not (genuine / "results").exists()


def test_an_ancestor_redirect_is_caught_by_the_canonical_comparison(tmp_path, monkeypatch):
    """Steps (a)-(c) see an ordinary leaf; only step (d) sees the ancestor."""
    from pi_harness_cfg1 import stage_output

    real_parent = tmp_path / "real_parent"
    (real_parent / "pkg").mkdir(parents=True)
    alias_parent = tmp_path / "alias_parent"
    try:
        make_directory_redirect(alias_parent, real_parent)
    except OSError:
        pytest.skip("this platform grants neither symlink nor junction creation")

    through_alias = str(alias_parent / "pkg")
    monkeypatch.setattr(stage_output, "_CAPTURED_PACKAGE_DIR", through_alias, raising=True)
    with pytest.raises(StageOutputAuthorityError) as excinfo:
        establish_stage_output_authority(stage_id="S1", stage_execution_id="S1-X1")
    assert excinfo.value.reason_code == "PACKAGE_DIR_NOT_CANONICAL"
    assert not (real_parent / "pkg" / "results").exists()


def test_a_vanished_results_root_refuses_at_the_next_consumption_boundary(make_authority):
    import shutil

    authority = make_authority("S1-X1")
    shutil.rmtree(authority.results_root)
    with pytest.raises(StageOutputAuthorityError) as excinfo:
        verify_stage_output_authority(authority)
    assert excinfo.value.reason_code == "RESULTS_ROOT_ABSENT"


def test_establish_results_root_never_creates_during_a_reproof(cfg1_package_dir, results_root):
    """The re-proof path is non-creating: a vanished root is refused, not remade."""
    assert not results_root.exists()
    with pytest.raises(StageOutputAuthorityError) as excinfo:
        _establish_results_root(create_if_absent=False)
    assert excinfo.value.reason_code == "RESULTS_ROOT_ABSENT"
    assert not results_root.exists()


# ---------------------------------------------------------------------------
# T-44 - T-49 -- ACTIVE while minted, RETIRED on every exit path
# ---------------------------------------------------------------------------


def test_t44_a_genuine_unretired_authority_passes_every_writer_in_one_stage(
    make_authority,
):
    """Positive control for the whole authority lifetime."""
    from cfg1_builders import run_payload
    from qualification.safety import ArtifactSafetyContext

    from pi_harness_cfg1.writers import emit_cfg1_run_record

    authority = make_authority("S1-X1")
    for ordinal in (1, 2, 3):
        result = emit_cfg1_run_record(
            authority,
            run_ordinal=ordinal,
            payload=run_payload(run_ordinal=ordinal),
            lifecycle_all_closed=True,
            safety=ArtifactSafetyContext.none_declared(),
        )
        assert result.emission_status == "RECORD_EMITTED"
    verify_stage_output_authority(authority)


def _drive_stage(authority, executor, probe=None):
    from pi_harness_cfg1.stage_runner import run_cfg1_stage

    return run_cfg1_stage(authority, run_executor=executor, _internal_probe=probe)


def test_t45_retirement_after_normal_successful_completion(make_authority):
    from cfg1_builders import synthetic_run_executor

    authority = make_authority("S1-X1")
    result = _drive_stage(authority, synthetic_run_executor())
    assert result.disposition == "STAGE_COMPLETED"
    with pytest.raises(StageOutputAuthorityError) as excinfo:
        verify_stage_output_authority(authority)
    assert excinfo.value.reason_code == "UNKNOWN_MINT_NONCE"


def test_t46_retirement_after_an_ordinary_halts_own_stage_closure_write(make_authority):
    from cfg1_builders import happy_observations, synthetic_run_executor

    def _observations(admission):
        from pi_harness_cfg1.arms import ARM_SHAPE

        overrides = {"runtime_reported_compat_shape": ARM_SHAPE[admission.arm_id]}
        if admission.run_ordinal == 2:
            overrides.update(
                {
                    "workspace_removed_verified": False,
                    "lifecycle_all_closed": False,
                    "lifecycle_failure_steps": ["L27"],
                    "verification_attempted": False,
                    "verification_skip_reason": "LIFECYCLE_UNPROVEN",
                    "verification_started": False,
                    "verification_completed": False,
                    "verification_return_code": None,
                    "verification_counts": {"passed": 0, "failed": 0, "error": 0},
                    "git_observation_2_performed": False,
                }
            )
        return happy_observations(**overrides)

    authority = make_authority("S1-X1")
    result = _drive_stage(authority, synthetic_run_executor(observations_for=_observations))
    assert result.disposition == "STAGE_HALTED"
    assert result.halted_after_ordinal == 2
    assert result.halt_reason_code == "LIFECYCLE_CLOSURE_UNPROVEN"
    assert result.stage_closure_confirmed is True
    with pytest.raises(StageOutputAuthorityError) as excinfo:
        verify_stage_output_authority(authority)
    assert excinfo.value.reason_code == "UNKNOWN_MINT_NONCE"


def test_t47_retirement_on_a_hard_stop_writes_nothing_afterwards(
    make_authority, tmp_path
):
    from cfg1_builders import synthetic_run_executor

    authority = make_authority("S1-X1")
    execution_directory = Path(authority.execution_directory)

    elsewhere = tmp_path / "hard-stop-target"
    elsewhere.mkdir()
    os.rmdir(execution_directory)
    try:
        make_directory_redirect(execution_directory, elsewhere)
    except OSError:
        pytest.skip("this platform grants neither symlink nor junction creation")

    result = _drive_stage(authority, synthetic_run_executor())
    assert result.disposition == "STAGE_OUTPUT_AUTHORITY_HARD_STOP"
    assert result.stage_closure_confirmed is False
    assert list(elsewhere.iterdir()) == []
    with pytest.raises(StageOutputAuthorityError) as excinfo:
        verify_stage_output_authority(authority)
    assert excinfo.value.reason_code == "UNKNOWN_MINT_NONCE"


def test_t48_retirement_after_a_stage_closure_collision_with_no_fallback(
    make_authority, monkeypatch
):
    from cfg1_builders import synthetic_run_executor

    from pi_harness_cfg1 import writers

    authority = make_authority("S1-X1")
    # Pre-occupy the stage-closure path so its own exclusive-create collides.
    Path(authority.execution_directory, "S1_stage_closure.json").write_text(
        "occupant", encoding="utf-8"
    )

    refusal_calls: list[object] = []
    monkeypatch.setattr(
        writers,
        "emit_cfg1_refusal_record",
        lambda *a, **k: refusal_calls.append((a, k)),
    )

    result = _drive_stage(authority, synthetic_run_executor())
    assert result.disposition == "STAGE_CLOSURE_EMISSION_FAILED"
    assert "STAGE_CLOSURE_CREATE_COLLISION" in result.console_codes
    assert refusal_calls == []
    assert (
        Path(authority.execution_directory, "S1_stage_closure.json").read_text(
            encoding="utf-8"
        )
        == "occupant"
    )
    with pytest.raises(StageOutputAuthorityError) as excinfo:
        verify_stage_output_authority(authority)
    assert excinfo.value.reason_code == "UNKNOWN_MINT_NONCE"


def test_t49_every_writer_refuses_a_retired_authority_before_any_filesystem_op(
    make_authority, monkeypatch
):
    """Each writer's own unconditional step 1 is what refuses -- not a caller."""
    from qualification.safety import ArtifactSafetyContext

    from pi_harness_cfg1 import writers
    from pi_harness_cfg1.writers import (
        _run_output_path,
        emit_cfg1_refusal_record,
        emit_cfg1_run_record,
        emit_cfg1_stage_closure,
    )

    authority = make_authority("S1-X1")
    _retire_stage_output_authority(authority)

    created: list[str] = []
    monkeypatch.setattr(
        writers, "_open_exclusive", lambda path: created.append(path)  # type: ignore[arg-type]
    )

    with pytest.raises(StageOutputAuthorityError) as excinfo:
        emit_cfg1_run_record(
            authority,
            run_ordinal=1,
            payload={},
            lifecycle_all_closed=True,
            safety=ArtifactSafetyContext.none_declared(),
        )
    assert excinfo.value.reason_code == "UNKNOWN_MINT_NONCE"

    with pytest.raises(StageOutputAuthorityError):
        emit_cfg1_refusal_record(
            authority,
            run_ordinal=1,
            refusal_payload={},
            safety=ArtifactSafetyContext.none_declared(),
        )
    with pytest.raises(StageOutputAuthorityError):
        emit_cfg1_stage_closure(authority, decision=object())
    with pytest.raises(StageOutputAuthorityError):
        _run_output_path_via_verified_boundary(authority)

    assert created == []


def _run_output_path_via_verified_boundary(authority):
    """A retired authority must not even derive a path through a writer entry."""
    from qualification.safety import ArtifactSafetyContext

    from pi_harness_cfg1.writers import emit_cfg1_run_record

    return emit_cfg1_run_record(
        authority,
        run_ordinal=1,
        payload={},
        lifecycle_all_closed=True,
        safety=ArtifactSafetyContext.none_declared(),
    )


def test_retirement_is_idempotent_and_never_acts_on_a_bare_identifier():
    """Cleanup follows the ownership HANDLE, never a name that looks expected."""
    before = dict(_STAGE_OUTPUT_MINTED)
    _retire_stage_output_authority("some-nonce-looking-string")
    _retire_stage_output_authority(None)
    _retire_stage_output_authority(object())
    assert dict(_STAGE_OUTPUT_MINTED) == before
